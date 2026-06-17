from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
import pytest_asyncio

from src.storage.database import DatabaseRuntime, build_runtime, init_db, seed_defaults

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture()
def sample_event_html() -> str:
    path = Path(__file__).resolve().parent / "fixtures" / "html" / "sample_event.html"
    return path.read_text(encoding="utf-8")


def _read_html_fixture(name: str) -> str:
    path = Path(__file__).resolve().parent / "fixtures" / "html" / name
    return path.read_text(encoding="utf-8")


@pytest.fixture()
def timepad_html() -> str:
    return _read_html_fixture("timepad_sample.html")


@pytest.fixture()
def mts_live_html() -> str:
    return _read_html_fixture("mts_live_sample.html")


@pytest.fixture()
def tbank_gorod_html() -> str:
    return _read_html_fixture("tbank_gorod_sample.html")


@pytest.fixture()
def mts_live_detail_html() -> str:
    return _read_html_fixture("mts_live_detail_sample.html")


@pytest.fixture()
def tbank_concert_detail_html() -> str:
    return _read_html_fixture("tbank_concert_detail_sample.html")


@pytest.fixture()
def mos_kultura_html() -> str:
    return _read_html_fixture("mos_kultura_sample.html")


@pytest.fixture()
def mos_sport_rayon_html() -> str:
    return _read_html_fixture("mos_sport_rayon_sample.html")


@pytest.fixture()
def timeout_msk_html() -> str:
    return _read_html_fixture("timeout_msk_sample.html")


@pytest.fixture()
def mtpp_html() -> str:
    return _read_html_fixture("mtpp_sample.html")


@pytest_asyncio.fixture()
async def db_runtime(tmp_path) -> AsyncGenerator[DatabaseRuntime, None]:
    db_path = tmp_path / "test.db"
    runtime = build_runtime(f"sqlite+aiosqlite:///{db_path}")
    await init_db(runtime)
    await seed_defaults(runtime)
    yield runtime
    await runtime.engine.dispose()
