"""Recorded DiTy/cross-encoder-russian-msmarco scores with activation_fn=identity."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RerankScoreSnapshot:
    name: str
    query: str
    names: tuple[str, ...]
    scores: tuple[float, ...]
    expected_relevant: tuple[bool, ...]


RERANK_SCORE_SNAPSHOTS: tuple[RerankScoreSnapshot, ...] = (
    RerankScoreSnapshot(
        "iphone",
        "телефон iphone",
        (
            "Apple Смартфон iPhone 17 (eSIM×2) - Global 8/256 ГБ, eSIM, черный, прозрачный",
            "Apple Смартфон iPhone 15 - SIM+eSIM (новый, не активирован, Face Time работает, eSIM поддерживается) - Global 128 ГБ, Nano-SIM, черный",
            "Защитное стекло для iPhone 15 Pro Max 2 шт",
            "Чехол для iPhone 17 прозрачный силиконовый",
            "Никита",
        ),
        (-2.5138, -3.3706, -6.6601, -5.3849, -6.7333),
        (True, True, False, False, False),
    ),
    RerankScoreSnapshot(
        "thinkbook16",
        "Ноутбук Lenovo ThinkBook 16",
        (
            "Ноутбук Lenovo ThinkBook 16p, AMD R9 9955HX, RAM 32 ГБ, SSD 512Гб, NVIDIA GeForce RTX 5060, Windows Pro, Кл-ра: Ru/Eng",
            "Аккумулятор для Lenovo (L22L4PG3) ThinkBook 16 G5+ APO, 71Wh, 4623mAh, 15.36v",
            "Никита",
        ),
        (3.3695, 1.0095, -6.6126),
        (True, True, False),
    ),
    RerankScoreSnapshot(
        "t410",
        "Ноутбук Lenovo T410",
        (
            "LENOVO THINKPAD T410. CORE i5-520M 2.4-2.9 ГГц, 14",
            "ThinkPad T410: мощный и надежный бизнес-ноутбук",
            "Ноутбук Lenovo ThinkBook 16p, AMD R9 9955HX, RAM 32 ГБ, SSD 512Гб, NVIDIA GeForce RTX 5060, Windows Pro, Кл-ра: Ru/Eng",
        ),
        (2.0604, -0.6631, 0.6959),
        (True, True, True),
    ),
    RerankScoreSnapshot(
        "samsung_tv",
        "телевизор samsung 55",
        (
            "Samsung TV 55 DU7100 Crystal UHD 4K",
            'Телевизор Samsung UE55DU7100UXRU 55" 4K UHD Smart TV',
            "Пульт ДУ для Samsung Smart TV BN59",
        ),
        (3.0202, 2.6842, -6.7780),
        (True, True, False),
    ),
)
