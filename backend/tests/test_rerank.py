from src.modules.search.rerank import (
    RELEVANCE_THRESHOLD,
    apply_rerank_scores,
    build_rerank_query,
    product_to_doc,
)
from src.modules.search.schemas import SearchResult


def test_build_rerank_query_adds_kupit_prefix() -> None:
    assert build_rerank_query("Ноутбук Lenovo ThinkBook 16") == "купить Ноутбук Lenovo ThinkBook 16"
    assert build_rerank_query("  купить телефон  ") == "купить телефон"


def test_product_to_doc_uses_name_only() -> None:
    result = SearchResult(
        name="Ноутбук Lenovo ThinkBook 16",
        characteristics={"RAM": "32 ГБ", "SSD": "512 Гб"},
    )
    assert product_to_doc(result) == "Ноутбук Lenovo ThinkBook 16"


def test_apply_rerank_scores_uses_absolute_threshold_and_preserves_order() -> None:
    results = [
        SearchResult(name="battery"),
        SearchResult(name="laptop"),
        SearchResult(name="noise"),
    ]
    scores = [-0.9, 3.5, -6.2]

    reranked = apply_rerank_scores(results, scores)

    assert RELEVANCE_THRESHOLD == 0.5
    assert [item.name for item in reranked] == ["battery", "laptop", "noise"]
    assert reranked[0].rerank_score == -0.9
    assert reranked[0].relevant is False
    assert reranked[1].rerank_score == 3.5
    assert reranked[1].relevant is True
    assert reranked[2].rerank_score == -6.2
    assert reranked[2].relevant is False


def test_apply_rerank_scores_marks_items_below_threshold_as_irrelevant() -> None:
    results = [
        SearchResult(name="chef_hat"),
        SearchResult(name="scrubs"),
    ]
    scores = [-0.56, -2.99]

    reranked = apply_rerank_scores(results, scores)

    assert reranked[0].relevant is False
    assert reranked[1].relevant is False


def test_apply_rerank_scores_keeps_original_order_on_mismatch() -> None:
    results = [SearchResult(name="a"), SearchResult(name="b")]
    assert apply_rerank_scores(results, [1.0]) == results
