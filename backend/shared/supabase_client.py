"""
Supabase REST API client.

Two interfaces:
- Sync (`SupabaseClient.query/insert/update/delete/rpc`) — for tools that
  Google ADK invokes synchronously. Uses a persistent requests.Session for
  HTTP keep-alive so we don't open a new TCP+TLS connection per call.
- Async (`SupabaseClient.aquery/...`) — for FastAPI handlers that should
  not block the event loop on DB calls. Uses a shared httpx.AsyncClient.

Both paths share the same auth headers and retry policy.
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any, Dict, List, Optional

import httpx
import requests
from dotenv import load_dotenv

from shared.logging_utils import get_logger

logger = get_logger("shared.supabase_client")

load_dotenv()

# ---------------------------------------------------------------- input safety
_FILTER_TERM_ALLOWED = re.compile(r"[^A-Za-z0-9 _\-/.]")


def sanitize_filter_term(term: str) -> str:
    """Strip characters that have meaning to PostgREST filter syntax.

    PostgREST filter values use commas, parens and operator dots as syntax.
    Unrestricted user input could re-shape the filter (e.g. `).or.(...`).
    We allow alphanumerics, spaces, underscores, hyphens, dots and slashes.
    """
    if not term:
        return ""
    return _FILTER_TERM_ALLOWED.sub("", term)[:120]


class SupabaseClient:
    """Sync + async Supabase REST API client."""

    def __init__(self) -> None:
        self.base_url = os.getenv("SUPABASE_URL")
        self.api_key = os.getenv("SUPABASE_KEY")

        if not self.base_url or not self.api_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_KEY must be set in environment variables"
            )

        self.rest_url = f"{self.base_url}/rest/v1"
        self.headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        self._session = requests.Session()
        self._session.headers.update(self.headers)
        self._async_client: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------ async client
    def _get_async_client(self) -> httpx.AsyncClient:
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                base_url=self.rest_url,
                headers=self.headers,
                timeout=10.0,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._async_client

    async def aclose(self) -> None:
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None

    # ------------------------------------------------------------------ sync API
    def query(
        self,
        table: str,
        select: str = "*",
        filters: Optional[Dict[str, Any]] = None,
        order: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        params = self._build_params(select, filters, order, limit, offset)
        url = f"{self.rest_url}/{table}"
        try:
            response = self._session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.warning("supabase_query_error", table=table, error=str(e))
            raise Exception(f"Supabase query failed: {e}")

    def insert(self, table: str, data: Dict[str, Any] | List[Dict[str, Any]]) -> Any:
        url = f"{self.rest_url}/{table}"
        try:
            response = self._session.post(url, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.warning("supabase_insert_error", table=table, error=str(e))
            raise Exception(f"Supabase insert failed: {e}")

    def insert_many(self, table: str, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self.insert(table, data)

    def update(
        self,
        table: str,
        filters: Dict[str, Any],
        data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        url = f"{self.rest_url}/{table}"
        try:
            response = self._session.patch(url, params=filters, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.warning("supabase_update_error", table=table, error=str(e))
            raise Exception(f"Supabase update failed: {e}")

    def delete(self, table: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = f"{self.rest_url}/{table}"
        try:
            response = self._session.delete(url, params=filters, timeout=10)
            response.raise_for_status()
            return response.json() if response.content else []
        except requests.RequestException as e:
            logger.warning("supabase_delete_error", table=table, error=str(e))
            raise Exception(f"Supabase delete failed: {e}")

    def rpc(self, function_name: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.rest_url}/rpc/{function_name}"
        try:
            response = self._session.post(url, json=params or {}, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.warning("supabase_rpc_error", function=function_name, error=str(e))
            raise Exception(f"Supabase RPC failed: {e}")

    # ---------------------------------------------------------------- async API
    async def aquery(
        self,
        table: str,
        select: str = "*",
        filters: Optional[Dict[str, Any]] = None,
        order: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        params = self._build_params(select, filters, order, limit, offset)
        client = self._get_async_client()
        try:
            response = await client.get(f"/{table}", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.warning("supabase_aquery_error", table=table, error=str(e))
            raise Exception(f"Supabase async query failed: {e}")

    async def ainsert(self, table: str, data: Dict[str, Any] | List[Dict[str, Any]]) -> Any:
        client = self._get_async_client()
        try:
            response = await client.post(f"/{table}", json=data)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.warning("supabase_ainsert_error", table=table, error=str(e))
            raise Exception(f"Supabase async insert failed: {e}")

    async def aupdate(
        self,
        table: str,
        filters: Dict[str, Any],
        data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        client = self._get_async_client()
        try:
            response = await client.patch(f"/{table}", params=filters, json=data)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.warning("supabase_aupdate_error", table=table, error=str(e))
            raise Exception(f"Supabase async update failed: {e}")

    async def adelete(self, table: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        client = self._get_async_client()
        try:
            response = await client.request("DELETE", f"/{table}", params=filters)
            response.raise_for_status()
            return response.json() if response.content else []
        except httpx.HTTPError as e:
            logger.warning("supabase_adelete_error", table=table, error=str(e))
            raise Exception(f"Supabase async delete failed: {e}")

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _build_params(
        select: str,
        filters: Optional[Dict[str, Any]],
        order: Optional[str],
        limit: Optional[int],
        offset: Optional[int],
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"select": select}
        if filters:
            params.update(filters)
        if order:
            params["order"] = order
        if limit:
            params["limit"] = str(limit)
        if offset:
            params["offset"] = str(offset)
        return params


_client: Optional[SupabaseClient] = None


def get_supabase_client() -> SupabaseClient:
    """Get or create the global Supabase client instance."""
    global _client
    if _client is None:
        _client = SupabaseClient()
    return _client
