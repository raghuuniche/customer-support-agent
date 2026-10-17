import os
from dotenv import load_dotenv

load_dotenv()


def check(name, fn):
    try:
        print(f"[OK]   {name}: {fn()}")
    except Exception as e:
        print(f"[FAIL] {name}: {e}")


def nebius_client():
    from openai import OpenAI
    return OpenAI(
        base_url=os.getenv("NEBIUS_BASE_URL"),
        api_key=os.getenv("NEBIUS_API_KEY"),
    )


def nebius_models():
    ids = sorted(m.id for m in nebius_client().models.list().data)
    print("       Available models")
    for i in ids:
        print("        ", i)
    return f"{len(ids)} models found"


def nebius_chat():
    r = nebius_client().chat.completions.create(
        model=os.getenv("NEBIUS_CHAT_MODEL"),
        messages=[{"role": "user", "content": "Say hello in five words."}],
        max_tokens=30,
    )
    return r.choices[0].message.content


def nebius_embed():
    r = nebius_client().embeddings.create(
        model=os.getenv("NEBIUS_EMBED_MODEL"),
        input="charge port will not open",
    )
    return f"vector length {len(r.data[0].embedding)}"


def pinecone_check():
    from pinecone import Pinecone
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    return f"connected, {len(pc.list_indexes().names())} existing indexes"


def langsmith_check():
    from langsmith import Client
    list(Client().list_projects(limit=1))
    return "connected"


def tavily_check():
    from tavily import TavilyClient
    t = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    t.search("Tesla charge port", max_results=1)
    return "connected"


check("Nebius model list", nebius_models)
if os.getenv("NEBIUS_CHAT_MODEL"):
    check("Nebius chat", nebius_chat)
if os.getenv("NEBIUS_EMBED_MODEL"):
    check("Nebius embeddings", nebius_embed)
check("Pinecone", pinecone_check)
check("LangSmith", langsmith_check)
if os.getenv("TAVILY_API_KEY"):
    check("Tavily", tavily_check)