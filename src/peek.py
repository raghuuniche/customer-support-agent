import json
from pathlib import Path

from rank_bm25 import BM25Okapi

from common import NAMESPACE, embed, pinecone_index, tokenize

chunks = json.loads(Path("data/chunks.json").read_text(encoding="utf-8"))
bm25 = BM25Okapi([tokenize(c["text"]) for c in chunks])
index = pinecone_index()

QUESTIONS = [
    "My charge port will not open",
    "Premium Connectivity",
    "The app says my car is asleep",
    "Is a Rivian better than a Tesla?",
]

for q in QUESTIONS:
    print("\nQUESTION", q)

    res = index.query(
        vector=embed([q])[0], top_k=4, include_metadata=True, namespace=NAMESPACE
    )
    print("  DENSE, cosine similarity")
    for m in res.matches:
        print(f"    {m.score:.3f}  {m.id:34s} {m.metadata['text'][:60]}")

    scores = bm25.get_scores(tokenize(q))
    top = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)[:4]
    print("  BM25, keyword score")
    for i in top:
        print(f"    {scores[i]:.2f}  {chunks[i]['id']:34s} {chunks[i]['text'][:60]}")