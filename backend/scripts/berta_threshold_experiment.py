"""Experiment: BERTA dense cosine similarity vs reranker for relevance threshold tuning."""

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


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def embed_dense(texts: list[str]) -> np.ndarray:
    result = meow.embed({"texts": texts, "dense_model_id": DENSE_MODEL_ID})
    return np.asarray(result.dense.vectors, dtype=np.float32)


def rerank_scores(query: str, docs: list[str]) -> list[float]:
    rerank_query = f"купить {query.strip()}"
    result = meow.rerank(
        RerankRequestDict(
            reranker_model_id=RERANKER_MODEL_ID,
            query=rerank_query,
            docs=docs,
        )
    )
    return list(result.scores[0])


def evaluate_case(name: str, query: str, docs: list[str], labels: list[str]) -> list[tuple[str, float]]:
    vectors = embed_dense([query.strip(), *docs])
    query_vector = vectors[0]
    doc_vectors = vectors[1:]

    cosines = [cosine_similarity(query_vector, doc_vector) for doc_vector in doc_vectors]
    rerank = rerank_scores(query, docs)

    rows = list(zip(labels, docs, cosines, rerank, strict=True))
    rows.sort(key=lambda row: row[2], reverse=True)

    print(f"\n{'=' * 80}")
    print(f"CASE: {name}")
    print(f"query: {query.strip()}")
    print(f"{'=' * 80}")
    print(f"{'label':<12} {'cosine':>8} {'rerank':>8}  doc")
    print("-" * 80)
    for label, doc, cosine, score in rows:
        print(f"{label:<12} {cosine:>8.4f} {score:>+8.4f}  {doc[:70]}")

    cosines_arr = np.array(cosines)
    print()
    print(
        "cosine stats:",
        f"min={cosines_arr.min():.4f}",
        f"max={cosines_arr.max():.4f}",
        f"mean={cosines_arr.mean():.4f}",
        f"std={cosines_arr.std():.4f}",
    )

    positives = [c for c, label in zip(cosines, labels, strict=True) if label == "relevant"]
    negatives = [c for c, label in zip(cosines, labels, strict=True) if label == "irrelevant"]
    if positives and negatives:
        gap = min(positives) - max(negatives)
        midpoint = (min(positives) + max(negatives)) / 2
        print(
            "manual labels:",
            f"relevant [{min(positives):.4f}, {max(positives):.4f}]",
            f"irrelevant [{min(negatives):.4f}, {max(negatives):.4f}]",
            f"gap={gap:.4f}",
            f"suggested midpoint threshold≈{midpoint:.4f}",
        )

    return list(zip(labels, cosines, strict=True))


def scan_thresholds() -> None:
    print(f"\n{'=' * 80}")
    print("THRESHOLD SCAN (manual labels from all cases)")
    print(f"{'=' * 80}")

    cases = [
        (
            "lenovo thinkbook",
            "Ноутбук Lenovo ThinkBook 16",
            [
                (
                    "relevant",
                    "Ноутбук Lenovo ThinkBook 16p, AMD R9 9955HX, RAM 32 ГБ, SSD 512Гб, NVIDIA GeForce RTX 5060, Windows Pro, Кл-ра: Ru/Eng",
                ),
                (
                    "irrelevant",
                    "Аккумулятор для Lenovo (L22L4PG3) ThinkBook 16 G5+ APO, 71Wh, 4623mAh, 15.36v",
                ),
                ("irrelevant", "Никита"),
            ],
        ),
        (
            "lenovo t410",
            "Ноутбук Lenovo T410",
            [
                (
                    "relevant",
                    "LENOVO THINKPAD T410. CORE i5-520M 2.4-2.9 ГГц, 14",
                ),
                (
                    "relevant",
                    "ThinkPad T410: мощный и надежный бизнес-ноутбук",
                ),
                (
                    "irrelevant",
                    "Ноутбук Lenovo ThinkBook 16p, AMD R9 9955HX, RAM 32 ГБ, SSD 512Гб, NVIDIA GeForce RTX 5060, Windows Pro, Кл-ра: Ru/Eng",
                ),
                (
                    "irrelevant",
                    "Аккумулятор 42T4791 для Lenovo ThinkPad T410, W520, E520 55+ 5200mAh",
                ),
            ],
        ),
        (
            "medical uniform",
            "спецовка медицинская три штуки",
            [
                (
                    "irrelevant",
                    "Колпак для поваров шапочка сетка MariSS универсальная медицинская шапочка многоразовая, с завязками (набор 3 штуки: черный, синий, серый)",
                ),
                ("relevant", "Медицинский костюм женский"),
                (
                    "relevant",
                    "Костюм медицинский / Женская спецодежда",
                ),
                (
                    "borderline",
                    "Tyvek/Комбинезоны Одноразовые/Защитный костюм Одноразовый медицинский защитный комбинезон 3 шт",
                ),
                (
                    "relevant",
                    "Комбинезон медицинский одежда медицинская форма спецодежда ALMEYA",
                ),
            ],
        ),
    ]

    labeled: list[tuple[str, float]] = []
    for case_name, query, items in cases:
        docs = [doc for _, doc in items]
        labels = [label for label, _ in items]
        for label, cosine in evaluate_case(case_name, query, docs, labels):
            labeled.append((label, cosine))

    thresholds = np.linspace(0.50, 0.95, 19)
    print(f"\n{'threshold':>10} {'precision':>10} {'recall':>10} {'f1':>10} {'accuracy':>10}")
    print("-" * 55)
    best_f1 = -1.0
    best_threshold = None
    for threshold in thresholds:
        tp = fp = tn = fn = 0
        for label, cosine in labeled:
            predicted = cosine >= threshold
            positive = label == "relevant"
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
        accuracy = (tp + tn) / len(labeled)
        print(f"{threshold:10.3f} {precision:10.3f} {recall:10.3f} {f1:10.3f} {accuracy:10.3f}")
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = threshold

    print(f"\nBest F1 threshold on manual labels: {best_threshold:.3f} (F1={best_f1:.3f})")
    print("Note: 'borderline' counted as negative for metrics.")
    print()
    print("RECOMMENDATIONS")
    print("- BERTA cosine is in ~0.4..0.8 range; do NOT reuse reranker threshold 0.5.")
    print("- For dense embeddings, skip the 'купить' prefix; use the raw search query.")
    print("- Absolute threshold 0.55..0.58 is a reasonable starting point on clean queries.")
    print("- Raw colloquial queries with quantity ('спецовка ... три штуки') break absolute thresholds.")
    print("- Per-source relative rule works better there: relevant if cosine >= max(source) - 0.08.")
    print("- T410/accessory case still traps on part numbers; reranker or query cleanup may still be needed.")


if __name__ == "__main__":
    scan_thresholds()
