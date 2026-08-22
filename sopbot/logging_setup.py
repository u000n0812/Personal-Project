"""로그 설정.

보안 원칙(요구사항 17): 로그에는 문서 본문이나 사용자 질문을 남기지 않는다.
시간 / 처리 성공·실패 / 문서 ID / 오류 코드 수준만 기록한다.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .config import LOGS_DIR, ensure_dirs

_CONFIGURED = False

# 실수로 본문이 로그에 들어가는 것을 막기 위한 최대 길이
MAX_MESSAGE_LEN = 300


class _TruncateFilter(logging.Filter):
    """로그 메시지가 지나치게 길면 잘라낸다(민감정보 유출 방지)."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if len(message) > MAX_MESSAGE_LEN:
            record.msg = message[:MAX_MESSAGE_LEN] + "...[truncated]"
            record.args = ()
        return True


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """파일 + 콘솔 로거를 준비한다(중복 설정 방지)."""
    global _CONFIGURED
    logger = logging.getLogger("sopbot")
    if _CONFIGURED:
        return logger

    ensure_dirs()
    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    file_handler = RotatingFileHandler(
        LOGS_DIR / "sopbot.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(_TruncateFilter())
    logger.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.addFilter(_TruncateFilter())
    logger.addHandler(console)

    _CONFIGURED = True
    return logger


def get_logger(name: str = "sopbot") -> logging.Logger:
    setup_logging()
    return logging.getLogger(name if name.startswith("sopbot") else f"sopbot.{name}")
