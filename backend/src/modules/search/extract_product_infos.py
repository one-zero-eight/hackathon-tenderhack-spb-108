"""Extract product listings from markdown pages via NuExtract3 (Ollama)."""

import json
import os
import re
import time
from urllib.parse import urljoin, urlparse

os.environ.setdefault("OLLAMA_HOST", "https://api.innohassle.ru/ollama")

import ollama  # noqa: E402
from ollama import ChatResponse, ResponseError

from src.logging_ import logger
from src.modules.search.markdown_urls import expand_url_label
from src.modules.search.schemas import SearchResult

MODEL = os.getenv("MODEL", "nuextract3:q8")
_CHUNK_MAX_CHARS = int(os.getenv("EXTRACT_CHUNK_MAX_CHARS", "8000"))
_CHUNK_OVERLAP_CHARS = int(os.getenv("EXTRACT_CHUNK_OVERLAP_CHARS", "0"))
_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "4096"))
_TEMPERATURE = float(os.getenv("EXTRACT_TEMPERATURE", "0"))
_RETRY_ATTEMPTS = int(os.getenv("OLLAMA_RETRY_ATTEMPTS", "4"))
_RETRY_BASE_DELAY = float(os.getenv("OLLAMA_RETRY_BASE_DELAY", "1.0"))
_RETRYABLE_STATUS = frozenset({429, 502, 503, 504})

_TEMPLATE = {
    "products": [
        {
            "name": "verbatim-string",
            "characteristics": {"verbatim-string": "verbatim-string"},
            "product_link": "verbatim-string",
            "price": "verbatim-string",
            "image_link": "verbatim-string",
            "rating": "verbatim-string",
            "reviews": "verbatim-string",
        }
    ]
}
_COMPACT_TEMPLATE = {
    "products": [
        {
            "n": "product name",
            "u": "product link",
            "p": "price without currency",
            "img": "image link",
            "r": "rating",
            "rv": "reviews count",
            "c": {"characteristic name": "characteristic value"},
        }
    ]
}

_EXAMPLES: list[tuple[str, str]] = [
    (
        """\
[![Минитрактор Кентавр Т-5 LITE](link1)](link2)

[Минитрактор Кентавр Т-5 LITE (фреза/плуг)](link2)

- Тип двигателя: Дизельный
- Мощность, л.с.: 15

349 900 руб.
""",
        json.dumps(
            {
                "products": [
                    {
                        "n": "Минитрактор Кентавр Т-5 LITE (фреза/плуг)",
                        "u": "link2",
                        "p": "349 900",
                        "img": "link1",
                        "c": {
                            "Тип двигателя": "Дизельный",
                            "Мощность, л.с.": "15",
                        },
                    }
                ]
            },
            ensure_ascii=False,
        ),
    ),
    (
        """\
[![Ноутбук игровой Lenovo LOQ 15IAX9E 15.6''/Core i5-12450HX/8Гб/512Гб/GeForce RTX 4050 6Гб/WIN11 Только АНГЛ/Серый(83LK00C9US)](link1)](link2)

[Рассрочка 0-0-24+5 10084 999 ₽99 999 ₽15%Ноутбук игровой Lenovo LOQ 15IAX9E 15.6''/Core i5-12450HX/8Гб/512Гб/GeForce RTX 4050 6Гб/WIN11 Только АНГЛ/Серый(83LK00C9US)](link2)
""",
        json.dumps(
            {
                "products": [
                    {
                        "n": "Ноутбук игровой Lenovo LOQ 15IAX9E 15.6''/Core i5-12450HX/8Гб/512Гб/GeForce RTX 4050 6Гб/WIN11 Только АНГЛ/Серый(83LK00C9US)",
                        "u": "link2",
                        "p": "99 999",
                        "img": "link1",
                    }
                ]
            },
            ensure_ascii=False,
        ),
    ),
    (
        """\
### [Костюм «АНТИСТАТ» утепленный, т/синий-василёк](link165)

16.485,0 ₽

[Выберите параметры](link165)[Подробнее](link165)

[!](link166)

[Добавить в избранное](link136)

[Закрыть](link4)
""",
        json.dumps(
            {
                "products": [
                    {
                        "n": "Костюм «АНТИСТАТ» утепленный, т/синий-василёк",
                        "u": "link165",
                        "p": "16.485,0",
                        "img": "link166",
                    }
                ]
            },
            ensure_ascii=False,
        ),
    ),
    (
        """\
[Плащ СПЕКТРОТЕК ПРЕМИУМ сигнальный двухсторонний желтый](link50)

Оптом: 4 698 р. 3 699 р.

В розницу: 5 598 р. 4 497 р.

[Купить в 1 клик](link46) [В корзину](link46)
""",
        json.dumps(
            {
                "products": [
                    {
                        "n": "Плащ СПЕКТРОТЕК ПРЕМИУМ сигнальный двухсторонний желтый",
                        "u": "link50",
                        "p": "4 497",
                    }
                ]
            },
            ensure_ascii=False,
        ),
    ),
    (
        """\
[Ноутбук Lenovo LOQ 15IRX10 (83JE009GPS)](link35)[Ноутбук Lenovo LOQ 15IRX10 (83JE009GPS)](link35)

Код: 188039

В наличии

Процессор

Intel Core i5-13450HX

Размер экрана

15.6"

Видеокарта

NVIDIA GeForce RTX 5060

Объем оперативной памяти

24 Гб

Объем SSD

512 Гб

В наличии

129 990 ₽ + 6500

В корзину
""",
        json.dumps(
            {
                "products": [
                    {
                        "n": "Ноутбук Lenovo LOQ 15IRX10 (83JE009GPS)",
                        "u": "link35",
                        "p": "129 990",
                        "c": {
                            "Код": "188039",
                            "Процессор": "Intel Core i5-13450HX",
                            "Размер экрана": '15.6"',
                            "Видеокарта": "NVIDIA GeForce RTX 5060",
                            "Объем оперативной памяти": "24 Гб",
                            "Объем SSD": "512 Гб",
                        },
                    }
                ]
            },
            ensure_ascii=False,
        ),
    ),
]

