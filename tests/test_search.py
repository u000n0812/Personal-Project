"""Phase 3~4: Vector Index 저장/유지, Keyword 검색, Hybrid 검색 검증."""

import tempfile
import unittest
from pathlib import Path

from sopbot.config import DEFAULT_SYNONYMS, Settings
from sopbot.db import Database
from sopbot.embed import HashingEmbedder
from sopbot.search import Retriever
from sopbot.keyword import KeywordIndex, coverage, expand_query, tokenize
from sopbot.vectorstore import VectorStore


class TokenizerTest(unittest.TestCase):
    def test_korean_bigrams_generated(self):
        tokens = tokenize("데이터 전달")
        self.assertIn("데이터", tokens)
        self.assertIn("데이", tokens)

    def test_synonym_expansion(self):
        expanded = expand_query("DBL 전 확인 항목", DEFAULT_SYNONYMS).lower()
        self.assertIn("database lock", expanded)
        self.assertIn("db lock", expanded)

    def test_coverage_signal(self):
        text = "Password는 반드시 별도의 Email로 전달한다."
        related = coverage("Password는 어떻게 전달해?", [text])
        unrelated = coverage("법인카드 사용 한도가 얼마인가요?", [text])
        self.assertGreaterEqual(related, 0.3)
        self.assertLess(unrelated, 0.2)
        self.assertGreater(related, unrelated)


class KeywordIndexTest(unittest.TestCase):
    def setUp(self):
        self.index = KeywordIndex().build(
            [
                (1, "Database Lock 이전에 모든 Query가 해소되었는지 확인한다."),
                (2, "External Data 전달 시 파일을 암호화하고 Password는 별도 Email로 전달한다."),
                (3, "교육 이수 기록은 5년간 보관한다."),
            ]
        )

    def test_abbreviation_matches_full_form(self):
        query = expand_query("DBL 확인", DEFAULT_SYNONYMS)
        top = self.index.search(query, top_k=1)
        self.assertEqual(top[0][0], 1)

    def test_keyword_search_ranks_relevant_chunk(self):
        top = self.index.search("파일 암호화 Password", top_k=1)
        self.assertEqual(top[0][0], 2)

    def test_no_match_returns_empty(self):
        self.assertEqual(self.index.search("법인카드 한도", top_k=3), [])


class VectorStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        self.embedder = HashingEmbedder(128)

    def tearDown(self):
        self.temp.cleanup()

    def _fill(self) -> VectorStore:
        store = VectorStore(self.dir)
        store.embedder_name = self.embedder.name
        texts = ["DB Lock 확인 항목", "외부 데이터 암호화 전달", "교육 이수 기록 보관"]
        store.add([10, 20, 30], self.embedder.encode_documents(texts))
        store.save()
        return store

    def test_index_survives_restart(self):
        self._fill()
        reopened = VectorStore(self.dir)   # 프로그램 재시작 상황
        self.assertEqual(len(reopened), 3)
        self.assertEqual(reopened.embedder_name, self.embedder.name)
        hits = reopened.search(self.embedder.encode_query("DB Lock 확인"), top_k=1)
        self.assertEqual(hits[0][0], 10)

    def test_remove_deletes_vectors(self):
        store = self._fill()
        self.assertEqual(store.remove([10]), 1)
        store.save()
        self.assertEqual(len(VectorStore(self.dir)), 2)

    def test_dimension_mismatch_rejected(self):
        store = self._fill()
        with self.assertRaises(ValueError):
            store.add([40], [[0.1, 0.2]])


if __name__ == "__main__":
    unittest.main()


class ThresholdTest(unittest.TestCase):
    """Embedding 모델마다 유사도 분포가 다르므로 threshold가 모델을 따라가야 한다."""

    def _retriever(self, settings: Settings) -> Retriever:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        return Retriever(
            Database(root / "t.sqlite3"),
            VectorStore(root / "index"),
            HashingEmbedder(64),
            settings,
        )

    def test_auto_threshold_follows_embedder(self):
        retriever = self._retriever(Settings(score_threshold=0.0))
        self.assertAlmostEqual(retriever.effective_threshold, 0.30)

    def test_explicit_threshold_wins(self):
        retriever = self._retriever(Settings(score_threshold=0.62))
        self.assertAlmostEqual(retriever.effective_threshold, 0.62)
