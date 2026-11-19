"""业务层基础抽象

定义业务处理的统一接口：上下文、结果、选项结构和意图处理器抽象基类。
"""
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field


class BusinessContext(BaseModel):
    """业务处理上下文

    封装一次意图处理所需的全部上下文信息。
    """

    session_id: str = Field(..., description="会话 ID")
    user_id: str = Field(..., description="用户 ID")
    intent: str = Field(..., description="当前意图名")
    slots: dict[str, object] = Field(
        default_factory=dict,
        description="已填充的槽位值",
    )


class BusinessResult(BaseModel):
    """业务处理结果

    意图处理器执行后返回的统一结果模型。
    支持三种形态：ask_slot（需要用户选择）、completed（执行完成）、错误。
    """

    success: bool = Field(..., description="是否执行成功")
    data: object = Field(
        default=None,
        description="业务数据，传给 NLG 模板渲染",
    )
    error_message: str = Field(
        default="",
        description="错误描述",
    )

    @property
    def message(self) -> str:
        """获取面向用户的消息文本

        优先从 data["message"] 取（ask_slot / completed 情况），
        否则回退到 error_message（error 情况）。
        """
        if isinstance(self.data, dict) and "message" in self.data:
            return str(self.data["message"])
        return self.error_message or ""

    # ── 统一工厂方法 ──────────────────────────────────

    @classmethod
    def ask_slot(
        cls,
        slot_to_fill: str,
        options: list["OptionItem"],
        message: str = "",
    ) -> "BusinessResult":
        """需要用户选择一个槽位值时使用。

        Args:
            slot_to_fill: 需要填充的槽位名称
            options: 可选项列表，前端据此渲染按钮
            message: 提示文字
        """
        return cls(
            success=True,
            data={
                "action": "ask_slot",
                "message": message,
                "slot_to_fill": slot_to_fill,
                "options": [o.model_dump() for o in options],
            },
        )

    @classmethod
    def completed(cls, message: str, **extra) -> "BusinessResult":
        """业务处理完成。extra 中的键值会合并到 data 中。

        Args:
            message: 展示给用户的结果消息
            **extra: 附加的业务数据（如 order_id、new_status 等）
        """
        return cls(
            success=True,
            data={
                "action": "completed",
                "message": message,
                **extra,
            },
        )

    @classmethod
    def error(cls, message: str) -> "BusinessResult":
        """业务处理失败。"""
        return cls(success=False, error_message=message)


class OptionItem(BaseModel):
    """选项条目 — 用于需要用户从多个选项中选择一个的场景。

    前端统一使用此结构渲染按钮列表：
    1. 取 data.options 数组
    2. 对每个 option 取 label 作为按钮文字
    3. 取 value 作为点击后发送给后端的槽位值
    4. 取 disabled 判断是否置灰
    """

    label: str = Field(..., description="展示给用户的文字")
    value: str = Field(..., description="回传给后端的槽位值")
    disabled: bool = Field(default=False, description="是否不可选")


class IntentHandler(ABC):
    """意图处理器抽象基类

    每个业务意图对应一个处理器。处理器内部可以自行查询业务数据库
    来补充槽位、执行业务逻辑。
    """

    @abstractmethod
    async def handle(self, ctx: BusinessContext) -> BusinessResult:
        """执行意图逻辑，返回业务结果"""
        ...
