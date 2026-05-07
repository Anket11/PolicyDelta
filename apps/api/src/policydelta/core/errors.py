"""Domain exception hierarchy + RFC 9457 problem+json handlers.

Services raise domain exceptions; one set of global handlers translates them.
Clients see exactly one error shape (``ProblemDetail``). Internals (stack
traces, SQL, upstream errors) are logged with the request id, never returned.
"""

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from policydelta.core.middleware import current_request_id
from policydelta.schemas.problem import FieldError, ProblemDetail

logger = structlog.get_logger(__name__)

PROBLEM_CONTENT_TYPE = "application/problem+json"


class AppError(Exception):
    """Base domain error. Subclasses pin status code + title."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    title: str = "Internal Server Error"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail
        super().__init__(detail or self.title)


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    title = "Unauthorized"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    title = "Forbidden"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    title = "Not Found"

    def __init__(self, resource: str, identifier: object = None) -> None:
        detail = f"{resource} not found" + (f": {identifier}" if identifier is not None else "")
        super().__init__(detail)


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    title = "Conflict"


class UnprocessableError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    title = "Unprocessable Entity"


class RateLimitedError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    title = "Too Many Requests"


class ProviderError(AppError):
    """Upstream AI provider failure — details are logged, never leaked."""

    status_code = status.HTTP_502_BAD_GATEWAY
    title = "Upstream AI Error"


class ServiceUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    title = "Service Unavailable"


