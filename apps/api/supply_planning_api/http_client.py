from __future__ import annotations

from typing import Any

import httpx


class SupabaseHttpClient:
    """One lazily-created async client shared by the Supabase adapters."""

    def __init__(
        self,
        *,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._client: httpx.AsyncClient | None = None
        self._closed = False

    @property
    def is_closed(self) -> bool:
        return self._closed

    def _get_client(self) -> httpx.AsyncClient:
        if self._closed:
            raise RuntimeError("Supabase HTTP client is closed")
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout_seconds,
                transport=self._transport,
            )
        return self._client

    async def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        return await self._get_client().request(method, url, **kwargs)

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._client is not None:
            await self._client.aclose()
