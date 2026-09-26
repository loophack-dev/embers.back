"""Exception handlers that enforce the single error shape `{"error": ErrorBody}`."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, cast

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from embers.contracts.errors import ErrorBody, ErrorCode
from embers.errors import ApiError

logger = logging.getLogger(__name__)

ExceptionHandler = Callable[[Request, Exception], Awaitable[Response]]


def _error_response(
    status_code: int,
    code: ErrorCode,
    message: str,
    details: dict[str, Any] | None,
) -> JSONResponse:
    body = ErrorBody(code=code, message=message, details=details)
    return JSONResponse(status_code=status_code, content={"error": body.model_dump(mode="json")})


def _field_path(error: dict[str, Any]) -> str:
    """Build the dotted field path for a Pydantic error, stripping the leading
    `body`/`query`/`path` segment added by FastAPI. Malformed JSON always maps to
    the `body` field."""
    if error.get("type") == "json_invalid":
        return "body"
    loc = tuple(error.get("loc", ()))
    parts = [str(segment) for segment in loc[1:]]
    return ".".join(parts) if parts else "body"


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    fields = [
        {"field": _field_path(error), "reason": str(error["msg"]).removeprefix("Value error, ")}
        for error in exc.errors()
    ]
    return _error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        ErrorCode.VALIDATION_ERROR,
        "The request did not pass validation.",
        {"fields": fields},
    )


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return _error_response(exc.status_code, exc.code, exc.message, exc.details)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code == status.HTTP_404_NOT_FOUND:
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            ErrorCode.NOT_FOUND,
            "The requested resource was not found.",
            None,
        )
    if exc.status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
        return _error_response(
            status.HTTP_405_METHOD_NOT_ALLOWED,
            ErrorCode.NOT_FOUND,
            "The method is not allowed for this resource.",
            None,
        )
    detail = exc.detail if isinstance(exc.detail, str) else "Unexpected error."
    return _error_response(exc.status_code, ErrorCode.INTERNAL_ERROR, detail, None)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled exception while processing request", exc_info=exc)
    return _error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.INTERNAL_ERROR,
        "An unexpected error occurred.",
        None,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        RequestValidationError, cast(ExceptionHandler, validation_exception_handler)
    )
    app.add_exception_handler(ApiError, cast(ExceptionHandler, api_error_handler))
    app.add_exception_handler(
        StarletteHTTPException, cast(ExceptionHandler, http_exception_handler)
    )
    app.add_exception_handler(Exception, unhandled_exception_handler)
