"""统一 API 响应模型"""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """统一响应信封"""

    success: bool = True
    data: T | None = None
    error: str | None = None
    meta: dict[str, Any] | None = None


def success_response(data: Any = None, meta: dict[str, Any] | None = None) -> dict:
    """构造成功响应"""
    return APIResponse(success=True, data=data, error=None, meta=meta).model_dump()


def error_response(error: str, status_code: int = 500) -> dict:
    """构造错误响应"""
    return APIResponse(success=False, data=None, error=error, meta=None).model_dump()
