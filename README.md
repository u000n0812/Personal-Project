# 사내 지침문서 어시스턴트 (Local RAG Chatbot)

업무 중 "이 절차가 어떻게 되더라?" 싶을 때 **등록해 둔 지침문서·SOP·업무절차서**에서
근거를 찾아 알려주는 **완전 로컬 실행** 챗봇입니다.

- 문서, 질문, 검색 결과, 답변, 대화 내용이 **PC 밖으로 나가지 않습니다.**
- OpenAI / Anthropic / Gemini 등 **외부 AI API를 전혀 사용하지 않습니다.**
- 인터넷을 끊은 상태에서도 모든 기능이 동작합니다(최초 모델 설치 제외).
- 답변에는 **항상 출처(문서명 · 버전 · Section · Page)** 가 표시되고, 근거가 없으면 답하지 않습니다.

```
질문 → 관련 지침 검색(Hybrid) → 로컬 LLM이 검색된 내용만 근거로 답변 → 출처 표시
```

---

## 1. 설치

### 1) Python 설치
Python 3.10 이상을 설치합니다. (Windows: 설치 시 **Add Python to PATH** 체크)

### 2) 프로그램 준비
```bat
:: 프로젝트 폴더에서
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Windows에서는 `run.bat`을 더블클릭하면 위 과정과 실행이 한 번에 진행됩니다.
(macOS / Linux는 `./run.sh`)

> 기본 구성은 **Embedding과 LLM을 모두 Ollama에서 실행**하므로 torch(수 GB)를 설치하지 않습니다.
> sentence-transformers를 쓰고 싶다면 `pip install -r requirements-sentence-transformers.txt` 로 설치하세요.

---

## 2. Local LLM 설치 (Ollama)

1. https://ollama.com 에서 Ollama를 내려받아 설치합니다.
2. 설치 후 터미널에서 아래 명령으로 서버를 실행합니다(보통 설치와 함께 자동 실행됩니다).
   ```bat
   ollama serve
   ```
3. Ollama는 `127.0.0.1:11434`에서만 동작하며, 이 프로그램은 그 주소로만 통신합니다.

---

## 3. 모델 준비 (최초 1회만 인터넷 필요)

### Embedding 모델 — bge-m3 (권장, 기본값)

```bat
ollama pull bge-m3
```

`bge-m3`는 한국어·영문이 섞인 지침문서 검색에 적합한 multilingual 모델(1024차원)입니다.
설치해 두면 프로그램이 자동으로 이 모델을 사용합니다(`Settings → Embedding backend: auto`).
Ollama를 통해 **로컬에서만** 실행되며 문서 내용이 외부로 전송되지 않습니다.

설치 후 아래 명령으로 모델이 제대로 동작하는지 확인할 수 있습니다.

```bat
python cli.py embed-check
```

관련 있는 문장과 무관한 문장의 유사도 차이를 보여주고, 이 모델에 맞는 threshold 권장값을 알려줍니다.
(정상이라면 관련 문장 0.6~0.8, 무관한 문장 0.3~0.45 수준으로 벌어집니다.)

> sentence-transformers를 쓰려면 `requirements-sentence-transformers.txt`를 설치한 뒤
> **Settings → Embedding backend**를 `sentence-transformers`로 바꾸고,
> 모델(`intfloat/multilingual-e5-small`)을 1회 내려받으세요.
> Embedding 모델을 바꾸면 **Settings → 전체 재색인**을 반드시 실행해야 합니다
> (모델마다 vector 차원과 값이 달라 기존 Index를 그대로 쓸 수 없습니다).

### LLM 모델
답변 생성에 사용할 모델을 하나 선택합니다(한국어 처리 가능, 업무용 PC 기준).

| 모델 | 명령 | 메모리 기준 |
|------|------|-------------|
| `qwen2.5:7b-instruct` (기본 권장) | `ollama pull qwen2.5:7b-instruct` | RAM 16GB |
| `qwen2.5:3b-instruct` (가벼움)    | `ollama pull qwen2.5:3b-instruct` | RAM 8GB |
| `exaone3.5:7.8b` (한국어 특화)    | `ollama pull exaone3.5:7.8b`      | RAM 16GB |

지침문서 검색이 목적이므로 지나치게 큰 모델은 사용하지 않습니다.

준비 상태는 아래 명령으로 한 번에 확인합니다.
```bat
python cli.py doctor
```
`Embedding backend : ollama:bge-m3 (dim=1024)` 로 표시되면 정상입니다.

---

## 4. 프로그램 실행

```bat
run.bat
```
또는
```bat
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

브라우저에서 **http://127.0.0.1:8501** 로 접속합니다.
`127.0.0.1`에만 Binding되므로 같은 네트워크의 다른 PC에서는 접속할 수 없습니다.

화면은 세 개입니다.

| 메뉴 | 설명 |
|------|------|
| **Chat** | 질문 → 답변 → 참고 문서(원문·유사도·문서 열기) |
| **Documents** | 문서 등록 / 목록 / 재색인 / 비활성화 / 삭제 |
| **Settings** | 모델, Top-K, threshold, 답변 길이, 재색인, 백업 |

