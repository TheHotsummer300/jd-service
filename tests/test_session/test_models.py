"""会话层 ORM 模型测试（SQLite 隔离）。"""
import uuid

from app.session.models import ChatSession, Message


async def test_create_session_and_message(session_factory):
    """插入会话与消息，断言 UUID 主键、默认标题、可空字段与外键关联。"""
    async with session_factory() as session:
        # 插入会话
        chat_session = ChatSession(user_id="1001")
        session.add(chat_session)
        await session.flush()

        assert isinstance(chat_session.id, uuid.UUID)
        assert chat_session.title == "新会话"
        assert chat_session.dialog_state is None

        # 插入消息并关联到会话
        message = Message(session_id=chat_session.id, role="user", content="hi")
        session.add(message)
        await session.flush()

        assert message.session_id == chat_session.id
        assert message.intent is None
        assert message.slots is None
