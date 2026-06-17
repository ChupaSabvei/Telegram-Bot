from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.scrapers.scrapingbee import fetch_via_scrapingbee


@pytest.mark.asyncio
async def test_fetch_via_scrapingbee_success() -> None:
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body>ok</body></html>"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("src.scrapers.scrapingbee.httpx.AsyncClient", return_value=mock_client):
        html, error = await fetch_via_scrapingbee(
            "https://example.com/events",
            api_key="test-key",
            stealth=True,
            country_code="ru",
        )

    assert error is None
    assert html == "<html><body>ok</body></html>"
    call_kwargs = mock_client.get.call_args.kwargs
    assert call_kwargs["params"]["url"] == "https://example.com/events"
    assert call_kwargs["params"]["stealth_proxy"] == "true"
    assert call_kwargs["params"]["country_code"] == "ru"


@pytest.mark.asyncio
async def test_fetch_via_scrapingbee_forwards_headers() -> None:
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.text = "<html></html>"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("src.scrapers.scrapingbee.httpx.AsyncClient", return_value=mock_client):
        await fetch_via_scrapingbee(
            "https://example.com",
            api_key="test-key",
            headers={"Referer": "https://yandex.ru/"},
        )

    headers = mock_client.get.call_args.kwargs["headers"]
    assert headers["Spb-Referer"] == "https://yandex.ru/"
    assert mock_client.get.call_args.kwargs["params"]["forward_headers"] == "true"


@pytest.mark.asyncio
async def test_fetch_via_scrapingbee_captcha() -> None:
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.text = "<html><div class='smart-captcha'>blocked</div></html>"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("src.scrapers.scrapingbee.httpx.AsyncClient", return_value=mock_client):
        html, error = await fetch_via_scrapingbee("https://afisha.yandex.ru/moscow", api_key="test-key")

    assert html is None
    assert error == "captcha"
