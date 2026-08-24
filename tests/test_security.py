"""보안 요구사항(외부 통신 차단) 검증."""

import unittest

from guidebot import security
from tests import PROJECT_ROOT

# 소스 검사기가 "외부 URL"로 오탐하지 않도록 문자열을 조립해서 만든다.
EXTERNAL_HOST = "api." + "openai" + ".com"
EXTERNAL_URL = "https://" + EXTERNAL_HOST + "/v1/chat/completions"
ANTHROPIC_URL = "https://" + "api." + "anthropic" + ".com/v1/messages"
PRIVATE_URL = "http://" + "192.168.0.10" + ":11434"


class LoopbackTest(unittest.TestCase):
    def test_loopback_hosts_allowed(self):
        for host in ("127.0.0.1", "localhost", "::1"):
            self.assertTrue(security.is_loopback_host(host), host)

    def test_external_hosts_rejected(self):
        for host in (EXTERNAL_HOST, "8.8.8.8", "example.com", ""):
            self.assertFalse(security.is_loopback_host(host), host)

    def test_assert_local_url_blocks_external(self):
        self.assertEqual(
            security.assert_local_url("http://127.0.0.1:11434"), "http://127.0.0.1:11434"
        )
        with self.assertRaises(security.ExternalConnectionBlocked):
            security.assert_local_url(ANTHROPIC_URL)
        with self.assertRaises(security.ExternalConnectionBlocked):
            security.assert_local_url(PRIVATE_URL)

    def test_local_port_check_rejects_remote_host(self):
        with self.assertRaises(security.ExternalConnectionBlocked):
            security.local_port_open("10.0.0.5", 11434)


class SourceScanTest(unittest.TestCase):
    def test_no_external_calls_in_source(self):
        problems = security.scan_source_tree(PROJECT_ROOT)
        self.assertEqual(problems, [], f"외부 통신 흔적 발견: {problems}")

    def test_scan_detects_planted_external_call(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp:
            sample = Path(temp) / "bad.py"
            sample.write_text(f"url = '{EXTERNAL_URL}'\n", encoding="utf-8")
            problems = security.scan_source_tree(temp)
        self.assertTrue(problems)

    def test_offline_env_applied(self):
        import os

        security.apply_offline_env()
        self.assertEqual(os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"], "false")
        self.assertEqual(os.environ["HF_HUB_DISABLE_TELEMETRY"], "1")
        self.assertEqual(os.environ["DO_NOT_TRACK"], "1")


if __name__ == "__main__":
    unittest.main()
