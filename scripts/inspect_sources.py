from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup

from src.scrapers.html_utils import fetch_html


async def inspect(url: str, name: str) -> None:
    html, err = await fetch_html(url, timeout=90)
    print(f"=== {name} err={err} len={len(html or '')}")
    if not html:
        return
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.select('script[type="application/ld+json"]')[:3]:
        raw = (script.string or script.get_text() or "").strip()
        print("LD:", raw[:600])
    next_script = soup.select_one("script#__NEXT_DATA__")
    if next_script and next_script.string:
        data = json.loads(next_script.string)
        print("__NEXT_DATA__ keys:", list(data.keys()))
        props = data.get("props", {})
        print("props keys:", list(props.keys())[:10])
    for pat in ("places", "events", "announcements", "sessions", "schedule"):
        found = [a.get("href", "") for a in soup.select(f'a[href*="{pat}"]')][:8]
        if found:
            print(f"links {pat}:", found)
    times = soup.select("time[datetime]")[:8]
    if times:
        print("times:", [(t.get("datetime"), t.get_text(" ", strip=True)[:50]) for t in times])
    cards = soup.select('[data-qa-type*="event"], article[class*="AnnouncementPreview"]')[:2]
    for card in cards:
        print("card snippet:", str(card)[:900])


async def inspect_detail(url: str, name: str) -> None:
    html, err = await fetch_html(url, timeout=90)
    print(f"=== DETAIL {name} err={err} len={len(html or '')}")
    if not html:
        return
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.select('script[type="application/ld+json"]'):
        raw = (script.string or script.get_text() or "").strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        entries = payload if isinstance(payload, list) else [payload]
        for entry in entries:
            if isinstance(entry, dict) and entry.get("@type") in {"Event", "MusicEvent"}:
                print("EVENT LD:", json.dumps(entry, ensure_ascii=False)[:1200])
    venue = soup.select_one('[class*="venue"], [class*="place"], [data-qa-type*="place"]')
    if venue:
        print("venue el:", venue.get_text(" ", strip=True)[:200])
    times = soup.select("time[datetime]")[:5]
    print("times:", [(t.get("datetime"), t.get_text(" ", strip=True)[:60]) for t in times])


async def main() -> None:
    await inspect("https://live.mts.ru/moscow", "mts list")
    await inspect_detail(
        "https://live.mts.ru/moscow/announcements/basta-guf?eventId=28754837",
        "mts event",
    )
    await inspect("https://www.tbank.ru/gorod/afisha/moscow/", "tbank list")
    await inspect("https://www.tbank.ru/gorod/afisha/moscow/events/", "tbank events")
    await inspect_detail(
        "https://www.tbank.ru/gorod/afisha/moscow/event/kishlak-12345/",
        "tbank event sample",
    )


async def mts_next_data() -> None:
    url = "https://live.mts.ru/moscow/announcements/basta-guf?eventId=28754837"
    html, err = await fetch_html(url, timeout=90)
    print(f"=== MTS NEXT DATA err={err}")
    if not html:
        return
    soup = BeautifulSoup(html, "html.parser")
    ns = soup.select_one("script#__NEXT_DATA__")
    if not ns or not ns.string:
        print("no __NEXT_DATA__")
        return
    data = json.loads(ns.string)
    blob = json.dumps(data, ensure_ascii=False)
    idx = blob.find("28754837")
    print(blob[max(0, idx - 500) : idx + 1500])
    for sel in (
        "[class*='Session']",
        "[class*='session']",
        "[class*='Date']",
        "[class*='Venue']",
        "[class*='Place']",
        "[class*='Address']",
    ):
        els = soup.select(sel)[:4]
        if els:
            print(sel, [e.get_text(" ", strip=True)[:100] for e in els])


async def tbank_events_page() -> None:
    html, err = await fetch_html("https://www.tbank.ru/gorod/afisha/moscow/events/", timeout=90)
    print(f"=== TBANK EVENTS err={err} len={len(html or '')}")
    if not html:
        return
    soup = BeautifulSoup(html, "html.parser")
    from collections import Counter

    c: Counter[str] = Counter()
    sample_event_links: list[str] = []
    for a in soup.select('a[href*="/gorod/afisha/moscow/"]'):
        href = a.get("href", "")
        if "/places/" in href:
            c["places"] += 1
        elif "/event/" in href or re.search(r"/events/[^/?#]+", href):
            c["events"] += 1
            if len(sample_event_links) < 8:
                sample_event_links.append(href)
        elif "/collections/" in href:
            c["collections"] += 1
        else:
            c["other"] += 1
    print("link types", dict(c))
    print("sample event links", sample_event_links)
    cards = soup.select('[data-qa-type*="event-card"], [data-qa-type*="card-click-area"]')[:3]
    for card in cards:
        print("card", str(card)[:1400])


if __name__ == "__main__":
    asyncio.run(main())
    asyncio.run(mts_next_data())
    asyncio.run(tbank_events_page())
