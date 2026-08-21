"""로깅 설정 (요구사항 17).

로그에는 문서 본문, 사용자 질문, AI 답변, 검색된 문장을 절대 남기지 않는다.
기록 항목: 시간 / 처리 성공·실패 / 문서 ID / 오류 코드 정도로 제한한다.
"""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler

from app.config import LOGS_DIR, ensure_directories

_LOGGER_NAME = "chatbot"
_configured = False

# 이 프로그램의 로그 메시지는 "key=value" 형태의 짧은 ASCII 문자열로만 작성한다.
# 아래 필터는 그 규칙을 강제하는 최종 방어선이다.
#   - 한글이 포함된 메시지 = 문서 본문/질문이 섞여 들어온 것으로 간주
#   - 지나치게 긴 메시지  = 본문이 섞여 들어온 것으로 간주
_MAX_MESSAGE_LEN = 200
_TRUNCATE_TO = 100
_HANGUL = re.compile(r"[가-힣]")


class SensitiveDataFilter(logging.Filter):
    """문서 본문/질문으로 보이는 내용을 잘라내는 필터."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D102
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - 포맷 실패 시 로그를 버린다
            return False
        if len(message) > _MAX_MESSAGE_LEN or _HANGUL.search(message):
            record.msg = message[:_TRUNCATE_TO] + " ...[truncated]"
            record.args = ()
        return True


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    global _configured
    logger = logging.getLogger(_LOGGER_NAME)
    if _configured:
        return logger

    ensure_directories()
    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = RotatingFileHandler(
        LOGS_DIR / "app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(formatter)
    handler.addFilter(SensitiveDataFilter())
    logger.addHandler(handler)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.addFilter(SensitiveDataFilter())
    logger.addHandler(console)

    _configured = True
    return logger


def get_logger(name: str = "") -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"{_LOGGER_NAME}.{name}" if name else _LOGGER_NAME)
