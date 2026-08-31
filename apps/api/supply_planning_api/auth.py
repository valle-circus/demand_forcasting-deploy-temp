from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from fastapi import HTTPException, status

from .config import Settings


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    user_id: str
    email: str | None


class IdentityVerifier(Protocol):
    async def verify(self, access_token: str) -> AuthenticatedUser: ...


def unauthorized_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "invalid_session",
            "message": "Sign in again before using the planning application.",
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


class SupabaseIdentityVerifier:
    """Validate a browser session through Supabase Auth without logging tokens."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def verify(self, access_token: str) -> AuthenticatedUser:
        if not self._settings.supabase_configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "auth_not_configured",
                    "message": "Supabase authentication is not configured on the API service.",
                },
            )
        if not access_token.strip():
            raise unauthorized_error()

        assert self._settings.supabase_url is not None
        assert self._settings.supabase_secret_key is not None
        endpoint = f"{self._settings.supabase_url.rstrip('/')}/auth/v1/user"
        headers = {
            "apikey": self._settings.supabase_secret_key.get_secret_value(),
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.supabase_timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.get(endpoint, headers=headers)
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "auth_unavailable",
                    "message": "The authentication service could not be reached.",
                },
            ) from exc

        if response.status_code != status.HTTP_200_OK:
            raise unauthorized_error()
        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "auth_unavailable",
                    "message": "The authentication service returned an invalid response.",
                },
            ) from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("id"), str):
            raise unauthorized_error()
        email = payload.get("email")
        return AuthenticatedUser(
            user_id=payload["id"],
            email=email if isinstance(email, str) else None,
        )
