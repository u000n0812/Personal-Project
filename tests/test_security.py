"""보안 요구사항 테스트 (요구사항 1, 17, 19 / Phase 9)."""

import logging
import socket
import zipfile
from pathlib import Path

import pytest

from app import netguard
from app.backup import create_backup, list_backups, restore_backup
from app.llm import NonLocalHostError, OllamaClient
from app.logging_setup import SensitiveDataFilter


@pytest.fixture
def guard():
    netguard.install()
    yield
    netguard.uninstall()


def test_outbound_connection_is_blocked(guard):
    with pytest.raises(netguard.OutboundNetworkBlocked):
        socket.create_connection(("api.openai.com", 443), timeout=1)
    with pytest.raises(netguard.OutboundNetworkBlocked):
        socket.socket().connect(("8.8.8.8", 53))


def test_loopback_connection_is_allowed(guard):
    # 로컬 LLM 통신 경로는 막히지 않아야 한다(연결 거부는 정상, 차단 예외는 비정상).
    with pytest.raises(OSError) as excinfo:
        socket.create_connection(("127.0.0.1", 1), timeout=1)
    assert not isinstance(excinfo.value, netguard.OutboundNetworkBlocked)


def test_guard_can_be_uninstalled_for_model_download():
    netguard.install()
    assert netguard.is_installed()
    netguard.uninstall()
    assert not netguard.is_installed()


def test_offline_env_disables_telemetry():
    import os

    netguard.apply_offline_env(offline=True)
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["HF_HUB_DISABLE_TELEMETRY"] == "1"
    assert os.environ["DO_NOT_TRACK"] == "1"
    assert os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] == "false"


def test_llm_client_rejects_non_local_host():
    with pytest.raises(NonLocalHostError):
        OllamaClient("http://api.example.com:11434")
    OllamaClient("http://127.0.0.1:11434")  # 정상


def test_log_filter_truncates_document_content():
    record = logging.LogRecord(
        name="chatbot",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Data Provider 는 파일을 반드시 암호화하여 전달하고 비밀번호는 별도 메일로 보낸다" * 3,
        args=(),
        exc_info=None,
    )
    assert SensitiveDataFilter().filter(record) is True
    assert record.getMessage().endswith("...[truncated]")
    assert len(record.getMessage()) < 400


def test_backup_contains_database_and_documents(index, sample_dir):
    index.ingest_folder(sample_dir)
    archive_path = create_backup()
    assert archive_path.exists()
    assert archive_path in list_backups()

    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
    assert any(name.startswith("database/") for name in names)
    assert any(name.startswith("documents/") for name in names)
    assert any(name.startswith("index/") for name in names)


def test_restore_rejects_path_outside_data_dir(tmp_path: Path):
    malicious = tmp_path / "evil.zip"
    with zipfile.ZipFile(malicious, "w") as archive:
        archive.writestr("../../evil.txt", "x")
    assert restore_backup(malicious, overwrite=True) == 0
