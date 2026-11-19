"""API v1 路由注册

汇总所有 v1 子路由，挂载到 /api/v1 前缀下。
"""
from fastapi import APIRouter

from app.api.v1.chat import router as chat_router
from app.api.v1.system import router as system_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(chat_router)
api_router.include_router(system_router)
