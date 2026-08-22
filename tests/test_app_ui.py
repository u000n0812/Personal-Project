"""Phase 7: Streamlit UI가 오류 없이 로드되는지 확인한다."""

import unittest

from tests import PROJECT_ROOT

try:
    from streamlit.testing.v1 import AppTest

    STREAMLIT_AVAILABLE = True
except ImportError:  # pragma: no cover - streamlit 미설치 환경
    STREAMLIT_AVAILABLE = False


@unittest.skipUnless(STREAMLIT_AVAILABLE, "streamlit이 설치되지 않아 UI 테스트를 건너뜁니다.")
class AppUiTest(unittest.TestCase):
    def _run(self) -> "AppTest":
        app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=60)
        app.run()
        return app

    def test_app_starts_without_exception(self):
        app = self._run()
        self.assertEqual(list(app.exception), [])

    def test_three_menus_exist(self):
        app = self._run()
        options = app.sidebar.radio[0].options
        self.assertEqual(options, ["Chat", "Documents", "Settings"])

    def test_documents_page_renders(self):
        app = self._run()
        app.sidebar.radio[0].set_value("Documents").run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(any("지침문서 관리" in str(item.value) for item in app.subheader))

    def test_settings_page_renders(self):
        app = self._run()
        app.sidebar.radio[0].set_value("Settings").run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(app.slider)


if __name__ == "__main__":
    unittest.main()
