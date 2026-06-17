from __future__ import annotations

import httpx

SCRAPINGBEE_API_URL = "https://app.scrapingbee.com/api/v1/"


async def fetch_via_scrapingbee(
    url: str,
    *,
    api_key: str,
    timeout: float = 60.0,
    headers: dict[str, str] | None = None,
    stealth: bool = True,
    premium: bool = False,
    country_code: str = "ru",
    render_js: bool = False,
) -> tuple[str | None, str | None]:
    params: dict[str, str] = {
        "api_key": api_key,
        "url": url,
        "country_code": country_code,
    }
    if stealth:
        params["stealth_proxy"] = "true"
    elif premium:
        params["premium_proxy"] = "true"
    if render_js and not stealth:
        params["render_js"] = "true"

    request_headers: dict[str, str] = {}
    if headers:
        params["forward_headers"] = "true"
        for key, value in headers.items():
            request_headers[f"Spb-{key}"] = value

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(SCRAPINGBEE_API_URL, params=params, headers=request_headers)
    except Exception as exc:
        return None, str(exc)

    if response.status_code >= 400:
        detail = response.text[:300].strip()
        return None, f"scrapingbee http {response.status_code}: {detail}"

    text = response.text
    lowered = text.lower()
    if "smart-captcha" in lowered or ("captcha" in lowered and "data-event-card" not in lowered):
        return None, "captcha"
    return text, None
