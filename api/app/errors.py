from __future__ import annotations

from typing import Any


class APIError(Exception):
    """Base error mapped to an HTTP response."""

    status_code = 400
    code = "bad_request"

    def __init__(self, message: str = "طلب غير صالح", details: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(APIError):
    status_code = 404
    code = "not_found"

    def __init__(self, message: str = "المورد غير موجود") -> None:
        super().__init__(message)


class AuthError(APIError):
    status_code = 401
    code = "unauthenticated"

    def __init__(self, message: str = "يجب تسجيل الدخول") -> None:
        super().__init__(message)


class PermissionError(APIError):
    status_code = 403
    code = "forbidden"

    def __init__(self, message: str = "ليست لديك صلاحية لهذا الإجراء") -> None:
        super().__init__(message)


class ConflictError(APIError):
    status_code = 409
    code = "conflict"

    def __init__(self, message: str = "تعارض في البيانات") -> None:
        super().__init__(message)


class ValidationFailure(APIError):
    status_code = 422
    code = "validation_error"


class RateLimitedError(APIError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, message: str = "تم تجاوز حد الطلبات، حاول لاحقًا", retry_after: int = 30) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def error_payload(err: APIError) -> dict[str, Any]:
    return {
        "error": {
            "code": err.code,
            "message": err.message,
            "details": err.details,
        }
    }
