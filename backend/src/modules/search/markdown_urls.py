"""Replace markdown link targets with short labels to save LLM tokens."""

import json
import re
from pathlib import Path

_PARENS_TARGET_RE = re.compile(r"\(([^)]+)\)")
_LABEL_RE = re.compile(r"^link\d+$")


def _looks_like_url(target: str) -> bool:
    if target.startswith(("http://", "https://", "/")):
        return True
    return "/" in target and " " not in target


def _collect_url_targets(markdown: str) -> list[str]:
    """All URL-like markdown link targets, including nested [![a](img)](product)."""
    ordered: list[str] = []
    seen: set[str] = set()
    for match in _PARENS_TARGET_RE.finditer(markdown):
        target = match.group(1).strip()
        if not target or _LABEL_RE.match(target) or target in seen:
            continue
        if "[" in target or "]" in target:
            continue
        if not _looks_like_url(target):
            continue
        seen.add(target)
        ordered.append(target)
    return ordered


def compress_markdown_urls(markdown: str) -> tuple[str, dict[str, str]]:
    """Return markdown with link targets replaced by link1, link2, … and label→url map."""
    ordered_targets = _collect_url_targets(markdown)

    label_to_url: dict[str, str] = {f"link{i}": target for i, target in enumerate(ordered_targets, start=1)}

    url_to_label = {url: label for label, url in label_to_url.items()}
    compressed = markdown
    for url in sorted(url_to_label, key=len, reverse=True):
        compressed = compressed.replace(f"({url})", f"({url_to_label[url]})")

    return compressed, label_to_url


def expand_url_label(value: str, url_map: dict[str, str]) -> str:
    value = value.strip()
    if _LABEL_RE.fullmatch(value):
        return url_map.get(value, value)
    return value


def save_url_map(path: Path, url_map: dict[str, str]) -> None:
    path.write_text(json.dumps(url_map, ensure_ascii=False, indent=2), encoding="utf-8")
