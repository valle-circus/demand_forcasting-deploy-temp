from __future__ import annotations

from typing import Any


class ApiError(Exception):
    """Planner-facing error with a stable HTTP and response contract."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


class RepositoryUnavailableError(ApiError):
    def __init__(self, message: str = "Planning persistence is currently unavailable.") -> None:
        super().__init__(503, "persistence_unavailable", message)


class NotFoundError(ApiError):
    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            404,
            "not_found",
            f"{resource} {identifier!r} was not found.",
        )


class ConflictError(ApiError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(409, code, message)


class ValidationError(ApiError):
    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(422, "validation_failed", message, details=details)
