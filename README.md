# 사내 지침 챗봇 (Local Guideline Assistant)

회사 지침문서·SOP·업무절차서를 **내 PC 안에서만** 검색해서, 근거(문서/버전/페이지/Section)와 함께
답변해 주는 개인용 로컬 AI Assistant입니다.

```
"External Data 전달 절차가 어떻게 되었지?"
"DB Lock 전에 확인해야 하는 항목이 뭐였지?"
"파일을 Vendor에게 전달할 때 암호화 규칙이 어떻게 돼?"
```

- 🔒 **완전 로컬 실행** — 외부 AI API(OpenAI/Anthropic/Gemini/Bedrock 등)를 전혀 사용하지 않습니다.
- 🔒 **문서 외부 전송 없음** — 문서·질문·답변·임베딩이 PC 밖으로 나가지 않습니다.
- 🔒 **오프라인 동작** — 모델 준비 후에는 인터넷을 끊어도 모든 기능이 동작합니다.
- 📎 **항상 출처 표시** — 답변에는 문서명·버전·Section·페이지가 함께 표시됩니다.
- 🚫 **없는 내용은 답하지 않음** — 근거가 없으면 "등록된 지침문서에서는 해당 내용을 확인하지 못했습니다."

---

## 목차

1. [설치](#1-설치)
2. [Local LLM 설치 (Ollama)](#2-local-llm-설치-ollama)
3. [모델 준비](#3-모델-준비)
4. [프로그램 실행](#4-프로그램-실행)
5. [문서 등록](#5-문서-등록)
6. [질문 방법](#6-질문-방법)
7. [백업](#7-백업)
8. [삭제 방법](#8-삭제-방법)
9. [설정](#9-설정)
10. [오프라인·보안 검증](#10-오프라인보안-검증)
11. [구조와 동작 방식](#11-구조와-동작-방식)
12. [문제 해결](#12-문제-해결)

---

## 1. 설치

### 가장 쉬운 방법 — 원클릭 자동 설치 (권장)

아래 파일 하나만 실행하면 **설치부터 실행까지 전부 자동**으로 끝납니다.

| OS | 실행할 것 |
|---|---|
| Windows | `설치.bat` **더블클릭** |
| macOS / Linux | 터미널에서 `./setup.sh` |

자동으로 처리되는 항목:

```
Python 확인 (Windows는 없으면 자동 설치)
   → 가상환경 생성 + 라이브러리 설치
   → PC 메모리를 확인해 알맞은 LLM 모델 자동 선택
   → Ollama 자동 설치 및 서버 기동
   → LLM 모델 다운로드
   → 임베딩 모델 다운로드
   → 설치 검증 후 프로그램 실행
```

- 소요 시간: **10~30분** (대부분 모델 다운로드 시간)
- **이때만 인터넷이 필요**하고, 이후에는 인터넷을 끊어도 동작합니다.
- 설치가 끝나면 다음부터는 `run.bat` / `./run.sh` 로 바로 실행됩니다.

메모리에 따라 자동으로 선택되는 모델:

| PC 메모리 | 자동 선택 모델 |
|---|---|
| 14GB 이상 | `qwen2.5:7b-instruct` |
| 14GB 미만 | `qwen2.5:3b-instruct` |

모델을 직접 고르고 싶으면:

```bat
.venv\Scripts\python scripts\setup.py --model exaone3.5:7.8b
```

> 아래 2~3장(Ollama 설치·모델 준비)은 원클릭 설치를 쓰면 **건너뛰어도 됩니다.**
> 직접 단계별로 설치하고 싶을 때만 참고하세요.

---

### 직접 설치하기 (수동)

#### 요구 사항
- Windows 10/11 (macOS·Linux도 동작), 일반 업무용 PC
- Python 3.10 이상
- 여유 디스크 8GB 이상 (LLM 모델 포함)
- 메모리 8GB 이상 권장 (16GB면 더 쾌적)

#### 설치 명령

```bat
:: 프로젝트 폴더에서
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> Docker, Kubernetes, 별도 서버, 별도 DB 서버가 전혀 필요 없습니다.
> 모든 데이터는 프로젝트 폴더 아래 `data/` 에만 저장됩니다.

---

## 2. Local LLM 설치 (Ollama)

> 원클릭 설치(`설치.bat` / `./setup.sh`)를 사용했다면 이 장은 이미 완료된 상태입니다.

1. https://ollama.com 에서 Ollama를 내려받아 설치합니다.
2. 설치 후 터미널에서 동작을 확인합니다.

```bat
ollama --version
ollama serve      :: 이미 백그라운드로 실행 중이면 생략 가능
```

Ollama는 `127.0.0.1:11434` 에서만 동작하며, 이 프로그램은 그 주소로만 요청합니다.

---

## 3. 모델 준비

> 원클릭 설치를 사용했다면 이 장도 이미 완료된 상태입니다.

**이 단계에서만 인터넷이 필요합니다.** 이후에는 오프라인으로 사용할 수 있습니다.

### 3.1 LLM 모델 (답변 생성)

```bat
ollama pull qwen2.5:7b-instruct
```

PC 성능에 따라 아래 중에서 고르세요. (한국어 처리 품질 기준)

| 모델 | 크기 | 권장 환경 | 비고 |
|---|---|---|---|
| `qwen2.5:3b-instruct` | 약 2GB | 8GB RAM | 가장 가볍고 빠름 |
| `qwen2.5:7b-instruct` | 약 4.7GB | 16GB RAM | **기본값 · 권장** |
| `exaone3.5:7.8b` | 약 4.8GB | 16GB RAM | 한국어 특화 |
| `gemma2:9b` | 약 5.4GB | 16GB RAM 이상 | 문장 품질 우수 |

지침문서 검색이 목적이므로 지나치게 큰 모델은 권장하지 않습니다.

### 3.2 Embedding 모델 (문서 검색)

```bat
python scripts/prepare_models.py
```

`data/models/` 아래에 임베딩 모델이 저장되며, 이후 프로그램은 오프라인 모드로 이 파일만 읽습니다.
기본 모델은 `intfloat/multilingual-e5-small`(약 470MB)이며, 검색 품질을 더 높이려면:

```bat
python scripts/prepare_models.py --embedding intfloat/multilingual-e5-base
```

> 임베딩 모델을 바꾸면 기존 인덱스를 쓸 수 없으므로 **전체 재색인**이 필요합니다.
> (Settings 화면에 재색인 버튼이 표시됩니다.)

### 3.3 준비 확인

```bat
python -m app.cli doctor
```

Ollama 연결, 설치된 모델, 임베딩 모델, 인덱스 상태를 한 번에 점검합니다.

---

## 4. 프로그램 실행

```bat
run.bat            :: Windows
```

```bash
./run.sh           # macOS / Linux
python run_app.py  # 공통
```

브라우저에서 다음 주소로 접속합니다.

```
http://127.0.0.1:8501
```

- `127.0.0.1` 에만 Binding 되어 **같은 네트워크의 다른 PC에서는 접속할 수 없습니다.**
- 최초 실행 시 `data/` 폴더와 SQLite DB가 자동으로 생성됩니다.
- 종료는 실행한 터미널 창에서 `Ctrl + C` 입니다.

---

## 5. 문서 등록

### UI에서 등록

`📁 Documents` → `문서 등록` 탭

- **파일 등록**: 여러 파일을 한 번에 선택할 수 있습니다.
- **폴더 등록**: 폴더 경로를 입력하면 하위 폴더까지 한 번에 등록합니다.

지원 형식: **PDF, DOCX, TXT, MD** (필수) / **XLSX, PPTX** (선택)

> 스캔(이미지) PDF는 지원하지 않습니다. 텍스트가 추출되지 않으면 등록이 거부되며,
> OCR이 필요한 문서는 텍스트 PDF로 변환한 뒤 등록하세요.

등록하면 자동으로 다음이 수행됩니다.

```
텍스트 추출 → 구조 분석(제목/Section/페이지) → Chunk 분할
   → 로컬 Embedding 생성 → Vector Index 저장 → Metadata 저장
```

### 버전 관리

파일명에 버전이 있으면 자동으로 인식합니다.

```
SOP_DataManagement_v1.0.pdf
SOP_DataManagement_v1.1.pdf
SOP_DataManagement_v2.0.pdf   ← 최신 버전만 '활성', 검색 기본 대상
```

- 이전 버전은 삭제되지 않고 **비활성** 상태로 남습니다(필요하면 다시 활성화 가능).
- 같은 버전인데 내용이 바뀐 파일을 등록하면 그 버전을 **교체**합니다.
- 내용이 동일한 파일을 다시 등록하면 재임베딩 없이 건너뜁니다.

### 명령줄에서 등록

```bat
python -m app.cli add "C:\회사지침\SOP_DataManagement_v2.0.pdf"
python -m app.cli addfolder "C:\회사지침"
python -m app.cli list
```

---

## 6. 질문 방법

`💬 Chat` 화면에서 평소 말하듯 질문하면 됩니다.

```
Q. External Data 전달 절차가 어떻게 되었지?
Q. 그럼 Password는?                 ← 이전 질문의 맥락을 이어서 이해합니다
```

답변 구성:

```
External Data 전달 시 Data Provider는 파일을 AES-256 이상으로 암호화하고,
Password는 파일과 함께 보내지 않고 별도의 Email로 전달해야 합니다. [1]

출처:
  [1] External Data Transfer Specification v2.1 / 5. Data Transfer > 5.3 Encryption Rule / Page 12
```

- **[참고한 문서]** 영역을 펼치면 실제로 검색된 원문과 Similarity 점수를 볼 수 있습니다.
- **문서 열기** 버튼으로 해당 원본 파일을 바로 열 수 있습니다.
- 근거를 찾지 못하면 답을 만들어내지 않고 다음과 같이 답합니다.
  - `등록된 지침문서에서는 해당 내용을 확인하지 못했습니다.`
  - `관련 내용으로 다음 문서가 검색되었지만 질문에 대한 명확한 절차는 확인되지 않습니다.`

명령줄에서도 확인할 수 있습니다.

```bat
python -m app.cli search "DB Lock 전에 확인해야 하는 항목"   :: 검색 결과만
python -m app.cli ask "External Data 전달 시 암호화 규칙"     :: 답변까지
```

### 약어 검색

`DBL`, `DB Lock`, `Database Lock` 처럼 표현이 달라도 검색되도록 동의어를 적용합니다.
사내 약어를 추가하려면 `data/synonyms.json` 을 만들어 채우면 됩니다.

```json
{
  "eot": ["end of trial", "종료보고"],
  "tmf": ["trial master file", "핵심문서"]
}
```

---

## 7. 백업

`⚙️ Settings` → **백업 생성** 을 누르면 `data/backup/backup_YYYYMMDD_HHMMSS.zip` 이 만들어집니다.
문서 원본 + Vector Index + SQLite DB + 설정이 모두 포함됩니다.

```bat
python -m app.cli backup
```

- 백업은 **로컬 디스크에만** 저장됩니다. 자동 Cloud Backup은 구현되어 있지 않습니다.
- 다른 PC로 옮기려면 이 zip 파일을 사내 규정에 맞는 방법으로 이동한 뒤,
  새 PC의 `data/` 폴더에 압축을 풀면 됩니다.

---

## 8. 삭제 방법

`📁 Documents` → `등록 목록` 탭 → 대상 문서 선택 → **삭제 확인** 체크 → **삭제**

삭제 시 다음이 **모두** 제거됩니다.

- 원본 파일 (`data/documents/`)
- 추출된 텍스트 / Chunk (SQLite)
- Embedding & Vector Index (`data/index/`)
- Metadata (SQLite)

```bat
python -m app.cli delete 3     :: 문서 ID 3 삭제
```

전체를 지우려면 프로그램을 종료한 뒤 `data/` 폴더를 통째로 삭제하면 됩니다.

---

## 9. 설정

`⚙️ Settings` 화면에서 다음을 조정합니다. (`data/config.json` 에 저장)

| 설정 | 기본값 | 설명 |
|---|---|---|
| LLM 모델 | `qwen2.5:7b-instruct` | Ollama에 설치된 모델 중 선택 |
| Embedding 모델 | `intfloat/multilingual-e5-small` | 변경 시 전체 재색인 필요 |
| 검색 문서 수 (Top-K) | 5 | LLM에 전달할 근거 개수 |
| 검색 threshold | 0.35 | 높일수록 엄격(근거 없으면 답변 거부) |
| Vector : Keyword 가중치 | 0.6 | 1.0이면 의미검색만, 0.0이면 키워드만 |
| 답변 길이 | 보통 | 짧게 / 보통 / 자세히 |
| 대화 Context | 3 turn | 이어지는 질문에 사용할 최근 대화 수 |

### threshold 튜닝

사용 중인 임베딩 모델에 맞는 threshold는 질문 세트로 측정해서 정하는 것이 정확합니다.

```bat
python scripts/evaluate.py                       :: samples/ 문서로 26개 질문 평가
python scripts/evaluate.py --threshold 0.45      :: threshold 바꿔 재측정
python scripts/evaluate.py --reuse-data          :: 실제 등록된 내 문서로 평가
```

`검색 정확도`(정답 문서를 찾는 비율)와 `거부 정확도`(문서에 없는 질문을 거부하는 비율)가
함께 표시됩니다. 두 값이 균형을 이루는 지점이 적절한 threshold입니다.

---

## 10. 오프라인·보안 검증

```bat
python scripts/check_offline.py
```

1. **코드 정적 검사** — 외부 API 호출·telemetry·외부 URL이 코드에 있는지 검사
2. **동작 검사** — 네트워크 차단 가드를 켠 상태에서 등록 → 검색 → 삭제가 되는지 확인

프로그램 실행 중에는 `app/netguard.py` 가 **loopback(127.0.0.1) 이외의 모든 소켓 연결을 차단**합니다.
어떤 라이브러리가 몰래 외부로 요청을 보내려 해도 연결 자체가 열리지 않습니다.

추가로 다음이 기본 적용됩니다.

- HuggingFace 오프라인 모드(`HF_HUB_OFFLINE=1`), telemetry 비활성화
- Streamlit 사용 통계 수집 비활성화, `127.0.0.1` 전용 Binding
- 로그에 문서 본문·질문·답변을 남기지 않음 (시간/성공 여부/문서 ID/오류 코드만 기록)

실제 환경 검증(권장 절차)은 [docs/security_checklist.md](docs/security_checklist.md) 를 참고하세요.

---

## 11. 구조와 동작 방식

```
사용자 문서 → 텍스트 추출 → Chunk 분할 → 로컬 Embedding → Vector Index 저장
                                                              ↓
사용자 질문 → Hybrid 검색(Vector + Keyword) → 관련 Chunk → 로컬 LLM → 근거 기반 답변
```

| 영역 | 사용 기술 | 위치 |
|---|---|---|
| UI | Streamlit (127.0.0.1:8501) | `ui/streamlit_app.py` |
| LLM | Ollama (로컬) | `app/llm.py` |
| Embedding | sentence-transformers (로컬) | `app/embedder.py` |
| Vector Index | FAISS (없으면 numpy 자동 대체) | `app/vectorstore.py` |
| Keyword 검색 | 자체 BM25 (한국어 2-gram) | `app/keyword.py` |
| Metadata | SQLite | `app/db.py` |
| 문서 추출 | pypdf / python-docx / openpyxl / python-pptx | `app/extractors.py` |

데이터 저장 위치:

```
data/
├ documents/   원본 문서 사본
├ index/       Vector Index (faiss.index 또는 vectors.npy)
├ database/    metadata.sqlite3 (문서/Chunk/Metadata)
├ models/      로컬 임베딩 모델
├ logs/        app.log (본문·질문 미기록)
└ backup/      백업 zip
```

대화 기록은 **디스크에 저장하지 않습니다**(브라우저 세션 메모리에만 유지).

### 테스트

```bat
pytest -q
```

문서 추출 / Chunking / 버전 관리 / 검색 / 답변 거부 / 보안 가드 / UI 렌더링까지
64개 테스트가 포함되어 있습니다.

---

## 12. 문제 해결

| 증상 | 확인 사항 |
|---|---|
| `로컬 LLM 미연결` 표시 | 터미널에서 `ollama serve` 실행, `python -m app.cli doctor` 로 점검 |
| `로컬에 임베딩 모델이 없습니다` | `python scripts/prepare_models.py` 를 인터넷 연결 상태에서 1회 실행 |
| 답변이 너무 느림 | 더 작은 LLM(`qwen2.5:3b-instruct`)로 변경, Top-K를 3으로 낮춤 |
| 검색이 엉뚱한 문서를 찾음 | Settings에서 threshold를 올리고, Vector:Keyword 가중치를 0.5 부근으로 조정 후 `scripts/evaluate.py` 로 재측정 |
| 문서를 등록했는데 검색되지 않음 | `등록 목록`에서 상태가 `비활성(과거 버전)`인지 확인 |
| 등록 시 "텍스트를 추출하지 못했습니다" | 스캔 PDF입니다. 텍스트 PDF로 변환 후 등록하세요 |
| `설치.bat` 이 중간에 멈춤 | 표시된 메시지를 확인하세요. 사내 방화벽이 `ollama.com`/`huggingface.co` 를 막는 경우가 많습니다. IT 부서에 두 주소 허용을 요청하거나, 인터넷이 되는 PC에서 설치 후 `data/models/` 를 복사하세요 |
| 인덱스가 깨진 것 같음 | Settings → 전체 재색인, 또는 `data/index/` 삭제 후 각 문서 재색인 |

---

## 라이선스 / 사용 시 주의

- 이 프로그램은 개인 PC에서 사내 지침문서를 빠르게 찾기 위한 보조 도구입니다.
- **최종 판단의 근거는 항상 원본 지침문서**이며, 답변에 표시된 출처를 확인한 뒤 업무에 적용하세요.
- 회사 보안 정책에 따라 문서 반입·반출 규정을 반드시 준수하세요.
