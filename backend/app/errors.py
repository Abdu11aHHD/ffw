"""Consistent API errors with Arabic messages for the UI."""

from __future__ import annotations

from fastapi import HTTPException, status


class ApiError(HTTPException):
    def __init__(self, status_code: int, code: str, message_ar: str,
                 detail_ar: str | None = None) -> None:
        super().__init__(status_code=status_code, detail={
            "code": code, "message_ar": message_ar, "detail_ar": detail_ar,
        })
        self.code = code
        self.message_ar = message_ar


def bad_request(code: str, message_ar: str, detail_ar: str | None = None) -> ApiError:
    return ApiError(status.HTTP_400_BAD_REQUEST, code, message_ar, detail_ar)


def unauthorized(message_ar: str = "يلزم تسجيل الدخول.") -> ApiError:
    return ApiError(status.HTTP_401_UNAUTHORIZED, "unauthorized", message_ar)


def forbidden(message_ar: str = "لا تملك صلاحية الوصول إلى هذا المورد.") -> ApiError:
    return ApiError(status.HTTP_403_FORBIDDEN, "forbidden", message_ar)


def not_found(message_ar: str = "العنصر المطلوب غير موجود.") -> ApiError:
    return ApiError(status.HTTP_404_NOT_FOUND, "not_found", message_ar)


def conflict(code: str, message_ar: str) -> ApiError:
    return ApiError(status.HTTP_409_CONFLICT, code, message_ar)


def unprocessable(code: str, message_ar: str, detail_ar: str | None = None) -> ApiError:
    return ApiError(status.HTTP_422_UNPROCESSABLE_ENTITY, code, message_ar, detail_ar)


def payload_too_large(message_ar: str) -> ApiError:
    return ApiError(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "too_large", message_ar)


def not_configured(message_ar: str) -> ApiError:
    return ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, "not_configured", message_ar)
