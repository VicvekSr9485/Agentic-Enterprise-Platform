"""
Centralised model configuration so the platform can swap providers
(OpenAI / Gemini / etc.) by changing env vars instead of editing every
agent.

Defaults to OpenAI:
    LLM_MODEL=openai/gpt-4o-mini
    EMBEDDING_MODEL=text-embedding-3-small   (1536 dimensions)

To go back to Gemini, set:
    LLM_MODEL=gemini/gemini-2.5-flash-lite
    EMBEDDING_MODEL=text-embedding-004       (768 dimensions)
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

DEFAULT_LLM_MODEL = "openai/gpt-4o-mini"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_EMBEDDING_DIM = 1536  # text-embedding-3-small / -3-large(1536). text-embedding-004 = 768.


def llm_model_id() -> str:
    return os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL)


def embedding_model_id() -> str:
    return os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)


def embedding_dimension() -> int:
    """Pick a sensible dim from the embedding model name when not explicit."""
    explicit = os.getenv("EMBEDDING_DIM")
    if explicit:
        try:
            return int(explicit)
        except ValueError:
            pass
    name = embedding_model_id().lower()
    if "text-embedding-3-large" in name:
        return 3072
    if "text-embedding-3-small" in name:
        return 1536
    if "text-embedding-004" in name or "embedding-004" in name:
        return 768
    return DEFAULT_EMBEDDING_DIM


def make_llm() -> Any:
    """Construct the model object that ADK's LlmAgent expects.

    For OpenAI/anthropic/etc. we route through ADK's LiteLlm wrapper.
    For native Gemini we keep the bare model-id string (ADK's preferred path).
    """
    model_id = llm_model_id()
    if model_id.startswith("gemini/") or model_id.startswith("gemini-"):
        return model_id.removeprefix("gemini/")
    # Anything else (openai/..., anthropic/..., azure/..., bedrock/...) goes via LiteLlm.
    from google.adk.models.lite_llm import LiteLlm
    return LiteLlm(model=model_id)


@lru_cache(maxsize=1)
def openai_client():
    """Cached OpenAI client. Used for intent classification + embeddings."""
    from openai import OpenAI
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def embed_text(text: str) -> list[float]:
    """Embed a single text using the configured embedding model."""
    client = openai_client()
    response = client.embeddings.create(
        model=embedding_model_id(),
        input=text,
    )
    return response.data[0].embedding


def chat_completion(prompt: str, *, system: str | None = None, temperature: float = 0.0) -> str:
    """Synchronous chat completion with the configured LLM_MODEL."""
    client = openai_client()
    # Strip provider prefix ("openai/gpt-4o-mini" -> "gpt-4o-mini")
    model = llm_model_id()
    if "/" in model:
        model = model.split("/", 1)[1]

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    return completion.choices[0].message.content or ""
