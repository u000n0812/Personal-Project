"""로컬 백업 / 복원.

backup/ 폴더에 zip 파일로 내보낸다. 자동 Cloud Backup은 구현하지 않는다.
"""

from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path

from .config import BACKUP_DIR, DATA_DIR, ensure_dirs
from .logging_setup import get_logger

logger = get_logger("backup")

# 로그는 민감정보가 없더라도 백업 대상에서 제외한다.
_EXCLUDE_DIRS = {"logs", "cache"}


def create_backup(target_dir: Path | str | None = None) -> Path:
    """data 폴더 전체(문서·Index·DB·설정)를 zip으로 내보낸다."""
    ensure_dirs()
    target_dir = Path(target_dir) if target_dir else BACKUP_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = target_dir / f"sopbot_backup_{stamp}.zip"

    file_count = 0
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(DATA_DIR.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(DATA_DIR)
            if relative.parts and relative.parts[0] in _EXCLUDE_DIRS:
                continue
            archive.write(path, arcname=str(relative))
            file_count += 1
    logger.info("backup created: files=%d", file_count)
    return archive_path


def restore_backup(archive_path: Path | str, target_dir: Path | str | None = None) -> int:
    """백업 zip을 data 폴더로 되돌린다(기존 파일은 덮어쓴다)."""
    archive_path = Path(archive_path)
    target = Path(target_dir) if target_dir else DATA_DIR
    if not archive_path.exists():
        raise FileNotFoundError(f"백업 파일을 찾을 수 없습니다: {archive_path}")
    target.mkdir(parents=True, exist_ok=True)
    restored = 0
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.namelist():
            # zip slip 방지: 대상 폴더 밖으로 나가는 경로는 건너뛴다.
            destination = (target / member).resolve()
            if not str(destination).startswith(str(target.resolve())):
                logger.error("backup member skipped (path escape)")
                continue
            archive.extract(member, target)
            restored += 1
    logger.info("backup restored: files=%d", restored)
    return restored


def list_backups(target_dir: Path | str | None = None) -> list[Path]:
    target_dir = Path(target_dir) if target_dir else BACKUP_DIR
    if not target_dir.exists():
        return []
    return sorted(target_dir.glob("sopbot_backup_*.zip"), reverse=True)
