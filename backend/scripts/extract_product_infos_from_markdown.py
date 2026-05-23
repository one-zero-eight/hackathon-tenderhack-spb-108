"""Extract product listings from markdown pages via NuExtract (Ollama)."""

import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

os.environ["OLLAMA_HOST"] = "https://api.innohassle.ru/ollama"

import ollama  # noqa: E402

from src.modules.search.schemas import SearchResult

MODEL = os.getenv("MODEL", "frob/nuextract-2.0:latest")
_CHUNK_MAX_CHARS = int(os.getenv("EXTRACT_CHUNK_MAX_CHARS", "5000"))
_CHUNK_MAX_PRODUCTS = int(os.getenv("EXTRACT_CHUNK_MAX_PRODUCTS", "3"))

_TEMPLATE = {
    "products": [
        {
            "name": "string",
            "characteristics": {"string": "string"},
            "product_link": "string",
            "price": "string",
            "image_link": "string",
            "rating": "string",
            "reviews": "string",
        }
    ]
}

_EXAMPLE_INPUT = """\
[![Минитрактор Кентавр Т-5 LITE](/img/t5.jpg)](katalog/t-5-lite.html)

[Минитрактор Кентавр Т-5 LITE (фреза/плуг)](katalog/t-5-lite.html)

- Тип двигателя: Дизельный
- Мощность, л.с.: 15

349 900 руб.
"""

_EXAMPLE_OUTPUT = json.dumps(
    {
        "products": [
            {
                "name": "Минитрактор Кентавр Т-5 LITE (фреза/плуг)",
                "characteristics": {
                    "Тип двигателя": "Дизельный",
                    "Мощность, л.с.": "15",
                },
                "product_link": "katalog/t-5-lite.html",
                "price": "349 900 руб.",
                "image_link": "/img/t5.jpg",
                "rating": None,
                "reviews": None,
            }
        ]
    },
    ensure_ascii=False,
)

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_model_json(content: str | None) -> dict:
    text = (content or "").strip()
    if not text:
        return {"products": []}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_OBJECT_RE.search(text)
        if not match:
            return {"products": []}
        return json.loads(match.group())


def _catalog_markdown(markdown: str) -> str:
    for marker in ("## Подробнее", "## О бренде", "## О компании"):
        if marker in markdown:
            return markdown.split(marker, 1)[0]
    return markdown


def _product_blocks(markdown: str) -> list[str]:
    markdown = _catalog_markdown(markdown)
    lines = markdown.splitlines(keepends=True)
    preamble: list[str] = []
    blocks: list[list[str]] = []
    current: list[str] | None = None

    for line in lines:
        if line.startswith("[!["):
            if current is not None:
                blocks.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
        else:
            preamble.append(line)
    if current is not None:
        blocks.append(current)

    if not blocks:
        return [markdown]
    preamble_text = "".join(preamble)
    return [preamble_text + "".join(block) for block in blocks]


def _split_product_chunks(
    markdown: str,
    *,
    max_chars: int = _CHUNK_MAX_CHARS,
    max_products: int = _CHUNK_MAX_PRODUCTS,
) -> list[str]:
    blocks = _product_blocks(markdown)
    if len(blocks) == 1 and "[![" not in blocks[0]:
        return blocks

    chunks: list[str] = []
    batch: list[str] = []
    batch_len = 0
    for block in blocks:
        if batch and (len(batch) >= max_products or batch_len + len(block) > max_chars):
            chunks.append("".join(batch))
            batch = []
            batch_len = 0
        batch.append(block)
        batch_len += len(block)
    if batch:
        chunks.append("".join(batch))
    return chunks


def _extract_chunk(markdown: str) -> list[SearchResult]:
    messages = [
        {"role": "template", "content": json.dumps(_TEMPLATE, ensure_ascii=False)},
        {"role": "examples.input", "content": _EXAMPLE_INPUT},
        {"role": "examples.output", "content": _EXAMPLE_OUTPUT},
        {"role": "user", "content": markdown},
    ]
    response = ollama.chat(model=MODEL, messages=messages)
    payload = _parse_model_json(response.message.content)
    products = payload.get("products") or []
    if not isinstance(products, list):
        return []
    results: list[SearchResult] = []
    for item in products:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        try:
            results.append(SearchResult.model_validate(item))
        except Exception:
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


def _resolve_result_links(product: SearchResult, url: str) -> SearchResult:
    updates: dict[str, str] = {}
    if product.product_link:
        updates["product_link"] = _absolutize_link(product.product_link, url)
    if product.image_link:
        updates["image_link"] = _absolutize_link(product.image_link, url)
    return product.model_copy(update=updates) if updates else product


def _url_from_frontmatter(markdown: str) -> str | None:
    if not markdown.startswith("---\n"):
        return None
    end = markdown.find("\n---", 4)
    if end == -1:
        return None
    for line in markdown[4:end].splitlines():
        if line.startswith("url:"):
            return line.removeprefix("url:").strip().strip("\"'")
    return None


def extract_product_infos(markdown: str, url: str) -> list[SearchResult]:
    chunks = _split_product_chunks(markdown)
    seen: set[tuple[str, str | None]] = set()
    results: list[SearchResult] = []
    for chunk in chunks:
        for p in _extract_chunk(chunk):
            product = _resolve_result_links(p, url)
            key = (product.name, product.product_link)
            if key in seen:
                continue
            seen.add(key)
            results.append(product)
    return results


def _main() -> None:
    drafts_dir = Path(__file__).resolve().parents[1] / "_mydrafts"
    for path in sorted(drafts_dir.glob("EXAMPLE-*.md")):
        markdown = path.read_text(encoding="utf-8")
        page_url = _url_from_frontmatter(markdown)
        if not page_url:
            print(f"\n=== {path.name}: skipped (no url in frontmatter) ===")
            continue
        results = extract_product_infos(markdown, page_url)
        print(f"\n=== {path.name} ({len(results)} products) ===")
        for product in results:
            print(product.model_dump_json(indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _main()
