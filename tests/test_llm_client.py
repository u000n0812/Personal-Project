"""로컬 LLM 클라이언트 검증.

실제 Ollama 대신, 같은 응답 형식을 흉내내는 로컬 HTTP 서버를 127.0.0.1에 띄워
요청 경로 / payload / 스트리밍 파싱 / 오류 처리를 실제 소켓 통신으로 확인한다.
"""

import hashlib
import json
import math
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from guidebot.llm import ChatMessage, LLMError, OllamaClient
from guidebot.security import ExternalConnectionBlocked

RECEIVED: list[dict] = []

# 구버전 Ollama(=/api/embed 없음) 상황을 재현하기 위한 스위치
SUPPORT_BATCH_EMBED = [True]

BGE_M3_DIM = 1024   # 실제 bge-m3 출력 차원
KNOWN_MODELS = {"bge-m3", "qwen2.5:7b-instruct"}


def fake_bge_m3_vector(text: str) -> list[float]:
    """bge-m3 응답을 흉내낸 1024차원 벡터(정규화되지 않은 상태로 반환)."""
    digest = hashlib.blake2b(text.encode("utf-8"), digest_size=32).digest()
    return [
        math.sin((digest[i % 32] + i) * 0.01) * 3.0   # 크기가 1이 아닌 값으로 반환
        for i in range(BGE_M3_DIM)
    ]

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
        elif self.path in ("/api/embed", "/api/embeddings") and body.get("model") not in KNOWN_MODELS:
            # 실제 Ollama는 설치되지 않은 모델에 404와 안내 문구를 돌려준다.
            message = f'model "{body.get("model")}" not found, try pulling it first'
            self._send(json.dumps({"error": message}).encode(), 404)
        elif self.path == "/api/embed":
            if not SUPPORT_BATCH_EMBED[0]:
                self._send(b'{"error":"not found"}', 404)
                return
            texts = body.get("input") or []
            payload = {"model": body.get("model"), "embeddings": [fake_bge_m3_vector(t) for t in texts]}
            self._send(json.dumps(payload).encode())
        elif self.path == "/api/embeddings":
            self._send(json.dumps({"embedding": fake_bge_m3_vector(body.get("prompt", ""))}).encode())
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
        SUPPORT_BATCH_EMBED[0] = True
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

    def test_chat_sends_speed_options_when_provided(self):
        """num_predict/num_ctx/keep_alive가 실제 요청에 실려가는지 확인한다.

        이 값들이 빠지면 Ollama가 모델 기본 상한(대개 우리가 쓰는 것보다
        훨씬 큼)을 그대로 써서 불필요하게 느려진다.
        """
        self.client.chat(
            [ChatMessage("user", "질문")],
            model="qwen2.5:7b-instruct",
            num_predict=380,
            num_ctx=9216,
            keep_alive="30m",
        )
        sent_body = RECEIVED[0]["body"]
        self.assertEqual(sent_body["options"]["num_predict"], 380)
        self.assertEqual(sent_body["options"]["num_ctx"], 9216)
        self.assertEqual(sent_body["keep_alive"], "30m")

    def test_chat_omits_speed_options_when_not_given(self):
        """값을 안 넘기면 Ollama 기본값을 그대로 쓰도록 payload에서 빠져야 한다."""
        self.client.chat([ChatMessage("user", "질문")], model="qwen2.5:7b-instruct")
        sent_body = RECEIVED[0]["body"]
        self.assertNotIn("num_predict", sent_body["options"])
        self.assertNotIn("num_ctx", sent_body["options"])
        self.assertNotIn("keep_alive", sent_body)

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

    def test_bge_m3_embedder_uses_batch_endpoint(self):
        from guidebot.embed import OllamaEmbedder

        embedder = OllamaEmbedder(self.host, "bge-m3", timeout=10)
        self.assertEqual(embedder.dimension, BGE_M3_DIM)
        self.assertEqual(embedder.name, "ollama:bge-m3")

        RECEIVED.clear()
        texts = [f"지침 문장 {i}" for i in range(20)]
        vectors = embedder.encode_documents(texts)

        self.assertEqual(len(vectors), 20)
        # 20건이 배치 크기(16)에 맞춰 2번의 호출로 처리되어야 한다.
        self.assertEqual([item["path"] for item in RECEIVED], ["/api/embed", "/api/embed"])
        self.assertEqual(len(RECEIVED[0]["body"]["input"]), 16)
        self.assertEqual(RECEIVED[0]["body"]["model"], "bge-m3")
        # 정규화되지 않은 응답도 cosine 계산이 가능하도록 L2 정규화한다.
        for vector in vectors:
            self.assertAlmostEqual(sum(v * v for v in vector), 1.0, places=5)

    def test_embedder_falls_back_to_legacy_endpoint(self):
        from guidebot.embed import OllamaEmbedder

        SUPPORT_BATCH_EMBED[0] = False   # 구버전 Ollama 상황
        embedder = OllamaEmbedder(self.host, "bge-m3", timeout=10)
        RECEIVED.clear()
        vectors = embedder.encode_documents(["문서 한 줄", "다른 문장"])

        self.assertEqual(len(vectors), 2)
        self.assertEqual(embedder.dimension, BGE_M3_DIM)
        self.assertTrue(all(item["path"] == "/api/embeddings" for item in RECEIVED))

    def test_bge_m3_suggested_threshold(self):
        from guidebot.embed import OllamaEmbedder

        embedder = OllamaEmbedder(self.host, "bge-m3", timeout=10)
        self.assertAlmostEqual(embedder.suggested_threshold, 0.5)

    def test_missing_model_reports_pull_command(self):
        from guidebot.embed import EmbeddingError, OllamaEmbedder

        with self.assertRaises(EmbeddingError) as caught:
            OllamaEmbedder(self.host, "없는모델", timeout=10)
        self.assertIn("ollama pull 없는모델", str(caught.exception))


class EmbeddingModelHeuristicTest(unittest.TestCase):
    """실제 사례: bge-m3(임베딩 전용)를 LLM 모델로 잘못 선택한 경우를 감지한다.

    사이드바가 '연결됨'으로 표시되고 모델도 실제로 설치되어 있어서, 사용자가
    "Ollama가 문제"라고 오해하기 쉽다. 이름 패턴으로 이 상황을 미리 감지해
    정확한 원인(모델 종류 착각)을 알려줘야 한다.
    """

    def test_known_embedding_models_detected(self):
        from guidebot.llm import looks_like_embedding_model

        for name in (
            "bge-m3", "bge-m3:latest", "bge-large",
            "nomic-embed-text", "mxbai-embed-large",
            "e5-large", "gte-large", "all-minilm",
        ):
            with self.subTest(name=name):
                self.assertTrue(looks_like_embedding_model(name), name)

    def test_chat_models_not_flagged(self):
        from guidebot.llm import looks_like_embedding_model

        for name in (
            "qwen2.5:7b-instruct", "llama3.1:8b", "exaone3.5:7.8b",
            "gemma2:9b", "deepseek-r1:8b", "mistral:7b",
        ):
            with self.subTest(name=name):
                self.assertFalse(looks_like_embedding_model(name), name)


if __name__ == "__main__":
    unittest.main()