_TEMPLATE_JSON = json.dumps(_TEMPLATE, indent=4, ensure_ascii=False)
_EXAMPLE_INPUT, _EXAMPLE_OUTPUT = _EXAMPLES[0]

_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["products"],
    "properties": {
        "products": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "name",
                    "characteristics",
                    "product_link",
                    "price",
                    "image_link",
                    "rating",
                    "reviews",
                ],
                "properties": {
                    "name": {"type": ["string", "null"]},
                    "characteristics": {
                        "type": "object",
                        "additionalProperties": {"type": ["string", "null"]},
                    },
                    "product_link": {"type": ["string", "null"]},
                    "price": {"type": ["string", "null"]},
                    "image_link": {"type": ["string", "null"]},
                    "rating": {"type": ["string", "null"]},
                    "reviews": {"type": ["string", "null"]},
                },
            },
        }
    },
}
_RESPONSE_SCHEMA_COMPACT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["products"],
    "properties": {
        "products": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["n"],
                "properties": {
                    "n": {"type": "string"},
                    "u": {"type": "string"},
                    "p": {"type": "string"},
                    "img": {"type": "string"},
                    "r": {"type": "string"},
                    "rv": {"type": "string"},
                    "c": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
                },
            },
        }
    },
}


_OLLAMA_CLIENT = ollama.Client()

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _expand_compact_product(item: dict) -> dict:
    return {
        "name": item.get("name") or item.get("n"),
        "characteristics": item.get("characteristics") or item.get("c") or {},
        "product_link": item.get("product_link") or item.get("u"),
        "price": item.get("price") or item.get("p"),
        "image_link": item.get("image_link") or item.get("img"),
        "rating": item.get("rating") or item.get("r"),
        "reviews": item.get("reviews") or item.get("rv"),
    }


