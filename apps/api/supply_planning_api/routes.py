from collections.abc import AsyncIterator, Callable
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth import AuthenticatedUser, IdentityVerifier, unauthorized_error
from .config import Settings
from .schemas import CreatePlanningRunRequest, UserResponse
from .services import Backend
from .uploads import SavedUpload, save_uploads

JsonResponse = dict[str, Any]
CurrentUserDependency = Callable[..., AsyncIterator[AuthenticatedUser]]


def current_user_dependency(verifier: IdentityVerifier) -> CurrentUserDependency:
    bearer = HTTPBearer(auto_error=False)

    async def current_user(
        credentials: Annotated[
            HTTPAuthorizationCredentials | None,
            Depends(bearer),
        ],
    ) -> AsyncIterator[AuthenticatedUser]:
        if credentials is None or credentials.scheme.casefold() != "bearer":
            raise unauthorized_error()
        yield await verifier.verify(credentials.credentials)

    return current_user


def create_domain_router(
    *,
    backend: Backend,
    verifier: IdentityVerifier,
    settings: Settings,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    require_user = current_user_dependency(verifier)
    User = Annotated[AuthenticatedUser, Depends(require_user)]

    @router.get("/me", response_model=UserResponse, tags=["identity"])
    async def me(user: User) -> UserResponse:
        return UserResponse(user_id=user.user_id, email=user.email)

    @router.get("/locations", tags=["planning"])
    async def locations(_user: User) -> JsonResponse:
        return await backend.list_locations()

    @router.get("/overview", tags=["planning"])
    async def overview(_user: User) -> JsonResponse:
        return await backend.overview()

    @router.get(
        "/locations/{location_id}/planning-status",
        tags=["planning"],
    )
    async def planning_status(location_id: str, _user: User) -> JsonResponse:
        return await backend.planning_status(location_id)

    @router.get("/locations/{location_id}/inventory", tags=["planning"])
    async def inventory(location_id: str, _user: User) -> JsonResponse:
        return await backend.inventory(location_id)

    @router.get("/locations/{location_id}/view", tags=["planning"])
    async def location_view(location_id: str, _user: User) -> JsonResponse:
        return await backend.location_view(location_id)

    @router.get("/locations/{location_id}/purchase-orders", tags=["planning"])
    async def purchase_orders(location_id: str, _user: User) -> JsonResponse:
        return await backend.purchase_orders(location_id)

    @router.get("/imports", tags=["imports"])
    async def imports(
        _user: User,
        dataset_type: Annotated[
            str | None,
            Query(pattern=r"^(master_data|planning_input|stock|purchase_orders)$"),
        ] = None,
        location_id: str | None = None,
    ) -> list[JsonResponse]:
        return await backend.list_imports(
            dataset_type=dataset_type,
            location_id=location_id,
        )

    @router.get("/imports/{import_id}", tags=["imports"])
    async def import_detail(import_id: UUID, _user: User) -> JsonResponse:
        return await backend.get_import(str(import_id))

    async def save_one_xlsx(upload: UploadFile, directory: Path) -> SavedUpload:
        files = await save_uploads(
            (upload,),
            directory,
            allowed_suffixes=frozenset({".xlsx"}),
            max_files=1,
            max_total_bytes=settings.max_upload_bytes,
        )
        return files[0]

    @router.post(
        "/imports/master-data",
        status_code=status.HTTP_201_CREATED,
        tags=["imports"],
    )
    async def import_master_data(
        file: Annotated[UploadFile, File()],
        user: User,
    ) -> JsonResponse:
        with TemporaryDirectory(prefix="supply-planning-master-") as path:
            saved = await save_one_xlsx(file, Path(path))
            return await backend.import_master_data(saved, user)

    @router.post(
        "/imports/planning-input",
        status_code=status.HTTP_201_CREATED,
        tags=["imports"],
    )
    async def import_planning_input(
        file: Annotated[UploadFile, File()],
        user: User,
    ) -> JsonResponse:
        with TemporaryDirectory(prefix="supply-planning-input-") as path:
            saved = await save_one_xlsx(file, Path(path))
            return await backend.import_planning_input(saved, user)

    @router.post(
        "/imports/stock",
        status_code=status.HTTP_201_CREATED,
        tags=["imports"],
    )
    async def import_stock(
        file: Annotated[UploadFile, File()],
        location_id: Annotated[str, Form(min_length=1, max_length=100)],
        user: User,
    ) -> JsonResponse:
        with TemporaryDirectory(prefix="supply-planning-stock-") as path:
            saved = await save_one_xlsx(file, Path(path))
            return await backend.import_stock(
                saved,
                location_id=location_id,
                user=user,
            )

    @router.post(
        "/imports/purchase-orders",
        status_code=status.HTTP_201_CREATED,
        tags=["imports"],
    )
    async def import_purchase_orders(
        files: Annotated[list[UploadFile], File()],
        location_id: Annotated[str, Form(min_length=1, max_length=100)],
        as_of_at: Annotated[datetime, Form()],
        user: User,
    ) -> JsonResponse:
        with TemporaryDirectory(prefix="supply-planning-po-") as path:
            saved = await save_uploads(
                files,
                Path(path),
                allowed_suffixes=frozenset({".pdf"}),
                max_files=settings.max_po_files,
                max_total_bytes=settings.max_upload_bytes,
            )
            return await backend.import_purchase_orders(
                saved,
                location_id=location_id,
                as_of_at=as_of_at,
                user=user,
            )

    @router.get("/master-data/versions", tags=["master data"])
    async def master_versions(_user: User) -> list[JsonResponse]:
        return await backend.list_master_versions()

    @router.post(
        "/master-data/versions/{version_id}/activate",
        tags=["master data"],
    )
    async def activate_master_version(version_id: UUID, user: User) -> JsonResponse:
        return await backend.activate_master_version(str(version_id), user)

    @router.post(
        "/planning-runs",
        status_code=status.HTTP_201_CREATED,
        tags=["planning runs"],
    )
    async def create_planning_run(
        request: CreatePlanningRunRequest,
        user: User,
    ) -> JsonResponse:
        return await backend.create_planning_run(request, user)

    @router.get("/planning-runs/{run_id}", tags=["planning runs"])
    async def planning_run(run_id: str, _user: User) -> JsonResponse:
        return await backend.get_planning_run(run_id)

    @router.get(
        "/planning-runs/{run_id}/recommendations",
        tags=["planning runs"],
    )
    async def recommendations(run_id: str, _user: User) -> JsonResponse:
        result = await backend.get_planning_run(run_id)
        return {
            "run": result["run"],
            "recommendations": result["recommendations"],
            "proposal_only": True,
        }

    @router.get("/planning-runs/{run_id}/risks", tags=["planning runs"])
    async def risks(run_id: str, _user: User) -> JsonResponse:
        result = await backend.get_planning_run(run_id)
        risk_rows = [
            row
            for row in result["netting_results"]
            if row.get("actionable_risk_status") == "at_risk"
        ]
        return {
            "run": result["run"],
            "risks": risk_rows,
            "exceptions": result["exceptions"],
        }

    @router.get("/planning-runs/{run_id}/export.json", tags=["exports"])
    async def export_json(run_id: str, _user: User) -> Response:
        payload = await backend.recommendation_json(run_id)
        from fastapi.responses import JSONResponse

        return JSONResponse(
            payload,
            headers={
                "Content-Disposition": (
                    f'attachment; filename="recommendations-{run_id}.json"'
                )
            },
        )

    @router.get("/planning-runs/{run_id}/export.csv", tags=["exports"])
    async def export_csv(run_id: str, _user: User) -> Response:
        payload = await backend.recommendation_csv(run_id)
        return Response(
            payload,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="recommendations-{run_id}.csv"'
                )
            },
        )

    return router
