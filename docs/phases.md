# 구현 단계별 진행 상태 (요구사항 23)

각 Phase 는 "구현 → 테스트 → 결과 확인 → 통과" 순으로 진행했다.
아래 명령으로 각 단계를 개별 검증할 수 있다.

| Phase | 내용 | 구현 위치 | 검증 방법 |
|---|---|---|---|
| 1 | 최소 실행 환경 / Local LLM 연결 | `app/llm.py`, `run_app.py` | `python -m app.cli doctor` |
| 2 | 문서 읽기 (PDF/DOCX/TXT/XLSX/PPTX) | `app/extractors.py` | `pytest tests/test_extractors.py` |
| 3 | Chunk + Embedding + 영속 Index | `app/chunker.py`, `app/embedder.py`, `app/vectorstore.py` | `pytest tests/test_chunker.py tests/test_pipeline.py` |
| 4 | 검색 (Hybrid) | `app/search.py`, `app/keyword.py` | `python -m app.cli search "질문"`, `python scripts/evaluate.py` |
| 5 | RAG 답변 + 출처 표시 | `app/rag.py` | `python -m app.cli ask "질문"`, `pytest tests/test_rag.py` |
| 6 | Hallucination 방지 | `app/rag.py` (SYSTEM_PROMPT, threshold) | `pytest tests/test_rag.py -k no_search_result` |
| 7 | Streamlit UI (Chat/Documents/Settings) | `ui/streamlit_app.py` | `pytest tests/test_ui_smoke.py`, `python run_app.py` |
| 8 | 문서 관리 (추가/삭제/재색인/버전) | `app/pipeline.py` | `pytest tests/test_pipeline.py` |
| 9 | 보안 검증 (외부 통신 차단) | `app/netguard.py`, `app/logging_setup.py` | `python scripts/check_offline.py`, `pytest tests/test_security.py` |
| 10 | 최종 테스트 (질문 26개) | `docs/test_questions.json` | `python scripts/evaluate.py`, `pytest tests/test_evaluation.py` |

## Phase 1 을 통과하는 최소 조건

```bat
ollama serve
ollama pull qwen2.5:7b-instruct
python -m app.cli doctor
```

`- Ollama : 정상` 과 `- 임베딩 모델 : ... (dim=384)` 이 표시되면 다음 단계로 진행한다.

## 검색 품질이 낮을 때 (Phase 4 재조정)

1. `python scripts/evaluate.py --reuse-data` 로 실제 문서 기준 정확도를 측정한다.
2. Chunk 크기(기본 900) / Overlap(기본 150)을 조정하고 재색인한다.
3. Vector:Keyword 가중치를 0.5~0.7 범위에서 조정한다.
4. 임베딩 모델을 `intfloat/multilingual-e5-base` 로 올린다(재색인 필요).