---

## 5. 문서 등록

**Documents** 화면에서:
- **파일 선택**: 여러 파일을 한 번에 등록
- **폴더 단위 등록**: 폴더 경로를 입력하면 하위 폴더까지 모두 등록

명령줄에서도 가능합니다.
```bat
python cli.py add "C:\SOP\2024"
python cli.py list
```

지원 형식: **PDF, DOCX, TXT, MD, XLSX, PPTX**
(이미지로만 된 스캔 PDF는 초기 버전에서 지원하지 않으며 등록 시 안내 메시지가 표시됩니다.)

등록하면 자동으로 다음 순서로 처리됩니다.
```
텍스트 추출 → 구조 분석(제목/Section/페이지) → Chunk 분할 → Embedding → Vector Index 저장 → Metadata 저장
```

### 문서 버전 관리
파일명에 버전이 있으면 자동으로 인식합니다. (`SOP_DataManagement_v1.1.pdf` → 버전 `1.1`)

- 같은 문서의 새 버전을 등록하면 이전 버전은 **덮어쓰지 않고** `과거 버전`으로 표시됩니다.
- 기본 검색·답변은 **최신 활성 버전**만 사용합니다.
- 과거 버전도 확인하려면 **Settings → 과거 버전 문서도 검색에 포함**을 켭니다.

---

## 6. 질문 방법

Chat 화면에 평소 말하듯 질문하면 됩니다.

```
External Data 전달 절차가 어떻게 되었지?
DB Lock 전에 확인해야 하는 항목이 뭐였지?
파일을 Vendor에게 전달할 때 암호화 규칙이 어떻게 돼?
이 업무는 누구에게 승인을 받아야 해?
```

- 이어서 묻기가 가능합니다. (`External Data 전달 절차 알려줘` → `그럼 Password는?`)
- 답변 아래 **[참고한 문서]** 를 펼치면 실제 검색된 원문, 유사도, 페이지를 확인하고
  **문서 열기** 버튼으로 원본을 바로 열 수 있습니다.
- 근거를 찾지 못하면 지어내지 않고 이렇게 답합니다.
  > 등록된 지침문서에서는 해당 내용을 확인하지 못했습니다.

명령줄에서 검색 결과만 확인하려면:
```bat
python cli.py search "DB Lock 전 확인 항목"
python cli.py ask "External Data 전달 절차 알려줘"
```

---

## 7. 백업

**Settings → 지금 백업하기** 를 누르면 `backup/` 폴더에 zip으로 저장됩니다.
(문서 사본 + Vector Index + SQLite DB + 설정)

```bat
python cli.py backup                    :: 백업 생성
python cli.py restore backup\sopbot_backup_20240115_101500.zip   :: 복원
```

자동 클라우드 백업은 **구현하지 않았습니다.** 백업 파일은 사내 규정에 맞는 위치에 보관하세요.

---

## 8. 삭제 방법

**Documents → 삭제** 를 누르면 다음이 **모두** 삭제됩니다.

- `data/documents/`의 문서 사본
- 추출된 텍스트(Chunk)
- Embedding / Vector Index 항목
- SQLite Metadata

```bat
python cli.py remove 3        :: ID 3번 문서 삭제
```

> 사용자가 원래 가지고 있던 원본 파일(예: `C:\SOP\...`)은 건드리지 않습니다.
> 전체 초기화가 필요하면 프로그램 종료 후 `data/` 폴더를 삭제하면 됩니다.

---

## 9. 보안 원칙과 확인 방법

| 항목 | 구현 |
|------|------|
| 외부 AI API | 사용하지 않음 (OpenAI/Anthropic/Gemini/Bedrock/Cohere 등) |
| 통신 대상 | `127.0.0.1` 로컬 Ollama **뿐**. 그 외 주소는 코드에서 차단(`sopbot/security.py`) |
| Telemetry | Streamlit 사용통계·HuggingFace telemetry 등 환경변수로 비활성화 |
| UI 접근 | `127.0.0.1:8501`만 Binding (`0.0.0.0` 사용 안 함) |
| 로그 | 시간 / 성공·실패 / 문서 ID / 오류 코드만 기록. 문서 본문·질문 내용은 기록하지 않음 |
| 데이터 위치 | `data/` 폴더 (documents / index / database / logs / cache) |

확인 명령:
```bat
python cli.py selfcheck     :: 소스코드에 외부 API·외부 URL·telemetry가 없는지 검사
python cli.py doctor        :: 실행 환경 + 보안 점검 요약
python cli.py embed-check   :: Embedding 모델(bge-m3) 분별력 확인
python -m unittest discover -s tests -t .    :: 전체 자동 테스트
```

