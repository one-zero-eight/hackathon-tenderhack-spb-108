"""Threshold sweep for Qwen3-Reranker (logit / default activation_fn)."""

from __future__ import annotations

import httpx
import numpy as np
from meow_embed import MeowEmbedClient
from meow_embed.types import RerankRequestDict

from src.modules.search.rerank import RERANKER_MODEL_ID, build_rerank_query
from tests.rerank_labeled_cases import RERANK_LABELED_CASES

meow = MeowEmbedClient(
    client=httpx.Client(base_url="https://api.innohassle.ru/meow-embed"),
    aclient=httpx.AsyncClient(base_url="https://api.innohassle.ru/meow-embed"),
)


def rerank_scores(query: str, docs: list[str]) -> list[float]:
    result = meow.rerank(
        RerankRequestDict(
            reranker_model_id=RERANKER_MODEL_ID,
            query=build_rerank_query(query),
            docs=docs,
        )
    )
    return list(result.scores[0])


def metrics(labeled: list[tuple[bool, float]], threshold: float) -> tuple[float, float, float, float]:
    tp = fp = tn = fn = 0
    for positive, score in labeled:
        predicted = score >= threshold
        if predicted and positive:
            tp += 1
        elif predicted and not positive:
            fp += 1
        elif not predicted and not positive:
            tn += 1
        else:
            fn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracy = (tp + tn) / len(labeled) if labeled else 0.0
    return precision, recall, f1, accuracy


def ranking_accuracy(labels: list[str], scores: list[float]) -> float:
    positives = [score for label, score in zip(labels, scores, strict=True) if label == "+"]
    negatives = [score for label, score in zip(labels, scores, strict=True) if label == "-"]
    if not positives or not negatives:
        return 1.0
    wins = sum(1 for pos in positives for neg in negatives if pos > neg)
    return wins / (len(positives) * len(negatives))


def print_case(name: str, query: str, labels: list[str], docs: list[str], scores: list[float]) -> None:
    print(f"\n{'=' * 88}")
    print(f"CASE: {name}")
    print(f"query: {build_rerank_query(query)!r}")
    print(f"{'=' * 88}")
    print(f"{'label':<4} {'score':>8}  doc")
    print("-" * 88)
    rows = sorted(zip(labels, docs, scores, strict=True), key=lambda row: row[2], reverse=True)
    for label, doc, score in rows:
        print(f"{label:<4} {score:>+8.4f}  {doc[:70]}")

    pos = [s for tag, s in zip(labels, scores, strict=True) if tag == "+"]
    neg = [s for tag, s in zip(labels, scores, strict=True) if tag == "-"]
    if pos and neg:
        print(f"gap (+min - -max): {min(pos) - max(neg):+.4f}  ranking acc: {ranking_accuracy(labels, scores):.0%}")


def sweep_thresholds(name: str, labeled: list[tuple[bool, float]], thresholds: np.ndarray) -> tuple[float, float]:
    print(f"\n--- {name} ---")
    print(f"{'threshold':>10} {'precision':>10} {'recall':>10} {'f1':>10} {'accuracy':>10}")
    print("-" * 55)
    best_f1 = -1.0
    best_threshold = 0.0
    for threshold in thresholds:
        precision, recall, f1, accuracy = metrics(labeled, float(threshold))
        print(f"{threshold:10.3f} {precision:10.3f} {recall:10.3f} {f1:10.3f} {accuracy:10.3f}")
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = float(threshold)
    print(f"best: threshold={best_threshold:.3f}, F1={best_f1:.3f}")
    return best_threshold, best_f1


def main() -> None:
    labeled: list[tuple[bool, float]] = []
    all_scores: list[float] = []

    for case in RERANK_LABELED_CASES:
        labels = [label for label, _ in case.items]
        docs = [doc for _, doc in case.items]
        scores = rerank_scores(case.query, docs)
        print_case(case.name, case.query, labels, docs, scores)
        all_scores.extend(scores)
        for label, score in zip(labels, scores, strict=True):
            if label in ("+", "-"):
                labeled.append((label == "+", score))

    low = min(all_scores) - 1.0
    high = max(all_scores) + 1.0
    thresholds = np.linspace(low, high, 201)
    best_t, best_f1 = sweep_thresholds("logit threshold sweep", labeled, thresholds)

    # also search [0,1] for comparison (wrong for logits but informative)
    best_01 = sweep_thresholds("comparison sweep [0,1] (not recommended for logits)", labeled, np.linspace(0, 1, 201))

    print(f"\n{'=' * 88}")
    print("SUMMARY")
    print(f"- Model: {RERANKER_MODEL_ID}")
    print("- Activation: default (logit)")
    print(f"- Labeled items: {len(labeled)} across {len(RERANK_LABELED_CASES)} cases")
    print(f"- Score range: {min(all_scores):.3f} .. {max(all_scores):.3f}")
    print(f"- Best logit threshold: {best_t:.3f} (F1={best_f1:.3f})")
    print(f"- Best [0,1] threshold: {best_01[0]:.3f} (F1={best_01[1]:.3f})")


if __name__ == "__main__":
    main()
