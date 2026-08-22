"""원클릭 설치 스크립트(scripts/setup.py) 검증."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load_setup():
    spec = importlib.util.spec_from_file_location("setup_script", ROOT / "scripts" / "setup.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


setup = _load_setup()


@pytest.mark.parametrize(
    ("ram_gb", "expected"),
    [
        (0.0, "qwen2.5:3b-instruct"),  # 사양 확인 실패 시 가벼운 모델
        (4.0, "qwen2.5:3b-instruct"),
        (8.0, "qwen2.5:3b-instruct"),
        (13.9, "qwen2.5:3b-instruct"),
        (14.0, "qwen2.5:7b-instruct"),
        (32.0, "qwen2.5:7b-instruct"),
    ],
)
def test_model_is_chosen_by_ram(ram_gb: float, expected: str):
    assert setup.choose_llm_model(ram_gb) == expected


def test_detect_ram_returns_non_negative():
    assert setup.detect_ram_gb() >= 0.0


def test_free_disk_is_positive():
    assert setup.free_disk_gb(ROOT) > 0.0


def test_find_ollama_prefers_path(monkeypatch):
    monkeypatch.setattr(setup.shutil, "which", lambda name: "/custom/bin/ollama")
    assert setup.find_ollama() == "/custom/bin/ollama"


def test_find_ollama_returns_none_when_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(setup.shutil, "which", lambda name: None)
    monkeypatch.setattr(setup, "WINDOWS_OLLAMA_PATHS", (str(tmp_path / "none.exe"),))
    monkeypatch.setattr(setup, "MACOS_OLLAMA_PATHS", (str(tmp_path / "none"),))
    monkeypatch.setattr(setup, "LINUX_OLLAMA_PATHS", (str(tmp_path / "none"),))
    assert setup.find_ollama() is None


def test_find_ollama_falls_back_to_standard_location(monkeypatch, tmp_path):
    """PATH 에 없어도 표준 설치 위치에 있으면 찾아야 한다."""
    binary = tmp_path / "ollama"
    binary.write_text("", encoding="utf-8")
    monkeypatch.setattr(setup.shutil, "which", lambda name: None)
    monkeypatch.setattr(setup, "WINDOWS_OLLAMA_PATHS", (str(binary),))
    monkeypatch.setattr(setup, "MACOS_OLLAMA_PATHS", (str(binary),))
    monkeypatch.setattr(setup, "LINUX_OLLAMA_PATHS", (str(binary),))
    assert setup.find_ollama() == str(binary)


def test_download_failure_raises_setup_error(monkeypatch, tmp_path):
    """네트워크가 막혀 있으면 사용자가 읽을 수 있는 메시지로 중단해야 한다."""
    import urllib.error

    def boom(*args, **kwargs):
        raise urllib.error.URLError("403 Forbidden")

    monkeypatch.setattr(setup.urllib.request, "urlretrieve", boom)
    with pytest.raises(setup.SetupError) as exc:
        setup._download("https://example.invalid/x", tmp_path / "x")
    assert "인터넷 연결" in str(exc.value)


def test_installed_models_is_empty_without_server():
    """Ollama 가 없어도 예외를 던지지 않고 빈 목록을 돌려줘야 한다."""
    assert setup.installed_models("http://127.0.0.1:1") == []


def test_ollama_host_must_be_loopback():
    """설치 스크립트도 외부 호스트는 거부해야 한다(보안 요구사항 1.1)."""
    from app.llm import NonLocalHostError

    with pytest.raises(NonLocalHostError):
        setup.ollama_ready("http://example.com:11434")


def test_installer_files_exist():
    assert (ROOT / "설치.bat").exists()
    assert (ROOT / "setup.sh").exists()


def test_setup_script_has_no_external_ai_api():
    """설치 스크립트가 외부 AI API 를 부르지 않는지 확인(보안 요구사항 1.3)."""
    source = (ROOT / "scripts" / "setup.py").read_text(encoding="utf-8").lower()
    for banned in ("openai", "anthropic", "generativelanguage", "bedrock", "cohere"):
        assert banned not in source
