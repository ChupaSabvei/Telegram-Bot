from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup

from src.scrapers.event_dates import parse_event_date_from_text
from src.scrapers.html_utils import fetch_html


async def main() -> None:
    html, _ = await fetch_html("https://www.tbank.ru/gorod/afisha/moscow/", timeout=120)
    soup = BeautifulSoup(html, "html.parser")
    for card in soup.select('[data-qa-type*="card-click-area"]')[:12]:
        link = card.select_one('a[href*="/gorod/afisha/moscow/"]')
        if link is None:
            continue
        href = link.get("href", "")
        if "/places/" in href or "/collections/" in href:
            continue
        text = card.get_text(" ", strip=True)
        title_el = card.select_one('[data-qa-type*="event-card-title"], h3, h4')
        title = title_el.get_text(" ", strip=True) if title_el else link.get_text(" ", strip=True)
        parsed = parse_event_date_from_text(text)
        print(href)
        print(" title:", title[:80])
        print(" text:", text[:160])
        print(" date:", parsed)
        print()

    detail_url = "https://www.tbank.ru/gorod/afisha/moscow/concerts/basta-guf-539245/"
    detail_html, _ = await fetch_html(detail_url, timeout=120)
    detail = BeautifulSoup(detail_html, "html.parser")
    print("=== DETAIL ===")
    for sel in ('time[datetime]', '[data-qa-type*="date"]', '[data-qa-type*="session"]'):
        els = detail.select(sel)[:5]
        if els:
            print(sel, [(el.get("datetime"), el.get_text(" ", strip=True)[:80]) for el in els])
    print(detail.get_text(" ", strip=True)[:500])


if __name__ == "__main__":
    asyncio.run(main())
