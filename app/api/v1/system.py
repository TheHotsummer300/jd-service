"""系统信息 API 端点

提供意图列表、系统状态等查询接口。
"""
from fastapi import APIRouter

from app.core.response import success_response
from app.nlu.registry import IntentRegistry

router = APIRouter(prefix="/system", tags=["系统信息"])


@router.get("/intents")
async def list_intents():
    """获取所有已注册的意图列表

    返回平台意图和所有已注册业务线意图的摘要信息，
    方便前端动态展示系统支持的能力。
    """
    intents = IntentRegistry.get_all_intents()
    data = [
        {
            "name": intent.name,
            "description": intent.description,
            "required_slots": [
                {"name": slot.name, "description": slot.description, "ask_prompt": slot.ask_prompt}
                for slot in intent.required_slots
            ],
        }
        for intent in intents
    ]
    return success_response(data=data)
