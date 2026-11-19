"""意图生命周期管理器 — 封装意图的创建、挂起、恢复、取消、完成逻辑"""
from loguru import logger

from app.business.base import BusinessContext
from app.nlu.registry import IntentRegistry


class IntentController:
    """意图生命周期管理器

    纯逻辑类，不持有状态。所有操作基于传入的 state 返回更新字典。
    """

    # ── 核心决策 ──────────────────────────────────────────

    @staticmethod
    def decide(state: dict, nlu_result) -> dict:
        """根据 NLU 输出更新意图容器和 active_intent

        Args:
            state: 当前 DialogState（部分字段）
            nlu_result: NLUResult，含 action / target_intent / slots_update

        Returns:
            包含 intents 和 active_intent 的更新字典
        """
        action = nlu_result.action
        target = nlu_result.target_intent
        intents = dict(state.get("intents", {}))
        active_intent = state.get("active_intent", "")

        if action == "continue":
            # 防御：如果 target 与 active_intent 不匹配，降级为 new
            if active_intent and target and target != active_intent:
                logger.warning(
                    f"continue 目标 {target} 与活跃意图 {active_intent} 不匹配，降级为 new"
                )
                action = "new"

        if action == "continue":
            if target in intents:
                _merge_slots(intents, target, nlu_result.slots_update)
            active_intent = target

        elif action == "new":
            # 同名去重
            if target in intents:
                old_status = intents[target].get("status", "")
                if old_status in ("completed", "cancelled"):
                    # 覆盖旧意图
                    intents[target] = _create_intent(target, nlu_result)
                else:
                    # 已存在活跃/挂起的同名意图 → 直接激活
                    intents[target]["status"] = "active"
            else:
                # 挂起当前活跃意图
                _suspend_active(intents)
                # 创建新意图
                intents[target] = _create_intent(target, nlu_result)
            active_intent = target

        elif action == "switch":
            # 挂起当前活跃意图
            _suspend_active(intents)
            # 激活目标意图
            if target in intents:
                intents[target]["status"] = "active"
            else:
                # 目标不存在 → 创建
                intents[target] = _create_intent(target, nlu_result)
            active_intent = target

        elif action == "cancel":
            if target in intents:
                intents[target]["status"] = "cancelled"
            active_intent = _restore_suspended(intents)

        elif action == "complete":
            if target in intents:
                intents[target]["status"] = "completed"
            active_intent = _restore_suspended(intents)

        return {"intents": intents, "active_intent": active_intent}

    # ── 查询 ──────────────────────────────────────────────

    @staticmethod
    def get_active_context(state: dict) -> BusinessContext:
        """从活跃意图构建业务节点所需的 BusinessContext"""
        active_intent = state.get("active_intent", "")
        intents = state.get("intents", {})
        slots = {}

        if active_intent and active_intent in intents:
            slots = intents[active_intent].get("slots", {})

        return BusinessContext(
            session_id=state.get("session_id", ""),
            user_id=state.get("user_id", ""),
            intent=active_intent,
            slots=slots,
        )

    @staticmethod
    def get_active_slots(state: dict) -> dict[str, object]:
        """获取当前活跃意图的槽位"""
        active_intent = state.get("active_intent", "")
        intents = state.get("intents", {})
        if active_intent and active_intent in intents:
            return dict(intents[active_intent].get("slots", {}))
        return {}

    @staticmethod
    def get_missing_slots(state: dict) -> list[str]:
        """动态计算活跃意图的缺失必填槽位"""
        active_intent = state.get("active_intent", "")
        intents = state.get("intents", {})
        if not active_intent or active_intent not in intents:
            return []
        intent_ctx = intents[active_intent]
        required = intent_ctx.get("required_slots", [])
        filled = intent_ctx.get("slots", {}).keys()
        return [s for s in required if s not in filled]

    @staticmethod
    def find_active(intents: dict) -> str:
        """从意图容器中找到 status="active" 的意图名，无则返回 "" """
        for name, ctx in intents.items():
            if ctx.get("status") == "active":
                return name
        return ""

    # ── 序列化 ────────────────────────────────────────────

    @staticmethod
    def to_snapshot(intents: dict) -> dict:
        """将意图容器序列化为纯 dict

        不保存 completed 和 cancelled 的意图（从容器中删除的效果）。
        """
        snapshot = {}
        for name, ctx in intents.items():
            status = ctx.get("status", "")
            if status in ("completed", "cancelled"):
                continue
            snapshot[name] = dict(ctx)
        return snapshot

    @staticmethod
    def from_snapshot(data: dict | None) -> dict[str, dict]:
        """从 DB 快照恢复意图容器"""
        if not data:
            return {}
        result = {}
        for name, ctx in data.items():
            result[name] = {
                "name": ctx.get("name", name),
                "confidence": ctx.get("confidence", 0.0),
                "status": ctx.get("status", "active"),
                "slots": dict(ctx.get("slots", {})),
                "required_slots": list(ctx.get("required_slots", [])),
                "optional_slots": list(ctx.get("optional_slots", [])),
            }
        return result

    # ── 辅助 ──────────────────────────────────────────────

    @staticmethod
    def build_all_intents() -> list[dict]:
        """从 IntentRegistry 构建 all_intents 列表

        每个条目: {name, description, required_slots: [{name, description}],
                    optional_slots: [{name, description}]}
        """
        intents = IntentRegistry.get_all_intents()
        result = []
        for intent in intents:
            result.append({
                "name": intent.name,
                "description": intent.description,
                "required_slots": [
                    {"name": s.name, "description": s.description}
                    for s in intent.required_slots
                ],
                "optional_slots": [
                    {"name": s.name, "description": s.description}
                    for s in intent.optional_slots
                ],
            })
        return result


# ── 模块级辅助函数 ──────────────────────────────────────────

def _merge_slots(intents: dict, target: str, slots_update: dict[str, object]) -> None:
    """将增量槽位合并到目标意图的 slots 中"""
    if target in intents and slots_update:
        existing = dict(intents[target].get("slots", {}))
        existing.update(slots_update)
        intents[target]["slots"] = existing


def _suspend_active(intents: dict) -> None:
    """将所有 active 状态的意图改为 suspended"""
    for ctx in intents.values():
        if ctx.get("status") == "active":
            ctx["status"] = "suspended"


def _create_intent(name: str, nlu_result) -> dict:
    """从 IntentRegistry 获取意图定义，创建新的 IntentContext"""
    intent_def = IntentRegistry.get_intent_by_name(name)
    required_slots = []
    optional_slots = []
    if intent_def:
        required_slots = [s.name for s in intent_def.required_slots]
        optional_slots = [s.name for s in intent_def.optional_slots]

    return {
        "name": name,
        "confidence": nlu_result.confidence,
        "status": "active",
        "slots": dict(nlu_result.slots_update),
        "required_slots": required_slots,
        "optional_slots": optional_slots,
    }


def _restore_suspended(intents: dict) -> str:
    """恢复最近挂起的意图（LIFO），返回恢复后的 active 意图名

    通过找出所有 suspended 意图，按它们在容器中的出现顺序（即创建顺序），
    取最后一个作为"最近挂起"的意图来恢复。
    由于 Python 3.7+ dict 保持插入顺序，suspended 列表中最后的元素即为"最近挂起"。
    """
    suspended_names = [
        name for name, ctx in intents.items()
        if ctx.get("status") == "suspended"
    ]
    if suspended_names:
        target = suspended_names[-1]
        intents[target]["status"] = "active"
        return target
    return ""
