from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup

from src.scrapers.html_utils import fetch_html


async def main() -> None:
    url = "https://www.tbank.ru/gorod/afisha/moscow/concerts/basta-guf-539245/"
    html, _ = await fetch_html(url, timeout=120)
    soup = BeautifulSoup(html, "html.parser")
    dates = soup.select('[data-qa-type="atom-desktop-slot-date"]')
    times = soup.select('[data-qa-type="atom-desktop-slot-time"]')
    print("dates", [d.get_text(" ", strip=True) for d in dates[:10]])
    print("times", [t.get_text(" ", strip=True) for t in times[:10]])
    cards = soup.select('[data-qa-type*="event-card"]')
    print("event cards", len(cards))
    for card in cards[:5]:
        print("---")
        print(card.get_text(" ", strip=True)[:200])
    addr = soup.select_one('[data-qa-type="desktop-afisha-event-object-object-address"]')
    print("main addr", addr.get_text(" ", strip=True) if addr else None)
    h1 = soup.select_one("h1")
    print("h1", h1.get_text(" ", strip=True) if h1 else None)


if __name__ == "__main__":
    asyncio.run(main())
