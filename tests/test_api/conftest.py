"""API 测试共享 fixture：文件 SQLite 隔离 + 依赖覆盖。"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.router import api_router, register_exception_handlers
from app.core.database import Base, get_db


@pytest.fixture
async def client(tmp_path, monkeypatch):
    """基于文件 SQLite 的 ASGI 客户端，覆盖 get_db 与 chat 的 get_session_factory。

    用文件 SQLite 而非内存库，保证 chat 端点多次开/关会话时共享同一份数据。
    """
    import app.session.models  # noqa: F401  # 注册表到 metadata

    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    app = FastAPI()
    app.include_router(api_router)
    register_exception_handlers(app)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    # chat 端点用 get_session_factory 手动开/关会话，覆盖为同一个 SQLite 工厂
    monkeypatch.setattr("app.api.v1.chat.get_session_factory", lambda: factory)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    await engine.dispose()
