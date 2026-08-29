from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import __version__
from .auth import IdentityVerifier, SupabaseIdentityVerifier
from .config import Settings, get_settings
from .errors import ApiError
from .repository import CanonicalStore, SupabaseCanonicalStore
from .routes import create_domain_router
from .services import Backend, PlanningBackend
from .supabase import ReadinessProbe, SupabaseReadinessProbe


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    environment: str


class DependencyResponse(BaseModel):
    status: Literal["ready", "not_configured", "unavailable"]
    message: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "degraded"]
    service: str
    version: str
    environment: str
    supabase: DependencyResponse


def create_app(
    *,
    settings: Settings | None = None,
    supabase_probe: ReadinessProbe | None = None,
    store: CanonicalStore | None = None,
    backend: Backend | None = None,
    identity_verifier: IdentityVerifier | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_probe = supabase_probe or SupabaseReadinessProbe(resolved_settings)
    resolved_store = store or SupabaseCanonicalStore(resolved_settings)
    resolved_backend = backend or PlanningBackend(resolved_store, resolved_settings)
    resolved_verifier = identity_verifier or SupabaseIdentityVerifier(resolved_settings)
    application = FastAPI(
        title="Supply Planning API",
        version=__version__,
        description=(
            "Thin HTTP boundary for the Phase 2 supply-planning engine. "
            "It does not place supplier orders."
        ),
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @application.exception_handler(ApiError)
    async def planner_error(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(
                {
                    "error": {
                        "code": exc.code,
                        "message": exc.message,
                        "details": exc.details,
                    }
                }
            ),
        )

    @application.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail and "message" in detail:
            error = {**detail, "details": detail.get("details", {})}
        else:
            error = {
                "code": "http_error",
                "message": str(detail),
                "details": {},
            }
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": error},
            headers=exc.headers,
        )

    @application.get("/", response_model=HealthResponse, tags=["system"])
    @application.get("/api/v1/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="supply-planning-api",
            version=__version__,
            environment=resolved_settings.app_environment,
        )

    @application.get(
        "/api/v1/readiness",
        response_model=ReadinessResponse,
        tags=["system"],
    )
    async def readiness() -> ReadinessResponse:
        dependency = await resolved_probe.check()
        return ReadinessResponse(
            status="ready" if dependency.status == "ready" else "degraded",
            service="supply-planning-api",
            version=__version__,
            environment=resolved_settings.app_environment,
            supabase=DependencyResponse(
                status=dependency.status,
                message=dependency.message,
            ),
        )

    application.include_router(
        create_domain_router(
            backend=resolved_backend,
            verifier=resolved_verifier,
            settings=resolved_settings,
        )
    )

    return application


app = create_app()