def _build_nuextract_prompt(markdown: str) -> str:
    template = json.dumps(_COMPACT_TEMPLATE, indent=4, ensure_ascii=False)

    examples = []
    for example_input, example_output in _EXAMPLES:
        examples.append(
            "〖example_input_start〗"
            + example_input.strip()
            + "〖example_input_end〗\n"
            + "〖example_output_start〗"
            + example_output.strip()
            + "〖example_output_end〗"
        )

    instructions = (
        "Extract only product listings/cards. "
        "Ignore navigation, filters, categories, sort options, contacts, breadcrumbs, ads, SEO text. "
        "Return compact JSON matching the template. "
        "Use keys exactly as in the template: n, u, p, img, r, rv, c. "
        "Omit missing fields instead of writing null. "
        "For c, include only explicit product-specific characteristics. "
        "Do not copy global filter names into c. "
        "If there are no characteristics, omit c or use {}. "
        "Extract at most 12 products from this document chunk."
    )

    return (
        "<|im_start|>user\n"
        "〖task〗structured\n"
        f"〖template_start〗{template}〖template_end〗\n"
        f"〖instructions_start〗{instructions}〖instructions_end〗\n"
        "〖examples_start〗\n" + "\n".join(examples) + "\n〖examples_end〗\n"
        "〖document_start〗\n"
        f"{markdown.strip()}\n"
        "〖document_end〗<|im_end|>\n"
        "<|im_start|>assistant\n"
        "<think>\n\n</think>\n\n"
    )


