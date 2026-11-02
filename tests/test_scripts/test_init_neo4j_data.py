"""init_neo4j_data 纯函数单测（不连接真实 MySQL / Neo4j）。"""
from scripts.init_neo4j_data import (
    build_sku_category_seed,
    embedding_text_for_sku,
    merge_seeds,
    mock_iphone12_seed,
)


def test_mock_iphone12_seed_has_expected_node_labels():
    # Arrange
    # Act
    seed = mock_iphone12_seed()
    labels = {label for label, _ in seed["nodes"]}
    # Assert
    assert {"SKU", "SPU", "Trademark", "Category1", "Category2", "Category3", "Attr"} <= labels


def test_mock_iphone12_seed_links_skus_to_spu():
    # Arrange
    # Act
    seed = mock_iphone12_seed()
    sku_to_spu = {
        r["start_props"]["sku_name"]: r["end_props"]["spu_name"]
        for r in seed["relationships"]
        if r["type"] == "Belong" and r["start_label"] == "SKU"
    }
    # Assert
    assert sku_to_spu["iPhone 12 64GB 黑色"] == "iPhone 12"
    assert sku_to_spu["iPhone 12 Pro 128GB 石墨色"] == "iPhone 12 Pro"
    assert sku_to_spu["iPhone 12 mini 64GB 紫色"] == "iPhone 12 mini"


def test_mock_iphone12_seed_has_dual_sim_attr():
    # Arrange
    # Act
    seed = mock_iphone12_seed()
    attr_values = {p["attr_value"] for l, p in seed["nodes"] if l == "Attr"}
    # Assert
    assert "支持双卡双待" in attr_values
    assert "支持5G" in attr_values


def test_build_sku_category_seed_maps_rows():
    # Arrange
    sku_rows = [
        {
            "sku_id": "sku123456",
            "sku_name": "男士纯棉T恤",
            "sku_price": 89.9,
            "sku_count": 150,
            "sku_category": "服装",
        }
    ]
    # Act
    seed = build_sku_category_seed(sku_rows, ["服装", "数码"])
    # Assert
    sku_nodes = [p for l, p in seed["nodes"] if l == "SKU"]
    assert len(sku_nodes) == 1
    assert sku_nodes[0]["sku_name"] == "男士纯棉T恤"
    assert sku_nodes[0]["sku_price"] == 89.9
    assert sku_nodes[0]["sku_id"] == "sku123456"

    assert any(r["type"] == "Belong" and r["start_label"] == "SKU" and r["end_label"] == "SPU"
               for r in seed["relationships"])
    assert any(r["end_label"] == "Category1" and r["end_props"]["category1_name"] == "服装"
               for r in seed["relationships"])


def test_embedding_text_for_sku_with_fulltext():
    # Arrange
    props = {"sku_name": "iPhone 12 64GB 黑色", "fulltext": "支持双卡双待，支持5G"}
    # Act / Assert
    assert embedding_text_for_sku(props) == "iPhone 12 64GB 黑色 支持双卡双待，支持5G"


def test_embedding_text_for_sku_falls_back_to_name():
    # Arrange
    props = {"sku_name": "男士纯棉T恤", "fulltext": "男士纯棉T恤"}
    # Act / Assert
    assert embedding_text_for_sku(props) == "男士纯棉T恤"


def test_merge_seeds_combines_nodes_and_relationships():
    # Arrange
    s1 = {"nodes": [("SKU", {"sku_name": "a"})], "relationships": []}
    s2 = {"nodes": [("SPU", {"spu_name": "b"})], "relationships": [{"type": "Belong"}]}
    # Act
    merged = merge_seeds(s1, s2)
    # Assert
    assert len(merged["nodes"]) == 2
    assert len(merged["relationships"]) == 1
