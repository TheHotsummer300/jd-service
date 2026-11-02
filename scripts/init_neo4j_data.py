"""初始化 Neo4j 商品知识图谱数据与索引。

从 MySQL 的 ecs 库抽取 sku_info、product_category 数据，并为 MySQL 中缺失的
SPU / 品牌 / 多级分类 / 属性 mock 一批 iPhone 12 相关数据，一起写入 Neo4j；
最后创建 GraphRAG 检索所需的 ``sku_vector`` 向量索引与 ``sku_fulltext`` 全文索引。

用法::

    uv run python scripts/init_neo4j_data.py                # 增量写入（MERGE，幂等）
    uv run python scripts/init_neo4j_data.py --clear        # 先清空图再写入
    uv run python scripts/init_neo4j_data.py --skip-mysql   # 不读 MySQL，仅写 mock 数据
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from loguru import logger
from neo4j import GraphDatabase
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.business.ecommerce.config import ecommerce_settings
from app.business.ecommerce.product_retrieval import DashScopeEmbedding

# ---------------------------------------------------------------------------
# 每个节点标签用于 MERGE 的唯一键属性（幂等写入）
# ---------------------------------------------------------------------------
MERGE_KEYS: dict[str, list[str]] = {
    "SKU": ["sku_name"],
    "SPU": ["spu_name"],
    "Trademark": ["trademark_name"],
    "Category1": ["category1_name"],
    "Category2": ["category2_name"],
    "Category3": ["category3_name"],
    "Attr": ["attr_name", "attr_value"],
}


# ---------------------------------------------------------------------------
# 纯函数：图谱数据构造（可单测，不依赖数据库）
# ---------------------------------------------------------------------------

def mock_iphone12_seed() -> dict[str, Any]:
    """构造 iPhone 12 系列的 mock 图谱数据（品牌/三级分类/属性/SPU/SKU）。

    MySQL 中没有 spu / 品牌 / 多级分类 / 属性表，这里补一份可演示的
    商品知识图谱，覆盖「双卡双待 / 5G / 屏幕 / 内存」等常见咨询事实。
    """
    nodes: list[tuple[str, dict[str, Any]]] = [
        ("Trademark", {"trademark_name": "苹果"}),
        ("Category1", {"category1_name": "数码"}),
        ("Category2", {"category2_name": "手机通讯"}),
        ("Category3", {"category3_name": "智能手机"}),
        # 属性：颜色
        ("Attr", {"attr_name": "颜色", "attr_value": "黑色"}),
        ("Attr", {"attr_name": "颜色", "attr_value": "蓝色"}),
        ("Attr", {"attr_name": "颜色", "attr_value": "白色"}),
        ("Attr", {"attr_name": "颜色", "attr_value": "石墨色"}),
        ("Attr", {"attr_name": "颜色", "attr_value": "紫色"}),
        # 属性：内存
        ("Attr", {"attr_name": "内存", "attr_value": "64GB"}),
        ("Attr", {"attr_name": "内存", "attr_value": "128GB"}),
        ("Attr", {"attr_name": "内存", "attr_value": "256GB"}),
        # 属性：特性
        ("Attr", {"attr_name": "特性", "attr_value": "支持双卡双待"}),
        ("Attr", {"attr_name": "特性", "attr_value": "支持5G"}),
        ("Attr", {"attr_name": "特性", "attr_value": "OLED屏幕"}),
        # SPU
        ("SPU", {"spu_name": "iPhone 12"}),
        ("SPU", {"spu_name": "iPhone 12 Pro"}),
        ("SPU", {"spu_name": "iPhone 12 mini"}),
        # SKU（fulltext 承载可检索的商品事实）
        ("SKU", {
            "sku_name": "iPhone 12 64GB 黑色",
            "sku_price": 6299.00,
            "fulltext": "iPhone 12 64GB 黑色，支持双卡双待，支持5G，"
                        "6.1英寸OLED超视网膜XDR显示屏，A14仿生芯片，1200万像素双摄",
        }),
        ("SKU", {
            "sku_name": "iPhone 12 128GB 蓝色",
            "sku_price": 6799.00,
            "fulltext": "iPhone 12 128GB 蓝色，支持双卡双待，支持5G，"
                        "6.1英寸OLED超视网膜XDR显示屏，A14仿生芯片",
        }),
        ("SKU", {
            "sku_name": "iPhone 12 256GB 白色",
            "sku_price": 7599.00,
            "fulltext": "iPhone 12 256GB 白色，支持双卡双待，支持5G，6.1英寸OLED屏",
        }),
        ("SKU", {
            "sku_name": "iPhone 12 Pro 128GB 石墨色",
            "sku_price": 8499.00,
            "fulltext": "iPhone 12 Pro 128GB 石墨色，支持双卡双待，支持5G，"
                        "6.1英寸OLED屏，三摄系统",
        }),
        ("SKU", {
            "sku_name": "iPhone 12 mini 64GB 紫色",
            "sku_price": 5499.00,
            "fulltext": "iPhone 12 mini 64GB 紫色，支持双卡双待，支持5G，5.4英寸OLED屏",
        }),
    ]

    relationships: list[dict[str, Any]] = [
        # SKU -[:Belong]-> SPU
        {"start_label": "SKU", "start_props": {"sku_name": "iPhone 12 64GB 黑色"},
         "type": "Belong", "end_label": "SPU", "end_props": {"spu_name": "iPhone 12"}},
        {"start_label": "SKU", "start_props": {"sku_name": "iPhone 12 128GB 蓝色"},
         "type": "Belong", "end_label": "SPU", "end_props": {"spu_name": "iPhone 12"}},
        {"start_label": "SKU", "start_props": {"sku_name": "iPhone 12 256GB 白色"},
         "type": "Belong", "end_label": "SPU", "end_props": {"spu_name": "iPhone 12"}},
        {"start_label": "SKU", "start_props": {"sku_name": "iPhone 12 Pro 128GB 石墨色"},
         "type": "Belong", "end_label": "SPU", "end_props": {"spu_name": "iPhone 12 Pro"}},
        {"start_label": "SKU", "start_props": {"sku_name": "iPhone 12 mini 64GB 紫色"},
         "type": "Belong", "end_label": "SPU", "end_props": {"spu_name": "iPhone 12 mini"}},
        # SPU -[:Belong]-> Trademark
        {"start_label": "SPU", "start_props": {"spu_name": "iPhone 12"},
         "type": "Belong", "end_label": "Trademark", "end_props": {"trademark_name": "苹果"}},
        {"start_label": "SPU", "start_props": {"spu_name": "iPhone 12 Pro"},
         "type": "Belong", "end_label": "Trademark", "end_props": {"trademark_name": "苹果"}},
        {"start_label": "SPU", "start_props": {"spu_name": "iPhone 12 mini"},
         "type": "Belong", "end_label": "Trademark", "end_props": {"trademark_name": "苹果"}},
        # SPU -[:Belong]-> Category3
        {"start_label": "SPU", "start_props": {"spu_name": "iPhone 12"},
         "type": "Belong", "end_label": "Category3", "end_props": {"category3_name": "智能手机"}},
        {"start_label": "SPU", "start_props": {"spu_name": "iPhone 12 Pro"},
         "type": "Belong", "end_label": "Category3", "end_props": {"category3_name": "智能手机"}},
        {"start_label": "SPU", "start_props": {"spu_name": "iPhone 12 mini"},
         "type": "Belong", "end_label": "Category3", "end_props": {"category3_name": "智能手机"}},
        # 分类层级 Category3 -> Category2 -> Category1
        {"start_label": "Category3", "start_props": {"category3_name": "智能手机"},
         "type": "Belong", "end_label": "Category2", "end_props": {"category2_name": "手机通讯"}},
        {"start_label": "Category2", "start_props": {"category2_name": "手机通讯"},
         "type": "Belong", "end_label": "Category1", "end_props": {"category1_name": "数码"}},
        # SKU -[:HasAttr]-> Attr（颜色 / 内存 / 特性）
        {"start_label": "SKU", "start_props": {"sku_name": "iPhone 12 64GB 黑色"},
         "type": "HasAttr", "end_label": "Attr", "end_props": {"attr_name": "颜色", "attr_value": "黑色"}},
        {"start_label": "SKU", "start_props": {"sku_name": "iPhone 12 64GB 黑色"},
         "type": "HasAttr", "end_label": "Attr", "end_props": {"attr_name": "内存", "attr_value": "64GB"}},
        {"start_label": "SKU", "start_props": {"sku_name": "iPhone 12 64GB 黑色"},
         "type": "HasAttr", "end_label": "Attr", "end_props": {"attr_name": "特性", "attr_value": "支持双卡双待"}},
        {"start_label": "SKU", "start_props": {"sku_name": "iPhone 12 128GB 蓝色"},
         "type": "HasAttr", "end_label": "Attr", "end_props": {"attr_name": "颜色", "attr_value": "蓝色"}},
        {"start_label": "SKU", "start_props": {"sku_name": "iPhone 12 128GB 蓝色"},
         "type": "HasAttr", "end_label": "Attr", "end_props": {"attr_name": "内存", "attr_value": "128GB"}},
        {"start_label": "SKU", "start_props": {"sku_name": "iPhone 12 256GB 白色"},
         "type": "HasAttr", "end_label": "Attr", "end_props": {"attr_name": "颜色", "attr_value": "白色"}},
        {"start_label": "SKU", "start_props": {"sku_name": "iPhone 12 256GB 白色"},
         "type": "HasAttr", "end_label": "Attr", "end_props": {"attr_name": "内存", "attr_value": "256GB"}},
        {"start_label": "SKU", "start_props": {"sku_name": "iPhone 12 Pro 128GB 石墨色"},
         "type": "HasAttr", "end_label": "Attr", "end_props": {"attr_name": "颜色", "attr_value": "石墨色"}},
        {"start_label": "SKU", "start_props": {"sku_name": "iPhone 12 mini 64GB 紫色"},
         "type": "HasAttr", "end_label": "Attr", "end_props": {"attr_name": "颜色", "attr_value": "紫色"}},
    ]

    return {"nodes": nodes, "relationships": relationships}


def build_sku_category_seed(
    sku_rows: list[dict[str, Any]],
    category_names: list[str],
) -> dict[str, Any]:
    """从 MySQL sku_info 行与分类名构造图谱数据。

    MySQL 中只有 sku_info（无 spu / 品牌 / 多级分类 / 属性），这里为每个
    SKU 补一个同名 SPU，并让 SPU 归属到其一级分类。
    """
    nodes: list[tuple[str, dict[str, Any]]] = []
    relationships: list[dict[str, Any]] = []

    for name in category_names:
        nodes.append(("Category1", {"category1_name": name}))

    for row in sku_rows:
        sku_name = str(row["sku_name"])
        price = row.get("sku_price")
        if price is not None:
            price = float(price)

        sku_props: dict[str, Any] = {"sku_name": sku_name, "fulltext": sku_name}
        if row.get("sku_id"):
            sku_props["sku_id"] = str(row["sku_id"])
        if price is not None:
            sku_props["sku_price"] = price
        if row.get("sku_count") is not None:
            sku_props["sku_count"] = int(row["sku_count"])

        nodes.append(("SKU", sku_props))
        nodes.append(("SPU", {"spu_name": sku_name}))

        relationships.append({
            "start_label": "SKU", "start_props": {"sku_name": sku_name},
            "type": "Belong", "end_label": "SPU", "end_props": {"spu_name": sku_name},
        })

        category = str(row.get("sku_category") or "").strip()
        if category:
            relationships.append({
                "start_label": "SPU", "start_props": {"spu_name": sku_name},
                "type": "Belong", "end_label": "Category1",
                "end_props": {"category1_name": category},
            })

    return {"nodes": nodes, "relationships": relationships}


def embedding_text_for_sku(sku_props: dict[str, Any]) -> str:
    """决定 SKU 节点生成 embedding 所使用的文本。"""
    name = str(sku_props.get("sku_name") or "")
    fulltext = str(sku_props.get("fulltext") or "").strip()
    if fulltext and fulltext != name:
        return f"{name} {fulltext}".strip()
    return name


def merge_seeds(*seeds: dict[str, Any]) -> dict[str, Any]:
    """合并多份图谱数据（节点 + 关系）为一份。"""
    nodes: list[tuple[str, dict[str, Any]]] = []
    relationships: list[dict[str, Any]] = []
    for seed in seeds:
        nodes.extend(seed.get("nodes", []))
        relationships.extend(seed.get("relationships", []))
    return {"nodes": nodes, "relationships": relationships}


# ---------------------------------------------------------------------------
# 数据源读取
# ---------------------------------------------------------------------------

async def _read_mysql() -> tuple[list[dict[str, Any]], list[str]]:
    """读取 ecs 库的 sku_info 与 product_category，失败返回空（不阻断 mock 写入）。"""
    engine = create_async_engine(
        ecommerce_settings.eco_database_url,
        connect_args={"charset": "utf8mb4"},
    )
    try:
        async with engine.connect() as conn:
            sku_rows = (await conn.execute(
                text("SELECT sku_id, sku_name, sku_price, sku_count, sku_category FROM sku_info")
            )).mappings().all()
            cat_rows = (await conn.execute(
                text("SELECT product_category FROM product_category")
            )).mappings().all()
        return [dict(r) for r in sku_rows], [r["product_category"] for r in cat_rows]
    except Exception as exc:  # noqa: BLE001 —— 初始化脚本需容忍 MySQL 未启动
        logger.warning("读取 MySQL 失败（将仅写入 mock 数据）: {}", exc)
        return [], []
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Neo4j 写入
# ---------------------------------------------------------------------------

async def _run(driver: Any, cypher: str, **params: Any) -> Any:
    """在事件循环外执行同步 driver 查询，避免阻塞。"""
    return await asyncio.to_thread(driver.execute_query, cypher, params)


def _merge_cypher(label: str, props: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """构造节点 MERGE 语句与参数（唯一键用于匹配，其余属性 SET 覆盖）。"""
    key_fields = MERGE_KEYS[label]
    merge_match = ", ".join(f"`{k}`: ${k}" for k in key_fields)
    cypher = f"MERGE (n:{label} {{{merge_match}}}) SET n += $props"
    params = {"props": props, **{k: props[k] for k in key_fields}}
    return cypher, params


def _rel_cypher(rel: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """构造关系 MERGE 语句与参数。"""
    start_label = rel["start_label"]
    end_label = rel["end_label"]
    start_props = rel["start_props"]
    end_props = rel["end_props"]

    def match_part(label: str, props: dict[str, Any], alias: str) -> str:
        key_fields = MERGE_KEYS[label]
        return f"{alias}:{label} {{{', '.join(f'`{k}`: ${alias}_{k}' for k in key_fields)}}}"

    params: dict[str, Any] = {}
    for k, v in start_props.items():
        params[f"a_{k}"] = v
    for k, v in end_props.items():
        params[f"b_{k}"] = v

    cypher = (
        f"MATCH ({match_part(start_label, start_props, 'a')}), "
        f"({match_part(end_label, end_props, 'b')}) "
        f"MERGE (a)-[:{rel['type']}]->(b)"
    )
    return cypher, params


async def _write_graph(driver: Any, data: dict[str, Any]) -> None:
    """写入节点与关系（节点先写，再写关系）。"""
    for label, props in data["nodes"]:
        cypher, params = _merge_cypher(label, props)
        await _run(driver, cypher, **params)

    for rel in data["relationships"]:
        cypher, params = _rel_cypher(rel)
        await _run(driver, cypher, **params)


def _index_statements() -> list[tuple[str, str, dict[str, Any]]]:
    """返回索引创建语句（幂等，IF NOT EXISTS），每项为 (索引名, cypher, 参数)。"""
    dim = ecommerce_settings.embedding_dimensions
    vector_cypher = (
        "CREATE VECTOR INDEX sku_vector IF NOT EXISTS "
        "FOR (n:SKU) ON (n.embedding) "
        "OPTIONS {indexConfig: {`vector.dimensions`: "
        f"{dim}"
        ", `vector.similarity_function`: 'cosine'}}"
    )
    fulltext_cypher = (
        "CREATE FULLTEXT INDEX sku_fulltext IF NOT EXISTS "
        "FOR (n:SKU) ON EACH [n.sku_name, n.fulltext]"
    )
    return [
        ("sku_vector", vector_cypher, {}),
        ("sku_fulltext", fulltext_cypher, {}),
    ]


async def _create_indexes(driver: Any) -> None:
    """创建 sku_vector 与 sku_fulltext 索引。"""
    for name, cypher, params in _index_statements():
        try:
            await _run(driver, cypher, **params)
            logger.info("索引创建成功: {}", name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("索引创建失败（可能已存在或版本不支持）: {}", exc)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

async def _main(clear: bool, skip_mysql: bool) -> None:
    sku_rows: list[dict[str, Any]] = []
    category_names: list[str] = []
    if not skip_mysql:
        sku_rows, category_names = await _read_mysql()

    seed = merge_seeds(
        build_sku_category_seed(sku_rows, category_names),
        mock_iphone12_seed(),
    )

    # 为所有 SKU 生成 embedding（DashScope text-embedding-v4）
    embeddings = DashScopeEmbedding()
    sku_texts = [embedding_text_for_sku(props) for label, props in seed["nodes"] if label == "SKU"]
    if sku_texts:
        vectors = await asyncio.to_thread(embeddings.embed_documents, sku_texts)
        for (label, props), vector in zip(seed["nodes"], vectors):
            if label == "SKU":
                props["embedding"] = vector

    driver = GraphDatabase.driver(
        ecommerce_settings.neo4j_uri,
        auth=(ecommerce_settings.neo4j_user, ecommerce_settings.neo4j_password),
    )
    try:
        driver.verify_connectivity()
        if clear:
            await _run(driver, "MATCH (n) DETACH DELETE n")
        await _write_graph(driver, seed)
        await _create_indexes(driver)
        logger.info(
            "Neo4j 初始化完成: 节点 {} 个, 关系 {} 条",
            len(seed["nodes"]), len(seed["relationships"]),
        )
    finally:
        driver.close()


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="初始化 Neo4j 商品知识图谱数据与索引")
    parser.add_argument("--clear", action="store_true", help="先清空图再写入")
    parser.add_argument("--skip-mysql", action="store_true", help="跳过 MySQL，仅写 mock 数据")
    args = parser.parse_args()
    asyncio.run(_main(clear=args.clear, skip_mysql=args.skip_mysql))


if __name__ == "__main__":
    main()
