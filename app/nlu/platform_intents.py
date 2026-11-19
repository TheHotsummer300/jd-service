"""平台级意图定义 — 适用于所有业务线"""
from app.nlu.models import IntentDefinition

PLATFORM_INTENTS: list[IntentDefinition] = [
    IntentDefinition(
        name="unknown",
        description="用户输入无法匹配任何已知意图，或者表达混乱、语义不清、超出客服范围",
    ),
    IntentDefinition(
        name="transfer_human",
        description="用户明确要求转接人工客服、投诉、索要人工联系方式（电话/邮箱）、或者表达对AI回复的不满",
    ),
]
