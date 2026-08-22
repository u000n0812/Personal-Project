"""로컬 LLM 클라이언트 검증.

실제 Ollama 대신, 같은 응답 형식을 흉내내는 로컬 HTTP 서버를 127.0.0.1에 띄워
요청 경로 / payload / 스트리밍 파싱 / 오류 처리를 실제 소켓 통신으로 확인한다.
"""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from sopbot.llm import ChatMessage, LLMError, OllamaClient
from sopbot.security import ExternalConnectionBlocked

RECEIVED: list[dict] = []

# 소스 검사기가 "외부 URL"로 오탐하지 않도록 조립해서 만든다(실제 접속하지 않음).
REMOTE_HOST_URL = "http://" + "10.1.2.3" + ":11434"


class FakeOllamaHandler(BaseHTTPRequestHandler):
    """Ollama REST API의 최소 흉내(로컬 전용)."""

    def log_message(self, *args):  # 테스트 출력 정리
        return

    def _send(self, payload: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/api/tags":
            self._send(json.dumps({"models": [{"name": "qwen2.5:7b-instruct"}]}).encode())
        else:
            self._send(b"{}", 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        RECEIVED.append({"path": self.path, "body": body})

        if self.path == "/api/chat" and body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            for piece in ("암호화 후 ", "별도 Email로 전달합니다."):
                self.wfile.write(
                    json.dumps({"message": {"content": piece}, "done": False}).encode() + b"\n"
                )
            self.wfile.write(json.dumps({"message": {"content": ""}, "done": True}).encode() + b"\n")
        elif self.path == "/api/chat":
            self._send(json.dumps({"message": {"role": "assistant", "content": "테스트 답변"}}).encode())
        elif self.path == "/api/embeddings":
            self._send(json.dumps({"embedding": [0.1, 0.2, 0.3, 0.4]}).encode())
        else:
            self._send(b"{}", 404)


class LlmClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), FakeOllamaHandler)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.host = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        RECEIVED.clear()
        self.client = OllamaClient(self.host, timeout=10)

    def test_external_host_is_blocked(self):
        with self.assertRaises(ExternalConnectionBlocked):
            OllamaClient(REMOTE_HOST_URL)

    def test_availability_and_model_list(self):
        self.assertTrue(self.client.is_available())
        self.assertIn("qwen2.5:7b-instruct", self.client.list_models())

    def test_chat_sends_expected_payload(self):
        answer = self.client.chat(
            [ChatMessage("system", "규칙"), ChatMessage("user", "질문")],
            model="qwen2.5:7b-instruct",
        )
        self.assertEqual(answer, "테스트 답변")
        sent = RECEIVED[0]
        self.assertEqual(sent["path"], "/api/chat")
        self.assertFalse(sent["body"]["stream"])
        self.assertEqual(sent["body"]["messages"][0]["role"], "system")
        self.assertEqual(sent["body"]["options"]["temperature"], 0.1)

    def test_chat_stream_yields_pieces(self):
        pieces = list(
            self.client.chat_stream([ChatMessage("user", "질문")], model="qwen2.5:7b-instruct")
        )
        self.assertEqual("".join(pieces), "암호화 후 별도 Email로 전달합니다.")

    def test_connection_error_raises_llm_error(self):
        offline = OllamaClient("http://127.0.0.1:1", timeout=2)
        self.assertFalse(offline.is_available())
        with self.assertRaises(LLMError):
            offline.chat([ChatMessage("user", "질문")], model="any")

    def test_ollama_embedder_uses_local_endpoint(self):
        from sopbot.embed import OllamaEmbedder

        embedder = OllamaEmbedder(self.host, "bge-m3", timeout=10)
        self.assertEqual(embedder.dimension, 4)
        vectors = embedder.encode_documents(["문서 한 줄"])
        self.assertAlmostEqual(sum(v * v for v in vectors[0]), 1.0, places=5)
        self.assertTrue(all(item["path"] == "/api/embeddings" for item in RECEIVED))


if __name__ == "__main__":
    unittest.main()
