"""DM 层 LangGraph 状态机组装。"""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.dm.nodes import (business_node, entry_node, fallback_node, nlu_node,
                          response_node, slot_filling_node)
from app.dm.router import route_after_nlu, route_after_slot_filling
from app.dm.state import DialogState


def build_graph() -> CompiledStateGraph:
    """每次调用新建 StateGraph，避免跨测试共享状态。"""
    graph = StateGraph(DialogState)

    graph.add_node("entry", entry_node)
    graph.add_node("nlu", nlu_node)
    graph.add_node("slot_filling", slot_filling_node)
    graph.add_node("business", business_node)
    graph.add_node("response", response_node)
    graph.add_node("fallback", fallback_node)

    graph.add_edge(START, "entry")
    graph.add_edge("entry", "nlu")
    graph.add_conditional_edges(
        "nlu",
        route_after_nlu,
        {"fallback": "fallback", "slot_filling": "slot_filling"},
    )
    graph.add_conditional_edges(
        "slot_filling",
        route_after_slot_filling,
        {"business": "business", "end": END},
    )
    graph.add_edge("business", "response")
    graph.add_edge("response", END)
    graph.add_edge("fallback", END)

    return graph.compile()
