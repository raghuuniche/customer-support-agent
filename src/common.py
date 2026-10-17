import os
import re

import yaml
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone
from langsmith.wrappers import wrap_openai

load_dotenv()

NAMESPACE = "support"


def load_intent(path="intent.yaml"):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def nebius():
    return wrap_openai(
        OpenAI(
            base_url=os.getenv("NEBIUS_BASE_URL"),
            api_key=os.getenv("NEBIUS_API_KEY"),
        )
    )


def embed(texts, batch=32):
    client = nebius()
    out = []
    for i in range(0, len(texts), batch):
        r = client.embeddings.create(
            model=os.getenv("NEBIUS_EMBED_MODEL"),
            input=texts[i : i + batch],
        )
        out.extend(d.embedding for d in sorted(r.data, key=lambda d: d.index))
    return out


def pinecone_index():
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    return pc.Index(os.getenv("PINECONE_INDEX"))


def tokenize(text):
    return re.findall(r"\w+", text.lower())