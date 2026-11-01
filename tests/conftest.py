# 测试共享 fixture 与配置（后续任务按需扩展）
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base


@pytest.fixture
async def session_factory():
    """基于内存 SQLite 的异步会话工厂，测试前建表、测试后销毁。

    供会话层 / 服务层 / API 层测试复用，不依赖真实 MySQL。
    """
    import app.session.models  # noqa: F401  # 运行时导入，确保表注册到 metadata

    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
