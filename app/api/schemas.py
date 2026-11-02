"""统一响应信封 ApiResponse。"""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应信封：{ success, data, error, meta }。"""

    success: bool
    data: T | None = None
    error: str | None = None
    meta: dict | None = None
