"""Policy semantic-search tool used by the Policy agent.

Caches the vecs vector-DB client and the Gemini embeddings client so that
each query does not pay the overhead of opening a new Postgres connection
and re-initializing the genai client.
"""

from __future__ import annotations

import os
from threading import Lock
from typing import Any, Optional

from dotenv import load_dotenv

from shared.logging_utils import get_logger

logger = get_logger("agents.policy.search_tool")
load_dotenv()

_vector_client: Optional[Any] = None
_collection: Optional[Any] = None
_genai_client: Optional[Any] = None
_init_lock = Lock()


def _ensure_clients() -> tuple[Any, Any]:
    """Lazily initialise the vector-DB collection and Gemini client."""
    global _vector_client, _collection, _genai_client

    with _init_lock:
        if _collection is not None and _genai_client is not None:
            return _collection, _genai_client

        db_url = os.getenv("SUPABASE_DB_URL")
        api_key = os.getenv("GOOGLE_API_KEY")
        if not db_url:
            raise RuntimeError("SUPABASE_DB_URL is not configured")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY is not configured")

        import vecs  # local import: heavy module
        from google import genai

        if _vector_client is None:
            _vector_client = vecs.create_client(db_url)
        if _collection is None:
            _collection = _vector_client.get_or_create_collection(
                name="policy_documents", dimension=768
            )
        if _genai_client is None:
            _genai_client = genai.Client(api_key=api_key)

        return _collection, _genai_client


def search_policy_documents(query: str) -> str:
    """Semantic search over policy documents (top 3 by similarity).

    Args:
        query: User query string.

    Returns:
        A formatted multi-document string suitable for LLM consumption,
        or a plain-language error message.
    """
    try:
        collection, client = _ensure_clients()
    except RuntimeError as e:
        return f"Policy search is temporarily unavailable: {e}"
    except Exception as e:
        logger.warning("policy_search_init_error", error=str(e))
        return "Policy search is temporarily unavailable."

    try:
        embedding_response = client.models.embed_content(
            model="text-embedding-004",
            contents=query,
        )

        if not embedding_response or not embedding_response.embeddings:
            return "Unable to process search query. Please try rephrasing."

        embedding = embedding_response.embeddings[0].values

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
        logger.warning("policy_search_error", error=str(e))
        return "An error occurred while searching policies. Please contact support if this persists."
