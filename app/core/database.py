"""平台库（ecs_platform）数据库引擎与会话管理。"""
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import Settings


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


def create_engine(url: str) -> AsyncEngine:
    """根据连接串创建异步引擎。"""
    return create_async_engine(url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """根据引擎创建异步会话工厂。"""
    return async_sessionmaker(engine, expire_on_commit=False)


# 平台引擎与会话工厂采用懒加载，避免导入时因缺少 .env 而失败。
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """懒加载平台引擎（由 Settings.platform_database_url 构建，生产为 asyncmy）。"""
    global _engine
    if _engine is None:
        _engine = create_engine(Settings().platform_database_url)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """懒加载平台会话工厂。"""
    global _session_factory
    if _session_factory is None:
        _session_factory = create_session_factory(get_engine())
    return _session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：提供异步会话并确保最终关闭。"""
    factory = get_session_factory()
    async with factory() as session:
        yield session
