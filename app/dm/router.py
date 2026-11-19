"""DM 层条件路由

提供给 LangGraph add_conditional_edges 使用的路由函数。
"""


def is_platform_intent(state: dict) -> bool:
    """判断当前活跃意图是否为平台意图或空（兜底）

    空 active_intent 表示无活跃意图，走 fallback 等 NLU 识别新意图。
    """
    active = state.get("active_intent", "")
    if not active:
        return True
    return active in ("unknown", "transfer_human")
