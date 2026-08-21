"""로컬 모델 준비 스크립트 (최초 1회만 인터넷 필요).

임베딩 모델 파일을 ``data/models`` 아래에 내려받아 둔다.
이후 프로그램은 오프라인 상태에서 이 파일만 읽어 동작한다.

    python scripts/prepare_models.py
    python scripts/prepare_models.py --embedding intfloat/multilingual-e5-base

주의: 이 스크립트는 모델 다운로드를 위해 네트워크 차단 가드를 사용하지 않는다.
      다운로드가 끝나면 인터넷을 끊은 상태에서 프로그램을 사용할 수 있다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import netguard  # noqa: E402
from app.config import MODELS_DIR, load_settings  # noqa: E402


def download_embedding(model_name: str) -> int:
    # 다운로드 동안에는 오프라인 환경변수를 해제한다.
    netguard.apply_offline_env(offline=False)
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("[오류] sentence-transformers 가 설치되어 있지 않습니다.")
        print("       pip install -r requirements.txt")
        return 1

    print(f"임베딩 모델 다운로드: {model_name}")
    print(f"저장 위치: {MODELS_DIR}")
    try:
        model = SentenceTransformer(model_name, cache_folder=str(MODELS_DIR))
    except Exception as exc:
        print(f"[실패] {type(exc).__name__}: {exc}")
        return 1

    vector = model.encode(["테스트 문장입니다."], normalize_embeddings=True)
    print(f"[완료] 차원={vector.shape[1]}")
    return 0


def main() -> int:
    settings = load_settings()
    parser = argparse.ArgumentParser(description="로컬 모델 준비")
    parser.add_argument("--embedding", default=settings.embedding_model)
    args = parser.parse_args()

    code = download_embedding(args.embedding)

    print()
    print("다음으로 로컬 LLM 을 준비하세요 (Ollama).")
    print("  1) https://ollama.com 에서 Ollama 설치")
    print(f"  2) ollama pull {settings.llm_model}")
    print("  3) ollama serve   (설치 시 자동 실행되는 경우도 있음)")
    print()
    print("준비가 끝나면 인터넷을 끊고 'python run_app.py' 로 실행할 수 있습니다.")
    return code


if __name__ == "__main__":
    sys.exit(main())
