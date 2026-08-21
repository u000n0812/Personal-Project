"""Streamlit UI 스모크 테스트 (Phase 7).

브라우저 없이 앱을 실행해 3개 화면이 예외 없이 렌더링되는지 확인한다.
"""

from pathlib import Path

import pytest

pytest.importorskip("streamlit", reason="streamlit 미설치")
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "ui" / "streamlit_app.py"


def run_app(timeout: int = 60) -> AppTest:
    app = AppTest.from_file(str(APP), default_timeout=timeout)
    app.run()
    return app


def test_chat_page_renders_without_error():
    app = run_app()
    assert not app.exception
    assert any("업무 절차 질문" in item.value for item in app.subheader)
    assert app.chat_input  # 질문 입력창이 존재한다


def test_documents_page_renders_without_error():
    app = run_app()
    app.sidebar.radio[0].set_value("📁 Documents").run()
    assert not app.exception
    assert any("지침문서 관리" in item.value for item in app.subheader)


def test_settings_page_shows_search_options():
    app = run_app()
    app.sidebar.radio[0].set_value("⚙️ Settings").run()
    assert not app.exception
    labels = [slider.label for slider in app.slider]
    assert any("Top-K" in label for label in labels)
    assert any("threshold" in label for label in labels)


def test_documents_page_lists_ingested_document(index, sample_dir):
    index.ingest_folder(sample_dir)
    app = run_app()
    app.sidebar.radio[0].set_value("📁 Documents").run()
    assert not app.exception
    assert app.dataframe  # 등록된 문서 목록 표가 그려진다
