from sqlalchemy import text

from app.core.database import create_engine, create_session_factory


async def test_engine_uses_sqlite_for_tests():
    """用 SQLite 连接串构建引擎并执行 SELECT 1，验证异步引擎可用。"""
    engine = create_engine("sqlite+aiosqlite://")
    factory = create_session_factory(engine)
    async with factory() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1
    await engine.dispose()
