"""意图注册中心 — 管理所有业务线的意图"""
from app.nlu.models import IntentDefinition
from app.nlu.platform_intents import PLATFORM_INTENTS


class IntentRegistry:
    """意图注册中心（单例模式）

    各业务线通过 register_business() 注册自己的意图。
    NLU 层通过 get_all_intents() 获取所有已注册意图。
    """

    _instance: "IntentRegistry | None" = None
    _business_intents: dict[str, list[IntentDefinition]] = {}

    def __new__(cls) -> "IntentRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register_business(
        cls,
        business_name: str,
        intents: list[IntentDefinition],
    ) -> None:
        """注册一个业务线的意图"""
        cls._business_intents[business_name] = intents

    @classmethod
    def get_all_intents(cls) -> list[IntentDefinition]:
        """获取所有意图（平台意图 + 所有已注册业务意图）"""
        all_intents = list(PLATFORM_INTENTS)
        for intents in cls._business_intents.values():
            all_intents.extend(intents)
        return all_intents

    @classmethod
    def get_intent_by_name(cls, name: str) -> IntentDefinition | None:
        """按名称查找意图"""
        for intent in cls.get_all_intents():
            if intent.name == name:
                return intent
        return None

    @classmethod
    def get_required_slot_names(cls, intent_name: str) -> list[str]:
        """获取某个意图的所有必填槽位名称"""
        intent = cls.get_intent_by_name(intent_name)
        if intent is None:
            return []
        return [s.name for s in intent.required_slots]

    @classmethod
    def get_handler(cls, intent_name: str) -> type | None:
        """按意图名获取对应的 Handler 类

        Handler 类由业务线在 IntentDefinition.handler 中绑定，
        平台代码不直接导入任何业务线 Handler。
        """
        intent = cls.get_intent_by_name(intent_name)
        if intent is None:
            return None
        return intent.handler

    @classmethod
    def clear(cls) -> None:
        """清空注册中心（用于测试）"""
        cls._business_intents = {}
