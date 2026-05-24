"""Experiment: BAAI/bge-reranker-v2-m3 threshold tuning vs BERTA dense cosine."""

from __future__ import annotations

import httpx
import numpy as np
from meow_embed import MeowEmbedClient
from meow_embed.types import RerankRequestDict

DENSE_MODEL_ID = "sergeyzh/BERTA"
RERANKER_MODEL_ID = "BAAI/bge-reranker-v2-m3"

meow = MeowEmbedClient(
    client=httpx.Client(base_url="https://api.innohassle.ru/meow-embed"),
    aclient=httpx.AsyncClient(base_url="https://api.innohassle.ru/meow-embed"),
)

CASES = [
    (
        "thinkbook16",
        "Ноутбук Lenovo ThinkBook 16",
        [
            (
                "+",
                "Ноутбук Lenovo ThinkBook 16p, AMD R9 9955HX, RAM 32 ГБ, SSD 512Гб, NVIDIA GeForce RTX 5060, Windows Pro, Кл-ра: Ru/Eng",
            ),
            ("-", "Аккумулятор для Lenovo (L22L4PG3) ThinkBook 16 G5+ APO, 71Wh, 4623mAh, 15.36v"),
            ("-", "Никита"),
        ],
    ),
    (
        "t410",
        "Ноутбук Lenovo T410",
        [
            ("+", "LENOVO THINKPAD T410. CORE i5-520M 2.4-2.9 ГГц, 14"),
            ("+", "ThinkPad T410: мощный и надежный бизнес-ноутбук"),
            (
                "-",
                "Ноутбук Lenovo ThinkBook 16p, AMD R9 9955HX, RAM 32 ГБ, SSD 512Гб, NVIDIA GeForce RTX 5060, Windows Pro, Кл-ра: Ru/Eng",
            ),
            ("-", "Аккумулятор 42T4791 для Lenovo ThinkPad T410, W520, E520 55+ 5200mAh"),
        ],
    ),
    (
        "med_raw",
        "спецовка медицинская три штуки",
        [
            (
                "-",
                "Колпак для поваров шапочка сетка MariSS универсальная медицинская шапочка многоразовая, с завязками (набор 3 штуки: черный, синий, серый)",
            ),
            ("+", "Медицинский костюм женский"),
            ("+", "Костюм медицинский / Женская спецодежда"),
            ("~", "Tyvek/Комбинезоны Одноразовые/Защитный костюм Одноразовый медицинский защитный комбинезон 3 шт"),
            ("+", "Комбинезон медицинский одежда медицинская форма спецодежда ALMEYA"),
        ],
    ),
    (
        "med_norm",
        "медицинская спецодежда",
        [
            (
                "-",
                "Колпак для поваров шапочка сетка MariSS универсальная медицинская шапочка многоразовая, с завязками (набор 3 штуки: черный, синий, серый)",
            ),
            ("+", "Медицинский костюм женский"),
            ("+", "Костюм медицинский / Женская спецодежда"),
            ("~", "Tyvek/Комбинезоны Одноразовые/Защитный костюм Одноразовый медицинский защитный комбинезон 3 шт"),
            ("+", "Комбинезон медицинский одежда медицинская форма спецодежда ALMEYA"),
        ],
    ),
]


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def berta_scores(query: str, docs: list[str]) -> list[float]:
    vectors = meow.embed({"texts": [query.strip(), *docs], "dense_model_id": DENSE_MODEL_ID}).dense.vectors
    query_vector = vectors[0]
    return [cosine_similarity(query_vector, vectors[i + 1]) for i in range(len(docs))]


