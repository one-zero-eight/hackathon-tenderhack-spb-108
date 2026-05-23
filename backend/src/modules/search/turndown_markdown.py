"""Convert live catalog pages to compact Markdown via Turndown in the browser."""

import os
import re
from urllib.parse import urljoin, urlparse

TURNDOWN_URL = "https://unpkg.com/turndown/dist/turndown.js"

_PAGE_TO_MARKDOWN_JS = f"""
async (baseUrl) => {{
  const loadScript = async (src) => {{
    if (document.querySelector(`script[src="${{src}}"]`)) return;
    await new Promise((resolve, reject) => {{
      const script = document.createElement('script');
      script.src = src;
      script.onload = resolve;
      script.onerror = () => reject(new Error('Failed to load ' + src));
      document.head.appendChild(script);
    }});
  }};

  const absUrl = (href) => {{
    if (!href) return '';
    try {{
      return new URL(href, baseUrl).href;
    }} catch {{
      return href;
    }}
  }};

  await loadScript({TURNDOWN_URL!r});

  const turndownService = new TurndownService({{
    headingStyle: 'atx',
    codeBlockStyle: 'fenced',
    bulletListMarker: '-',
  }});

  const anchorTextLines = (node) => {{
    const clone = node.cloneNode(true);
    clone.querySelectorAll('img, picture, svg, button, [role="button"], input, select, textarea').forEach((el) => el.remove());
    return (clone.innerText || '')
      .split('\\n')
      .map((line) => line.replace(/\\s+/g, ' ').trim())
      .filter((line) => line.length >= 2);
  }};

  turndownService.addRule('links', {{
    filter: 'a',
    replacement: (content, node) => {{
      const href = absUrl(node.getAttribute('href') || node.href || '');
      if (!href || href.startsWith('javascript:')) return content;

      const img = node.querySelector('img');
      const alt = (img?.getAttribute('alt') || img?.getAttribute('title') || '').replace(/\\s+/g, ' ').trim();
      const src = img ? absUrl(img.getAttribute('src') || img.getAttribute('data-src') || '') : '';
      const extraLines = anchorTextLines(node);

      if (img && extraLines.length > 0) {{
        const parts = [];
        if (src) parts.push(`[![${{alt}}](${{src}})](${{href}})`);
        let linkedTitle = false;
        for (const line of extraLines) {{
          if (!linkedTitle && alt && (line === alt || line.includes(alt))) {{
            parts.push(`[${{line}}](${{href}})`);
            linkedTitle = true;
            continue;
          }}
          if (!parts.includes(line)) parts.push(line);
        }}
        if (parts.length) return parts.join('\\n\\n') + '\\n\\n';
      }}

      if (img && src) return `[![${{alt}}](${{src}})](${{href}})`;
      let text = (content || '').replace(/\\s+/g, ' ').trim();
      if (!text) text = (node.getAttribute('title') || node.getAttribute('aria-label') || '').trim();
      if (!text) return '';
      const bracket = text.indexOf('[');
      if (bracket > 0) text = text.slice(0, bracket).trim();
      return `[${{text}}](${{href}})`;
    }},
  }});

  turndownService.addRule('images', {{
    filter: 'img',
    replacement: (_content, node) => {{
      const src = absUrl(node.getAttribute('src') || node.getAttribute('data-src') || '');
      if (!src || src.startsWith('data:')) return '';
      const alt = (node.getAttribute('alt') || node.getAttribute('title') || '').replace(/\\s+/g, ' ').trim();
      return `![${{alt}}](${{src}})`;
    }},
  }});

  turndownService.remove(['script', 'style', 'noscript', 'iframe', 'svg']);

  const catalogSelectors = [
    '.catalog-products',
    '[data-catalog-products]',
    '[class*="catalog-products"]',
    '[class*="products-list"]',
    '[class*="product-list"]',
    '[class*="goods-list"]',
    '.products-page__content',
    'main',
  ];
  let root = null;
  for (const selector of catalogSelectors) {{
    root = document.querySelector(selector);
    if (root) break;
  }}
  root = root || document.body;

  const clone = root.cloneNode(true);
  clone.querySelectorAll('script, style, noscript, iframe, svg').forEach((el) => el.remove());

  const title =
    document.querySelector('.products-page__title h1, .products-page__title .title, h1')?.textContent?.trim() ||
    document.title?.trim() ||
    baseUrl;

  const iconEl = document.querySelector('link[rel="icon"], link[rel="shortcut icon"]');
  const favicon = iconEl ? absUrl(iconEl.getAttribute('href') || iconEl.href) : null;

  let markdown = turndownService.turndown(clone);
  if (title) {{
    markdown = `# ${{title}}\\n\\n${{markdown}}`;
  }}

  return {{ markdown, title, favicon }};
}}
"""

_MAX_MARKDOWN_CHARS = int(os.getenv("EXTRACT_MARKDOWN_MAX_CHARS", "50000"))
_EMPTY_LINK_RE = re.compile(r"\[\s*\]\([^)]+\)\s*")
_MULTILINE_LINK_RE = re.compile(r"\[\s*\n+\s*\]\(([^)]+)\)")
_BRACKET_ESCAPE_RE = re.compile(r"\\(\[|\])")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_NOISE_LINE_RE = re.compile(r"\]\([^)]*\?(?:opinion|communicator|rating)\)")


def clean_catalog_markdown(markdown: str, page_url: str) -> str:
    text = markdown.strip()
    text = _EMPTY_LINK_RE.sub("", text)
    text = _MULTILINE_LINK_RE.sub(r"![](\1)", text)
    text = _BRACKET_ESCAPE_RE.sub(r"\1", text)

    origin = f"{urlparse(page_url).scheme}://{urlparse(page_url).netloc}"

    def _abs_link(match: re.Match[str]) -> str:
        href = match.group(1)
        if href.startswith(("http://", "https://", "#", "mailto:", "tel:")):
            return f"]({href})"
        return f"]({urljoin(origin, href)})"

    text = re.sub(r"\]\((/[^)]*)\)", _abs_link, text)

    lines = [line.rstrip() for line in text.splitlines()]
    compact: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if compact and compact[-1] != "":
                compact.append("")
            continue
        if stripped.startswith("<iframe"):
            continue
        if _NOISE_LINE_RE.search(stripped):
            continue
        compact.append(line)
    text = _BLANK_LINES_RE.sub("\n\n", "\n".join(compact).strip())

    if len(text) > _MAX_MARKDOWN_CHARS:
        text = text[:_MAX_MARKDOWN_CHARS].rsplit("\n", 1)[0] + "\n"
    return text


async def page_to_markdown(page, url: str) -> tuple[str, str, str | None]:
    result = await page.evaluate(_PAGE_TO_MARKDOWN_JS, url)
    markdown = clean_catalog_markdown(result.get("markdown") or "", url)
    title = (result.get("title") or url).strip()
    favicon = result.get("favicon") or None
    return markdown, title, favicon
