"""DM 层 DialogState 定义

对话状态的核心数据结构，贯穿整个 LangGraph 图的执行流程。
"""
from typing import Any, TypedDict


class IntentContext(TypedDict):
    """意图上下文 — 会话中产生的每个意图的完整状态"""
    name: str                       # 意图名，如 "order_query"
    confidence: float               # 识别置信度 0-1
    status: str                     # "active" | "suspended" | "completed" | "cancelled"
    slots: dict[str, object]        # 该意图独立槽位（不再共享全局 slots）
    required_slots: list[str]       # 必填槽位名列表
    optional_slots: list[str]       # 可选槽位名列表


class DialogState(TypedDict):
    """对话状态

    LangGraph StateGraph 的状态字典。每个节点读取并返回部分字段的更新。

    字段说明：
    - session_id / user_id / user_input: 由 API 层在入口注入
    - messages: 对话历史，格式 [{"role": "user"|"assistant", "content": "..."}]
    - all_intents: 系统+业务线全部可用意图定义，供 NLU prompt 构造使用
    - intents: 会话中产生的意图注册表，key 为意图名，value 含 status + 独立 slots
    - active_intent: 当前活跃意图名，由 NLU 节点产出（冗余方便路由）
    - business_result: 业务节点执行结果（BusinessResult | None）
    - final_response: 最终要返回给用户的回复文本
    - should_fallback: 是否触发兜底流程
    """
    session_id: str
    user_id: str
    user_input: str
    messages: list[dict[str, str]]
    all_intents: list[dict]              # 系统+业务线全部意图定义
    intents: dict[str, IntentContext]    # 会话中产生的意图（含 status + 独立 slots）
    active_intent: str                   # 当前活跃意图名
    business_result: object              # BusinessResult | None
    final_response: str
    should_fallback: bool
