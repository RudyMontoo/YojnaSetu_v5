"""
RAG Ingestion Script — Yojna Setu
Loads all scheme JSONs → generates embeddings → stores in ChromaDB

Run once to build the vector store, then use rag_chain.py to query.
Usage: python ingest.py
"""
import json, os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

import chromadb
from chromadb.utils import embedding_functions

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
DATA_DIR   = BASE_DIR / "data" / "schemes"
CHROMA_DIR = BASE_DIR / "chroma_db"
COLLECTION = "yojna_setu_schemes"

# Use sentence-transformers for local embeddings (no API key needed for indexing)
EMBED_MODEL = "all-MiniLM-L6-v2"

# ── Helper to build a flat text chunk from a scheme dict ─────────────────────
def scheme_to_text(scheme: dict, state: str = None) -> str:
    parts = []

    name = scheme.get("name") or scheme.get("name_en", "")
    name_hi = scheme.get("name_hi", "")
    benefit = scheme.get("benefit") or scheme.get("benefit_en", "")
    benefit_hi = scheme.get("benefit_hi", "")
    eligibility = scheme.get("eligibility", "")
    docs = ", ".join(scheme.get("documents", []))
    ministry = scheme.get("ministry", "")
    sector = scheme.get("sector", "")
    url = scheme.get("apply_url", "")
    scheme_type = scheme.get("type", "Central")

    parts.append(f"Scheme: {name}")
    if name_hi:
        parts.append(f"Hindi Name: {name_hi}")
    if ministry:
        parts.append(f"Ministry: {ministry}")
    if state:
        parts.append(f"State: {state}")
    else:
        parts.append(f"Type: {scheme_type} scheme")
    parts.append(f"Sector: {sector}")
    parts.append(f"Benefit: {benefit}")
    if benefit_hi:
        parts.append(f"Benefit (Hindi): {benefit_hi}")
    parts.append(f"Eligibility: {eligibility}")
    parts.append(f"Documents Required: {docs}")
    parts.append(f"Apply at: {url}")

    return "\n".join(parts)


def scheme_to_metadata(scheme: dict, sector: str, state: str = None, source_file: str = "") -> dict:
    return {
        "name": (scheme.get("name") or scheme.get("name_en", ""))[:500],
        "sector": sector,
        "state": state or "Central",
        "type": scheme.get("type", "State" if state else "Central"),
        "apply_url": scheme.get("apply_url", "")[:500],
        "status": scheme.get("status", "active"),
        "source_file": source_file,
    }


# ── Load all schemes from data/schemes/*.json (central + new sectors) ─────────
def load_all_schemes():
    all_docs = []   # (id, text, metadata)
    idx = 0

    # 1. Central sector files in root of schemes/
    for f in sorted(DATA_DIR.glob("*.json")):
        if f.name in ("all_schemes.json",):
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        sector = data.get("sector", f.stem)
        for scheme in data.get("schemes", []):
            if scheme.get("status") == "active" or "status" not in scheme:
                text = scheme_to_text(scheme)
                meta = scheme_to_metadata(scheme, sector, source_file=f.name)
                all_docs.append((f"central_{sector}_{idx}", text, meta))
                idx += 1

    # 2. State scheme files
    state_dir = DATA_DIR / "states"
    for f in sorted(state_dir.glob("*.json")):
        if f.name in ("all_states.json",):
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        state_en = data.get("state_en", f.stem)
        for scheme in data.get("schemes", []):
            if scheme.get("status") == "active" or "status" not in scheme:
                sector = scheme.get("sector", "general")
                text = scheme_to_text(scheme, state=state_en)
                meta = scheme_to_metadata(scheme, sector, state=state_en, source_file=f.name)
                all_docs.append((f"state_{f.stem}_{idx}", text, meta))
                idx += 1

    return all_docs


# ── Main ingestion ─────────────────────────────────────────────────────────────
def main():
    print("🔍 Loading schemes from JSON files...")
    docs = load_all_schemes()
    print(f"   Loaded {len(docs)} active schemes")

    print("\n📦 Connecting to ChromaDB...")
    CHROMA_DIR.mkdir(exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    # Use local sentence-transformers for free embeddings
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBED_MODEL
    )

    # Delete old collection if re-running
    try:
        client.delete_collection(COLLECTION)
        print(f"   Deleted old collection '{COLLECTION}'")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"}
    )

    # Batch upsert (ChromaDB handles up to 5000 per call)
    BATCH = 200
    ids   = [d[0] for d in docs]
    texts = [d[1] for d in docs]
    metas = [d[2] for d in docs]

    print(f"\n✏️  Embedding and indexing {len(docs)} documents (batch={BATCH})...")
    for i in range(0, len(docs), BATCH):
        batch_ids   = ids[i:i+BATCH]
        batch_texts = texts[i:i+BATCH]
        batch_metas = metas[i:i+BATCH]
        collection.upsert(
            ids=batch_ids,
            documents=batch_texts,
            metadatas=batch_metas,
        )
        print(f"   ✅ Indexed {min(i+BATCH, len(docs))}/{len(docs)}")

    print(f"\n🎉 ChromaDB ready: {collection.count()} documents indexed")
    print(f"📁 Stored at: {CHROMA_DIR}")
    print(f"\nTo query: python rag_chain.py")


if __name__ == "__main__":
    main()
