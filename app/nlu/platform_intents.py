"""平台级意图定义，适用于所有业务线。"""

PLATFORM_INTENTS = frozenset({"unknown", "transfer_human"})

# 平台意图的中文描述，供意图分类器拼入 prompt，帮助 LLM 区分语义
PLATFORM_INTENT_DESCRIPTIONS = {
    "unknown": "无法识别意图",
    "transfer_human": "用户要求转接人工客服",
}
