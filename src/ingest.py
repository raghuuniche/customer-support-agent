import json
import os
import sqlite3
import time
from pathlib import Path

from pinecone import Pinecone, ServerlessSpec
from pypdf import PdfReader

from common import NAMESPACE, embed, load_intent

cfg = load_intent()
CHUNK = cfg["retrieval"]["chunk_size"]
OVERLAP = cfg["retrieval"]["chunk_overlap"]
INDEX = os.getenv("PINECONE_INDEX")


def split_text(text, size, overlap):
    """Cut text into overlapping pieces that end at sentence or word boundaries."""
    text = " ".join(text.split())
    pieces, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            period = text.rfind(". ", start + size // 2, end)
            if period != -1:
                end = period + 1
            else:
                space = text.rfind(" ", start, end)
                if space > start:
                    end = space
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
        space = text.find(" ", start)
        if space != -1 and space < end:
            start = space + 1
    return pieces


def load_pdf_chunks():
    chunks = []
    folder = Path(cfg["sources"]["pdfs"]["folder"])
    for pdf in sorted(folder.glob("*.pdf")):
        title = pdf.stem.replace("_", " ").title()
        reader = PdfReader(str(pdf))
        for page_no, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            for i, piece in enumerate(split_text(text, CHUNK, OVERLAP)):
                chunks.append(
                    {
                        "id": f"{pdf.stem}-p{page_no}-c{i}",
                        "text": f"{title}. {piece}",
                        "meta": {
                            "doc_type": "pdf",
                            "source": pdf.name,
                            "title": title,
                            "page": page_no,
                        },
                    }
                )
    return chunks


def load_ticket_chunks():
    t = cfg["sources"]["tickets"]
    con = sqlite3.connect(t["database"])
    rows = con.execute(
        f"SELECT ticket_id, model, category, question, resolution FROM {t['table']} WHERE status = ?",
        (t["only_status"],),
    ).fetchall()
    con.close()
    chunks = []
    for tid, model, category, question, resolution in rows:
        chunks.append(
            {
                "id": tid,
                "text": f"Past support ticket {tid} for {model}, {category}. Question: {question} Answer: {resolution}",
                "meta": {
                    "doc_type": "ticket",
                    "source": tid,
                    "title": f"Ticket {tid}",
                    "model": model,
                    "category": category,
                },
            }
        )
    return chunks


def main():
    pdf_chunks = load_pdf_chunks()
    ticket_chunks = load_ticket_chunks()
    chunks = pdf_chunks + ticket_chunks
    print(f"PDF chunks {len(pdf_chunks)} | ticket chunks {len(ticket_chunks)} | total {len(chunks)}")

    Path("data/chunks.json").write_text(json.dumps(chunks, indent=1), encoding="utf-8")
    print("Saved data/chunks.json for BM25")

    print("Embedding all chunks ...")
    vectors = embed([c["text"] for c in chunks])
    dim = len(vectors[0])
    print(f"Vector length {dim}")

    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    if INDEX not in pc.list_indexes().names():
        print(f"Creating index {INDEX} ...")
        pc.create_index(
            name=INDEX,
            dimension=dim,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        while not pc.describe_index(INDEX).status["ready"]:
            time.sleep(2)
    index = pc.Index(INDEX)

    try:
        index.delete(delete_all=True, namespace=NAMESPACE)
    except Exception:
        pass

    records = [
        {"id": c["id"], "values": v, "metadata": {**c["meta"], "text": c["text"]}}
        for c, v in zip(chunks, vectors)
    ]
    for i in range(0, len(records), 50):
        index.upsert(vectors=records[i : i + 50], namespace=NAMESPACE)
        print(f"Upserted {min(i + 50, len(records))} of {len(records)}")

    time.sleep(5)
    print(index.describe_index_stats())
    print("Done.")


if __name__ == "__main__":
    main()