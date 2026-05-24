import httpx
from meow_embed import MeowEmbedClient
from meow_embed.types import RerankRequestDict

meow = MeowEmbedClient(
    client=httpx.Client(base_url="https://api.innohassle.ru/meow-embed"),
    aclient=httpx.AsyncClient(base_url="https://api.innohassle.ru/meow-embed"),  # NOTE: async version
)


reranked = meow.rerank(
    RerankRequestDict(
        reranker_model_id="BAAI/bge-reranker-v2-m3",
        query="купить Ноутбук Lenovo ThinkBook 16",
        docs=[
            "Ноутбук Lenovo ThinkBook 16p, AMD R9 9955HX, RAM 32 ГБ, SSD 512Гб, NVIDIA GeForce RTX 5060, Windows Pro, Кл-ра: Ru/Eng",
            "Аккумулятор для Lenovo (L22L4PG3) ThinkBook 16 G5+ APO, 71Wh, 4623mAh, 15.36v",
            "Никита",
        ],
    )
)

print(reranked)


reranked = meow.rerank(
    RerankRequestDict(
        reranker_model_id="BAAI/bge-reranker-v2-m3",
        query="купить Ноутбук Lenovo T410",
        docs=[
            "Ноутбук Lenovo ThinkBook 16p, AMD R9 9955HX, RAM 32 ГБ, SSD 512Гб, NVIDIA GeForce RTX 5060, Windows Pro, Кл-ра: Ru/Eng",
            "Аккумулятор 42T4791 для Lenovo ThinkPad T410, W520, E520 55+ 5200mAh",
            "Import Trade Аккумулятор ноутбука Lenovo ThinkPad T410 (42T4235) 7800mAh",
            "LENOVO THINKPAD T410. CORE i5-520M 2.4-2.9 ГГц, 14",
            "ThinkPad T410: мощный и надежный бизнес-ноутбук",
        ],
    )
)

print(reranked)
