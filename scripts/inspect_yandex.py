from __future__ import annotations

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup


def main() -> None:
    html = Path("yandex_rendered.html").read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for link in soup.select("a[href]"):
        href = link.get("href") or ""
        if href.startswith("/moscow/concert/") and href.count("/") >= 3 and "source=menu" not in href:
            items.append(link)
    print("candidates", len(items))
    for link in items[:8]:
        title = (
            link.get_text(" ", strip=True)
            or (link.get("aria-label") or "")
            or ((link.select_one("img") and link.select_one("img").get("alt")) or "")
        )
        container = link
        for _ in range(5):
            if container.parent is None:
                break
            container = container.parent
        text = container.get_text(" ", strip=True)[:180]
        time_el = container.select_one("time")
        time_value = time_el.get("datetime") if time_el else ""
        line = f"href={link.get('href')} | title={title[:50]} | time={time_value} | text={text}"
        print(line.encode("cp1251", "replace").decode("cp1251"))

    scripts = soup.select("script")
    print("scripts", len(scripts))
    for script in scripts:
        text = (script.string or script.get_text("", strip=True) or "").strip()
        if not text:
            continue
        if any(token in text for token in ("INITIAL", "STATE", "rubric", "event", "schedule", "entities")):
            snippet = text[:220]
            print(("script: " + snippet).encode("cp1251", "replace").decode("cp1251"))

    payload = None
    for script in scripts:
        text = (script.string or script.get_text("", strip=True) or "").strip()
        marker = "window['__initialState'] = "
        if text.startswith(marker):
            raw = text[len(marker) :].strip()
            if raw.endswith(";"):
                raw = raw[:-1]
            payload = json.loads(raw)
            break
    print("initialState found", payload is not None)
    if payload is not None:
        print("initialState keys", len(payload.keys()))
        for key, value in payload.items():
            low = key.lower()
            if any(token in low for token in ("event", "rubric", "feed", "items", "list")):
                if isinstance(value, list):
                    print(" ", key, "list", len(value))
                elif isinstance(value, dict):
                    print(" ", key, "dict", len(value.keys()))


if __name__ == "__main__":
    main()
