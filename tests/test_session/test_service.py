"""会话层 CRUD 服务测试（SQLite 隔离）。"""
import asyncio
import uuid

from app.session.service import SessionService


async def test_add_message_bumps_session_updated_at(session_factory):
    """加消息后会话的 updated_at 变大。"""
    async with session_factory() as session:
        service = SessionService(session)
        chat_session = await service.create_session("1001")
        first_updated = chat_session.updated_at

        await asyncio.sleep(0.01)
        await service.add_message(chat_session.id, "user", "hi")

        refreshed = await service.get_session(chat_session.id)
        assert refreshed.updated_at > first_updated


async def test_list_sessions_ordered_by_updated_at(session_factory):
    """两个会话按 updated_at 倒序，后更新的排前。"""
    async with session_factory() as session:
        service = SessionService(session)
        first = await service.create_session("1001")
        await asyncio.sleep(0.01)
        second = await service.create_session("1001")

        sessions = await service.list_sessions("1001")
        assert [s.id for s in sessions] == [second.id, first.id]


async def test_dialog_state_roundtrip(session_factory):
    """dialog_state 写读往返一致，不存在的会话读回 None。"""
    async with session_factory() as session:
        service = SessionService(session)
        chat_session = await service.create_session("1001")

        state = {"active_intent": "order_query", "slots": {}}
        await service.save_dialog_state(chat_session.id, state)

        assert await service.load_dialog_state(chat_session.id) == state
        assert await service.load_dialog_state(uuid.uuid4()) is None
