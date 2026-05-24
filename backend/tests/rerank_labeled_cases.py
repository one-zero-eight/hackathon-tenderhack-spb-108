"""Labeled rerank evaluation cases: '+' relevant, '-' irrelevant, '~' borderline (excluded from metrics)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RerankCase:
    name: str
    query: str
    items: tuple[tuple[str, str], ...]


RERANK_LABELED_CASES: tuple[RerankCase, ...] = (
    RerankCase(
        "iphone",
        "телефон iphone",
        (
            (
                "+",
                "Apple Смартфон iPhone 17 (eSIM×2) - Global 8/256 ГБ, eSIM, черный, прозрачный",
            ),
            (
                "+",
                "Apple Смартфон iPhone 15 - SIM+eSIM (новый, не активирован, Face Time работает, eSIM поддерживается) - Global 128 ГБ, Nano-SIM, черный",
            ),
            ("+", "Apple iPhone 15 128GB Black"),
            ("-", "Чехол для iPhone 17 прозрачный силиконовый"),
            ("-", "Защитное стекло для iPhone 15 Pro Max 2 шт"),
            ("-", "Никита"),
        ),
    ),
    RerankCase(
        "iphone_typo",
        "телефон ihone",
        (
            ("+", "Apple Смартфон iPhone 15 128GB Black"),
            ("+", "Apple Смартфон iPhone 17 (eSIM×2) - Global 8/256 ГБ"),
            ("-", "Чехол для iPhone 17 прозрачный"),
            ("-", "Samsung Galaxy S24 Ultra 256GB"),
        ),
    ),
    RerankCase(
        "thinkbook16",
        "Ноутбук Lenovo ThinkBook 16",
        (
            (
                "+",
                "Ноутбук Lenovo ThinkBook 16p, AMD R9 9955HX, RAM 32 ГБ, SSD 512Гб, NVIDIA GeForce RTX 5060, Windows Pro, Кл-ра: Ru/Eng",
            ),
            ("-", "Аккумулятор для Lenovo (L22L4PG3) ThinkBook 16 G5+ APO, 71Wh, 4623mAh, 15.36v"),
            ("-", "Никита"),
        ),
    ),
    RerankCase(
        "t410",
        "Ноутбук Lenovo T410",
        (
            ("+", "LENOVO THINKPAD T410. CORE i5-520M 2.4-2.9 ГГц, 14"),
            ("+", "ThinkPad T410: мощный и надежный бизнес-ноутбук"),
            (
                "-",
                "Ноутбук Lenovo ThinkBook 16p, AMD R9 9955HX, RAM 32 ГБ, SSD 512Гб, NVIDIA GeForce RTX 5060, Windows Pro, Кл-ра: Ru/Eng",
            ),
            ("-", "Аккумулятор 42T4791 для Lenovo ThinkPad T410, W520, E520 55+ 5200mAh"),
        ),
    ),
    RerankCase(
        "med_raw",
        "спецовка медицинская три штуки",
        (
            (
                "-",
                "Колпак для поваров шапочка сетка MariSS универсальная медицинская шапочка многоразовая, с завязками (набор 3 штуки: черный, синий, серый)",
            ),
            ("+", "Медицинский костюм женский"),
            ("+", "Костюм медицинский / Женская спецодежда"),
            ("+", "Комбинезон медицинский одежда медицинская форма спецодежда ALMEYA"),
            ("-", "Никита"),
        ),
    ),
    RerankCase(
        "med_norm",
        "медицинская спецодежда",
        (
            (
                "-",
                "Колпак для поваров шапочка сетка MariSS универсальная медицинская шапочка многоразовая, с завязками (набор 3 штуки: черный, синий, серый)",
            ),
            ("+", "Медицинский костюм женский"),
            ("+", "Костюм медицинский / Женская спецодежда"),
            ("+", "Комбинезон медицинский одежда медицинская форма спецодежда ALMEYA"),
            ("-", "Никита"),
        ),
    ),
    RerankCase(
        "samsung_tv",
        "телевизор samsung 55",
        (
            ("+", 'Телевизор Samsung UE55DU7100UXRU 55" 4K UHD Smart TV'),
            ("+", "Samsung TV 55 DU7100 Crystal UHD 4K"),
            ("-", "Кронштейн для телевизора Samsung 55 дюймов настенный"),
            ("-", "Пульт ДУ для Samsung Smart TV BN59"),
        ),
    ),
)
