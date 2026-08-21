# 보안 검증 체크리스트 (Phase 9 / Phase 22)

배포 전, 그리고 지침문서를 등록하기 전에 아래 항목을 순서대로 확인한다.

## 1. 코드 검사

```bat
python scripts/check_offline.py
```

- [ ] 외부 AI API 호출 코드 없음 (OpenAI / Anthropic / Gemini / Bedrock / Cohere / Azure OpenAI)
- [ ] `requests` / `httpx` 등으로 외부 URL을 호출하는 코드 없음
- [ ] telemetry / analytics / crash report 전송 코드 없음
- [ ] cloud sync, 외부 logging 코드 없음

## 2. 설정 검사

- [ ] `data/config.json` 의 `ollama_host` 가 `http://127.0.0.1:11434`
- [ ] Streamlit 이 `127.0.0.1` 로만 Binding (`.streamlit/config.toml`, `run_app.py`)
- [ ] `strict_offline` 이 `true`
- [ ] 브라우저 사용 통계 수집 off (`browser.gatherUsageStats = false`)

## 3. 네트워크 차단 상태 기능 검사 (요구사항 22)

Wi-Fi / 유선 네트워크를 **모두 끊은 상태**에서 다음을 수행한다.

- [ ] 1. 프로그램 실행 (`run.bat`)
- [ ] 2. 문서 등록 (PDF / DOCX / TXT 각 1건)
- [ ] 3. Embedding 생성 완료 확인 (Chunk 수 표시)
- [ ] 4. 질문 입력
- [ ] 5. 검색 결과 표시 확인 ([참고한 문서] 영역)
- [ ] 6. AI 답변 생성 확인
- [ ] 7. 문서 삭제 후 `data/documents/`, `data/index/` 에서 실제로 제거되었는지 확인

## 4. 통신 모니터링 (선택, 권장)

프로그램 실행 중 외부로 나가는 연결이 없는지 확인한다.

```bat
netstat -ano | findstr ESTABLISHED
```

- [ ] 프로그램 관련 연결이 `127.0.0.1` 로만 존재
- [ ] 외부 IP 로 향하는 연결 없음

Windows 방화벽에서 Python 실행 파일의 아웃바운드를 차단해 두면 이중으로 안전하다.

## 5. 로그 검사 (요구사항 17)

```bat
type data\logs\app.log
```

- [ ] 문서 본문이 기록되지 않음
- [ ] 사용자 질문 / AI 답변이 기록되지 않음
- [ ] 파일명 전체 경로 등 민감 정보가 과도하게 기록되지 않음
- [ ] 시간 / 성공·실패 / 문서 ID / 오류 코드 수준으로만 기록됨

## 6. 데이터 보관 검사

- [ ] 모든 데이터가 `data/` 아래에만 저장됨
- [ ] 대화 기록이 디스크에 저장되지 않음 (세션 메모리만 사용)
- [ ] 백업 zip 이 `data/backup/` 에만 생성됨 (자동 업로드 없음)

## 7. 최종 품질 검사 (Phase 10)

```bat
pytest -q
python scripts/evaluate.py
```

- [ ] 전체 테스트 통과
- [ ] 20개 이상의 실제 질문에 대해 정답 문서가 Top-3 안에 검색됨
- [ ] 문서에 없는 질문에 대해 "등록된 지침문서에서는 해당 내용을 확인하지 못했습니다." 로 응답
- [ ] 답변에 출처(문서명 / 버전 / Section / 페이지)가 표시됨
- [ ] 검색 1~3초, 답변 수초~수십 초 수준
