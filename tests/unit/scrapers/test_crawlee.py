from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.scrapers.crawlee_client import fetch_via_crawlee


@pytest.mark.asyncio
async def test_fetch_via_crawlee_success() -> None:
    process = AsyncMock()
    payload = {"html": "<html><body>ok</body></html>", "error": None}
    process.communicate.return_value = (json.dumps(payload).encode("utf-8"), b"")
    process.returncode = 0

    with patch("pathlib.Path.exists", return_value=True):
        with patch("src.scrapers.crawlee_client.asyncio.create_subprocess_exec", return_value=process):
            html, error = await fetch_via_crawlee("https://example.com", timeout=20)

    assert error is None
    assert html == "<html><body>ok</body></html>"


@pytest.mark.asyncio
async def test_fetch_via_crawlee_error_from_payload() -> None:
    process = AsyncMock()
    payload = {"html": None, "error": "blocked"}
    process.communicate.return_value = (json.dumps(payload).encode("utf-8"), b"")
    process.returncode = 1

    with patch("pathlib.Path.exists", return_value=True):
        with patch("src.scrapers.crawlee_client.asyncio.create_subprocess_exec", return_value=process):
            html, error = await fetch_via_crawlee("https://example.com")

    assert html is None
    assert error == "crawlee: blocked"


@pytest.mark.asyncio
async def test_fetch_via_crawlee_missing_script() -> None:
    with patch("pathlib.Path.exists", return_value=False):
        html, error = await fetch_via_crawlee("https://example.com")

    assert html is None
    assert error is not None
    assert "script not found" in error
