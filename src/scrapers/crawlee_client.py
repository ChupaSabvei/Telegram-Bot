from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
CRAWLEE_SCRIPT = ROOT_DIR / "scripts" / "crawlee_fetch.mjs"


async def fetch_via_crawlee(
    url: str,
    *,
    timeout: float = 30.0,
    headers: dict[str, str] | None = None,
) -> tuple[str | None, str | None]:
    if not CRAWLEE_SCRIPT.exists():
        return None, f"crawlee script not found: {CRAWLEE_SCRIPT}"

    headers_payload = json.dumps(headers or {}, ensure_ascii=False)
    headers_b64 = base64.b64encode(headers_payload.encode("utf-8")).decode("ascii")
    timeout_ms = str(max(int(timeout * 1000), 10_000))

    process = await asyncio.create_subprocess_exec(
        "node",
        str(CRAWLEE_SCRIPT),
        url,
        timeout_ms,
        headers_b64,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(ROOT_DIR),
    )

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=max(timeout + 15, 20))
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        return None, "crawlee timeout"

    raw_stdout = stdout.decode("utf-8", errors="replace").strip()
    raw_stderr = stderr.decode("utf-8", errors="replace").strip()

    if not raw_stdout:
        if raw_stderr:
            return None, f"crawlee: {raw_stderr[:300]}"
        return None, "crawlee empty stdout"

    json_line = raw_stdout.splitlines()[-1] if "\n" in raw_stdout else raw_stdout

    try:
        payload = json.loads(json_line)
    except json.JSONDecodeError:
        return None, f"crawlee invalid output: {raw_stdout[:300]}"

    html = payload.get("html")
    error = payload.get("error")
    if html is None:
        if error:
            return None, f"crawlee: {error}"
        if raw_stderr:
            return None, f"crawlee: {raw_stderr[:300]}"
        return None, "crawlee empty response"

    lowered = html.lower()
    if "smart-captcha" in lowered or ("captcha" in lowered and "data-event-card" not in lowered):
        return None, "captcha"
    return html, None
