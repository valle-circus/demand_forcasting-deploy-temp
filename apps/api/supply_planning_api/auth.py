from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from fastapi import HTTPException, status

from .config import Settings
from .http_client import SupabaseHttpClient


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


def forbidden_error(code: str, message: str) -> HTTPException:
    """
    A valid Supabase session that this application still refuses. Distinct from
    `unauthorized_error` on purpose: signing in again would change nothing, so
    the browser must not clear the session and re-prompt.
    """
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": code, "message": message},
    )


class SupabaseIdentityVerifier:
    """Validate a browser session through Supabase Auth without logging tokens."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        http_client: SupabaseHttpClient | None = None,
    ) -> None:
        if transport is not None and http_client is not None:
            raise ValueError("Pass either transport or http_client, not both")
        self._settings = settings
        self._http_client = http_client or SupabaseHttpClient(
            timeout_seconds=settings.supabase_timeout_seconds,
            transport=transport,
        )
        self._owns_http_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_http_client:
            await self._http_client.aclose()

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
            response = await self._http_client.request("GET", endpoint, headers=headers)
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
        raw_email = payload.get("email")
        email = raw_email if isinstance(raw_email, str) else None
        self._require_admissible_account(email, payload.get("email_confirmed_at"))
        return AuthenticatedUser(user_id=payload["id"], email=email)

    def _require_admissible_account(
        self,
        email: str | None,
        email_confirmed_at: Any,
    ) -> None:
        """
        The second half of the sign-up gate.

        Supabase itself blocks the disallowed cases first: the `auth.users`
        trigger refuses the insert, and project settings withhold a session
        until the address is confirmed. This repeats both checks because the
        browser holds a publishable key and can call Supabase Auth directly,
        so neither of those is a boundary this API controls. This admits an
        identity only; the request must still resolve a current workspace and
        role before it can reach planning data.
        """
        if not isinstance(email_confirmed_at, str) or not email_confirmed_at.strip():
            raise forbidden_error(
                "email_not_confirmed",
                "Confirm your email address using the link we sent, then sign in.",
            )
        if email is None or "@" not in email:
            raise forbidden_error(
                "email_domain_not_allowed",
                "This account has no email address and cannot use the planning "
                "application.",
            )
        domain = email.rpartition("@")[2].lower()
        if domain not in self._settings.allowed_email_domains:
            raise forbidden_error(
                "email_domain_not_allowed",
                "This application is limited to approved company email domains.",
            )
