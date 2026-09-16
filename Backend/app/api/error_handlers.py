"""Shared API error response handling."""

from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """Application error that should become a public HTTP response."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Create a safe error carrying the shared API error fields."""

        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details


async def api_error_handler(
    request: Request,
    exc: ApiError,
) -> JSONResponse:
    """Convert an :class:`ApiError` into the shared JSON error envelope."""

    # Reuse the Nginx request identifier when available.
    request_id = (
        request.headers.get("X-Request-ID")
        or str(uuid4())
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
                "details": exc.details,
            },
            "request_id": request_id,
        },
        headers={
            "X-Request-ID": request_id,
        },
    )


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Convert FastAPI/Pydantic validation failures to the API contract."""

    request_id = (
        request.headers.get("X-Request-ID")
        or str(uuid4())
    )

    details = []
    for error in exc.errors():
        location = error.get("loc", ())
        field = ".".join(
            str(part)
            for part in location
            if part not in {"body", "query", "path", "header"}
        )

        details.append(
            {
                "field": field or None,
                "message": error.get("msg", "Invalid value."),
                "type": error.get("type", "validation_error"),
            }
        )

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "The request contains invalid data.",
                "retryable": False,
                "details": {
                    "fields": details,
                },
            },
            "request_id": request_id,
        },
        headers={
            "X-Request-ID": request_id,
        },
    )
