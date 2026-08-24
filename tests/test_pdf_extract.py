"""PDF 등록 실패 원인별 동작 검증 (암호 보호 / 텍스트 없음 / 텍스트 적음)."""

import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from guidebot.extract import ExtractionError, _pdf_read_error_message, extract_document

try:
    import pypdf

    PYPDF_AVAILABLE = True
except ImportError:  # pragma: no cover
    PYPDF_AVAILABLE = False

PLAIN_PDF_B64 = 'JVBERi0xLjMKJenr8b8KMSAwIG9iago8PAovQ291bnQgMQovS2lkcyBbMyAwIFJdCi9NZWRpYUJveCBbMCAwIDU5NS4yOCA4NDEuODldCi9UeXBlIC9QYWdlcwo+PgplbmRvYmoKMiAwIG9iago8PAovT3BlbkFjdGlvbiBbMyAwIFIgL0ZpdEggbnVsbF0KL1BhZ2VMYXlvdXQgL09uZUNvbHVtbgovUGFnZXMgMSAwIFIKL1R5cGUgL0NhdGFsb2cKPj4KZW5kb2JqCjMgMCBvYmoKPDwKL0NvbnRlbnRzIDQgMCBSCi9QYXJlbnQgMSAwIFIKL1Jlc291cmNlcyA2IDAgUgovVHlwZSAvUGFnZQo+PgplbmRvYmoKNCAwIG9iago8PAovRmlsdGVyIC9GbGF0ZURlY29kZQovTGVuZ3RoIDEzMwo+PgpzdHJlYW0KeJxVzL0OgjAUhuGdq/hGHTy2JaUwasTB1XMDjRykpkFSEMPd+5M4uL558hqcMkXW4ZntGdujhjakFLhFzZ+Ua9IlXFVS8a4NVpZyHPzkwcn3YytpDb79Y2epyr+YO8GQ7nNoJGHsfIyQ/pKWYYLMkha0IQoeY+iv2NXnjbEF/X4vq5cp5wplbmRzdHJlYW0KZW5kb2JqCjUgMCBvYmoKPDwKL0Jhc2VGb250IC9IZWx2ZXRpY2EKL0VuY29kaW5nIC9XaW5BbnNpRW5jb2RpbmcKL1N1YnR5cGUgL1R5cGUxCi9UeXBlIC9Gb250Cj4+CmVuZG9iago2IDAgb2JqCjw8Ci9Gb250IDw8L0YxIDUgMCBSPj4KL1Byb2NTZXQgWy9QREYgL1RleHQgL0ltYWdlQiAvSW1hZ2VDIC9JbWFnZUldCj4+CmVuZG9iago3IDAgb2JqCjw8Ci9DcmVhdGlvbkRhdGUgKEQ6MjAyNjA4MjQwMDM5NDNaKQo+PgplbmRvYmoKeHJlZgowIDgKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDE1IDAwMDAwIG4gCjAwMDAwMDAxMDIgMDAwMDAgbiAKMDAwMDAwMDIwNSAwMDAwMCBuIAowMDAwMDAwMjg1IDAwMDAwIG4gCjAwMDAwMDA0OTAgMDAwMDAgbiAKMDAwMDAwMDU4NyAwMDAwMCBuIAowMDAwMDAwNjc0IDAwMDAwIG4gCnRyYWlsZXIKPDwKL1NpemUgOAovUm9vdCAyIDAgUgovSW5mbyA3IDAgUgovSUQgWzwyOTY5NkQ0NjhBRTNEQjNDMTZDQjQ1NzRCOTg4Qzg4Qj48Mjk2OTZENDY4QUUzREIzQzE2Q0I0NTc0Qjk4OEM4OEI+XQo+PgpzdGFydHhyZWYKNzI5CiUlRU9GCg=='
EMPTY_PW_PDF_B64 = 'JVBERi0xLjMKJeLjz9MKMSAwIG9iago8PAovUHJvZHVjZXIgPGVlNGVmNjEwMjA+Cj4+CmVuZG9iagoyIDAgb2JqCjw8Ci9UeXBlIC9QYWdlcwovQ291bnQgMQovS2lkcyBbIDQgMCBSIF0KPj4KZW5kb2JqCjMgMCBvYmoKPDwKL1R5cGUgL0NhdGFsb2cKL1BhZ2VzIDIgMCBSCj4+CmVuZG9iago0IDAgb2JqCjw8Ci9Db250ZW50cyA1IDAgUgovUmVzb3VyY2VzIDYgMCBSCi9UeXBlIC9QYWdlCi9NZWRpYUJveCBbIDAgMCA1OTUuMjggODQxLjg5IF0KL1BhcmVudCAyIDAgUgo+PgplbmRvYmoKNSAwIG9iago8PAovRmlsdGVyIC9GbGF0ZURlY29kZQovTGVuZ3RoIDEzMwo+PgpzdHJlYW0KmK5mLDQSlnv5oA+C5hog3rgAnZadiT9RgJcd/sfceoC7s7GAAr6gafOK+OhAQ5PYMDKheirifm3JHQhzR4n2sCSP+ig3+LPpqHPg/6h+c9f20ihE1t/3qKs3xeciXCZutqs4ThcUgfdqTFfXvpIMSTzmJgU6AUyYBsT8/won8LZaaRCMTAplbmRzdHJlYW0KZW5kb2JqCjYgMCBvYmoKPDwKL0ZvbnQgPDwKL0YxIDcgMCBSCj4+Ci9Qcm9jU2V0IFsgL1BERiAvVGV4dCAvSW1hZ2VCIC9JbWFnZUMgL0ltYWdlSSBdCj4+CmVuZG9iago3IDAgb2JqCjw8Ci9CYXNlRm9udCAvSGVsdmV0aWNhCi9FbmNvZGluZyAvV2luQW5zaUVuY29kaW5nCi9TdWJ0eXBlIC9UeXBlMQovVHlwZSAvRm9udAo+PgplbmRvYmoKOCAwIG9iago8PAovViAyCi9SIDMKL0xlbmd0aCAxMjgKL1AgNDI5NDk2NzI5MgovRmlsdGVyIC9TdGFuZGFyZAovTyA8MzY0NTFiZDM5ZDc1M2I3YzFkMTA5MjJjMjhlNjY2NWFhNGYzMzUzZmIwMzQ4YjUzNjg5M2UzYjFkYjVjNTc5Yj4KL1UgPGU0YWU4ZjY3OTM4NTdmNjk1YjgzNTQxZmZkYjRiMTAxMjhiZjRlNWU0ZTc1OGE0MTY0MDA0ZTU2ZmZmYTAxMDg+Cj4+CmVuZG9iagp4cmVmCjAgOQowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAwMTUgMDAwMDAgbiAKMDAwMDAwMDA1OSAwMDAwMCBuIAowMDAwMDAwMTE4IDAwMDAwIG4gCjAwMDAwMDAxNjcgMDAwMDAgbiAKMDAwMDAwMDI3OSAwMDAwMCBuIAowMDAwMDAwNDg0IDAwMDAwIG4gCjAwMDAwMDA1NzUgMDAwMDAgbiAKMDAwMDAwMDY3MiAwMDAwMCBuIAp0cmFpbGVyCjw8Ci9TaXplIDkKL1Jvb3QgMyAwIFIKL0luZm8gMSAwIFIKL0lEIFsgPDYyMzAzNDY2NjQzOTY2NjQzNTY1NjIzNDMyMzE2MzMxMzMzMjM4MzUzNDM2NjYzMTMzMzQzMzMxMzA2NDMwMzM+IDw2MjMwMzQ2NjY0Mzk2NjY0MzU2NTYyMzQzMjMxNjMzMTMzMzIzODM1MzQzNjY2MzEzMzM0MzMzMTMwNjQzMDMzPiBdCi9FbmNyeXB0IDggMCBSCj4+CnN0YXJ0eHJlZgo4ODcKJSVFT0YK'
REAL_PW_PDF_B64 = 'JVBERi0xLjMKJeLjz9MKMSAwIG9iago8PAovUHJvZHVjZXIgPDc3YzY1ZmY2NjM+Cj4+CmVuZG9iagoyIDAgb2JqCjw8Ci9UeXBlIC9QYWdlcwovQ291bnQgMQovS2lkcyBbIDQgMCBSIF0KPj4KZW5kb2JqCjMgMCBvYmoKPDwKL1R5cGUgL0NhdGFsb2cKL1BhZ2VzIDIgMCBSCj4+CmVuZG9iago0IDAgb2JqCjw8Ci9Db250ZW50cyA1IDAgUgovUmVzb3VyY2VzIDYgMCBSCi9UeXBlIC9QYWdlCi9NZWRpYUJveCBbIDAgMCA1OTUuMjggODQxLjg5IF0KL1BhcmVudCAyIDAgUgo+PgplbmRvYmoKNSAwIG9iago8PAovRmlsdGVyIC9GbGF0ZURlY29kZQovTGVuZ3RoIDEzMwo+PgpzdHJlYW0KNo7VvRBt3RpHBnyndnWugIdrIIOm0BXSphkQURhmjgacyY6G7Ym3QMy7psaJOVxFyR+NCe+NU2Jlr0zxpDxuz8oI5AD4kHQogjaxxNbOG2CLvllQGsD8dqAVClWEkYDnPZ83F+tZPrxr1efHQCdUApxGwEDQS7+uPLwqYbAbliuR5u3HWgplbmRzdHJlYW0KZW5kb2JqCjYgMCBvYmoKPDwKL0ZvbnQgPDwKL0YxIDcgMCBSCj4+Ci9Qcm9jU2V0IFsgL1BERiAvVGV4dCAvSW1hZ2VCIC9JbWFnZUMgL0ltYWdlSSBdCj4+CmVuZG9iago3IDAgb2JqCjw8Ci9CYXNlRm9udCAvSGVsdmV0aWNhCi9FbmNvZGluZyAvV2luQW5zaUVuY29kaW5nCi9TdWJ0eXBlIC9UeXBlMQovVHlwZSAvRm9udAo+PgplbmRvYmoKOCAwIG9iago8PAovViAyCi9SIDMKL0xlbmd0aCAxMjgKL1AgNDI5NDk2NzI5MgovRmlsdGVyIC9TdGFuZGFyZAovTyA8NmFjNDdkOTQ5MGRjNjBjNzc1YmRlNWM0MDQ3OWU0NDEyODZmMzY0MDlkOTM1ZTNlMGM4Y2NlNDYwZTk1NzZhND4KL1UgPGQzOTcwOWI1Yzk2YzM1ZDNkYThiODQzMWFlYTg1YzZhMjhiZjRlNWU0ZTc1OGE0MTY0MDA0ZTU2ZmZmYTAxMDg+Cj4+CmVuZG9iagp4cmVmCjAgOQowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAwMTUgMDAwMDAgbiAKMDAwMDAwMDA1OSAwMDAwMCBuIAowMDAwMDAwMTE4IDAwMDAwIG4gCjAwMDAwMDAxNjcgMDAwMDAgbiAKMDAwMDAwMDI3OSAwMDAwMCBuIAowMDAwMDAwNDg0IDAwMDAwIG4gCjAwMDAwMDA1NzUgMDAwMDAgbiAKMDAwMDAwMDY3MiAwMDAwMCBuIAp0cmFpbGVyCjw8Ci9TaXplIDkKL1Jvb3QgMyAwIFIKL0luZm8gMSAwIFIKL0lEIFsgPDYyMzAzNDY2NjQzOTY2NjQzNTY1NjIzNDMyMzE2MzMxMzMzMjM4MzUzNDM2NjYzMTMzMzQzMzMxMzA2NDMwMzM+IDw2MjMwMzQ2NjY0Mzk2NjY0MzU2NTYyMzQzMjMxNjMzMTMzMzIzODM1MzQzNjY2MzEzMzM0MzMzMTMwNjQzMDMzPiBdCi9FbmNyeXB0IDggMCBSCj4+CnN0YXJ0eHJlZgo4ODcKJSVFT0YK'


