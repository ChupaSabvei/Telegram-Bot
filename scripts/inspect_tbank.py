from __future__ import annotations

import asyncio
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup

from src.scrapers.html_utils import fetch_html


async def tbank_main() -> None:
    html, err = await fetch_html("https://www.tbank.ru/gorod/afisha/moscow/", timeout=120)
    print("err", err, "len", len(html or ""))
    if not html:
        return
    soup = BeautifulSoup(html, "html.parser")
    for card in soup.select('[data-qa-type*="event-card"], [data-qa-type*="card-click-area"]')[:8]:
        link = card.select_one('a[href*="/gorod/afisha/"]')
        print("---")
        print("qa", card.get("data-qa-type"))
        print("href", link.get("href") if link else None)
        print("text", card.get_text(" ", strip=True)[:220])
    hrefs = {a.get("href", "") for a in soup.select('a[href*="/gorod/afisha/moscow/"]')}
    counts: Counter[str] = Counter()
    for href in hrefs:
        if "/places/" in href:
            counts["places"] += 1
        elif "/collections/" in href:
            counts["collections"] += 1
        elif "/event/" in href or "/events/" in href:
            counts["events"] += 1
        else:
            counts["other"] += 1
    print("counts", dict(counts))
    print("event hrefs", [h for h in sorted(hrefs) if "/event" in h][:10])


async def tbank_collection() -> None:
    url = "https://www.tbank.ru/gorod/afisha/moscow/collections/titles-segodnya-v-kino-3214/"
    html, err = await fetch_html(url, timeout=120)
    print("collection err", err, "len", len(html or ""))
    if not html:
        return
    soup = BeautifulSoup(html, "html.parser")
    for card in soup.select('[data-qa-type*="event-card"], [data-qa-type*="card-click-area"]')[:5]:
        link = card.select_one('a[href*="/gorod/afisha/"]')
        print("href", link.get("href") if link else None, "|", card.get_text(" ", strip=True)[:180])


async def tbank_event_detail() -> None:
    from src.scrapers.html_utils import parse_json_ld_events

    url = "https://www.tbank.ru/gorod/afisha/moscow/cinema/maykl-103693/"
    html, err = await fetch_html(url, timeout=120)
    print("detail err", err, "len", len(html or ""))
    if not html:
        return
    events = parse_json_ld_events(
        html,
        source_slug="tbank_gorod",
        city_slug="moscow",
        base_url="https://www.tbank.ru",
    )
    print("jsonld", len(events))
    if events:
        event = events[0]
        print(event.title, event.start_at, event.venue, event.address)
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.select('script[type="application/ld+json"]')[:2]:
        print((script.string or script.get_text() or "")[:900])


if __name__ == "__main__":
    asyncio.run(tbank_main())
    asyncio.run(tbank_collection())
    asyncio.run(tbank_event_detail())
