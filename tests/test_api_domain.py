from __future__ import annotations

import unittest
from pathlib import Path
from typing import cast

import httpx
from fastapi import FastAPI

from apps.api.supply_planning_api.auth import AuthenticatedUser, IdentityVerifier
from apps.api.supply_planning_api.config import Settings
from apps.api.supply_planning_api.main import create_app
from apps.api.supply_planning_api.services import Backend
from apps.api.supply_planning_api.supabase import DependencyState, ReadinessProbe
from apps.api.supply_planning_api.uploads import SavedUpload


class _ReadyProbe:
    async def check(self) -> DependencyState:
        return DependencyState("ready", "Ready.")


class _Verifier:
    def __init__(self) -> None:
        self.tokens: list[str] = []

    async def verify(self, access_token: str) -> AuthenticatedUser:
        self.tokens.append(access_token)
        return AuthenticatedUser(
            user_id="11111111-1111-1111-1111-111111111111",
            email="maintainer@example.test",
        )


class _RouteBackend:
    def __init__(self) -> None:
        self.upload_path: Path | None = None
        self.upload_existed_during_call = False

    async def overview(self) -> dict[str, object]:
        return {"kpis": {"locations_ready": 1}, "proposal_only": True}

    async def import_master_data(
        self,
        file: SavedUpload,
        _user: AuthenticatedUser,
    ) -> dict[str, object]:
        self.upload_path = file.path
        self.upload_existed_during_call = file.path.exists()
        return {
            "id": "22222222-2222-2222-2222-222222222222",
            "dataset_type": "master_data",
            "status": "accepted",
            "file_names": [file.file_name],
        }


class _FailingRouteBackend(_RouteBackend):
    async def overview(self) -> dict[str, object]:
        raise RuntimeError("private diagnostic detail")


class ApiDomainTests(unittest.IsolatedAsyncioTestCase):
    def _settings(self) -> Settings:
        return Settings.model_validate(
            {
                "APP_ENV": "test",
                "CORS_ORIGINS": "http://localhost:5173",
                "SUPABASE_URL": None,
                "SUPABASE_SECRET_KEY": None,
                "MAX_UPLOAD_BYTES": 1024,
            }
        )

    def _app(
        self,
        backend: _RouteBackend,
        verifier: _Verifier,
    ) -> FastAPI:
        return create_app(
            settings=self._settings(),
            supabase_probe=cast(ReadinessProbe, _ReadyProbe()),
            backend=cast(Backend, backend),
            identity_verifier=cast(IdentityVerifier, verifier),
        )

    async def test_domain_endpoint_rejects_missing_session(self) -> None:
        backend = _RouteBackend()
        verifier = _Verifier()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self._app(backend, verifier)),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/overview")

        self.assertEqual(401, response.status_code)
        self.assertEqual("invalid_session", response.json()["error"]["code"])
        self.assertEqual([], verifier.tokens)

    async def test_valid_session_reaches_identity_and_overview(self) -> None:
        backend = _RouteBackend()
        verifier = _Verifier()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self._app(backend, verifier)),
            base_url="http://test",
            headers={"Authorization": "Bearer valid-token"},
        ) as client:
            me = await client.get("/api/v1/me")
            overview = await client.get("/api/v1/overview")

        self.assertEqual(200, me.status_code)
        self.assertEqual("maintainer", me.json()["role"])
        self.assertEqual(1, overview.json()["kpis"]["locations_ready"])
        self.assertEqual(["valid-token", "valid-token"], verifier.tokens)

    async def test_xlsx_upload_is_request_scoped_and_cleaned_up(self) -> None:
        backend = _RouteBackend()
        verifier = _Verifier()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self._app(backend, verifier)),
            base_url="http://test",
            headers={"Authorization": "Bearer valid-token"},
        ) as client:
            response = await client.post(
                "/api/v1/imports/master-data",
                files={
                    "file": (
                        "..\\Phase2_Master_Data_Template_v1.xlsx",
                        b"synthetic-xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )

        self.assertEqual(201, response.status_code)
        self.assertTrue(backend.upload_existed_during_call)
        self.assertEqual("Phase2_Master_Data_Template_v1.xlsx", response.json()["file_names"][0])
        assert backend.upload_path is not None
        self.assertFalse(backend.upload_path.exists())

    async def test_upload_rejects_wrong_extension_before_backend(self) -> None:
        backend = _RouteBackend()
        verifier = _Verifier()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self._app(backend, verifier)),
            base_url="http://test",
            headers={"Authorization": "Bearer valid-token"},
        ) as client:
            response = await client.post(
                "/api/v1/imports/master-data",
                files={"file": ("master.csv", b"not-xlsx", "text/csv")},
            )

        self.assertEqual(422, response.status_code)
        self.assertEqual("validation_failed", response.json()["error"]["code"])
        self.assertIsNone(backend.upload_path)

    async def test_unexpected_error_is_sanitized_and_keeps_cors_header(self) -> None:
        backend = _FailingRouteBackend()
        verifier = _Verifier()
        with self.assertLogs(
            "apps.api.supply_planning_api.main",
            level="ERROR",
        ) as captured:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(
                    app=self._app(backend, verifier),
                    raise_app_exceptions=False,
                ),
                base_url="http://test",
                headers={
                    "Authorization": "Bearer valid-token",
                    "Origin": "http://localhost:5173",
                },
            ) as client:
                response = await client.get("/api/v1/overview")

        self.assertEqual(500, response.status_code)
        self.assertIn("Unhandled supply-planning API error", captured.output[0])
        self.assertEqual("internal_error", response.json()["error"]["code"])
        self.assertNotIn("private diagnostic detail", response.text)
        self.assertEqual(
            "http://localhost:5173",
            response.headers["access-control-allow-origin"],
        )


if __name__ == "__main__":
    unittest.main()
