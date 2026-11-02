"""
实现思路：
    先确定查询知识图谱的入口节点，根据入口节点和用户意图生成Cypher语句进行查询
    1.LLM根据用户输入，确定需要的入口节点类型以及实体
    2.根据提供的入口节点类型和实体，使用混合检索获取候选入口节点信息
    3.LLM根据用户输入和入口节点信息生成Cypher查询语句
    4.LLM验证生成的Cypher语法、逻辑是否正确，罗列出错误信息
    5.LLM根据用户输入、入口节点、错误信息、先前Cypher语句来生成更正后的Cypher语句
    6.执行Cypher查询，返回查询结果
工作流程:
    用户提问：用户输入查询问题
    标签路由：LLM识别问题涉及的节点类型和实体
    节点检索：使用混合检索找到候选入口节点
    Cypher生成：LLM根据入口节点和问题生成Cypher查询语句
    语句验证：验证Cypher语句的正确性
    语句校正：如有错误则进行校正
    执行查询：在Neo4j中执行Cypher查询
    返回结果：将查询结果返回给用户
"""

import asyncio
import json
import re
from dataclasses import dataclass, field

import jieba
from dashscope import TextEmbedding
from langchain_core.embeddings import Embeddings
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain_openai import ChatOpenAI
from loguru import logger
from neo4j import GraphDatabase
from neo4j.exceptions import CypherSyntaxError
from neo4j_graphrag.retrievers import HybridRetriever
from neo4j_graphrag.retrievers.text2cypher import extract_cypher
from pydantic import BaseModel, Field

from app.business.ecommerce.config import ecommerce_settings
from app.llm.client import get_llm


# ---------------------------------------------------------------------------
# SearchResult —— GraphRAG 检索结果
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    """GraphRAG 检索结果"""
    text: str = ""
    metadata: dict[str, object] = field(default_factory=dict)
    score: float = 0.0


# ---------------------------------------------------------------------------
# Pydantic 数据模型
# ---------------------------------------------------------------------------

class RouteItem(BaseModel):
    """路由项：标签 + 实体"""
    label: str = Field(..., description='节点类型，比如"SKU"')
    entity: str = Field(..., description="实体文本")


class RouteOutput(BaseModel):
    """路由输出：路由项列表"""
    outputs: list[RouteItem]


# ---------------------------------------------------------------------------
# 关键词提取
# ---------------------------------------------------------------------------

def _keyword_variants(query: str) -> list[str]:
    """Extract compact product fact keywords for SKU text fallback search."""
    if not query:
        return []

    stop_words = (
        "帮我",
        "查找",
        "满足",
        "以下",
        "条件",
        "商品",
        "产品",
        "名称",
        "产品名称",
        "用户",
        "需求",
        "用户需求",
        "分类",
        "产品分类",
        "请问",
        "是否",
        "支持",
        "有",
        "吗",
        "么",
        "?",
        "？",
        " ",
    )

    variants: list[str] = []
    for word in jieba.lcut(query):
        word = word.strip()
        if len(word) >= 2 and word not in stop_words:
            variants.append(word)

    deduped: list[str] = []
    for variant in variants:
        if variant and variant not in deduped:
            deduped.append(variant)
    return deduped


# ---------------------------------------------------------------------------
# DashScopeEmbedding —— 基于阿里云 text-embedding-v4 的嵌入实现
# ---------------------------------------------------------------------------

