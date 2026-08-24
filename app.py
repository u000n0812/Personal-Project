"""GuideBot - 사내 지침문서 조회 챗봇 (로컬 Web UI).

실행:  python -m streamlit run app.py
접속:  http://127.0.0.1:8501  (127.0.0.1에만 Binding, 외부 접근 불가)
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import webbrowser
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from guidebot.backup import create_backup, list_backups  # noqa: E402
from guidebot.config import (  # noqa: E402
    BACKUP_DIR,
    DATA_DIR,
    Settings,
    ensure_dirs,
)
from guidebot.db import STATUS_ACTIVE, STATUS_DISABLED, STATUS_SUPERSEDED  # noqa: E402
from guidebot.extract import SUPPORTED_EXTENSIONS  # noqa: E402
from guidebot.rag import postprocess_answer  # noqa: E402  (strict_mode 해제 시 사용)
from guidebot.service import AppService  # noqa: E402

STATUS_LABEL = {
    STATUS_ACTIVE: "🟢 활성(최신)",
    STATUS_SUPERSEDED: "🟡 과거 버전",
    STATUS_DISABLED: "⚪ 비활성",
}


@st.cache_resource(show_spinner=False)
def get_service() -> AppService:
    ensure_dirs()
    return AppService(Settings.load())


ACROBAT_CANDIDATES = (
    r"C:\Program Files\Adobe\Acrobat DC\Acrobat\Acrobat.exe",
    r"C:\Program Files (x86)\Adobe\Acrobat DC\Acrobat\Acrobat.exe",
    r"C:\Program Files\Adobe\Acrobat Reader DC\Reader\AcroRd32.exe",
    r"C:\Program Files (x86)\Adobe\Acrobat Reader DC\Reader\AcroRd32.exe",
    r"C:\Program Files (x86)\Adobe\Reader 11.0\Reader\AcroRd32.exe",
)


def _open_pdf_at_page(target: Path, page: int) -> str | None:
    """PDF를 지정한 페이지에서 연다. 성공하면 안내 문구, 실패하면 None."""
    system = platform.system()

    # 1순위: Adobe Acrobat/Reader (페이지 지정 옵션을 정식 지원)
    if system == "Windows":
        executables = [path for path in ACROBAT_CANDIDATES if Path(path).exists()]
        found = shutil.which("AcroRd32.exe") or shutil.which("Acrobat.exe")
        if found:
            executables.append(found)
        for executable in executables:
            try:
                subprocess.Popen([executable, "/A", f"page={page}", str(target)])
                return f"{page} 페이지로 문서를 열었습니다."
            except OSError:
                continue

    # 2순위: 기본 브라우저(Edge/Chrome/Firefox 모두 #page= 앵커를 지원)
    try:
        if webbrowser.open(f"{target.resolve().as_uri()}#page={page}"):
            return f"{page} 페이지로 문서를 열었습니다(브라우저 PDF 뷰어)."
    except Exception:
        pass
    return None


def open_local_file(path: str, page: int | None = None) -> str:
    """등록된 원본 문서를 로컬 뷰어로 연다(외부 전송 없음).

    PDF이고 페이지를 알고 있으면 해당 페이지에서 바로 열리도록 시도한다.
    """
    target = Path(path)
    if not target.exists():
        return "파일을 찾을 수 없습니다(삭제되었거나 이동됨)."

    if target.suffix.lower() == ".pdf" and page and page > 0:
        message = _open_pdf_at_page(target, page)
        if message:
            return message

    try:
        system = platform.system()
        if system == "Windows":
            os.startfile(str(target))  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
    except OSError as exc:
        return f"문서를 열지 못했습니다: {exc.__class__.__name__}"

    if page:
        return f"문서를 열었습니다. ({page} 페이지를 확인하세요)"
    return "문서를 열었습니다."


def render_sources(results, key_prefix: str) -> None:
    """[참고한 문서] 영역: 유사도와 원문 일부, 문서 열기 버튼."""
    if not results:
        return
    st.markdown("**[참고한 문서]**")
    for index, result in enumerate(results, start=1):
        document = result.document
        badge = "✅" if result.confidence >= 0.9 else ("🔎" if result.confidence >= 0.5 else "•")
        header = (
            f"{index}. {badge} {document.title} v{document.version}"
            f"{' / ' + result.page_label if result.page_label else ''}"
            f"  ·  유사도 {result.confidence:.2f}"
        )
        with st.expander(header):
            if result.chunk.section:
                st.caption(f"Section: {result.chunk.section}")
            st.caption(
                f"파일: {document.file_name}  |  vector {result.vector_score:.3f}"
                f"  |  keyword {result.keyword_score:.2f}"
                f"  |  단어일치 {result.token_coverage:.2f}"
            )
            st.text(result.chunk.text)
            columns = st.columns([1, 3])
            with columns[0]:
                page = result.chunk.page_start
                label = f"문서 열기 ({page}p)" if page else "문서 열기"
                if st.button(label, key=f"{key_prefix}_open_{index}"):
                    st.info(open_local_file(document.stored_path, page))
            with columns[1]:
                stored = Path(document.stored_path)
                if stored.exists():
                    st.download_button(
                        "사본 내려받기",
                        data=stored.read_bytes(),
                        file_name=document.file_name,
                        key=f"{key_prefix}_dl_{index}",
                    )


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
def page_chat(service: AppService) -> None:
    st.subheader("💬 지침문서에 물어보기")

    if "history" not in st.session_state:
        st.session_state.history = []   # [(question, answer, results)]

    stats = service.db.stats()
    if stats["chunks"] == 0:
        st.info("등록된 문서가 없습니다. 왼쪽 메뉴의 **Documents**에서 지침문서를 먼저 등록하세요.")

    for turn_index, (question, answer, results) in enumerate(st.session_state.history):
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            st.write(answer)
            render_sources(results, key_prefix=f"hist{turn_index}")

    question = st.chat_input("예) External Data 전달 절차가 어떻게 되었지?")
    if not question:
        return

    with st.chat_message("user"):
        st.write(question)

    history_pairs = [(q, a) for q, a, _ in st.session_state.history]
    with st.chat_message("assistant"):
        placeholder = st.empty()
        with st.spinner("지침문서를 검색하는 중..."):
            stream, results, evidence, state = service.engine.answer_stream(question, history_pairs)
        collected = ""
        for piece in stream:
            collected += piece
            placeholder.markdown(collected)
        report = None
        if state.error and results:
            collected, report = service.engine.finalize_stream(collected, results, state)
            placeholder.markdown(collected)
            st.error("로컬 LLM 호출에 실패했습니다. 사이드바의 LLM 상태를 확인하세요.")
        elif evidence == "ok" and results:
            # 문서에 근거가 없는 문장을 제거하고, 출처를 실제 검색 결과로 교체한다.
            collected, report = service.engine.finalize_stream(collected, results, state)
            placeholder.markdown(collected)
            if report is None:
                collected = postprocess_answer(collected, results)
        if report is not None:
            if report.unsupported:
                st.caption(
                    f"🛡️ 근거 검증: {report.summary} · "
                    f"문서에서 확인되지 않은 문장 {len(report.unsupported)}개 제외"
                )
            else:
                st.caption(f"🛡️ 근거 검증: {report.summary} 모두 지침문서에서 확인됨")
        render_sources(results, key_prefix=f"live{len(st.session_state.history)}")

    st.session_state.history.append((question, collected, results))


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------
def page_documents(service: AppService) -> None:
    st.subheader("📄 지침문서 관리")

    with st.expander("문서 등록", expanded=True):
        uploaded = st.file_uploader(
            "파일 선택 (여러 개 가능)",
            type=[e.lstrip(".") for e in sorted(SUPPORTED_EXTENSIONS)],
            accept_multiple_files=True,
        )
        if uploaded and st.button("선택한 파일 등록", type="primary"):
            temp_dir = Path(tempfile.mkdtemp(prefix="guidebot_upload_"))
            paths = []
            for item in uploaded:
                target = temp_dir / item.name
                target.write_bytes(item.getbuffer())
                paths.append(target)
            with st.spinner("문서를 처리하는 중입니다(추출 → 분할 → Embedding)..."):
                results = service.register(paths)
            for result in results:
                (st.success if result.ok else st.warning)(f"{result.file_name}: {result.message}")
            for path in paths:
                path.unlink(missing_ok=True)
            st.rerun()

        folder = st.text_input("폴더 단위 등록 (폴더 경로 입력)", placeholder=r"예) C:\SOP\2024")
        if folder and st.button("폴더 등록"):
            folder_path = Path(folder.strip('" '))
            if not folder_path.is_dir():
                st.error("폴더를 찾을 수 없습니다.")
            else:
                with st.spinner("폴더의 문서를 처리하는 중입니다..."):
                    results = service.register([folder_path])
                success = sum(1 for r in results if r.ok)
                st.success(f"처리 완료: 총 {len(results)}건 / 등록 {success}건")
                for result in results:
                    if not result.ok:
                        st.warning(f"{result.file_name}: {result.message}")
                st.rerun()

    documents = service.documents(include_all=True)
    st.markdown(f"**등록된 문서: {len(documents)}건**")
    if not documents:
        st.info("아직 등록된 문서가 없습니다.")
        return

    header = st.columns([3, 1, 1.4, 1.4, 0.8, 2.4])
    for column, label in zip(header, ["문서명", "버전", "등록일", "상태", "Chunk", "관리"]):
        column.markdown(f"**{label}**")

    for document in documents:
        columns = st.columns([3, 1, 1.4, 1.4, 0.8, 2.4])
        columns[0].write(f"{document.title}  \n<small>{document.file_name}</small>", unsafe_allow_html=True)
        columns[1].write(f"v{document.version}")
        columns[2].write(document.registered_at[:10])
        columns[3].write(STATUS_LABEL.get(document.status, document.status))
        columns[4].write(str(document.chunk_count))

        with columns[5]:
            action_columns = st.columns(3)
            if action_columns[0].button("재색인", key=f"re_{document.id}"):
                with st.spinner("재색인 중..."):
                    result = service.ingestor.reindex(document.id)
                    service.retriever.invalidate()
                (st.success if result.ok else st.error)(result.message)
                st.rerun()

            toggle_label = "활성화" if document.status == STATUS_DISABLED else "비활성"
            if action_columns[1].button(toggle_label, key=f"tg_{document.id}"):
                new_status = STATUS_ACTIVE if document.status == STATUS_DISABLED else STATUS_DISABLED
                service.ingestor.set_status(document.id, new_status)
                service.retriever.invalidate()
                st.rerun()

            if action_columns[2].button("삭제", key=f"del_{document.id}"):
                st.session_state[f"confirm_delete_{document.id}"] = True

        if st.session_state.get(f"confirm_delete_{document.id}"):
            st.warning(
                f"'{document.title}' 문서를 삭제하면 원본 사본, 추출 텍스트, Embedding, "
                "Vector Index, Metadata가 모두 삭제됩니다."
            )
            confirm_columns = st.columns([1, 1, 6])
            if confirm_columns[0].button("삭제 확인", key=f"delok_{document.id}", type="primary"):
                service.ingestor.delete(document.id)
                service.retriever.invalidate()
                st.session_state.pop(f"confirm_delete_{document.id}", None)
                st.rerun()
            if confirm_columns[1].button("취소", key=f"delno_{document.id}"):
                st.session_state.pop(f"confirm_delete_{document.id}", None)
                st.rerun()


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
def page_settings(service: AppService) -> None:
    st.subheader("⚙️ 설정")
    settings = service.settings

    with st.form("settings_form"):
        st.markdown("**로컬 LLM**")
        installed = service.client.list_models() if service.client.is_available() else []
        if installed:
            options = installed if settings.llm_model in installed else [settings.llm_model] + installed
            llm_model = st.selectbox("LLM 모델", options, index=options.index(settings.llm_model))
        else:
            llm_model = st.text_input("LLM 모델", value=settings.llm_model)
            st.caption("Ollama에 연결되지 않아 모델 목록을 불러오지 못했습니다.")

        st.markdown("**Embedding (로컬 실행)**")
        backends = ["auto", "sentence-transformers", "ollama", "hashing"]
        embed_backend = st.selectbox(
            "Embedding backend", backends, index=backends.index(settings.embed_backend)
        )
        ollama_embed_model = st.text_input(
            "Embedding 모델 (Ollama, 권장)", value=settings.ollama_embed_model,
            help="예: bge-m3. `ollama pull bge-m3` 로 설치한다.",
        )
        embed_model = st.text_input(
            "Embedding 모델 (sentence-transformers)", value=settings.embed_model,
            help="Ollama 대신 sentence-transformers를 쓸 때만 사용한다.",
        )

        st.markdown("**검색 / 답변**")
        top_k = st.slider("검색 문서 수 (Top-K)", 1, 15, settings.top_k)
        score_threshold = st.slider(
            "검색 threshold (0 = 모델별 자동)", 0.0, 0.95, float(settings.score_threshold), 0.05,
            help=(
                "이 값 이상이면 근거로 인정한다. 값이 높을수록 답변을 더 자주 거부한다. "
                "0으로 두면 Embedding 모델에 맞는 권장값이 자동 적용된다 "
                "(bge-m3 0.50 / e5 0.80 / hashing 0.30)."
            ),
        )
        st.caption(
            f"현재 적용 중인 threshold: {service.retriever.effective_threshold:.2f} "
            f"(Embedding: {service.embedder.name})"
        )
        high_confidence = st.slider(
            "‘찾았습니다’로 답할 유사도", 0.5, 1.0, float(settings.high_confidence), 0.05,
            help="이 값 이상이면 질문에 해당하는 지침을 찾은 것으로 보고 바로 답변한다.",
        )
        medium_confidence = st.slider(
            "‘유사한 내용’으로 안내할 최소 유사도", 0.1, 0.9, float(settings.medium_confidence), 0.05,
            help=(
                "이 값 이상 ~ 위 값 미만이면 '유사한 내용을 찾았습니다. 확인해 주세요'를 함께 안내한다. "
                "이 값 미만이면 근거 부족으로 답변하지 않는다."
            ),
        )
        min_coverage = st.slider(
            "질문 단어 일치 최소 비율", 0.0, 1.0, float(settings.min_keyword_coverage), 0.05,
            help="질문에 쓰인 단어가 검색 결과에서 확인된 비율. Embedding 모델과 무관한 보조 판단 기준.",
        )
        answer_length = st.radio(
            "답변 길이", ["짧게", "보통", "자세히"],
            index=["짧게", "보통", "자세히"].index(settings.answer_length),
            horizontal=True,
        )

        st.markdown("**지침문서 전용 모드**")
        strict_mode = st.checkbox(
            "등록된 지침문서 내용만 답변 (권장)", value=settings.strict_mode,
            help=(
                "켜면 ① 지침 조회가 아닌 요청(코드 작성·번역·일반 상담)과 규칙 무시 시도를 "
                "LLM 호출 전에 거부하고, ② 생성된 답변에서 문서에 근거가 없는 문장을 제거한다."
            ),
        )
        min_sentence_support = st.slider(
            "답변 문장의 문서 일치 최소 비율", 0.0, 0.9, float(settings.min_sentence_support), 0.05,
            help=(
                "답변 문장의 단어가 검색된 문서에서 확인되는 비율. 높일수록 엄격해진다. "
                "문서에 없는 숫자(기간·횟수)가 나오면 비율과 무관하게 제외한다."
            ),
        )
        include_superseded = st.checkbox(
            "과거 버전 문서도 검색에 포함", value=settings.include_superseded
        )

        submitted = st.form_submit_button("설정 저장", type="primary")

    if submitted:
        updated = Settings(
            ollama_host=settings.ollama_host,
            llm_model=llm_model,
            temperature=settings.temperature,
            llm_timeout_sec=settings.llm_timeout_sec,
            embed_backend=embed_backend,
            embed_model=embed_model,
            ollama_embed_model=ollama_embed_model,
            top_k=top_k,
            candidate_k=settings.candidate_k,
            score_threshold=score_threshold,
            keyword_weight=settings.keyword_weight,
            min_keyword_coverage=min_coverage,
            min_score_ratio=settings.min_score_ratio,
            high_confidence=high_confidence,
            medium_confidence=medium_confidence,
            strict_mode=strict_mode,
            min_sentence_support=min_sentence_support,
            include_superseded=include_superseded,
            answer_length=answer_length,
            max_context_chars=settings.max_context_chars,
            history_turns=settings.history_turns,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        service.apply_settings(updated)
        st.success("설정을 저장했습니다.")

    st.divider()
    st.markdown("**상태 점검**")
    if st.button("지금 점검하기"):
        with st.spinner("점검 중..."):
            report = service.health()
        st.code("\n".join(report.as_lines()))
        if report.embedding_model_changed:
            st.warning("Embedding 모델이 변경되었습니다. 아래 '전체 재색인'을 실행하세요.")

    if st.button("전체 재색인 (Embedding 모델 변경 시)"):
        with st.spinner("Vector Index를 다시 만드는 중..."):
            count = service.ingestor.rebuild_index()
            service.retriever.invalidate()
        st.success(f"재색인 완료: chunk {count}개")

    st.divider()
    st.markdown("**백업**")
    st.caption(f"백업 위치: {BACKUP_DIR} (자동 클라우드 백업 없음)")
    if st.button("지금 백업하기"):
        with st.spinner("백업 중..."):
            path = create_backup()
        st.success(f"백업 완료: {path.name}")
    existing = list_backups()
    if existing:
        st.caption("최근 백업: " + ", ".join(p.name for p in existing[:5]))

    st.divider()
    st.caption(f"데이터 저장 위치: {DATA_DIR}")
    st.caption("모든 처리는 이 PC 내부에서만 수행되며 외부로 전송되지 않습니다.")


# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="GuideBot", page_icon="📘", layout="wide")
    service = get_service()

    with st.sidebar:
        st.title("📘 GuideBot")
        st.caption("사내 지침문서 조회 챗봇")
        st.caption("완전 로컬 실행 · 외부 전송 없음")
        menu = st.radio("메뉴", ["Chat", "Documents", "Settings"], label_visibility="collapsed")

        st.divider()
        llm_ok = service.client.is_available()
        st.markdown(f"로컬 LLM: {'🟢 연결됨' if llm_ok else '🔴 연결 안 됨'}")
        if not llm_ok:
            st.caption("터미널에서 `ollama serve` 실행 후 새로고침하세요.")
        else:
            installed = service.client.list_models()
            selected = service.settings.llm_model
            ready = any(
                m == selected or m.split(":")[0] == selected.split(":")[0] for m in installed
            )
            if not ready:
                st.error(
                    f"답변 생성용 LLM 모델 `{selected}` 이(가) 설치되어 있지 않습니다.\n\n"
                    f"터미널에서 설치하세요:\n\n`ollama pull {selected}`\n\n"
                    "설치된 모델: " + (", ".join(installed) if installed else "없음")
                )
        stats = service.db.stats()
        st.markdown(f"문서 {stats['active_documents']}건 / Chunk {stats['chunks']}개")
        st.caption(f"Embedding: {service.embedder.name}")
        if service.settings.strict_mode:
            st.caption("🛡️ 지침문서 전용 모드 ON")
        else:
            st.warning("지침문서 전용 모드가 꺼져 있습니다(문서 밖 내용이 나올 수 있음).")
        if service.ingestor.embedding_model_changed():
            st.error(
                "Vector Index는 "
                f"`{service.store.embedder_name}` 로 만들어졌는데 지금은 "
                f"`{service.embedder.name}` 가 사용 중입니다.\n\n"
                "Ollama 실행 여부를 확인하거나, Settings에서 **전체 재색인**을 실행하세요."
            )

        if menu == "Chat" and st.button("대화 초기화"):
            st.session_state.history = []
            st.rerun()

    if menu == "Chat":
        page_chat(service)
    elif menu == "Documents":
        page_documents(service)
    else:
        page_settings(service)


main()
