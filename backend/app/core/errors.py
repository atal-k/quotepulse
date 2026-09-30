import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.errors")


class DomainError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "domain_error"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)


class Unauthorized(DomainError):
    """Missing/invalid/expired credentials. Distinct from PermissionDenied (authenticated but
    not allowed) — not one of CLAUDE.md §5's five domain exceptions, since it's an
    authentication-layer concern rather than a business rule, but kept on the same envelope."""

    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"


class NotFound(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class PermissionDenied(DomainError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"


class Conflict(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class ValidationFailed(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "validation_failed"


class ApprovalRequired(DomainError):
    status_code = status.HTTP_202_ACCEPTED
    code = "approval_required"


def _envelope(code: str, message: str, details: dict[str, Any]) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_envelope(
                "validation_failed",
                "Invalid request.",
                {"errors": jsonable_encoder(exc.errors())},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope("http_error", str(exc.detail), {}),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope("internal_error", "Something went wrong.", {}),
        )