### 오프라인 검증 절차
1. 네트워크 어댑터를 끄거나 랜선을 분리합니다.
2. `run.bat` 실행 → `python cli.py add sample_docs` → Chat에서 질문 → 문서 삭제까지 수행합니다.
3. 모든 단계가 정상 동작하면 오프라인 검증 통과입니다.
   (모델을 아직 내려받지 않은 상태라면 3장 '모델 준비'를 먼저 온라인에서 1회 수행해야 합니다.)

---

## 10. 폴더 구조

```
Personal-Project/
├─ app.py               Streamlit UI (Chat / Documents / Settings)
├─ cli.py               명령줄 도구 (등록·검색·질문·백업·점검)
├─ run.bat / run.sh     실행 스크립트
├─ requirements.txt     설치 목록 (bge-m3 기준, torch 불필요)
├─ sopbot/
│  ├─ security.py       외부 통신 차단, 소스 점검
│  ├─ config.py         설정값, 경로, 동의어 사전
│  ├─ db.py             SQLite Metadata (documents / chunks)
│  ├─ extract.py        PDF·DOCX·TXT·XLSX·PPTX 텍스트 추출
│  ├─ chunk.py          제목/Section 구조 기반 Chunk 분할
│  ├─ embed.py          로컬 Embedding (Ollama bge-m3 / sentence-transformers / fallback)
│  ├─ vectorstore.py    로컬 Vector Index (numpy·faiss, 파일 저장)
│  ├─ keyword.py        BM25 Keyword 검색 + 동의어 확장
│  ├─ search.py         Hybrid 검색 + 근거 충분성 판단
│  ├─ llm.py            로컬 Ollama 클라이언트 (127.0.0.1 전용)
│  ├─ rag.py            System Prompt, 답변 생성, Hallucination 방지
│  ├─ ingest.py         등록/재색인/삭제/버전 관리
│  ├─ backup.py         zip 백업·복원
│  └─ service.py        구성 요소 조립 + 상태 점검
├─ sample_docs/         테스트용 예시 SOP + 평가 질문 22개
├─ tests/               자동 테스트 (58개)
└─ data/                실행 시 자동 생성 (문서·Index·DB·로그)
```

---

## 11. 설정 값 안내 (Settings)

| 항목 | 설명 | 기본값 |
|------|------|--------|
| LLM 모델 | Ollama에 설치된 모델 | `qwen2.5:7b-instruct` |
| Embedding backend | `auto` / `ollama` / `sentence-transformers` / `hashing` | `auto` (→ Ollama `bge-m3`) |
| 검색 문서 수 (Top-K) | 답변에 사용할 검색 결과 수 | 5 |
| 검색 threshold | Vector 유사도 최소값. 높을수록 답변을 더 자주 거부 | 0 (자동: bge-m3 0.50 / e5 0.80) |
| 질문 단어 일치 최소 비율 | 질문 단어가 문서에서 확인된 비율(모델 무관 보조 기준) | 0.3 |
| 답변 길이 | 짧게 / 보통 / 자세히 | 보통 |

> threshold를 **0으로 두면 Embedding 모델에 맞는 권장값이 자동 적용**됩니다.
> 직접 조정할 때는 답변을 너무 자주 거부하면 값을 낮추고, 관련 없는 문서로 답하면 높입니다.
> `python cli.py embed-check` 가 현재 모델에 맞는 값을 알려줍니다.
> `hashing` fallback은 모델을 찾지 못했을 때만 쓰이는 임시 backend이며 검색 품질이 낮습니다.
> 사이드바에 이 backend가 표시되면 Ollama 실행 상태와 `ollama pull bge-m3` 설치를 확인하세요.

---

## 12. 자주 겪는 문제

| 증상 | 확인 |
|------|------|
| 사이드바에 "로컬 LLM 연결 안 됨" | 터미널에서 `ollama serve` 실행 여부, 포트 11434 |
| "Embedding 모델을 불러오지 못했습니다" | 3장 '모델 준비' 수행, 또는 backend를 `ollama`로 변경 |
| 답변이 계속 "확인하지 못했습니다" | 문서 등록 여부 확인 → Settings에서 threshold를 낮춤 |
| 답변이 느림 | 더 작은 LLM 모델 사용(`qwen2.5:3b-instruct`), Top-K를 3으로 낮춤 |
| 스캔 PDF 등록 실패 | 초기 버전은 OCR 미지원. 텍스트 PDF로 변환 후 등록 |
| Embedding 모델 변경 후 검색 이상 | Settings → **전체 재색인** 실행 |
| 사이드바에 "Index는 …로 만들어졌는데" 경고 | Ollama 실행 확인 후 `python cli.py rebuild` |
| Embedding backend가 `hashing`으로 표시됨 | `ollama serve` 실행 여부, `ollama pull bge-m3` 설치 확인 |

---

## 13. 성능 기준

- 문서 100~500개 규모를 기준으로 설계했습니다.
- 검색: 보통 1~3초 이내 (문서 수와 PC 성능에 따라 다름)
- LLM 답변: PC 성능에 따라 수 초 ~ 수십 초
- 한 번 Embedding한 문서는 재사용하며, 프로그램을 다시 실행해도 재색인하지 않습니다.
