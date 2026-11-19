"""产品咨询意图处理器

使用 GraphRAG 在 Neo4j 知识图谱中检索商品信息，
回答用户关于商品价格、规格、库存、推荐等方面的问题。

检索结果先经 LLM 根据用户问题生成自然、易读的优雅答案，
再返回给前端。

槽位驱动模式：query 槽位由 NLU 层从用户输入中提取，
缺失时返回 ask_slot 引导用户输入问题。
"""
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from loguru import logger

from app.business.base import (
    BusinessContext,
    BusinessResult,
    IntentHandler,
)
from app.business.ecommerce.config import ecommerce_settings
from app.business.ecommerce.product_retrieval import GraphRAG, SearchResult
from app.config import settings

# ---------------------------------------------------------------------------
# 模块级 GraphRAG 单例 —— 避免每次请求都重新连接 Neo4j、加载 schema
# ---------------------------------------------------------------------------

_graphrag_singleton: GraphRAG | None = None


def _get_or_create_graphrag() -> GraphRAG:
    """获取或创建模块级 GraphRAG 单例"""
    global _graphrag_singleton
    if _graphrag_singleton is not None:
        return _graphrag_singleton

    graphrag = GraphRAG()
    neo4j_config = {
        "uri": ecommerce_settings.neo4j_uri,
        "user": ecommerce_settings.neo4j_user,
        "password": ecommerce_settings.neo4j_password,
    }
    graphrag.connect(neo4j_config)
    _graphrag_singleton = graphrag
    logger.info("GraphRAG 单例已初始化并连接到 Neo4j")
    return graphrag


def _reset_graphrag_singleton() -> None:
    """重置 GraphRAG 单例（仅用于测试清理）"""
    global _graphrag_singleton
    if _graphrag_singleton is not None:
        try:
            _graphrag_singleton.close()
        except Exception:
            pass
        _graphrag_singleton = None


# ---------------------------------------------------------------------------
# LLM 答案优化 Prompt
# ---------------------------------------------------------------------------

_ANSWER_SYSTEM_PROMPT = """你是一个专业的电商客服助手，负责根据知识图谱检索到的商品信息回答用户问题。

请遵循以下规则：
- 用自然、友好的中文回答用户，语气亲切但不啰嗦
- 严格基于提供的商品数据，不要编造数据中没有的信息
- 如果数据不足以完整回答用户问题，诚实说明并给出已有信息
- 回答简明扼要，重点突出用户关心的信息
- 如果涉及价格，保留两位小数并带上"元"单位
- 多条商品时用简洁的列表形式呈现，每条标注核心差异"""

_ANSWER_HUMAN_TEMPLATE = """用户问题：{question}

知识图谱中检索到的商品信息如下：
---
{raw_data}
---

请根据以上信息回答用户的问题。"""


# ---------------------------------------------------------------------------
# ProductInquiryHandler
# ---------------------------------------------------------------------------


class ProductInquiryHandler(IntentHandler):
    """产品咨询处理器

    将用户问题送入 GraphRAG 检索流水线（标签路由 → 节点检索 →
    Cypher 生成 → 验证校正 → 执行查询），检索结果经 LLM 优化为
    自然语言答案后返回给前端。

    支持通过构造函数注入 GraphRAG 和 LLM 实例用于测试。
    """

    def __init__(
        self,
        graphrag: GraphRAG | None = None,
        llm: ChatOpenAI | None = None,
    ):
        """初始化处理器

        Args:
            graphrag: 可选的 GraphRAG 实例，用于测试注入。
                      为 None 时使用模块级单例。
            llm: 可选的 LLM 实例，用于测试注入。
                 为 None 时从项目配置创建。
        """
        self._graphrag = graphrag
        self._llm = llm

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    async def handle(self, ctx: BusinessContext) -> BusinessResult:
        """执行产品咨询意图

        槽位检查：query 为用户原始问题，由 NLU 层从对话中提取。
        缺失时返回 ask_slot 引导用户输入。
        """
        query = str(ctx.slots.get("query", "")).strip()
        if not query:
            return BusinessResult.ask_slot(
                slot_to_fill="query",
                options=[],
                message="请问您想了解什么商品信息？",
            )

        return await self._search_and_answer(query)

    # ------------------------------------------------------------------
    # 检索 + LLM 优化
    # ------------------------------------------------------------------

    async def _search_and_answer(self, query: str) -> BusinessResult:
        """GraphRAG 检索 → LLM 生成优化答案"""
        graphrag = self._graphrag or _get_or_create_graphrag()

        try:
            results = await graphrag.search(query, top_k=5)

            if not results:
                return BusinessResult.completed(
                    message="抱歉，没有找到相关的商品信息，请尝试换个方式描述您的需求。",
                    results=[],
                    count=0,
                )

            # 组装原始数据供 LLM 优化
            raw_data = self._build_raw_data_text(results)
            answer = await self._generate_answer(query, raw_data)

            items = [
                {
                    "text": r.text,
                    "source": r.metadata.get("source", ""),
                    "score": r.score,
                }
                for r in results
            ]
            return BusinessResult.completed(
                message=answer,
                results=items,
                count=len(results),
            )

        except Exception as e:
            logger.error(f"产品咨询检索失败: {e}")
            return BusinessResult.error("查询商品信息时出现错误，请稍后重试")

    # ------------------------------------------------------------------
    # LLM 答案生成
    # ------------------------------------------------------------------

    async def _generate_answer(self, question: str, raw_data: str) -> str:
        """调用 LLM 根据用户问题和检索数据生成优化答案

        Args:
            question: 用户原始问题
            raw_data: 格式化后的原始检索数据

        Returns:
            LLM 生成的优化答案；失败时降级为原始数据拼接文本
        """
        try:
            llm = self._get_llm()
            messages = [
                SystemMessage(content=_ANSWER_SYSTEM_PROMPT),
                HumanMessage(
                    content=_ANSWER_HUMAN_TEMPLATE.format(
                        question=question,
                        raw_data=raw_data,
                    )
                ),
            ]
            response = await llm.ainvoke(messages)
            answer = response.content.strip()
            logger.info(f"LLM 答案生成成功，长度: {len(answer)} 字符")
            return answer
        except Exception as e:
            logger.warning(f"LLM 答案生成失败，降级为原始数据: {e}")
            return self._fallback_format(raw_data)

    def _get_llm(self) -> ChatOpenAI:
        """获取 LLM 实例（延迟创建，支持注入）"""
        if self._llm is not None:
            return self._llm
        return ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0.3,  # 较低温度保证准确性
        )

    # ------------------------------------------------------------------
    # 数据组装
    # ------------------------------------------------------------------

    @staticmethod
    def _build_raw_data_text(results: list[SearchResult]) -> str:
        """将检索结果组装为 LLM 可理解的原始数据文本"""
        parts: list[str] = []
        for i, r in enumerate(results, 1):
            source = r.metadata.get("source", "未知")
            parts.append(f"[{i}] 来源: {source}\n    {r.text}")
        return "\n\n".join(parts)

    @staticmethod
    def _fallback_format(raw_data: str) -> str:
        """LLM 失败时的降级展示"""
        lines = ["📦 为您找到以下相关商品信息：", "", raw_data]
        return "\n".join(lines)
