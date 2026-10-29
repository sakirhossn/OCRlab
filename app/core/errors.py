"""Custom application exceptions and RFC 7807 problem details handlers."""

from typing import Any, Dict, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class UnauthorizedError(AppException):
    def __init__(self, message: str = "Invalid or missing API key"):
        super().__init__(
            code="UNAUTHORIZED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenError(AppException):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class NotFoundError(AppException):
    def __init__(self, resource: str = "Resource", message: Optional[str] = None):
        super().__init__(
            code="NOT_FOUND",
            message=message or f"{resource} not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class QuotaExceededError(AppException):
    def __init__(self, message: str = "Monthly page quota exceeded"):
        super().__init__(
            code="QUOTA_EXCEEDED",
            message=message,
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
        )


class RateLimitExceededError(AppException):
    def __init__(self, retry_after: int = 60, message: str = "Rate limit exceeded"):
        super().__init__(
            code="RATE_LIMIT_EXCEEDED",
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"retry_after_seconds": retry_after},
        )


class DocumentSecurityError(AppException):
    def __init__(self, message: str, code: str = "DOCUMENT_SECURITY_REJECTED"):
        super().__init__(
            code=code,
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    payload = {
        "error": {
            "code": exc.code,
            "message": exc.message,
            "request_id": request_id,
            "details": exc.details,
        }
    }
    headers = {}
    if isinstance(exc, RateLimitExceededError) and "retry_after_seconds" in exc.details:
        headers["Retry-After"] = str(exc.details["retry_after_seconds"])

    return JSONResponse(status_code=exc.status_code, content=payload, headers=headers)
