from __future__ import annotations

import asyncio
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup

from src.scrapers.event_dates import parse_event_date_from_text
from src.scrapers.html_utils import fetch_html


async def main() -> None:
    html, _ = await fetch_html("https://www.tbank.ru/gorod/afisha/moscow/", timeout=120)
    soup = BeautifulSoup(html, "html.parser")
    hrefs = sorted({a.get("href", "") for a in soup.select('a[href*="/gorod/afisha/moscow/"]')})
    cats: Counter[str] = Counter()
    for href in hrefs:
        parts = [p for p in href.strip("/").split("/") if p]
        # gorod afisha moscow {category} ...
        if len(parts) >= 4:
            cats[parts[3]] += 1
    print("categories", cats.most_common(20))
    samples = [h for h in hrefs if "/places/" not in h and "/collections/" not in h][:25]
    print("samples:")
    for href in samples:
        card = soup.select_one(f'a[href="{href}"]')
        text = card.get_text(" ", strip=True)[:160] if card else ""
        parsed = parse_event_date_from_text(text)
        print(href, "|", text[:100], "|", parsed)


if __name__ == "__main__":
    asyncio.run(main())
