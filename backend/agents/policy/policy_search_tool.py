"""Policy semantic-search tool used by the Policy agent.

Caches the vecs vector-DB collection so each query does not pay the
overhead of opening a new Postgres connection.

Embeddings are produced via OpenAI by default (`text-embedding-3-small`,
1536-dim). Override with EMBEDDING_MODEL / EMBEDDING_DIM env vars — see
shared/llm_config.py.
"""

from __future__ import annotations

import os
from threading import Lock
from typing import Any, Optional

from dotenv import load_dotenv

from shared.logging_utils import get_logger
from shared.llm_config import embed_text, embedding_dimension, embedding_model_id

logger = get_logger("agents.policy.search_tool")
load_dotenv()

_vector_client: Optional[Any] = None
_collection: Optional[Any] = None
_init_lock = Lock()


def _ensure_collection() -> Any:
    """Lazily initialise the vecs collection."""
    global _vector_client, _collection

    with _init_lock:
        if _collection is not None:
            return _collection

        db_url = os.getenv("SUPABASE_DB_URL")
        if not db_url:
            raise RuntimeError("SUPABASE_DB_URL is not configured")
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not configured")

        import vecs  # local import: heavy module

        if _vector_client is None:
            _vector_client = vecs.create_client(db_url)
        _collection = _vector_client.get_or_create_collection(
            name="policy_documents", dimension=embedding_dimension()
        )
        return _collection


def search_policy_documents(query: str) -> str:
    """Semantic search over policy documents (top 3 by similarity).

    Args:
        query: User query string.

    Returns:
        A formatted multi-document string suitable for LLM consumption,
        or a plain-language error message.
    """
    try:
        collection = _ensure_collection()
    except RuntimeError as e:
        return f"Policy search is temporarily unavailable: {e}"
    except Exception as e:
        logger.warning("policy_search_init_error", error=str(e))
        return "Policy search is temporarily unavailable."

    try:
        embedding = embed_text(query)

        if not embedding:
            return "Unable to process search query. Please try rephrasing."

        results = collection.query(
            data=embedding,
            limit=3,
            include_value=True,
            include_metadata=True,
        )

        if not results:
            return (
                "No policies found matching your query. Try different keywords "
                "or ask about available policy categories."
            )

        formatted = []
        for result in results:
            metadata = result[2] if len(result) > 2 else {}
            content = metadata.get("content", "No content available")
            formatted.append(
                f"**{metadata.get('title', 'Company Policy')}**\n"
                f"Source: {metadata.get('filename', 'Internal Document')}\n"
                f"Category: {metadata.get('category', 'General')}\n\n"
                f"{content}\n"
            )

        return "\n---\n\n".join(formatted)

    except (ConnectionError, TimeoutError) as e:
        logger.warning("policy_search_transport_error", error=str(e))
        return "Unable to connect to policy database. Please try again later."
    except Exception as e:
        logger.warning("policy_search_error", embedding_model=embedding_model_id(), error=str(e))
        return "An error occurred while searching policies. Please contact support if this persists."
