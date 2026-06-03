"""
RAG Chain — Yojna Setu
LangChain retrieval chain using ChromaDB + Groq (Llama 3.3 70B)

Improvements:
  - Per-session conversation memory (ConversationBufferMemory)
  - No-match hallucination guard
  - Streaming support via chain.stream()
"""
import os
from pathlib import Path
from dotenv import load_dotenv

_env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

import chromadb
from chromadb.utils import embedding_functions

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.chat_history import InMemoryChatMessageHistory

# ── Config ────────────────────────────────────────────────────────────────────
CHROMA_DIR   = Path(__file__).parent / "chroma_db"
COLLECTION   = "yojna_setu_schemes"
EMBED_MODEL  = "all-MiniLM-L6-v2"
TOP_K        = 5
GROQ_MODEL   = "llama-3.3-70b-versatile"   # free on Groq, very capable

# ── Per-session memory store ──────────────────────────────────────────────────
# { session_id: InMemoryChatMessageHistory }
_memory_store: dict[str, InMemoryChatMessageHistory] = {}

NO_MATCH_RESPONSE = (
    "Maafi kijiye, aapke sawal se related koi yojana abhi hamare database mein nahi mili. "
    "Aap seedha https://myscheme.gov.in par ja ke apni eligibility check kar sakte hain. "
    "Kya main kisi aur topic mein aapki madad kar sakta hun?"
)

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are Yojna Sathi — a friendly, empathetic AI assistant for Yojna Setu that helps \
Indian citizens discover and apply for government schemes in simple Hinglish (Hindi + English mix).

Use ONLY the retrieved scheme context below. NEVER hallucinate scheme names, amounts, or portals.

RULES:
- If context says "No matching schemes found" — say so honestly, suggest myscheme.gov.in.
- For each scheme mention: Name, Benefit (₹ amount), Who is eligible, Where to apply.
- Prioritize state-specific schemes if the user mentions their state.
- Keep response concise — max 3-4 schemes unless more are asked.
- End with an encouraging Hinglish line.
- You have memory of this conversation — use it for context.

Retrieved Schemes Context:
{context}
"""

# ── ChromaDB retriever ────────────────────────────────────────────────────────
def get_retriever(top_k: int = TOP_K):
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    collection = client.get_collection(name=COLLECTION, embedding_function=ef)

    def retrieve(query: str, filters: dict = None) -> str:
        results = collection.query(
            query_texts=[query],
            n_results=top_k,
            where=filters if filters else None,
        )
        docs  = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]

        if not docs:
            return "No matching schemes found."

        chunks = []
        for i, (doc, meta) in enumerate(zip(docs, metas), 1):
            chunks.append(
                f"[Scheme {i} — {meta.get('state','Central')} / {meta.get('sector','')}]\n{doc}"
            )
        return "\n\n".join(chunks)

    return retrieve


def get_chromadb_count() -> int:
    """Return number of documents currently indexed in ChromaDB."""
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
        col = client.get_collection(name=COLLECTION, embedding_function=ef)
        return col.count()
    except Exception:
        return -1


# ── Memory helpers ────────────────────────────────────────────────────────────
def get_memory(session_id: str) -> InMemoryChatMessageHistory:
    """Get or create a chat history for the given session."""
    if session_id not in _memory_store:
        _memory_store[session_id] = InMemoryChatMessageHistory()
    return _memory_store[session_id]


def clear_memory(session_id: str):
    """Clear session memory (e.g. when user starts fresh)."""
    _memory_store.pop(session_id, None)


# ── Build RAG chain (stateless — memory injected per call) ────────────────────
def build_rag_chain():
    llm = ChatGroq(
        model=GROQ_MODEL,
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.3,
    )
    retriever = get_retriever()

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{question}"),
    ])

    chain = (
        {
            "context":      lambda x: retriever(x["question"], x.get("filters")),
            "question":     RunnablePassthrough() | (lambda x: x["question"]),
            "chat_history": lambda x: x.get("chat_history", []),
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    return chain


def invoke_with_memory(
    chain,
    question: str,
    session_id: str = "default",
    filters: dict = None,
) -> str:
    """
    Invoke the RAG chain with conversation memory.
    Saves the exchange to session memory automatically.
    """
    history = get_memory(session_id)  # InMemoryChatMessageHistory
    chat_messages = history.messages  # list of HumanMessage / AIMessage

    context_text = get_retriever()(question, filters)

    # No-match guard — don't call LLM if nothing found
    if context_text.strip() == "No matching schemes found.":
        history.add_user_message(question)
        history.add_ai_message(NO_MATCH_RESPONSE)
        return NO_MATCH_RESPONSE

    result = chain.invoke({
        "question": question,
        "filters": filters,
        "chat_history": chat_messages,
    })

    # Save to memory
    history.add_user_message(question)
    history.add_ai_message(result)

    return result


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"🔗 ChromaDB schemes indexed: {get_chromadb_count()}")
    print("🔗 Building RAG chain...\n")
    chain = build_rag_chain()

    test_session = "test-001"
    queries = [
        "Main ek kisan hoon Rajasthan se, mujhe koi subsidy milegi?",
        "Meri beti ke liye koi scholarship hai?",
        "Pichle sawal ka jawab dobara batao",       # memory test
        "Ghar banane ke liye paisa milega?",
        "koi alien scheme hai?",                    # no-match guard test
    ]

    for q in queries:
        print(f"❓ {q}")
        print("─" * 60)
        ans = invoke_with_memory(chain, q, session_id=test_session)
        print(ans)
        print("═" * 60 + "\n")
