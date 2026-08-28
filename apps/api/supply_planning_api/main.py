from __future__ import annotations

from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import __version__
from .config import Settings, get_settings
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
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_probe = supabase_probe or SupabaseReadinessProbe(resolved_settings)
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

    return application


app = create_app()
