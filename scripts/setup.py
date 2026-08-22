"""원클릭 자동 설치 스크립트.

사용자가 판단할 항목 없이 아래를 순서대로 자동 처리한다.

    1) PC 사양(RAM) 확인 → 적합한 LLM 모델 자동 선택
    2) Ollama 설치 여부 확인 → 없으면 자동 설치
    3) Ollama 서버 기동
    4) LLM 모델 자동 다운로드
    5) 임베딩 모델 자동 다운로드
    6) 설치 결과 검증

이 스크립트는 모델을 내려받아야 하므로 네트워크 차단 가드를 켜지 않는다.
설치가 끝나면 인터넷을 끊은 상태에서 프로그램을 사용할 수 있다.

    python scripts/setup.py
    python scripts/setup.py --model qwen2.5:3b-instruct   # 모델 직접 지정
    python scripts/setup.py --skip-ollama                 # LLM 설치 건너뛰기
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import netguard  # noqa: E402
from app.config import MODELS_DIR, load_settings, save_settings  # noqa: E402

TOTAL_STEPS = 6

# RAM 하한(GB) → 사용할 모델. 위에서부터 처음 만족하는 항목을 쓴다.
MODEL_BY_RAM: tuple[tuple[float, str], ...] = (
    (14.0, "qwen2.5:7b-instruct"),
    (0.0, "qwen2.5:3b-instruct"),
)

OLLAMA_WINDOWS_URL = "https://ollama.com/download/OllamaSetup.exe"
OLLAMA_MACOS_URL = "https://ollama.com/download/Ollama-darwin.zip"
OLLAMA_LINUX_SCRIPT = "https://ollama.com/install.sh"

# Ollama 가 설치될 수 있는 표준 위치(PATH 에 아직 안 잡혔을 때 탐색용)
WINDOWS_OLLAMA_PATHS = (
    r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe",
    r"%PROGRAMFILES%\Ollama\ollama.exe",
)
MACOS_OLLAMA_PATHS = (
    "/Applications/Ollama.app/Contents/Resources/ollama",
    "/usr/local/bin/ollama",
    "/opt/homebrew/bin/ollama",
)
LINUX_OLLAMA_PATHS = ("/usr/local/bin/ollama", "/usr/bin/ollama")


class SetupError(RuntimeError):
    """설치 도중 사용자가 조치해야 하는 오류."""


# ---------------------------------------------------------------------------
# 출력 도우미
# ---------------------------------------------------------------------------
def step(number: int, title: str) -> None:
    print()
    print("=" * 68)
    print(f" [{number}/{TOTAL_STEPS}] {title}")
    print("=" * 68)


def info(message: str) -> None:
    print(f"  {message}")


def warn(message: str) -> None:
    print(f"  [주의] {message}")


# ---------------------------------------------------------------------------
# 1) PC 사양 확인
# ---------------------------------------------------------------------------
def detect_ram_gb() -> float:
    """설치된 물리 메모리를 GB 로 반환한다. 확인 불가 시 0.0."""
    system = platform.system()
    try:
        if system == "Windows":
            import ctypes

            class MemoryStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatusEx()
            status.dwLength = ctypes.sizeof(MemoryStatusEx)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return status.ullTotalPhys / (1024**3)

        if system == "Darwin":
            out = subprocess.run(
                ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=10
            )
            return int(out.stdout.strip()) / (1024**3)

        meminfo = Path("/proc/meminfo").read_text(encoding="utf-8")
        for line in meminfo.splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) / (1024**2)
    except Exception:  # 사양 확인 실패는 설치를 막을 이유가 아니다
        pass
    return 0.0


def choose_llm_model(ram_gb: float) -> str:
    for minimum, model in MODEL_BY_RAM:
        if ram_gb >= minimum:
            return model
    return MODEL_BY_RAM[-1][1]


def free_disk_gb(path: Path) -> float:
    try:
        return shutil.disk_usage(path).free / (1024**3)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# 2) Ollama 설치
# ---------------------------------------------------------------------------
def find_ollama() -> str | None:
    """설치된 ollama 실행 파일 경로를 찾는다."""
    found = shutil.which("ollama")
    if found:
        return found

    system = platform.system()
    if system == "Windows":
        candidates = [os.path.expandvars(p) for p in WINDOWS_OLLAMA_PATHS]
    elif system == "Darwin":
        candidates = list(MACOS_OLLAMA_PATHS)
    else:
        candidates = list(LINUX_OLLAMA_PATHS)

    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def _download(url: str, target: Path) -> None:
    """진행률을 보여주며 파일을 내려받는다."""
    info(f"다운로드: {url}")

    def hook(block_num: int, block_size: int, total_size: int) -> None:
        if total_size <= 0:
            return
        done = min(block_num * block_size, total_size)
        percent = done * 100 / total_size
        print(
            f"\r    {percent:5.1f}%  ({done / 1024**2:,.0f} / {total_size / 1024**2:,.0f} MB)",
            end="",
            flush=True,
        )

    try:
        urllib.request.urlretrieve(url, target, reporthook=hook)
    except urllib.error.URLError as exc:
        raise SetupError(
            f"다운로드에 실패했습니다: {exc.reason}\n"
            "       인터넷 연결(또는 회사 방화벽/프록시)을 확인해 주세요."
        ) from exc
    print()


def install_ollama() -> str:
    """플랫폼별로 Ollama 를 자동 설치하고 실행 파일 경로를 반환한다."""
    system = platform.system()

    if system == "Windows":
        with tempfile.TemporaryDirectory() as tmp:
            installer = Path(tmp) / "OllamaSetup.exe"
            _download(OLLAMA_WINDOWS_URL, installer)
            info("설치 실행 중... (수 분 걸릴 수 있습니다)")
            # Inno Setup 계열 → /VERYSILENT, 구버전 NSIS → /S
            for flags in (["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], ["/S"]):
                result = subprocess.run([str(installer), *flags], timeout=1800)
                if result.returncode == 0:
                    break
            else:
                raise SetupError("Ollama 설치 프로그램이 정상 종료하지 않았습니다.")

    elif system == "Darwin":
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "Ollama-darwin.zip"
            _download(OLLAMA_MACOS_URL, archive)
            info("/Applications 에 설치 중...")
            with zipfile.ZipFile(archive) as zf:
                zf.extractall("/Applications")
            binary = Path(MACOS_OLLAMA_PATHS[0])
            if binary.exists():
                binary.chmod(0o755)

    else:  # Linux
        info("공식 설치 스크립트 실행 중...")
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "install.sh"
            _download(OLLAMA_LINUX_SCRIPT, script)
            result = subprocess.run(["sh", str(script)], timeout=1800)
            if result.returncode != 0:
                raise SetupError(
                    "Ollama 설치 스크립트가 실패했습니다. sudo 권한이 필요할 수 있습니다."
                )

    exe = find_ollama()
    if not exe:
        raise SetupError(
            "설치는 끝났지만 ollama 실행 파일을 찾지 못했습니다.\n"
            "       터미널을 새로 연 뒤 이 스크립트를 다시 실행해 주세요."
        )
    return exe


# ---------------------------------------------------------------------------
# 3) Ollama 서버 기동
# ---------------------------------------------------------------------------
def ollama_ready(host: str) -> bool:
    from app.llm import OllamaClient

    return OllamaClient(host=host, timeout=5).health()


def start_ollama_serve(exe: str, host: str, wait_seconds: int = 60) -> bool:
    """ollama serve 를 백그라운드로 띄우고 응답할 때까지 기다린다."""
    if ollama_ready(host):
        info("이미 실행 중입니다.")
        return True

    info("ollama serve 기동 중...")
    kwargs: dict = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if platform.system() == "Windows":
        # 콘솔 창을 새로 띄우지 않고 백그라운드로 유지
        kwargs["creationflags"] = 0x00000008 | 0x08000000  # DETACHED | NO_WINDOW
    else:
        kwargs["start_new_session"] = True

    try:
        subprocess.Popen([exe, "serve"], **kwargs)
    except OSError as exc:
        warn(f"자동 기동 실패: {exc}")
        return False

    for _ in range(wait_seconds):
        if ollama_ready(host):
            info("서버 응답 확인.")
            return True
        time.sleep(1)
    return False


# ---------------------------------------------------------------------------
# 4) LLM 모델 다운로드
# ---------------------------------------------------------------------------
def installed_models(host: str) -> list[str]:
    from app.llm import OllamaClient

    try:
        return OllamaClient(host=host, timeout=10).list_models()
    except Exception:
        return []


def pull_model(exe: str, model: str, host: str) -> None:
    if model in installed_models(host):
        info(f"이미 준비됨: {model}")
        return

    info(f"모델 다운로드: {model}  (수 GB, 시간이 걸립니다)")
    result = subprocess.run([exe, "pull", model], timeout=7200)
    if result.returncode != 0:
        raise SetupError(
            f"모델 다운로드에 실패했습니다: {model}\n"
            f"       터미널에서 'ollama pull {model}' 을 직접 실행해 확인해 주세요."
        )


# ---------------------------------------------------------------------------
# 5) 임베딩 모델 다운로드
# ---------------------------------------------------------------------------
def download_embedding(model_name: str) -> None:
    netguard.apply_offline_env(offline=False)
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise SetupError(
            "sentence-transformers 가 설치되어 있지 않습니다.\n"
            "       pip install -r requirements.txt 를 먼저 실행해 주세요."
        ) from exc

    info(f"임베딩 모델: {model_name}")
    info(f"저장 위치: {MODELS_DIR}")
    try:
        model = SentenceTransformer(model_name, cache_folder=str(MODELS_DIR))
        vector = model.encode(["테스트 문장입니다."], normalize_embeddings=True)
    except Exception as exc:
        raise SetupError(
            f"임베딩 모델 준비 실패: {type(exc).__name__}: {exc}\n"
            "       인터넷 연결(또는 회사 방화벽/프록시)을 확인해 주세요."
        ) from exc
    info(f"확인 완료 (차원={vector.shape[1]})")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> int:
    settings = load_settings()
    parser = argparse.ArgumentParser(description="사내 지침 챗봇 원클릭 설치")
    parser.add_argument("--model", help="사용할 LLM 모델 (미지정 시 PC 사양에 맞춰 자동 선택)")
    parser.add_argument("--embedding", default=settings.embedding_model)
    parser.add_argument("--skip-ollama", action="store_true", help="LLM 설치 단계를 건너뛴다")
    args = parser.parse_args()

    print()
    print("사내 지침 챗봇 - 자동 설치")
    print("이 단계에서만 인터넷이 필요하며, 이후에는 오프라인으로 동작합니다.")

    # --- 1) PC 사양 ---
    step(1, "PC 사양 확인")
    ram_gb = detect_ram_gb()
    disk_gb = free_disk_gb(ROOT)
    info(f"메모리     : {ram_gb:.1f} GB" if ram_gb else "메모리     : 확인 불가")
    info(f"여유 디스크: {disk_gb:.1f} GB")
    info(f"운영체제   : {platform.system()} {platform.release()}")

    llm_model = args.model or choose_llm_model(ram_gb)
    info(f"선택된 LLM : {llm_model}")
    if disk_gb and disk_gb < 8:
        warn(f"여유 공간이 부족할 수 있습니다(권장 8GB 이상, 현재 {disk_gb:.1f}GB).")

    # --- 2~4) Ollama ---
    if args.skip_ollama:
        step(2, "Ollama 설치 (건너뜀)")
        step(3, "Ollama 서버 기동 (건너뜀)")
        step(4, "LLM 모델 준비 (건너뜀)")
    else:
        step(2, "Ollama 설치 확인")
        exe = find_ollama()
        if exe:
            info(f"이미 설치됨: {exe}")
        else:
            info("설치되어 있지 않습니다. 자동 설치를 시작합니다.")
            exe = install_ollama()
            info(f"설치 완료: {exe}")

        step(3, "Ollama 서버 기동")
        if not start_ollama_serve(exe, settings.ollama_host):
            raise SetupError(
                "Ollama 서버가 응답하지 않습니다.\n"
                "       터미널을 새로 열고 'ollama serve' 를 직접 실행한 뒤 다시 시도해 주세요."
            )

        step(4, "LLM 모델 준비")
        pull_model(exe, llm_model, settings.ollama_host)

    # --- 5) 임베딩 ---
    step(5, "임베딩 모델 준비")
    download_embedding(args.embedding)

    # --- 6) 검증 ---
    step(6, "설치 검증")
    settings.llm_model = llm_model
    settings.embedding_model = args.embedding
    save_settings(settings)
    info(f"설정 저장: LLM={llm_model}, Embedding={args.embedding}")

    from app.cli import main as cli_main

    print()
    cli_main(["doctor"])

    print()
    print("=" * 68)
    print(" 설치가 끝났습니다.")
    print("=" * 68)
    print()
    print("  실행:  run.bat        (Windows)")
    print("         ./run.sh       (macOS / Linux)")
    print()
    print("  브라우저에서 http://127.0.0.1:8501 로 접속하면 됩니다.")
    print("  이제 인터넷을 끊어도 모든 기능이 동작합니다.")
    print()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SetupError as exc:
        print()
        print("=" * 68)
        print(f" [설치 중단] {exc}")
        print("=" * 68)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n사용자가 취소했습니다.")
        sys.exit(130)
