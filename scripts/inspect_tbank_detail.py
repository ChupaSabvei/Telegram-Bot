from __future__ import annotations

import asyncio
import re
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
    for el in soup.select('[data-qa-type]'):
        qa = el.get("data-qa-type", "")
        if any(token in qa for token in ("date", "time", "venue", "place", "session", "address", "location")):
            print(qa, "=>", el.get_text(" ", strip=True)[:120])
    for el in soup.select("time[datetime]")[:10]:
        print("time", el.get("datetime"), el.get_text(" ", strip=True))
    text = soup.get_text(" ", strip=True)
    for pat in (r"\d{1,2}:\d{2}", r"\d{1,2}\s+[а-я]+\s+\d{4}"):
        print(pat, re.findall(pat, text, flags=re.I)[:8])


async def cinema_detail() -> None:
    url = "https://www.tbank.ru/gorod/afisha/moscow/cinema/maykl-103693/"
    html, err = await fetch_html(url, timeout=120)
    print("cinema detail err", err, "len", len(html or ""))
    if not html:
        return
    soup = BeautifulSoup(html, "html.parser")
    for qa in (
        "atom-desktop-slot-date",
        "atom-desktop-slot-time",
        "desktop-afisha-event-object-object-address",
    ):
        el = soup.select_one(f'[data-qa-type="{qa}"]')
        print(qa, el.get_text(" ", strip=True) if el else None)


if __name__ == "__main__":
    asyncio.run(cinema_detail())