def _ollama_generate(markdown: str, url: str) -> str:
    last_error: Exception | None = None

    for attempt in range(_RETRY_ATTEMPTS):
        try:
            logger.info("%s Calling ollama generate (%s)", url, MODEL)
            response = _OLLAMA_CLIENT.generate(
                model=MODEL,
                prompt=_build_nuextract_prompt(markdown),
                stream=False,
                raw=True,
                think=False,
                format=_RESPONSE_SCHEMA_COMPACT,
                options={
                    "temperature": _TEMPERATURE,
                    "num_predict": _NUM_PREDICT,
                },
            )
            return response.response

        except ResponseError as exc:
            last_error = exc
            if exc.status_code not in _RETRYABLE_STATUS or attempt >= _RETRY_ATTEMPTS - 1:
                raise

        except (ConnectionError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt >= _RETRY_ATTEMPTS - 1:
                raise

        delay = _RETRY_BASE_DELAY * (2**attempt)
        logger.warning(
            "%s Ollama generate failed (attempt %d/%d), retrying in %.1fs: %s",
            url,
            attempt + 1,
            _RETRY_ATTEMPTS,
            delay,
            last_error,
        )
        time.sleep(delay)

    if last_error is not None:
        raise last_error
    raise RuntimeError("Ollama generate failed without an exception")


def _catalog_markdown(markdown: str) -> str:
    for marker in ("## Подробнее", "## О бренде", "## О компании"):
        if marker in markdown:
            return markdown.split(marker, 1)[0]
    return markdown


def _split_markdown_chunks(markdown: str, *, max_chars: int = _CHUNK_MAX_CHARS) -> list[str]:
    markdown = _catalog_markdown(markdown)
    if len(markdown) <= max_chars:
        return [markdown]

    chunks: list[str] = []
    start = 0

    while start < len(markdown):
        end = min(len(markdown), start + max_chars)

        # Prefer line boundary, but do not require site-specific structure.
        if end < len(markdown):
            line_end = markdown.rfind("\n", start, end)
            if line_end > start + max_chars // 2:
                end = line_end

        chunks.append(markdown[start:end])

        if end >= len(markdown):
            break

        start = max(0, end - _CHUNK_OVERLAP_CHARS)

    return chunks


_PRODUCTS_ARRAY_RE = re.compile(r'"products"\s*:\s*\[', re.DOTALL)


def _salvage_products_from_truncated_json(text: str) -> list[dict]:
    match = _PRODUCTS_ARRAY_RE.search(text)
    if not match:
        return []

    decoder = json.JSONDecoder()
    i = match.end()
    products: list[dict] = []

    while i < len(text):
        while i < len(text) and text[i] in " \t\r\n,":
            i += 1

        if i >= len(text) or text[i] == "]":
            break

        if text[i] != "{":
            break

        try:
            obj, end = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            break

        if isinstance(obj, dict):
            products.append(obj)

        i = end

    return products


def _parse_model_json(content: str | None) -> dict:
    text = (content or "").strip()
    if not text:
        return {"products": []}

    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    match = _JSON_OBJECT_RE.search(text)
    if match:
        try:
            payload = json.loads(match.group())
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass

    return {"products": _salvage_products_from_truncated_json(text)}


def _chunks_for_extraction(markdown: str) -> list[str]:
    chunks = _split_markdown_chunks(markdown)
    if len(chunks) > 1:
        logger.info("Split markdown (%d chars) into %d Ollama chunk(s)", len(markdown), len(chunks))
    return chunks


def _build_messages(markdown: str) -> list[dict[str, str]]:
    """Build Ollama chat messages.

    The nuextract3 GGUF modelfile only renders system + user prompt; it does not
    apply vLLM-style chat_template_kwargs, so the extraction template must be
    sent in the system message.
    """
    return [
        {"role": "user", "content": markdown},
    ]


def _ollama_chat(markdown: str, url: str) -> ChatResponse:
    last_error: Exception | None = None
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            logger.info("%s Calling ollama (%s)", url, MODEL)
            return _OLLAMA_CLIENT.chat(
                model=MODEL,
                messages=_build_messages(markdown),
                format="json",
                think=False,
                options={"temperature": _TEMPERATURE, "num_predict": _NUM_PREDICT},
            )
        except ResponseError as exc:
            last_error = exc
            if exc.status_code not in _RETRYABLE_STATUS or attempt >= _RETRY_ATTEMPTS - 1:
                raise
        except (ConnectionError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt >= _RETRY_ATTEMPTS - 1:
                raise
        delay = _RETRY_BASE_DELAY * (2**attempt)
        logger.warning(
            "%s Ollama chat failed (attempt %d/%d), retrying in %.1fs: %s",
            url,
            attempt + 1,
            _RETRY_ATTEMPTS,
            delay,
            last_error,
        )
        time.sleep(delay)
    if last_error is not None:
        raise last_error
    raise RuntimeError("Ollama chat failed without an exception")


def _extract_chunk(markdown: str, url: str) -> list[SearchResult]:
    content = _ollama_generate(markdown, url)
    logger.info("Ollama response: %s", content)

    payload = _parse_model_json(content)
    print(payload)
    products = payload.get("products") or []
    print(products)

    results: list[SearchResult] = []

    for item_ in products:
        if not isinstance(item_, dict):
            continue

        print(item_)
        item = _expand_compact_product(item_)
        print(item)

        if not item.get("name"):
            continue

        try:
            results.append(SearchResult.model_validate(item))
        except Exception as e:
            logger.info("Result is discarded: %s", e)
            continue

    return results


def _absolutize_link(link: str, page_url: str) -> str:
    link = link.strip()
    if link.startswith(("http://", "https://")):
        return link
    origin = f"{urlparse(page_url).scheme}://{urlparse(page_url).netloc}"
    if link.startswith("/"):
        return urljoin(origin, link)
    return urljoin(origin, "/" + link.lstrip("/"))


def _resolve_result_links(
    product: SearchResult,
    url: str,
    url_map: dict[str, str] | None = None,
) -> SearchResult:
    updates: dict[str, str] = {}
    mapping = url_map or {}
    if product.product_link:
        link = expand_url_label(product.product_link, mapping)
        updates["product_link"] = _absolutize_link(link, url)
    if product.image_link:
        link = expand_url_label(product.image_link, mapping)
        updates["image_link"] = _absolutize_link(link, url)
    return product.model_copy(update=updates) if updates else product


def extract_product_infos(
    markdown: str,
    url: str,
    url_map: dict[str, str] | None = None,
) -> list[SearchResult]:
    chunks = _chunks_for_extraction(markdown)
    seen: set[tuple[str, str | None]] = set()
    results: list[SearchResult] = []
    for chunk in chunks:
        for p in _extract_chunk(chunk, url):
            product = _resolve_result_links(p, url, url_map)
            key = (product.name, product.product_link)
            if key in seen:
                continue
            seen.add(key)
            results.append(product)
    return results
