from __future__ import annotations

import unittest

import httpx

from apps.api.supply_planning_api.config import Settings
from apps.api.supply_planning_api.main import create_app
from apps.api.supply_planning_api.supabase import DependencyState


class _StubProbe:
    def __init__(self, state: DependencyState) -> None:
        self._state = state

    async def check(self) -> DependencyState:
        return self._state


class ApiFoundationTests(unittest.IsolatedAsyncioTestCase):
    def _settings(self) -> Settings:
        return Settings.model_validate(
            {
                "APP_ENV": "test",
                "CORS_ORIGINS": "http://localhost:5173",
                "SUPABASE_URL": None,
                "SUPABASE_SECRET_KEY": None,
            }
        )

    async def test_health_is_independent_from_supabase(self) -> None:
        application = create_app(
            settings=self._settings(),
            supabase_probe=_StubProbe(
                DependencyState("unavailable", "Dependency is offline.")
            ),
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/health")

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "status": "ok",
                "service": "supply-planning-api",
                "version": "0.1.0",
                "environment": "test",
            },
            response.json(),
        )

    async def test_readiness_reports_sanitized_supabase_state(self) -> None:
        application = create_app(
            settings=self._settings(),
            supabase_probe=_StubProbe(
                DependencyState(
                    "not_configured",
                    "Add SUPABASE_URL and SUPABASE_SECRET_KEY on the API service.",
                )
            ),
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/readiness")

        self.assertEqual(200, response.status_code)
        self.assertEqual("degraded", response.json()["status"])
        self.assertEqual("not_configured", response.json()["supabase"]["status"])
        self.assertNotIn("secret", response.text.lower().replace("secret_key", ""))

    async def test_configured_local_origin_receives_cors_headers(self) -> None:
        application = create_app(
            settings=self._settings(),
            supabase_probe=_StubProbe(DependencyState("ready", "Ready.")),
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application),
            base_url="http://test",
        ) as client:
            response = await client.options(
                "/api/v1/readiness",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "GET",
                },
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            "http://localhost:5173",
            response.headers["access-control-allow-origin"],
        )

    def test_wildcard_cors_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "must list exact origins"):
            Settings.model_validate({"CORS_ORIGINS": "*"})


if __name__ == "__main__":
    unittest.main()
