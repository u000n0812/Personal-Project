"""GuideBot - 사내 지침문서 Local RAG 챗봇.

모든 처리는 로컬 PC 내부에서만 수행한다(외부 AI API 사용 금지).
"""

from . import security as _security

# 어떤 모듈보다 먼저 telemetry/자동 다운로드 차단 환경변수를 적용한다.
_security.apply_offline_env()

__version__ = "1.0.0"
