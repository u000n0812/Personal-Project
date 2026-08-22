"""Phase 2~3: 문서명 해석과 구조 기반 Chunk 분할 검증."""

import unittest

from sopbot.chunk import build_embedding_text, chunk_blocks, detect_heading
from sopbot.extract import Block
from sopbot.naming import is_newer_version, parse_doc_name


class NamingTest(unittest.TestCase):
    def test_parse_version_from_file_name(self):
        cases = {
            "SOP_DataManagement_v1.1.pdf": ("sop_datamanagement", "1.1"),
            "SOP_DataManagement_v2.0.pdf": ("sop_datamanagement", "2.0"),
            "External Data Transfer Specification v2.1.docx": (
                "external_data_transfer_specification",
                "2.1",
            ),
            "업무절차서_rev3.txt": ("업무절차서", "3"),
        }
        for file_name, (doc_key, version) in cases.items():
            with self.subTest(file_name=file_name):
                parsed_key, parsed_version, _ = parse_doc_name(file_name)
                self.assertEqual(parsed_key, doc_key)
                self.assertEqual(parsed_version, version)

    def test_missing_version_defaults(self):
        _, version, title = parse_doc_name("데이터관리지침.pdf")
        self.assertEqual(version, "1.0")
        self.assertEqual(title, "데이터관리지침")

    def test_version_comparison(self):
        self.assertTrue(is_newer_version("2.0", "1.9"))
        self.assertTrue(is_newer_version("1.10", "1.9"))
        self.assertFalse(is_newer_version("1.0", "1.0"))


class HeadingTest(unittest.TestCase):
    def test_numbered_heading_detected(self):
        found, level, text = detect_heading("5.3 Data Transfer")
        self.assertTrue(found)
        self.assertEqual(level, 2)
        self.assertEqual(text, "5.3 Data Transfer")

    def test_sentence_is_not_heading(self):
        self.assertFalse(detect_heading("승인은 Project Manager가 수행한다.")[0])
        self.assertFalse(detect_heading("1. 이 절차는 모든 담당자가 반드시 따라야 하는 내용이다.")[0])

    def test_english_upper_heading(self):
        self.assertTrue(detect_heading("DATA TRANSFER PROCEDURE")[0])


class ChunkTest(unittest.TestCase):
    def setUp(self):
        self.blocks = [
            Block("External Data Transfer Specification", 1, "heading", 1),
            Block("5.3 Data Transfer", 1),
            Block("Data Provider는 파일을 암호화하여 전달한다. " * 20, 1),
            Block("Password는 별도 Email로 전달한다.", 2),
            Block("6. 승인", 2),
            Block("승인은 Project Manager가 수행한다.", 3),
        ]

    def test_chunk_metadata_preserved(self):
        chunks = chunk_blocks(self.blocks, chunk_size=300, overlap=60, doc_title="EDT Spec")
        self.assertGreater(len(chunks), 1)
        for index, chunk in enumerate(chunks):
            self.assertEqual(chunk.chunk_index, index)
            self.assertTrue(chunk.section)
            self.assertTrue(chunk.heading_path.startswith("EDT Spec"))
            self.assertGreaterEqual(chunk.page_end, chunk.page_start)

    def test_section_boundary_splits_chunks(self):
        chunks = chunk_blocks(self.blocks, chunk_size=2000, overlap=0, doc_title="EDT Spec")
        sections = {chunk.section for chunk in chunks}
        self.assertIn("5.3 Data Transfer", sections)
        self.assertIn("6. 승인", sections)

    def test_chunk_size_respected(self):
        chunks = chunk_blocks(self.blocks, chunk_size=300, overlap=50, doc_title="EDT Spec")
        for chunk in chunks:
            self.assertLessEqual(len(chunk.text), 300 + 120)

    def test_overlap_keeps_context(self):
        long_block = [Block("문장 하나가 반복된다. " * 120, 1)]
        chunks = chunk_blocks(long_block, chunk_size=400, overlap=100, doc_title="Doc")
        self.assertGreater(len(chunks), 1)
        self.assertTrue(chunks[1].text.startswith("문장 하나가"))

    def test_embedding_text_includes_structure(self):
        chunks = chunk_blocks(self.blocks, chunk_size=300, overlap=50, doc_title="EDT Spec")
        text = build_embedding_text(chunks[0], doc_title="EDT Spec", version="2.1")
        self.assertIn("EDT Spec", text)
        self.assertIn("v2.1", text)


if __name__ == "__main__":
    unittest.main()
