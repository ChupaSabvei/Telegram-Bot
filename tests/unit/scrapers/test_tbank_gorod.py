from __future__ import annotations

from src.scrapers.tbank_gorod import TbankGorodScraper


def test_tbank_supports_all_project_cities() -> None:
    assert len(TbankGorodScraper.supported_cities) == 2
