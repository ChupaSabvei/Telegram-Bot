from __future__ import annotations

from src.scrapers.mts_live import MtsLiveScraper


def test_mts_live_collects_announcement_links() -> None:
    html = """
    <article class="AnnouncementPreview_root">
      <a href="/moscow/announcements/basta-guf?eventId=28754837" aria-label="Баста"></a>
    </article>
    """
    urls = MtsLiveScraper.collect_announcement_urls(html, city_slug="moscow")
    assert len(urls) == 1
    assert "eventId=28754837" in urls[0]


def test_mts_live_supports_all_project_cities() -> None:
    assert len(MtsLiveScraper.supported_cities) == 2
