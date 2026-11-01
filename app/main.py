"""FastAPI 应用入口：装配意图注册、CORS、统一异常 handler 与健康检查。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

import app.business.ecommerce  # noqa: F401  # 触发电商意图注册（装配点）
from app.api.router import api_router, register_exception_handlers
from app.config import Settings
from app.core.exceptions import AppError
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化日志（读取 .env 的 log_level）。"""
    setup_logging(Settings().log_level)
    yield


app = FastAPI(lifespan=lifespan, title="电商智能客服系统")

# CORS：允许前端 dev 源
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
register_exception_handlers(app)


@app.exception_handler(AppError)
async def _app_error(request: Request, exc: AppError) -> JSONResponse:
    """应用异常兜底：未单独注册子类的 AppError 统一返回 500 信封并记录日志。"""
    logger.opt(exception=exc).error("未处理的应用异常")
    return JSONResponse(
        status_code=500,
        content={"success": False, "data": None, "error": "服务内部错误", "meta": None},
    )


@app.get("/healthz")
async def healthz() -> dict:
    """健康检查。"""
    return {"success": True, "data": "ok", "error": None, "meta": None}