class DashScopeEmbedding(Embeddings):
    """通过 DashScope SDK 调用 text-embedding-v4 模型

    使用阿里云 dashscope 库的 TextEmbedding API，
    不依赖 OpenAI 兼容接口。
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        dimensions: int = 1024,
    ):
        self._api_key = api_key or ecommerce_settings.dashscope_api_key
        self._model = model or ecommerce_settings.embedding_model
        self._dimensions = dimensions or ecommerce_settings.embedding_dimensions

    def embed_query(self, text: str) -> list[float]:
        """将单个查询文本转为向量"""
        return self.embed_documents([text])[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量将文本转为向量

        dashscope TextEmbedding 支持一次传入字符串列表，
        底层自动分批处理，无需手动分批。
        """
        resp = TextEmbedding.call(
            model=self._model,
            input=texts,
            api_key=self._api_key,
            dimension=self._dimensions,
        )

        if resp.status_code != 200:
            raise RuntimeError(
                f"DashScope embedding API 返回错误 "
                f"(status={resp.status_code}): {resp.message}"
            )

        # 按 index 排序后提取 embedding
        sorted_items = sorted(
            resp.output.get("embeddings", []),
            key=lambda item: item.get("text_index", 0),
        )
        return [item["embedding"] for item in sorted_items]


# ---------------------------------------------------------------------------
# GraphRAG —— 核心检索类
# ---------------------------------------------------------------------------

