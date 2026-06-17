from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup

from src.scrapers.html_utils import fetch_html


async def main() -> None:
    html, _ = await fetch_html(
        "https://www.tbank.ru/gorod/afisha/moscow/cinema/maykl-103693/",
        timeout=120,
    )
    soup = BeautifulSoup(html, "html.parser")
    schedule = soup.select_one('[data-qa-type="desktop-afisha-cinema-schedule"]')
    premiere = soup.select_one('[data-qa-type="desktop-afisha-about-cinema-premiere-date-russia"]')
    out = {
        "premiere": premiere.get_text(" ", strip=True) if premiere else None,
        "schedule_text": schedule.get_text(" ", strip=True)[:2000] if schedule else None,
        "schedule_html": str(schedule)[:4000] if schedule else None,
    }
    Path("tbank_cinema.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