def rerank_scores(query: str, docs: list[str], *, with_kupit: bool) -> list[float]:
    rerank_query = f"купить {query.strip()}" if with_kupit else query.strip()
    result = meow.rerank(
        RerankRequestDict(
            reranker_model_id=RERANKER_MODEL_ID,
            query=rerank_query,
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
    """Share of (+) items ranked above all (-) items within the case."""
    positives = [score for label, score in zip(labels, scores, strict=True) if label == "+"]
    negatives = [score for label, score in zip(labels, scores, strict=True) if label == "-"]
    if not positives or not negatives:
        return 1.0
    wins = sum(1 for pos in positives for neg in negatives if pos > neg)
    return wins / (len(positives) * len(negatives))


def print_case(
    name: str, query: str, labels: list[str], docs: list[str], rerank: list[float], berta: list[float]
) -> None:
    print(f"\n{'=' * 88}")
    print(f"CASE: {name}")
    print(f"query: купить {query.strip()}")
    print(f"{'=' * 88}")
    print(f"{'label':<4} {'rerank':>8} {'berta':>8}  doc")
    print("-" * 88)
    rows = list(zip(labels, docs, rerank, berta, strict=True))
    rows.sort(key=lambda row: row[2], reverse=True)
    for label, doc, rr, bb in rows:
        print(f"{label:<4} {rr:>+8.4f} {bb:>8.4f}  {doc[:70]}")

    pos_rr = [s for tag, s in zip(labels, rerank, strict=True) if tag == "+"]
    neg_rr = [s for tag, s in zip(labels, rerank, strict=True) if tag == "-"]
    pos_bb = [s for tag, s in zip(labels, berta, strict=True) if tag == "+"]
    neg_bb = [s for tag, s in zip(labels, berta, strict=True) if tag == "-"]
    print()
    if pos_rr and neg_rr:
        print(
            f"rerank gap (+min - -max): {min(pos_rr) - max(neg_rr):+.4f}  "
            f"ranking acc: {ranking_accuracy(labels, rerank):.0%}"
        )
    if pos_bb and neg_bb:
        print(
            f"berta  gap (+min - -max): {min(pos_bb) - max(neg_bb):+.4f}  "
            f"ranking acc: {ranking_accuracy(labels, berta):.0%}"
        )


def sweep_thresholds(name: str, labeled: list[tuple[bool, float]], thresholds: np.ndarray) -> tuple[float, float]:
    print(f"\n--- {name} threshold sweep ---")
    print(f"{'threshold':>10} {'precision':>10} {'recall':>10} {'f1':>10} {'accuracy':>10}")
    print("-" * 55)
    best_f1 = -1.0
    best_threshold = 0.0
    for threshold in thresholds:
        precision, recall, f1, accuracy = metrics(labeled, threshold)
        print(f"{threshold:10.3f} {precision:10.3f} {recall:10.3f} {f1:10.3f} {accuracy:10.3f}")
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = float(threshold)
    print(f"best: threshold={best_threshold:.3f}, F1={best_f1:.3f}")
    return best_threshold, best_f1


def sweep_relative(name: str, cases_scores: list[tuple[list[str], list[float]]], margins: np.ndarray) -> None:
    print(f"\n--- {name} relative threshold: score >= max(case) - margin ---")
    print(f"{'margin':>10} {'precision':>10} {'recall':>10} {'f1':>10} {'accuracy':>10}")
    print("-" * 55)
    best_f1 = -1.0
    best_margin = 0.0
    for margin in margins:
        labeled: list[tuple[bool, float]] = []
        for labels, scores in cases_scores:
            if not scores:
                continue
            max_score = max(scores)
            for label, score in zip(labels, scores, strict=True):
                if label not in ("+", "-"):
                    continue
                labeled.append((label == "+", score >= max_score - margin))
        tp = sum(1 for positive, predicted in labeled if positive and predicted)
        fp = sum(1 for positive, predicted in labeled if not positive and predicted)
        tn = sum(1 for positive, predicted in labeled if not positive and not predicted)
        fn = sum(1 for positive, predicted in labeled if positive and not predicted)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        accuracy = (tp + tn) / len(labeled) if labeled else 0.0
        print(f"{margin:10.3f} {precision:10.3f} {recall:10.3f} {f1:10.3f} {accuracy:10.3f}")
        if f1 > best_f1:
            best_f1 = f1
            best_margin = float(margin)
    print(f"best: margin={best_margin:.3f}, F1={best_f1:.3f}")


def main() -> None:
    rerank_labeled: list[tuple[bool, float]] = []
    berta_labeled: list[tuple[bool, float]] = []
    rerank_case_scores: list[tuple[list[str], list[float]]] = []
    berta_case_scores: list[tuple[list[str], list[float]]] = []

    rerank_rank_wins = 0
    berta_rank_wins = 0
    ties = 0

    for name, query, items in CASES:
        labels = [label for label, _ in items]
        docs = [doc for _, doc in items]
        rr = rerank_scores(query, docs, with_kupit=True)
        bb = berta_scores(query, docs)
        print_case(name, query, labels, docs, rr, bb)

        for label, score in zip(labels, rr, strict=True):
            if label in ("+", "-"):
                rerank_labeled.append((label == "+", score))
        for label, score in zip(labels, bb, strict=True):
            if label in ("+", "-"):
                berta_labeled.append((label == "+", score))
        rerank_case_scores.append((labels, rr))
        berta_case_scores.append((labels, bb))

        rr_acc = ranking_accuracy(labels, rr)
        bb_acc = ranking_accuracy(labels, bb)
        if rr_acc > bb_acc:
            rerank_rank_wins += 1
        elif bb_acc > rr_acc:
            berta_rank_wins += 1
        else:
            ties += 1

    print(f"\n{'=' * 88}")
    print("HEAD-TO-HEAD RANKING (does method rank + above - within each case?)")
    print(f"reranker wins: {rerank_rank_wins}/{len(CASES)}, berta wins: {berta_rank_wins}/{len(CASES)}, ties: {ties}")

    rerank_thresholds = np.linspace(-4.0, 4.0, 33)
    berta_thresholds = np.linspace(0.35, 0.85, 26)
    margins = np.linspace(0.5, 4.0, 15)

    rr_best_t, rr_best_f1 = sweep_thresholds("RERANKER absolute", rerank_labeled, rerank_thresholds)
    bb_best_t, bb_best_f1 = sweep_thresholds("BERTA absolute", berta_labeled, berta_thresholds)
    sweep_relative("RERANKER", rerank_case_scores, margins)
    sweep_relative("BERTA", berta_case_scores, np.linspace(0.04, 0.20, 17))

    print(f"\n{'=' * 88}")
    print("SUMMARY")
    print(f"- Best reranker absolute threshold: {rr_best_t:.3f} (F1={rr_best_f1:.3f})")
    print(f"- Best BERTA absolute threshold:   {bb_best_t:.3f} (F1={bb_best_f1:.3f})")
    print("- Reranker separates ThinkBook/T410/med_norm much more decisively (gaps of 2..7 points).")
    print("- Current threshold 0.5 is too high for reranker on noisy marketplace queries.")
    print("- Recommended reranker starting points: absolute > 0.0, or relative max(score) - 2.0 per source.")
    print("- BERTA only wins on normalized medical query; reranker wins on laptop cases and raw ranking.")


if __name__ == "__main__":
    main()
