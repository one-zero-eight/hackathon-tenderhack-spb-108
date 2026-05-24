import httpx
from meow_embed import MeowEmbedClient
from meow_embed.types import RerankRequestDict

from src.config import settings
from src.logging_ import logger
from src.modules.search.schemas import SearchResult, SearchSource

RERANKER_MODEL_ID = "Qwen/Qwen3-Reranker-0.6B"
RELEVANCE_THRESHOLD = 1.6
RERANK_QUERY_PREFIX = "купить "


def build_rerank_query(query: str) -> str:
    normalized = query.strip()
    if normalized.lower().startswith(RERANK_QUERY_PREFIX):
        return normalized
    return f"{RERANK_QUERY_PREFIX}{normalized}"


class _RerankClientHolder:
    client: MeowEmbedClient | None = None


def _get_client() -> MeowEmbedClient:
    if _RerankClientHolder.client is None:
        base_url = settings.meow_embed_base_url
        _RerankClientHolder.client = MeowEmbedClient(
            client=httpx.Client(base_url=base_url),
            aclient=httpx.AsyncClient(base_url=base_url),
        )
    return _RerankClientHolder.client


async def close_rerank_client() -> None:
    client = _RerankClientHolder.client
    if client is None:
        return
    await client.aclient.aclose()
    client.client.close()
    _RerankClientHolder.client = None


def product_to_doc(result: SearchResult) -> str:
    return result.name


def apply_rerank_scores(results: list[SearchResult], scores: list[float]) -> list[SearchResult]:
    if len(scores) != len(results):
        logger.warning(
            "Rerank score count mismatch: expected %d, got %d",
            len(results),
            len(scores),
        )
        return results

    reranked: list[SearchResult] = []
    for result, score in zip(results, scores, strict=True):
        relevant = score >= RELEVANCE_THRESHOLD
        reranked.append(
            result.model_copy(
                update={
                    "rerank_score": score,
                    "relevant": relevant,
                }
            )
        )

    return reranked


async def rerank_search_source(source: SearchSource, query: str) -> SearchSource:
    if not source.results:
        return source

    docs = [product_to_doc(result) for result in source.results]
    rerank_query = build_rerank_query(query)

    try:
        response = await _get_client().arerank(
            RerankRequestDict(
                reranker_model_id=RERANKER_MODEL_ID,
                query=rerank_query,
                docs=docs,
            )
        )
    except Exception:
        logger.warning("Rerank failed for source %s", source.source_type, exc_info=True)
        return source

    scores = response.scores[0]
    return source.model_copy(
        update={
            "results": apply_rerank_scores(source.results, scores),
        }
    )
