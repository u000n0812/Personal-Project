"""로컬 백업 / 복원 (요구사항 19).

data/ 아래의 문서 원본, Vector Index, SQLite DB, 설정을 하나의 zip 으로 묶는다.
자동 Cloud Backup 은 구현하지 않는다. 저장 위치는 항상 로컬 디스크다.
"""

from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path

from app.config import (
    BACKUP_DIR,
    CONFIG_PATH,
    DATA_DIR,
    DATABASE_DIR,
    DOCUMENTS_DIR,
    INDEX_DIR,
    SYNONYMS_PATH,
    ensure_directories,
)
from app.logging_setup import get_logger

logger = get_logger("backup")

BACKUP_TARGETS = (DOCUMENTS_DIR, INDEX_DIR, DATABASE_DIR)


def create_backup(destination: Path | None = None) -> Path:
    """백업 zip 을 만들고 경로를 반환한다."""
    ensure_directories()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = Path(destination) if destination else BACKUP_DIR / f"backup_{stamp}.zip"
    target.parent.mkdir(parents=True, exist_ok=True)

    file_count = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for folder in BACKUP_TARGETS:
            if not folder.exists():
                continue
            for path in folder.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(DATA_DIR).as_posix())
                    file_count += 1
        for extra in (CONFIG_PATH, SYNONYMS_PATH):
            if extra.exists():
                archive.write(extra, extra.relative_to(DATA_DIR).as_posix())
                file_count += 1

    logger.info("backup created | files=%s size=%s", file_count, target.stat().st_size)
    return target


def restore_backup(archive_path: Path, *, overwrite: bool = False) -> int:
    """백업 zip 을 data/ 로 복원한다. 복원 후 프로그램 재시작을 권장한다."""
    archive_path = Path(archive_path)
    if not archive_path.exists():
        raise FileNotFoundError(f"백업 파일을 찾을 수 없습니다: {archive_path}")

    ensure_directories()
    restored = 0
    with zipfile.ZipFile(archive_path) as archive:
        for name in archive.namelist():
            # zip slip 방지: data/ 밖으로 나가는 경로는 무시한다.
            target = (DATA_DIR / name).resolve()
            if DATA_DIR.resolve() not in target.parents:
                logger.warning("backup entry skipped | reason=path_outside_data")
                continue
            if target.exists() and not overwrite:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as source, open(target, "wb") as handle:
                handle.write(source.read())
            restored += 1

    logger.info("backup restored | files=%s", restored)
    return restored


def list_backups() -> list[Path]:
    ensure_directories()
    return sorted(BACKUP_DIR.glob("backup_*.zip"), reverse=True)