def write_pdf(directory: Path, name: str, data_b64: str) -> Path:
    path = directory / name
    path.write_bytes(base64.b64decode(data_b64))
    return path


@unittest.skipUnless(PYPDF_AVAILABLE, "pypdf가 설치되지 않아 PDF 테스트를 건너뜁니다.")
class PdfExtractionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_normal_pdf_extracted(self):
        path = write_pdf(self.dir, "plain.pdf", PLAIN_PDF_B64)
        document = extract_document(path)
        text = document.text
        self.assertIn("AES-256", text)
        self.assertEqual(document.warning, "")

    def test_empty_password_pdf_is_registered(self):
        """빈 암호로 보호된 사내 PDF도 등록되어야 한다."""
        path = write_pdf(self.dir, "empty_pw.pdf", EMPTY_PW_PDF_B64)
        document = extract_document(path)
        self.assertIn("AES-256", document.text)

    def test_password_protected_pdf_reports_reason(self):
        path = write_pdf(self.dir, "real_pw.pdf", REAL_PW_PDF_B64)
        with self.assertRaises(ExtractionError) as caught:
            extract_document(path)
        self.assertIn("암호", str(caught.exception))

    def test_image_only_pdf_reports_ocr_guidance(self):
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=595, height=842)
        writer.add_blank_page(width=595, height=842)
        path = self.dir / "scanned.pdf"
        with open(path, "wb") as handle:
            writer.write(handle)

        with self.assertRaises(ExtractionError) as caught:
            extract_document(path)
        message = str(caught.exception)
        self.assertIn("텍스트를 찾지 못했습니다", message)
        self.assertIn("OCR", message)
        self.assertIn("2쪽", message)   # 진단에 필요한 실제 수치를 알려준다

    def test_sparse_pdf_registers_with_warning(self):
        """글자가 적어도 최소 기준을 넘으면 등록하되 경고를 남긴다."""
        reader = pypdf.PdfReader(str(write_pdf(self.dir, "src.pdf", PLAIN_PDF_B64)))
        writer = pypdf.PdfWriter()
        writer.add_page(reader.pages[0])
        for _ in range(8):   # 빈 페이지를 덧붙여 페이지당 글자 수를 낮춘다
            writer.add_blank_page(width=595, height=842)
        path = self.dir / "sparse.pdf"
        with open(path, "wb") as handle:
            writer.write(handle)

        document = extract_document(path)
        self.assertTrue(document.warning, "텍스트가 적으면 경고가 있어야 한다")
        self.assertIn("텍스트가 적게", document.warning)

    def test_missing_cryptography_dependency_gives_actionable_message(self):
        """cryptography 미설치로 AES 복호화가 실패하는 상황을 흉내낸다.

        실제로는 pypdf.errors.DependencyError가 나지만, 이 환경에는
        cryptography가 설치돼 있으므로 reader.pages 접근 자체를 모킹해
        같은 상황(페이지 접근 시 예외)을 재현한다.
        """

        class FakeDependencyError(Exception):
            pass

        mock_pages = MagicMock()
        mock_pages.__len__.side_effect = FakeDependencyError(
            "cryptography>=3.1 is required for AES algorithm"
        )
        mock_reader = MagicMock(is_encrypted=False, pages=mock_pages)

        path = write_pdf(self.dir, "aes.pdf", PLAIN_PDF_B64)   # 내용은 모킹되므로 무관
        with patch("pypdf.PdfReader", return_value=mock_reader):
            with self.assertRaises(ExtractionError) as caught:
                extract_document(path)

        message = str(caught.exception)
        self.assertIn("cryptography", message)
        self.assertIn("pip install cryptography", message)

    def test_pdf_read_error_message_detects_dependency_error_by_class_name(self):
        """메시지에 'cryptography'가 없어도 예외 클래스명이 DependencyError면 안내한다."""

        class DependencyError(Exception):
            pass

        message = _pdf_read_error_message(DependencyError("some backend missing"))
        self.assertIn("pip install cryptography", message)

    def test_other_pdf_errors_get_generic_message(self):
        message = _pdf_read_error_message(ValueError("unexpected EOF"))
        self.assertNotIn("cryptography", message)
        self.assertIn("PDF를 읽는 중 오류", message)


if __name__ == "__main__":
    unittest.main()
