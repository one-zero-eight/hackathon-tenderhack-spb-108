import pytest

from src.modules.search.rerank import (
    RELEVANCE_THRESHOLD,
    apply_rerank_scores,
    build_rerank_query,
    product_to_doc,
)
from src.modules.search.schemas import SearchResult
from tests.rerank_score_snapshots import RERANK_SCORE_SNAPSHOTS


def test_build_rerank_query_adds_kupit_prefix() -> None:
    assert build_rerank_query("Ноутбук Lenovo ThinkBook 16") == "купить Ноутбук Lenovo ThinkBook 16"
    assert build_rerank_query("  купить телефон  ") == "купить телефон"


def test_product_to_doc_uses_name_only() -> None:
    result = SearchResult(
        name="Ноутбук Lenovo ThinkBook 16",
        characteristics={"RAM": "32 ГБ", "SSD": "512 Гб"},
    )
    assert product_to_doc(result) == "Ноутбук Lenovo ThinkBook 16"


def test_relevance_threshold_value() -> None:
    assert RELEVANCE_THRESHOLD == -5.251


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (-5.25, True),
        (-5.251, True),
        (-5.252, False),
        (2.0, True),
        (-10.0, False),
    ],
)
def test_threshold_boundary(score: float, expected: bool) -> None:
    results = [SearchResult(name="item")]
    reranked = apply_rerank_scores(results, [score])
    assert reranked[0].relevant is expected


def test_apply_rerank_scores_preserves_order() -> None:
    results = [
        SearchResult(name="battery"),
        SearchResult(name="laptop"),
        SearchResult(name="noise"),
    ]
    scores = [0.2, 0.9, 0.001]

    reranked = apply_rerank_scores(results, scores)

    assert [item.name for item in reranked] == ["battery", "laptop", "noise"]
    assert reranked[0].rerank_score == 0.2
    assert reranked[1].rerank_score == 0.9
    assert reranked[2].rerank_score == 0.001


def test_apply_rerank_scores_keeps_original_order_on_mismatch() -> None:
    results = [SearchResult(name="a"), SearchResult(name="b")]
    assert apply_rerank_scores(results, [1.0]) == results


def test_score_snapshots_rank_clear_negatives_below_positives() -> None:
    for snapshot in RERANK_SCORE_SNAPSHOTS:
        if snapshot.name == "iphone":
            assert snapshot.scores[0] > snapshot.scores[3]
            assert snapshot.scores[1] > snapshot.scores[4]
        if snapshot.name == "thinkbook16":
            assert snapshot.scores[0] > snapshot.scores[2]
        if snapshot.name == "samsung_tv":
            assert min(snapshot.scores[:2]) > snapshot.scores[2]


@pytest.mark.parametrize("snapshot", RERANK_SCORE_SNAPSHOTS, ids=lambda s: s.name)
def test_score_snapshots_at_production_threshold(snapshot) -> None:
    results = [SearchResult(name=name) for name in snapshot.names]
    reranked = apply_rerank_scores(results, list(snapshot.scores))

    assert [item.name for item in reranked] == list(snapshot.names)
    assert tuple(item.relevant for item in reranked) == snapshot.expected_relevant
    for item, score in zip(reranked, snapshot.scores, strict=True):
        assert item.rerank_score == score


def test_apply_rerank_scores_marks_all_above_threshold_relevant() -> None:
    results = [SearchResult(name="a"), SearchResult(name="b")]
    reranked = apply_rerank_scores(results, [0.5, 0.2])
    assert all(item.relevant for item in reranked)


def test_apply_rerank_scores_marks_all_below_threshold_irrelevant() -> None:
    results = [SearchResult(name="a"), SearchResult(name="b")]
    reranked = apply_rerank_scores(results, [-6.0, -6.5])
    assert not any(item.relevant for item in reranked)
