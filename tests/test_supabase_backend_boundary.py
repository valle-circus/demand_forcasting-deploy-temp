from __future__ import annotations

import unittest

import httpx
from fastapi import HTTPException

from apps.api.supply_planning_api.auth import SupabaseIdentityVerifier
from apps.api.supply_planning_api.config import Settings
from apps.api.supply_planning_api.repository import (
    REQUIRED_SCHEMA_FUNCTIONS,
    REQUIRED_SCHEMA_TABLES,
    SupabaseCanonicalStore,
)


def _settings(secret: str = "sb_secret_server-test") -> Settings:
    return Settings.model_validate(
        {
            "APP_ENV": "test",
            "CORS_ORIGINS": "http://localhost:5173",
            "SUPABASE_URL": "https://project.example.supabase.co",
            "SUPABASE_SECRET_KEY": secret,
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
                },
            )

        verifier = SupabaseIdentityVerifier(
            _settings(),
            transport=httpx.MockTransport(handler),
        )
        user = await verifier.verify("browser-access-token")

        self.assertEqual("maintainer@example.test", user.email)
        self.assertEqual("/auth/v1/user", seen[0].url.path)
        self.assertEqual("sb_secret_server-test", seen[0].headers["apikey"])
        self.assertEqual("Bearer browser-access-token", seen[0].headers["authorization"])

    async def test_invalid_supabase_session_is_rejected(self) -> None:
        verifier = SupabaseIdentityVerifier(
            _settings(),
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(401, json={"message": "invalid"})
            ),
        )

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

        state = await SupabaseCanonicalStore(
            _settings(),
            transport=httpx.MockTransport(handler),
        ).schema_state()

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
        await store.select_rows("source_imports", limit=1)

        self.assertEqual("sb_secret_server-test", seen[0].headers["apikey"])
        self.assertNotIn("authorization", seen[0].headers)


if __name__ == "__main__":
    unittest.main()
