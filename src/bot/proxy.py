from __future__ import annotations

import logging
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)


def resolve_telegram_proxy(raw: str | None) -> str | None:
    """Normalize proxy URL for aiogram AiohttpSession (socks5/http/https)."""
    if not raw or not raw.strip():
        return None

    value = raw.strip()
    if not value.startswith("tg://"):
        return value

    parsed = urlparse(value.replace("tg://", "http://", 1))
    params = parse_qs(parsed.query)
    server = params.get("server", [None])[0]
    port = params.get("port", [None])[0]
    if not server or not port:
        logger.warning("Invalid tg:// proxy URL: missing server or port")
        return None

    logger.warning(
        "tg:// is MTProto (for Telegram app). Bot API usually needs SOCKS5/HTTP. "
        "Trying socks5://%s:%s as best-effort fallback.",
        server,
        port,
    )
    return f"socks5://{server}:{port}"
