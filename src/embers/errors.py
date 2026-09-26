"""Domain-level API error, raised by endpoints and turned into an ErrorResponse."""

from __future__ import annotations

from typing import Any

from embers.contracts.errors import ErrorCode


class ApiError(Exception):
    """An error that maps directly to an HTTP status code and an ErrorBody."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        status_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
