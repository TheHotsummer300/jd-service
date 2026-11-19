"""FastAPI 应用入口

启动时自动发现并注册所有业务线意图，配置统一异常处理和健康检查。
"""
import importlib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

from app.api.v1.router import api_router
from app.core.exceptions import AppException
from app.core.response import error_response
from app.nlu.registry import IntentRegistry


def _discover_business_lines() -> None:
    """自动发现并注册 business/ 下所有业务线

    遍历 app/business/ 目录下的所有子包，导入其 intents 模块，
    读取 INTENTS 属性（list[IntentDefinition]），注册到 IntentRegistry。

    约定：
    - 每个业务线是 app/business/ 下的一个子包
    - 子包内必须有 intents.py 模块
    - intents.py 必须导出 INTENTS: list[IntentDefinition]
    - 每个 IntentDefinition.handler 绑定对应的处理器类（None 表示暂未实现）
    """
    import app.business as business_pkg

    business_dir = Path(business_pkg.__path__[0])
    for entry in sorted(business_dir.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("_") or entry.name.startswith("__"):
            continue

        pkg_name = entry.name
        try:
            intents_module = importlib.import_module(
                f"app.business.{pkg_name}.intents"
            )
        except ImportError as e:
            logger.warning(
                f"跳过业务线 '{pkg_name}'：无法导入 intents 模块 ({e})"
            )
            continue

        if not hasattr(intents_module, "INTENTS"):
            logger.warning(
                f"跳过业务线 '{pkg_name}'：intents 模块未导出 INTENTS 属性"
            )
            continue

        intents = intents_module.INTENTS
        IntentRegistry.register_business(pkg_name, intents)
        logger.info(
            f"已注册业务线 '{pkg_name}'，意图: "
            f"{[i.name for i in intents]}"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时：自动发现并注册所有业务线意图
    logger.info("正在启动应用…")
    _discover_business_lines()
    all_intents = IntentRegistry.get_all_intents()
    logger.info(f"全部已注册意图: {[i.name for i in all_intents]}")
    yield
    # 关闭时清理
    logger.info("应用关闭")


app = FastAPI(
    title="电商智能客服系统",
    description="基于 LangGraph + FastAPI 的可扩展智能客服",
    version="0.1.0",
    lifespan=lifespan,
)

# 注册路由
app.include_router(api_router)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """统一业务异常处理"""
    logger.warning(f"业务异常 [{exc.status_code}]: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(exc.message),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局未知异常处理 — 不泄露内部细节"""
    logger.exception(f"未知异常: {exc}")
    return JSONResponse(
        status_code=500,
        content=error_response("系统繁忙，请稍后重试"),
    )


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}
