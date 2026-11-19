"""意图分类器 — 基于 LLM prompt 进行意图识别和槽位提取"""
import json

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from loguru import logger

from app.nlu.models import NLUResult
from app.config import settings


class IntentClassifier:
    """LLM 驱动的意图分类器

    通过构造包含所有已注册意图的系统 prompt，
    让 LLM 对用户输入进行意图变化识别和槽位提取。
    """

    def __init__(self, llm: ChatOpenAI | None = None):
        """初始化分类器

        Args:
            llm: 可选的 ChatOpenAI 实例，用于测试时注入 mock
        """
        self._llm = llm

    @property
    def llm(self) -> ChatOpenAI:
        """懒加载 LLM 实例"""
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                temperature=0.1,
            )
        return self._llm

    def _build_system_prompt(self, all_intents: list[dict] | None = None) -> str:
        """构造包含所有意图定义的系统 prompt"""
        intents = all_intents or []

        intent_descriptions = []
        for intent in intents:
            name = intent.get("name", "")
            desc_text = intent.get("description", "")
            required = intent.get("required_slots", [])
            optional = intent.get("optional_slots", [])

            desc = f"- {name}: {desc_text}"
            if required:
                slot_info = ", ".join(
                    f"{s['name']}({s['description']})" for s in required
                )
                desc += f"。必填槽位: {slot_info}"
            if optional:
                slot_info = ", ".join(
                    f"{s['name']}({s['description']})" for s in optional
                )
                desc += f"。可选槽位: {slot_info}"
            intent_descriptions.append(desc)

        return f"""你是一个电商智能客服系统的意图识别模块。你的任务是分析用户输入，判断意图变化并提取槽位。

## 可识别的意图

{chr(10).join(intent_descriptions)}

## 输出格式

请严格按以下 JSON 格式输出，不要输出其他内容：
```json
{{
    "action": "new",
    "target_intent": "意图名称",
    "confidence": 0.95,
    "slots_update": {{"槽位名": "槽位值"}}
}}
```

## action 说明

- **new**: 用户表达了新的意图需求，需要创建新意图
- **continue**: 用户在当前的活跃意图上下文中继续填槽位（默认值）
- **switch**: 用户想切回之前挂起的意图
- **cancel**: 用户表达取消当前意图（如"算了"、"不办了"）

## 规则

1. 如果用户输入是在当前活跃意图的上下文中填槽位 → action="continue"，target_intent 设为当前活跃意图名
2. 如果用户表达了新意图需求 → action="new"，target_intent 设为新意图名
3. 如果用户输入无法匹配任何已知意图 → target_intent="unknown"，action="new"
4. 如果用户要求转人工 → target_intent="transfer_human"，action="new"
5. 如果用户说"取消"、"不办了"、"算了" → action="cancel"，target_intent 设为当前活跃意图名
6. **槽位值识别**：如果用户输入是单个值（如订单号），且当前有活跃意图的缺失槽位，则将该值识别为缺失槽位的填充值，action="continue"，target_intent 保持与 active_intent 一致，不可重新分类为新意图
7. slots_update 只填本次提取到的值，不重复输出已填槽位
8. confidence 取值 0-1，表示你对分类结果的把握程度"""

    def _build_user_prompt(
        self,
        user_input: str,
        session_intents: dict | None = None,
        active_intent: str | None = None,
        messages: list[dict[str, str]] | None = None,
    ) -> str:
        """构造包含会话意图状态和对话历史的用户 prompt"""
        parts = []

        # 对话历史
        if messages:
            history_text = "\n".join(
                f"[{m['role']}]: {m['content']}" for m in messages
            )
            parts.append(f"对话历史:\n{history_text}")

        # 会话意图状态
        if session_intents:
            active_ctx = None
            other_intents = []
            for name, ctx in session_intents.items():
                if ctx.get("status") == "active":
                    active_ctx = (name, ctx)
                else:
                    other_intents.append((name, ctx))

            if active_ctx:
                name, ctx = active_ctx
                filled = ctx.get("slots", {})
                required = ctx.get("required_slots", [])
                missing = [s for s in required if s not in filled]
                parts.append(
                    f"当前活跃意图: {name}（状态: active，"
                    f"已填槽位: {json.dumps(filled, ensure_ascii=False)}，"
                    f"缺失槽位: {json.dumps(missing, ensure_ascii=False)}）"
                )

            if other_intents:
                other_lines = []
                for name, ctx in other_intents:
                    filled = ctx.get("slots", {})
                    required = ctx.get("required_slots", [])
                    missing = [s for s in required if s not in filled]
                    other_lines.append(
                        f"- {name}（状态: {ctx.get('status', '')}，"
                        f"已填槽位: {json.dumps(filled, ensure_ascii=False)}，"
                        f"缺失槽位: {json.dumps(missing, ensure_ascii=False)}）"
                    )
                parts.append("会话中其他意图:\n" + "\n".join(other_lines))
        elif active_intent:
            parts.append(f"当前活跃意图: {active_intent}")

        parts.append(f"用户输入: {user_input}")
        return "\n".join(parts)

    async def classify(
        self,
        user_input: str,
        all_intents: list[dict] | None = None,
        session_intents: dict | None = None,
        active_intent: str | None = None,
        messages: list[dict[str, str]] | None = None,
    ) -> NLUResult:
        """对用户输入进行意图变化识别和槽位提取

        Args:
            user_input: 用户原始输入
            all_intents: 所有可用意图定义（从 IntentController.build_all_intents()）
            session_intents: 会话中已产生的意图（含状态+槽位）
            active_intent: 当前活跃意图名
            messages: 对话历史，格式 [{"role": "user"|"assistant", "content": "..."}]

        Returns:
            NLUResult: 增量式意图变化
        """
        system_prompt = self._build_system_prompt(all_intents)
        user_prompt = self._build_user_prompt(
            user_input,
            session_intents or {},
            active_intent or "",
            messages or [],
        )

        llm_messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        try:
            structured_llm = self.llm.with_structured_output(
                schema=NLUResult,
                method="json_mode",
            )
            result = await structured_llm.ainvoke(llm_messages)
            logger.info(
                f"意图分类: action={result.action}, "
                f"target_intent={result.target_intent}, "
                f"confidence={result.confidence}, "
                f"slots_update={result.slots_update}"
            )
            return result
        except Exception as e:
            logger.error(f"意图分类失败: {e}")
            # 降级返回 unknown
            return NLUResult(
                action="new",
                target_intent="unknown",
                confidence=0.0,
                slots_update={},
            )
