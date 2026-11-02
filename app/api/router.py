"""通道层路由汇总与统一异常 handler。"""

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1 import chat, sessions
from app.core.exceptions import AppValidationError, LLMError, NotFoundError

api_router = APIRouter()
api_router.include_router(sessions.router, prefix="/api/v1")
api_router.include_router(chat.router, prefix="/api/v1")


def _envelope(status_code: int, error: str) -> JSONResponse:
    """统一错误信封：success=false，不泄漏内部细节。"""
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "data": None, "error": error, "meta": None},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """注册统一异常 handler：404/422/500 均返回统一信封。"""

    @app.exception_handler(NotFoundError)
    async def _not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return _envelope(404, "资源不存在")

    @app.exception_handler(AppValidationError)
    async def _validation(request: Request, exc: AppValidationError) -> JSONResponse:
        return _envelope(422, "输入不合法")

    @app.exception_handler(RequestValidationError)
    async def _request_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _envelope(422, "输入不合法")

    @app.exception_handler(LLMError)
    async def _llm_error(request: Request, exc: LLMError) -> JSONResponse:
        return _envelope(500, "服务暂时不可用")
