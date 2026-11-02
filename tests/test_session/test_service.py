"""会话层 CRUD 服务测试（SQLite 隔离）与标题截取纯函数测试。"""
import asyncio
import uuid

from app.session.service import SessionService, session_title_from_content


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


def test_title_short_content_kept_as_is():
    assert session_title_from_content("查订单") == "查订单"


def test_title_long_content_truncated_with_ellipsis():
    content = "iPhone 12 支持双卡双待吗，请问现在有货吗？"
    assert session_title_from_content(content) == content[:20] + "…"


def test_title_merges_newlines_and_whitespace():
    assert (
        session_title_from_content("  iPhone\n12   支持双卡双待  ")
        == "iPhone 12 支持双卡双待"
    )


def test_title_empty_content_falls_back_to_default():
    assert session_title_from_content("") == "新会话"
    assert session_title_from_content("   \n  ") == "新会话"


def test_title_custom_max_length():
    assert session_title_from_content("abcdefghij", max_length=5) == "abcde…"
