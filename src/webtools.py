"""
Web Tools — internet access for any executor.

  search(query) → list of {title, url, snippet}
  fetch(url)   → page text (stripped HTML)
"""
from __future__ import annotations

import re
import urllib.request
import urllib.error
import urllib.parse
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    """Extract visible text from HTML, ignoring scripts/styles."""
    def __init__(self):
        super().__init__()
        self.text = []
        self.skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.skip = False

    def handle_data(self, data):
        if not self.skip:
            t = data.strip()
            if t:
                self.text.append(t)


def search(query: str, max_results: int = 5) -> list[dict]:
    """Search DuckDuckGo and return results."""
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={"User-Agent": "SelfEvolvingAgent/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        results = []
        # Parse DuckDuckGo HTML results
        titles = re.findall(r'class="result__title[^"]*">\s*<a[^>]*>(.*?)</a>', html, re.DOTALL)
        snippets = re.findall(r'class="result__snippet">(.*?)</a>', html, re.DOTALL)
        urls = re.findall(r'class="result__url"[^>]*>(.*?)</', html)

        for i in range(min(len(titles), max_results)):
            results.append({
                "title": re.sub(r'<[^>]+>', '', titles[i]).strip(),
                "url": urls[i].strip() if i < len(urls) else "",
                "snippet": re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else "",
            })
        return results
    except Exception:
        return []


def fetch(url: str, timeout: int = 15) -> str:
    """Fetch and extract text from a URL."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SelfEvolvingAgent/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()

        # Try UTF-8
        try:
            html = data.decode("utf-8")
        except UnicodeDecodeError:
            html = data.decode("latin-1", errors="replace")

        # Extract text
        parser = _TextExtractor()
        parser.feed(html)
        text = " ".join(parser.text)
        # Truncate to ~4000 chars
        return text[:4000]
    except Exception as e:
        return f"[fetch error: {e}]"
