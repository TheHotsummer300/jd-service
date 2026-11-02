"""product_retrieval 安全防护测试：只读 Cypher 校验与标签白名单。"""
from app.business.ecommerce.product_retrieval import (
    _VALID_LABELS,
    _is_readonly_cypher,
)


def test_valid_labels_whitelist_contains_expected_labels():
    # Assert：白名单应覆盖 optional_label 中的全部节点类型
    assert _VALID_LABELS == {
        "SKU",
        "SPU",
        "Trademark",
        "Category1",
        "Category2",
        "Category3",
        "Attr",
    }


def test_readonly_cypher_accepts_match_return():
    assert _is_readonly_cypher("MATCH (n:SKU) RETURN n.sku_name LIMIT 5")


def test_readonly_cypher_accepts_empty():
    assert _is_readonly_cypher("")
    assert _is_readonly_cypher(None)  # type: ignore[arg-type]


def test_readonly_cypher_rejects_delete():
    assert not _is_readonly_cypher("MATCH (n) DETACH DELETE n")


def test_readonly_cypher_rejects_delete_lowercase():
    assert not _is_readonly_cypher("match (n) delete n")


def test_readonly_cypher_rejects_create():
    assert not _is_readonly_cypher("CREATE (n:SKU {name: 'x'})")


def test_readonly_cypher_rejects_merge():
    assert not _is_readonly_cypher("MERGE (n:SKU {name: 'x'})")


def test_readonly_cypher_rejects_set():
    assert not _is_readonly_cypher("MATCH (n:SKU) SET n.price = 0")


def test_readonly_cypher_rejects_call():
    assert not _is_readonly_cypher("CALL apoc.export.csv.all('out.csv', {})")