class GraphRAG:
    """基于 Neo4j 知识图谱的 GraphRAG 检索系统

    使用 ChatOpenAI（系统 LLM 配置）生成 Cypher，通过阿里云
    text-embedding-v4 做向量化检索。
    """

    def __init__(self):
        self.driver = None
        self.embeddings: DashScopeEmbedding | None = None
        self.llm: ChatOpenAI | None = None
        self.neo4j_schema: str = ""
        self.cypher_corrector = None

        # ---- 入口节点可选标签（仅商品相关节点，不含 User） ----
        self.optional_label = (
            '- Category1:   一级分类，如"食品饮料"、"家用电器"、"手机"\n'
            '- Category2:   二级分类，如"大家电"、"香水彩妆"\n'
            '- Category3:   三级分类，如"手机"、"香水"、"笔记本"\n'
            '- Trademark:   品牌，如"华为"、"索芙特"、"金沙河"\n'
            '- SPU:         商品名称，如"华为Mate 40 pro"\n'
            '- SKU:         单品名称，如"联想(Lenovo) 拯救者Y9000P 2022 16英寸游戏笔记本电脑 i9-12900H RTX3070Ti 钛晶灰"\n'
            '- Attr:        商品属性值，如"70英寸"、"蓝色"、"非有机食品"'
        )

        # ---- Prompt 模板 ----
        # 注意：JSON 示例中的花括号需写成 {{ 和 }} 转义，避免 str.format() 解析错误
        self.route_label_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(
                "你是一个智能检索路由Agent。\n"
                "现在根据用户输入判断最可能需要的一个或多个标签以及每个标签对应的实体，"
                "作为后续Neo4j查询的入口节点。\n"
                "仅关注商品相关的节点类型（分类、品牌、SPU、SKU、属性值），不要加入用户相关节点。\n"
                "严格输出JSON对象，格式如下（不要输出其他内容）：\n"
                '{{"outputs": [{{"label": "SPU", "entity": "iPhone 16 Pro"}}]}}\n'
                "可选节点类型:\n{optional_label}"
            ),
            HumanMessagePromptTemplate.from_template("{query}"),
        ])

        self.generate_cypher_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(
                "你是一个Cypher专家，正在根据入口节点信息和用户输入，"
                "参照schema生成准确无误的Cypher查询语句。\n"
                "**注意：查询结果中不可以包含嵌入向量等多余属性**\n"
                "仅返回Cypher语句。\n"
                "schema:\n{schema}"
            ),
            HumanMessagePromptTemplate.from_template(
                "入口节点:\n{entry_nodes}\n\n用户输入:\n{query}\n\nCypher语句:"
            ),
        ])

        self.validate_cypher_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(
                "你是一位Cypher专家，正在审查一位初级开发人员编写的Cypher语句。"
                "你需要根据schema和用户输入，检查如下内容：\n"
                "* Cypher语句中是否有任何语法错误？\n"
                "* Cypher语句中的关系方向是否符合schema中的定义？\n"
                "* Cypher语句中是否漏定义了变量或使用了未定义的变量？\n"
                "* Cypher语句检索出的内容能否用于回答用户的问题？\n"
                "以严格列表格式输出错误信息，比如'[\"错误1\", \"错误2\"]'，"
                "始终解释schema与Cypher语句之间的差异。\n"
                "如果确认没有问题，返回空内容即可。\n"
                "schema:\n{schema}"
            ),
            HumanMessagePromptTemplate.from_template(
                "入口节点:\n{entry_nodes}\n\n"
                "用户输入:\n{query}\n\n"
                "待验证的Cypher语句:\n{cypher}"
            ),
        ])

        self.correct_cypher_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(
                "你是一位Cypher专家，正在审查一位初级开发人员编写的Cypher语句。"
                "你需要根据schema以及提供的错误信息更正Cypher语句。\n"
                "仅返回Cypher语句。\n"
                "schema:\n{schema}"
            ),
            HumanMessagePromptTemplate.from_template(
                "入口节点:\n{entry_nodes}\n\n"
                "用户输入:\n{query}\n\n"
                "错误信息:\n{errors}\n\n"
                "待更正的Cypher语句:\n{cypher}\n\n"
                "更正后的Cypher语句:"
            ),
        ])

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------

    def _init_embeddings(self):
        """初始化嵌入模型（延迟加载）"""
        if self.embeddings is not None:
            return
        self.embeddings = DashScopeEmbedding()
        logger.info("嵌入模型已加载: text-embedding-v4 (1024 维)")

    def _init_llm(self):
        """初始化 LLM（复用项目 LLM 单例，Cypher 生成需要确定性输出）"""
        if self.llm is not None:
            return
        self.llm = get_llm(temperature=0.0)
        logger.info(f"GraphRAG LLM 已初始化: model={self.llm.model_name}")

    # ------------------------------------------------------------------
    # 连接
    # ------------------------------------------------------------------

    def connect(self, config: dict[str, object] | None = None) -> None:
        """连接检索系统：连接到Neo4j数据库并初始化相关组件"""
        config = config or {}

        # 1、创建Neo4j驱动程序
        neo4j_url = config.get("uri") or config.get("neo4j_url", "bolt://localhost:7687")
        neo4j_user = config.get("user", "neo4j")
        neo4j_password = config.get("password", "")
        neo4j_auth = (neo4j_user, neo4j_password)
        self.driver = GraphDatabase.driver(neo4j_url, auth=neo4j_auth)

        # 2、获取图数据库 schema（依赖 APOC 插件，docker-compose 已挂载 apoc-core.jar）
        from langchain_neo4j import Neo4jGraph
        from langchain_neo4j.chains.graph_qa.cypher_utils import CypherQueryCorrector, Schema

        neo4j_graph = Neo4jGraph(
            neo4j_url,
            neo4j_auth[0],
            neo4j_auth[1],
            enhanced_schema=True,
        )
        self.neo4j_schema = neo4j_graph.schema
        corrector_schema = [
            Schema(el["start"], el["type"], el["end"])
            for el in neo4j_graph.structured_schema.get("relationships")
        ]

        # 3、初始化 Cypher查询校正器
        self.cypher_corrector = CypherQueryCorrector(corrector_schema)

        # 4、初始化 LLM（复用系统全局 LLM 配置）
        self._init_llm()

        # 5、初始化嵌入模型
        self._init_embeddings()

        logger.info(f"GraphRAG 已连接到 Neo4j: {neo4j_url}")

    # ------------------------------------------------------------------
    # JSON 提取
    # ------------------------------------------------------------------

    def _extract_json_from_text(self, text: str) -> str:
        """从文本中提取 JSON 部分。

        处理 LLM 输出可能包含的额外内容（如思考过程 <think>...</think>、
        markdown 代码块等）。
        """
        if not text:
            return "[]"

        text = text.strip()

        # 1. 移除思考模式的 <think>...</think> 标签内容
        text = re.sub(r'<think>[\s\S]*?</think>', '', text).strip()

        # 2. 尝试直接解析
        if text.startswith("[") or text.startswith("{"):
            return text

        # 3. 尝试从 markdown 代码块中提取
        code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if code_block_match:
            return code_block_match.group(1).strip()

        # 4. 尝试找到 JSON 数组或对象
        json_match = re.search(r'(\[[\s\S]*\]|\{[\s\S]*\})', text)
        if json_match:
            return json_match.group(1)

        return "[]"

    def _parse_route_json(self, json_str: str) -> list[RouteItem]:
        """解析 LLM 返回的路由 JSON，兼容两种格式。

        优先尝试 RouteOutput 的 {"outputs": [...]} 格式（structured output 的标准格式和
        新 prompt 推荐格式），失败时回退到裸数组 [...] 格式。
        """
        data = json.loads(json_str)
        if isinstance(data, dict) and "outputs" in data:
            return [RouteItem(**item) for item in data["outputs"]]
        if isinstance(data, list):
            return [RouteItem(**item) for item in data]
        logger.warning(f"无法解析路由JSON，返回空列表: {json_str[:200]}")
        return []

    # ------------------------------------------------------------------
    # 路由标签识别
    # ------------------------------------------------------------------

    async def route_label(self, query: str) -> list[RouteItem]:
        """识别标签，抽取实体 —— 使用LLM识别用户查询中涉及的节点类型和实体"""

        prompt = self.route_label_prompt.format_prompt(
            optional_label=self.optional_label, query=query
        )

        try:
            llm_output = await self.llm.with_structured_output(
                RouteOutput, method="json_mode"
            ).ainvoke(prompt)
            if llm_output is None:
                logger.warning("LLM structured output 返回 None，尝试普通调用方式")
                llm_output = await self.llm.ainvoke(prompt)
                json_str = self._extract_json_from_text(llm_output.content)
                outputs = self._parse_route_json(json_str)
            else:
                outputs = llm_output.outputs
        except Exception as e:
            logger.warning(f"LLM structured output 调用失败: {e}，尝试普通调用方式")
            llm_output = await self.llm.ainvoke(prompt)
            json_str = self._extract_json_from_text(llm_output.content)
            outputs = self._parse_route_json(json_str)

        logger.info(f"入口节点标签与实体: {outputs}")
        return outputs

    # ------------------------------------------------------------------
    # 节点检索
    # ------------------------------------------------------------------

    async def node_retrieval(self, route_res: list[RouteItem], top_k: int) -> dict:
        """根据标签和实体，检索入口节点

        优先使用混合检索（向量+全文），若 Neo4j 中未创建对应向量/全文索引，
        则降级为 Cypher 文本精确匹配检索。
        """
        pairs: list[tuple[str, str]] = []
        for item in route_res:
            if item.entity:
                pairs.append((item.label, item.entity))

        if not pairs:
            return {}

        labels, entities = zip(*pairs)
        labels, entities = list(labels), list(entities)

        retrieved_nodes: dict[str, list] = {}

        # 对每个实体进行中文分词，用 " OR " 连接生成全文检索查询文本
        query_texts = [
            " OR ".join([
                word.strip()
                for word in jieba.lcut(entity)
                if re.fullmatch(r"[a-zA-Z0-9一-龥]+", word.strip())
            ])
            for entity in entities
        ]
        # 对实体进行向量化
        query_vectors = self.embeddings.embed_documents(entities)

        # 为每个标签创建混合检索任务（带降级处理）
        tasks = []
        for label, query_text, query_vector in zip(labels, query_texts, query_vectors):
            tasks.append(
                self._hybrid_retrieve_or_fallback(
                    label, query_text, query_vector, top_k
                )
            )

        results = await asyncio.gather(*tasks)

        for (label, _), result in zip(pairs, results):
            key_name = f"{label.lower()}_name" if label != "Attr" else f"{label.lower()}_value"
            for item in result:
                retrieved_nodes.setdefault(label, []).append(item)

        logger.info(f"入口节点: {retrieved_nodes}")
        return retrieved_nodes

    async def _hybrid_retrieve_or_fallback(
        self,
        label: str,
        query_text: str,
        query_vector: list[float],
        top_k: int,
    ) -> list[dict]:
        """尝试混合检索，索引缺失时降级为 CYPher 文本精确匹配"""
        vector_index_name = label.lower() + "_vector"
        fulltext_index_name = label.lower() + "_fulltext"

        try:
            retriever = HybridRetriever(
                self.driver,
                vector_index_name=vector_index_name,
                fulltext_index_name=fulltext_index_name,
            )
            raw_result = await asyncio.to_thread(
                retriever.get_search_results,
                query_text,
                query_vector,
                top_k,
                effective_search_ratio=2,
            )
            key_name = f"{label.lower()}_name" if label != "Attr" else f"{label.lower()}_value"
            return [
                {key_name: item["node"][key_name], "score": item["score"]}
                for item in raw_result.records
            ]
        except Exception as e:
            logger.warning(
                f"混合检索失败（label={label}, vector_index={vector_index_name}, "
                f"fulltext_index={fulltext_index_name}），降级为文本匹配检索: {e}"
            )
            return await self._fallback_text_search(label, query_text, top_k)

    async def _fallback_text_search(
        self,
        label: str,
        query_text: str,
        top_k: int,
    ) -> list[dict]:
        """降级方案：Cypher 文本模糊匹配检索节点

        在对应标签的节点中，用 CONTAINS 或 = 匹配实体名称。
        """
        assert self.driver is not None

        # 将 OR 形式的全文查询转为实体列表
        search_terms = [term.strip() for term in query_text.split(" OR ") if term.strip()]
        if not search_terms:
            return []

        key_name = f"{label.lower()}_name" if label != "Attr" else f"{label.lower()}_value"

        try:
            # 构建模糊匹配查询
            or_conditions = []
            params: dict[str, object] = {"limit": top_k}
            for i, term in enumerate(search_terms):
                param_key = f"term_{i}"
                params[param_key] = f"%{term}%"
                or_conditions.append(f"n.{key_name} LIKE ${param_key}")

            where_clause = " OR ".join(or_conditions)
            cypher = f"""
                MATCH (n:{label})
                WHERE {where_clause}
                RETURN n.{key_name} AS {key_name}
                LIMIT $limit
            """

            records = self.driver.execute_query(cypher, params).records
            return [
                {key_name: record[key_name], "score": 0.5}
                for record in records
            ]
        except Exception as e:
            logger.warning(f"降级文本搜索也失败（label={label}）: {e}")
            return []

    # ------------------------------------------------------------------
    # Cypher 生成
    # ------------------------------------------------------------------

    async def generate_cypher(self, query: str, entry_nodes: dict) -> str:
        """用LLM根据入口节点和用户查询生成Cypher查询语句"""

        prompt = self.generate_cypher_prompt.format_prompt(
            schema=self.neo4j_schema, query=query, entry_nodes=entry_nodes
        )

        llm_output = await self.llm.ainvoke(prompt)
        cypher = extract_cypher(llm_output.content)

        logger.info(f"Cypher生成: {cypher}")
        return cypher

    # ------------------------------------------------------------------
    # Cypher 验证
    # ------------------------------------------------------------------

    async def validate_cypher(
        self, query: str, entry_nodes: dict, cypher: str
    ) -> list[str]:
        """使用 LLM 验证生成的Cypher语句的语法和逻辑正确性"""

        errors: list[str] = []

        # 1、验证 Cypher 语法
        try:
            assert self.driver is not None
            self.driver.execute_query(f"explain {cypher}")
        except CypherSyntaxError as e:
            errors.append(str(e))

        # 2、验证 Cypher 逻辑是否符合用户查询意图
        prompt = self.validate_cypher_prompt.format_prompt(
            schema=self.neo4j_schema,
            query=query,
            cypher=cypher,
            entry_nodes=entry_nodes,
        )
        llm_output = await self.llm.ainvoke(prompt)

        try:
            llm_errors = json.loads(llm_output.content)
            if isinstance(llm_errors, list):
                errors.extend(llm_errors)
        except Exception:
            pass

        logger.info(f"Cypher验证: {errors}")
        return errors

    # ------------------------------------------------------------------
    # Cypher 校正
    # ------------------------------------------------------------------

    async def correct_cypher(
        self, query: str, entry_nodes: dict, cypher: str, errors: list[str]
    ) -> str:
        """使用 LLM 根据错误信息校正Cypher语句"""

        prompt = self.correct_cypher_prompt.format_prompt(
            schema=self.neo4j_schema,
            query=query,
            cypher=cypher,
            entry_nodes=entry_nodes,
            errors=errors,
        )

        llm_output = await self.llm.ainvoke(prompt)
        cypher = extract_cypher(llm_output.content)

        return cypher

    # ------------------------------------------------------------------
    # 结果格式化
    # ------------------------------------------------------------------

    def _format_record_as_text(self, record: dict) -> str:
        """将 Cypher 查询结果记录格式化为自然语言文本"""

        field_name_map: dict[str, str] = {
            'sku_name': '商品名称', 's.sku_name': '商品名称',
            'sku_price': '价格', 's.sku_price': '价格',
            'sku_desc': '商品描述', 's.sku_desc': '商品描述',
            'spu_name': 'SPU名称', 'sp.spu_name': 'SPU名称',
            'trademark_name': '品牌', 'tm.trademark_name': '品牌',
            'category1_name': '一级分类', 'c1.category1_name': '一级分类',
            'category2_name': '二级分类', 'c2.category2_name': '二级分类',
            'category3_name': '三级分类', 'c3.category3_name': '三级分类',
            'attr_name': '属性名', 'a.attr_name': '属性名',
            'attr_value': '属性值', 'av.attr_value': '属性值',
        }

        parts: list[str] = []
        for key, value in record.items():
            friendly_name = field_name_map.get(key)
            if not friendly_name:
                clean_key = key.split('.')[-1] if '.' in key else key
                friendly_name = field_name_map.get(clean_key, clean_key)
            if value is not None and str(value).strip():
                parts.append(f"{friendly_name}: {value}")

        return "，".join(parts) if parts else str(record)

    def _determine_source(self, record: dict) -> str:
        """根据查询结果字段确定数据来源类型"""
        keys = set(record.keys())
        key_str = str(keys).lower()

        if 'sku' in key_str:
            return "商品信息"
        elif 'spu' in key_str:
            return "产品信息"
        elif 'trademark' in key_str:
            return "品牌信息"
        elif 'category' in key_str:
            return "分类信息"
        elif 'attr' in key_str:
            return "属性信息"
        else:
            return "知识库"

    def _fallback_search_sku_text(
        self,
        query: str,
        entry_nodes: dict[str, list],
        top_k: int,
    ) -> list[SearchResult]:
        """Fallback for facts stored directly in SKU name/fulltext."""
        spu_names = [
            item.get("spu_name")
            for item in entry_nodes.get("SPU", [])
            if isinstance(item, dict) and item.get("spu_name")
        ][:3]
        if not spu_names:
            return []

        attr_keywords = [
            item.get("attr_value")
            for item in entry_nodes.get("Attr", [])
            if isinstance(item, dict) and item.get("attr_value")
        ]
        keywords = [
            keyword
            for keyword in [*attr_keywords, *_keyword_variants(query)]
            if not any(keyword.lower() in spu.lower() for spu in spu_names)
        ][:5]

        try:
            assert self.driver is not None
            records = self.driver.execute_query(
                """
                MATCH (sku:SKU)-[:Belong]->(spu:SPU)
                WHERE spu.spu_name IN $spu_names
                  AND (
                    size($keywords) = 0
                    OR any(keyword IN $keywords WHERE
                        toLower(sku.sku_name) CONTAINS toLower(keyword)
                        OR toLower(coalesce(sku.fulltext, "")) CONTAINS toLower(keyword)
                    )
                  )
                RETURN sku.sku_name AS sku_name,
                       spu.spu_name AS spu_name,
                       sku.fulltext AS sku_fulltext
                LIMIT $limit
                """,
                {
                    "spu_names": spu_names,
                    "keywords": keywords,
                    "limit": top_k,
                },
            ).records
        except Exception as e:
            logger.warning(f"SKU文本兜底检索异常: {e}")
            return []

        results: list[SearchResult] = []
        for rec in records:
            record_dict = dict(rec)
            results.append(SearchResult(
                text=self._format_record_as_text(record_dict),
                metadata={"source": "商品信息", "raw_data": record_dict},
                score=0.8,
            ))
        if results:
            logger.info(f"SKU文本兜底检索结果: {results}")
        return results

    # ------------------------------------------------------------------
    # 主入口 —— 搜索
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """执行检索流程主入口，按顺序执行各步骤并返回结果

        Args:
            query: 用户查询文本
            top_k: 返回结果数上限
        """

        query = (query or "").strip()
        if not query:
            return []

        # 1、获取入口节点标签
        route_res = await self.route_label(query)

        # 2、检索入口节点
        entry_nodes = await self.node_retrieval(route_res, 10)

        # 3、生成 Cypher 语句
        cypher = await self.generate_cypher(query, entry_nodes)

        # 4、验证 Cypher 语句
        errors = await self.validate_cypher(query, entry_nodes, cypher)

        # 5、校正 Cypher 语句
        if errors:
            cypher = await self.correct_cypher(query, entry_nodes, cypher, errors)

        # 6、校正关系方向（仅在 Cypher 非空且校正成功时使用）
        assert self.cypher_corrector is not None
        corrected = self.cypher_corrector(cypher)
        if corrected and corrected.strip():
            cypher = corrected
        logger.info(f"Cypher校正: {cypher}")

        # 7、执行 Cypher 语句
        results: list[SearchResult] = []
        try:
            assert self.driver is not None
            records = self.driver.execute_query(cypher).records
            for rec in records:
                record_dict = dict(rec)
                text = self._format_record_as_text(record_dict)
                source = self._determine_source(record_dict)
                results.append(SearchResult(
                    text=text,
                    metadata={"source": source, "raw_data": record_dict},
                    score=1.0,
                ))
        except Exception as e:
            logger.warning(f"执行Cypher语句异常: {e}")

        # SKU 文本兜底检索（Cypher 无结果时）
        if not results:
            fallback_results = self._fallback_search_sku_text(query, entry_nodes, top_k)
            if fallback_results:
                results = fallback_results

        logger.info(f"检索结果: {results}")
        return results

    # ------------------------------------------------------------------
    # 关闭
    # ------------------------------------------------------------------

    def close(self):
        """关闭连接"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j 连接已关闭")


# ---------------------------------------------------------------------------
# 测试入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio

    neo4j_url = ecommerce_settings.neo4j_uri
    neo4j_user = ecommerce_settings.neo4j_user
    neo4j_password = ecommerce_settings.neo4j_password

    async def test_retrieval(query: str):
        """测试检索过程"""
        graphrag = GraphRAG()
        graphrag.connect({
            "uri": neo4j_url,
            "user": neo4j_user,
            "password": neo4j_password,
        })
        results = await graphrag.search(
            query,
            top_k=5,
        )
        print(f"检索结果: {len(results)} 条")
        for i, r in enumerate(results):
            print(f"{i+1}. {r.text[:200] if len(r.text) > 200 else r.text}")
        graphrag.close()

    query = "手机有哪些商品？"
    asyncio.run(test_retrieval(query))
