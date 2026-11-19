"""LangGraph 对话图构建

组装 DM 层的全部节点和路由，编译为可执行的 StateGraph。
"""
from langgraph.graph import StateGraph, END

from app.dm.state import DialogState
from app.dm.router import is_platform_intent
from app.dm.nodes.nlu_node import nlu_node
from app.dm.nodes.business_node import business_node
from app.dm.nodes.response_node import response_node
from app.dm.nodes.fallback_node import fallback_node


def build_dialog_graph() -> StateGraph:
    """构建对话状态图

    节点流程：
    ```
    entry → nlu → [条件路由]
      ├─ 平台意图 (unknown/transfer_human) → fallback → response → END
      └─ 业务意图 → business → response → END
    ```

    注意：
    - 槽位填充由业务 Handler 内部通过 BusinessResult.ask_slot() 处理，
      DM 图不需要独立的 slot_filling 节点。
    - NLU 节点将缺失槽位放入 state.missing_slots，供业务 Handler 参考。
    """
    workflow = StateGraph(DialogState)

    # ── 添加节点 ──────────────────────────────────────
    workflow.add_node("nlu", nlu_node)
    workflow.add_node("business", business_node)
    workflow.add_node("response", response_node)
    workflow.add_node("fallback", fallback_node)

    # ── 设置入口 ──────────────────────────────────────
    workflow.set_entry_point("nlu")

    # ── NLU 后的条件路由 ──────────────────────────────
    # 平台意图（unknown/transfer_human）→ fallback
    # 业务意图 → business
    workflow.add_conditional_edges(
        "nlu",
        lambda state: "fallback" if is_platform_intent(state) else "business",
        {
            "fallback": "fallback",
            "business": "business",
        },
    )

    # ── business / fallback 都走向 response ───────────
    workflow.add_edge("business", "response")
    workflow.add_edge("fallback", "response")
    workflow.add_edge("response", END)

    return workflow.compile()
