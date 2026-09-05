from __future__ import annotations

import asyncio
import unittest
from typing import cast

import httpx
from fastapi import HTTPException
from pydantic import ValidationError

from apps.api.supply_planning_api.auth import (
    AuthenticatedUser,
    SupabaseIdentityVerifier,
)
from apps.api.supply_planning_api.config import Settings
from apps.api.supply_planning_api.http_client import SupabaseHttpClient
from apps.api.supply_planning_api.repository import (
    REQUIRED_SCHEMA_FUNCTIONS,
    REQUIRED_SCHEMA_TABLES,
    SupabaseCanonicalStore,
)
from apps.api.supply_planning_api.request_metrics import collect_request_metrics


def _settings(secret: str = "sb_secret_server-test") -> Settings:
    return Settings.model_validate(
        {
            "APP_ENV": "test",
            "CORS_ORIGINS": "http://localhost:5173",
            "SUPABASE_URL": "https://project.example.supabase.co",
            "SUPABASE_SECRET_KEY": secret,
            # The tests below assert transport behaviour, so their fixture
            # address has to be one the sign-up gate admits.
            "ALLOWED_EMAIL_DOMAINS": "example.test",
        }
    )


class SupabaseBackendBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_auth_uses_user_bearer_and_server_api_key(self) -> None:
        seen: list[httpx.Request] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(
                200,
                json={
                    "id": "11111111-1111-1111-1111-111111111111",
                    "email": "maintainer@example.test",
                    "email_confirmed_at": "2026-09-03T09:00:00Z",
                },
            )

        verifier = SupabaseIdentityVerifier(
            _settings(),
            transport=httpx.MockTransport(handler),
        )
        self.addAsyncCleanup(verifier.aclose)
        user = await verifier.verify("browser-access-token")

        self.assertEqual("maintainer@example.test", user.email)
        self.assertEqual("/auth/v1/user", seen[0].url.path)
        self.assertEqual("sb_secret_server-test", seen[0].headers["apikey"])
        self.assertEqual("Bearer browser-access-token", seen[0].headers["authorization"])

    async def _verify_user(
        self,
        *,
        email: str,
        email_confirmed_at: object = "2026-09-03T09:00:00Z",
        allowed_domains: str = "circuskitchens.com",
    ) -> AuthenticatedUser:
        settings = Settings.model_validate(
            {
                "APP_ENV": "test",
                "CORS_ORIGINS": "http://localhost:5173",
                "SUPABASE_URL": "https://project.example.supabase.co",
                "SUPABASE_SECRET_KEY": "sb_secret_server-test",
                "ALLOWED_EMAIL_DOMAINS": allowed_domains,
            }
        )
        payload: dict[str, object] = {
            "id": "11111111-1111-1111-1111-111111111111",
            "email": email,
        }
        if email_confirmed_at is not None:
            payload["email_confirmed_at"] = email_confirmed_at
        verifier = SupabaseIdentityVerifier(
            settings,
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, json=payload)
            ),
        )
        self.addAsyncCleanup(verifier.aclose)
        return await verifier.verify("browser-access-token")

    async def test_outside_email_domain_is_refused_despite_valid_session(self) -> None:
        # The auth.users trigger should stop this account existing at all. The
        # API repeats the check because the browser can call Supabase Auth
        # directly. Workspace authorization remains a separate request gate.
        with self.assertRaises(HTTPException) as captured:
            await self._verify_user(email="outsider@gmail.com")

        self.assertEqual(403, captured.exception.status_code)
        self.assertEqual(
            "email_domain_not_allowed",
            cast(dict[str, str], captured.exception.detail)["code"],
        )

    async def test_unconfirmed_email_is_refused(self) -> None:
        with self.assertRaises(HTTPException) as captured:
            await self._verify_user(
                email="colleague@circuskitchens.com",
                email_confirmed_at=None,
            )

        self.assertEqual(403, captured.exception.status_code)
        self.assertEqual(
            "email_not_confirmed",
            cast(dict[str, str], captured.exception.detail)["code"],
        )

    async def test_confirmed_company_address_is_accepted(self) -> None:
        user = await self._verify_user(email="Colleague@CircusKitchens.com")

        # Mixed case must pass: the domain compares case-insensitively.
        self.assertEqual("Colleague@CircusKitchens.com", user.email)

    async def test_domain_allowlist_refuses_an_empty_value(self) -> None:
        # An empty allowlist must not be read as "allow everyone".
        with self.assertRaises(ValidationError):
            Settings.model_validate(
                {
                    "APP_ENV": "test",
                    "CORS_ORIGINS": "http://localhost:5173",
                    "ALLOWED_EMAIL_DOMAINS": "  ",
                }
            )

    async def test_invalid_supabase_session_is_rejected(self) -> None:
        verifier = SupabaseIdentityVerifier(
            _settings(),
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(401, json={"message": "invalid"})
            ),
        )
        self.addAsyncCleanup(verifier.aclose)

        with self.assertRaises(HTTPException) as captured:
            await verifier.verify("expired-token")
        self.assertEqual(401, captured.exception.status_code)

    async def test_schema_probe_checks_tables_and_transaction_functions(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/rest/v1/":
                return httpx.Response(
                    200,
                    json={
                        "paths": {
                            **{f"/{table}": {} for table in REQUIRED_SCHEMA_TABLES},
                            **{
                                f"/rpc/{function}": {}
                                for function in REQUIRED_SCHEMA_FUNCTIONS
                            },
                        }
                    },
                )
            return httpx.Response(200, json=[])

        store = SupabaseCanonicalStore(
            _settings(),
            transport=httpx.MockTransport(handler),
        )
        self.addAsyncCleanup(store.aclose)
        state = await store.schema_state()

        self.assertTrue(state.ready)
        self.assertEqual((), state.missing_tables)
        self.assertEqual((), state.missing_functions)

    async def test_schema_probe_reports_one_missing_relation(self) -> None:
        missing = "planning_projection_days"

        async def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "paths": {
                        **{
                            f"/{table}": {}
                            for table in REQUIRED_SCHEMA_TABLES
                            if table != missing
                        },
                        **{
                            f"/rpc/{function}": {}
                            for function in REQUIRED_SCHEMA_FUNCTIONS
                        },
                    }
                },
            )

        store = SupabaseCanonicalStore(
            _settings(),
            transport=httpx.MockTransport(handler),
        )
        self.addAsyncCleanup(store.aclose)
        state = await store.schema_state()

        self.assertFalse(state.ready)
        self.assertEqual((missing,), state.missing_tables)

    async def test_new_server_secret_is_not_sent_as_bearer_to_postgrest(self) -> None:
        seen: list[httpx.Request] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json=[])

        store = SupabaseCanonicalStore(
            _settings(),
            transport=httpx.MockTransport(handler),
        )
        self.addAsyncCleanup(store.aclose)
        await store.select_rows("source_imports", limit=1)

        self.assertEqual("sb_secret_server-test", seen[0].headers["apikey"])
        self.assertNotIn("authorization", seen[0].headers)

    async def test_planning_persistence_uses_v3_contract_rpc(self) -> None:
        seen: list[httpx.Request] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json="run-v3")

        store = SupabaseCanonicalStore(
            _settings(),
            transport=httpx.MockTransport(handler),
        )
        self.addAsyncCleanup(store.aclose)

        run_id = await store.persist_planning_run({"run": {"run_id": "run-v3"}})

        self.assertEqual(run_id, "run-v3")
        self.assertEqual(
            seen[0].url.path,
            "/rest/v1/rpc/persist_planning_run_v3",
        )

    async def test_auth_and_postgrest_can_share_one_reusable_client(self) -> None:
        seen_paths: list[str] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            seen_paths.append(request.url.path)
            if request.url.path == "/auth/v1/user":
                return httpx.Response(
                    200,
                    json={
                        "id": "user-1",
                        "email": "maintainer@example.test",
                        "email_confirmed_at": "2026-09-03T09:00:00Z",
                    },
                )
            return httpx.Response(200, json=[])

        shared_client = SupabaseHttpClient(
            timeout_seconds=1,
            transport=httpx.MockTransport(handler),
        )
        self.addAsyncCleanup(shared_client.aclose)
        store = SupabaseCanonicalStore(_settings(), http_client=shared_client)
        verifier = SupabaseIdentityVerifier(_settings(), http_client=shared_client)

        with collect_request_metrics() as metrics:
            _, _, user = await asyncio.gather(
                store.select_rows("source_imports", limit=1),
                store.select_rows("master_data_versions", limit=1),
                verifier.verify("browser-access-token"),
            )

        self.assertEqual("user-1", user.user_id)
        self.assertCountEqual(
            [
                "/rest/v1/source_imports",
                "/rest/v1/master_data_versions",
                "/auth/v1/user",
            ],
            seen_paths,
        )
        self.assertFalse(shared_client.is_closed)
        self.assertEqual(3, metrics.supabase_calls)
        self.assertEqual(1, metrics.auth_calls)
        self.assertEqual(2, metrics.postgrest_reads)
        self.assertEqual(0, metrics.postgrest_writes)
        self.assertGreaterEqual(metrics.supabase_elapsed_ms, 0)


if __name__ == "__main__":
    unittest.main()
