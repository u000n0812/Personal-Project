"""사내 지침 챗봇 - 로컬 Web UI (요구사항 13, 14, 15 / Phase 7, 8).

실행:
    python run_app.py
    (또는) streamlit run ui/streamlit_app.py --server.address 127.0.0.1

127.0.0.1 에만 Binding 되며, 외부 네트워크로는 어떤 데이터도 전송하지 않는다.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# 패키지 import 경로 확보 (streamlit run 으로 실행될 때 필요)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import netguard  # noqa: E402

netguard.install()  # 외부 통신 차단을 가장 먼저 설치한다.

import streamlit as st  # noqa: E402

from app.backup import create_backup, list_backups  # noqa: E402
from app.config import (  # noqa: E402
    DATA_DIR,
    SUPPORTED_EXTENSIONS,
    Settings,
    load_settings,
    save_settings,
)
from app.llm import OllamaClient  # noqa: E402
from app.pipeline import DocumentIndex  # noqa: E402
from app.rag import RagEngine, format_sources  # noqa: E402
from app.search import open_source_file  # noqa: E402
from app.vectorstore import index_model_name  # noqa: E402

st.set_page_config(page_title="사내 지침 챗봇", page_icon="📘", layout="wide")


# --------------------------------------------------------------------- 자원
@st.cache_resource(show_spinner=False)
def get_engine(signature: str) -> RagEngine:
    """설정이 바뀌면 새 엔진을 만든다(모델/인덱스는 캐시해 재사용)."""
    settings = load_settings()
    return RagEngine(settings, index=DocumentIndex(settings))


def settings_signature(settings: Settings) -> str:
    return f"{settings.embedding_model}|{settings.llm_model}|{settings.ollama_host}"


def current_engine() -> RagEngine:
    settings = st.session_state.settings
    engine = get_engine(settings_signature(settings))
    # 검색 파라미터는 매번 최신 설정을 반영한다(재로딩 불필요).
    engine.settings = settings
    engine.index.settings = settings
    return engine


def init_state() -> None:
    if "settings" not in st.session_state:
        st.session_state.settings = load_settings()
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "page" not in st.session_state:
        st.session_state.page = "💬 Chat"


# --------------------------------------------------------------------- 공통
def render_sidebar() -> str:
    settings = st.session_state.settings
    with st.sidebar:
        st.title("📘 사내 지침 챗봇")
        st.caption("완전 로컬 실행 · 외부 전송 없음")

        page = st.radio(
            "메뉴", ["💬 Chat", "📁 Documents", "⚙️ Settings"], label_visibility="collapsed"
        )

        st.divider()
        client = OllamaClient(settings.ollama_host)
        if client.health():
            st.success(f"로컬 LLM 연결됨\n\n{settings.llm_model}")
        else:
            st.error("로컬 LLM 미연결\n\n터미널에서 `ollama serve` 실행")

        try:
            info = current_engine().index.stats()
            st.metric("등록 문서", f"{info['active_documents']} / {info['documents']}")
            st.caption(f"Chunk {info['chunks']:,}개 · Vector {info['vectors']:,}개 ({info['backend']})")
        except Exception as exc:
            st.warning(f"인덱스 준비 필요\n\n{type(exc).__name__}")

        st.divider()
        st.caption(
            f"🔒 외부 네트워크 차단: {'ON' if netguard.is_installed() else 'OFF'}\n\n"
            f"📂 데이터 폴더\n\n`{DATA_DIR}`"
        )
    return page


def render_sources(hits: list[dict], key_prefix: str) -> None:
    """검색된 실제 문장을 확인할 수 있게 한다 (요구사항 15)."""
    if not hits:
        return
    st.markdown("**[참고한 문서]**")
    for number, hit in enumerate(hits, start=1):
        header = f"{number}. {hit['citation']}  ·  Similarity {hit['vector_score']:.2f} / Score {hit['score']:.2f}"
        with st.expander(header):
            st.markdown(f"> {hit['body'][:1500].replace(chr(10), chr(10) + '> ')}")
            columns = st.columns([1, 4])
            with columns[0]:
                if st.button("문서 열기", key=f"{key_prefix}_open_{number}"):
                    if open_source_file(hit["stored_path"]):
                        st.toast(f"{hit['filename']} 을(를) 열었습니다.")
                    else:
                        st.warning("파일을 열 수 없습니다. 경로를 확인하세요.")
            with columns[1]:
                st.caption(f"`{hit['stored_path']}`")


def hit_to_dict(hit) -> dict:
    return {
        "citation": hit.citation,
        "title": hit.title,
        "version": hit.version,
        "filename": hit.filename,
        "stored_path": hit.stored_path,
        "page": hit.page,
        "section": hit.heading_path or hit.section,
        "body": hit.body,
        "score": hit.score,
        "vector_score": hit.vector_score,
        "keyword_score": hit.keyword_score,
    }


# --------------------------------------------------------------------- Chat
def page_chat() -> None:
    header = st.columns([4, 1])
    with header[0]:
        st.subheader("💬 업무 절차 질문하기")
        st.caption(
            "등록된 지침문서에서 근거를 찾아 답변합니다. 문서에 없는 내용은 답변하지 않습니다."
        )
    with header[1]:
        if st.session_state.messages and st.button("대화 새로 시작", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    engine = current_engine()

    for index_, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                render_sources(message.get("hits", []), key_prefix=f"msg{index_}")

    question = st.chat_input("예) External Data 전달 절차가 어떻게 되었지?")
    if not question:
        return

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    history = [
        {"role": message["role"], "content": message["content"]}
        for message in st.session_state.messages[:-1]
    ]

    with st.chat_message("assistant"):
        with st.spinner("지침문서를 검색하는 중..."):
            stream, result = engine.ask_stream(question, history=history)
        answer_text = st.write_stream(stream)
        hits = [hit_to_dict(hit) for hit in result.hits]
        if hits and "등록된 지침문서에서는" not in answer_text:
            sources = format_sources(result.hits)
            answer_text = f"{answer_text}\n\n{sources}"
            st.markdown(f"```\n{sources}\n```")
        render_sources(hits, key_prefix=f"msg{len(st.session_state.messages)}")

    st.session_state.messages.append(
        {"role": "assistant", "content": answer_text, "hits": hits}
    )


# ---------------------------------------------------------------- Documents
def page_documents() -> None:
    st.subheader("📁 지침문서 관리")
    engine = current_engine()
    index = engine.index

    tab_add, tab_list = st.tabs(["문서 등록", "등록 목록"])

    with tab_add:
        st.markdown("**파일 등록** (여러 개 선택 가능)")
        uploaded = st.file_uploader(
            "지원 형식: " + ", ".join(sorted(extension[1:].upper() for extension in SUPPORTED_EXTENSIONS)),
            type=[extension[1:] for extension in sorted(SUPPORTED_EXTENSIONS)],
            accept_multiple_files=True,
        )
        force = st.checkbox("이미 등록된 문서도 다시 색인", value=False)
        if uploaded and st.button("등록 시작", type="primary"):
            with tempfile.TemporaryDirectory() as workspace:
                paths = []
                for item in uploaded:
                    path = Path(workspace) / item.name
                    path.write_bytes(item.getbuffer())
                    paths.append(path)
                progress = st.progress(0.0, text="등록 준비 중...")
                results = []
                for number, path in enumerate(paths, start=1):
                    progress.progress(
                        number / len(paths), text=f"({number}/{len(paths)}) {path.name}"
                    )
                    results.append(index.ingest_file(path, force=force))
                progress.empty()
            _show_ingest_results(results)

        st.divider()
        st.markdown("**폴더 단위 등록**")
        folder = st.text_input("폴더 경로", placeholder=r"예) C:\회사지침\SOP")
        recursive = st.checkbox("하위 폴더 포함", value=True)
        if folder and st.button("폴더 등록"):
            with st.spinner("폴더의 문서를 등록하는 중..."):
                results = index.ingest_folder(folder, recursive=recursive, force=force)
            _show_ingest_results(results)

    with tab_list:
        rows = index.documents()
        if not rows:
            st.info("아직 등록된 문서가 없습니다. [문서 등록] 탭에서 지침문서를 추가하세요.")
            return

        st.dataframe(
            [
                {
                    "ID": row["id"],
                    "문서명": row["title"],
                    "버전": row["version"] or "-",
                    "형식": row["ext"],
                    "Chunk 수": row["chunk_count"],
                    "상태": "활성" if row["status"] == "active" else "비활성(과거 버전)",
                    "등록일": row["created_at"],
                    "수정일": row["updated_at"],
                }
                for row in rows
            ],
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("**문서 작업**")
        labels = {
            f"[{row['id']}] {row['title']} {('v' + row['version']) if row['version'] else ''}": int(row["id"])
            for row in rows
        }
        selected = st.selectbox("대상 문서", list(labels.keys()))
        document_id = labels[selected]
        selected_row = next(row for row in rows if int(row["id"]) == document_id)

        columns = st.columns(4)
        with columns[0]:
            if st.button("재색인", use_container_width=True):
                with st.spinner("재색인 중..."):
                    result = index.reindex_document(document_id)
                st.success(result.message) if result.ok else st.error(result.message)
                st.rerun()
        with columns[1]:
            activate = selected_row["status"] != "active"
            if st.button("활성화" if activate else "비활성화", use_container_width=True):
                index.set_status(document_id, active=activate)
                st.rerun()
        with columns[2]:
            if st.button("문서 열기", use_container_width=True):
                if not open_source_file(selected_row["stored_path"]):
                    st.warning("파일을 열 수 없습니다.")
        with columns[3]:
            confirm = st.checkbox("삭제 확인", key=f"confirm_delete_{document_id}")
            if st.button("삭제", type="primary", disabled=not confirm, use_container_width=True):
                index.delete_document(document_id)
                st.success("원본/Chunk/Embedding/Metadata 를 모두 삭제했습니다.")
                st.rerun()

        st.caption(
            "같은 문서의 새 버전을 등록하면 이전 버전은 자동으로 비활성 처리되고, "
            "검색은 최신 활성 버전을 기준으로 수행됩니다."
        )


def _show_ingest_results(results) -> None:
    if not results:
        st.warning("처리할 문서가 없습니다.")
        return
    succeeded = [result for result in results if result.ok]
    failed = [result for result in results if not result.ok]
    if succeeded:
        st.success(f"{len(succeeded)}건 처리 완료")
    for result in results:
        line = f"**{result.filename}** · {result.status} · {result.message}"
        st.error(line) if not result.ok else st.write(line)
    if failed:
        st.warning(f"{len(failed)}건 실패")


# ----------------------------------------------------------------- Settings
def page_settings() -> None:
    st.subheader("⚙️ 설정")
    settings: Settings = st.session_state.settings
    client = OllamaClient(settings.ollama_host)
    installed_models = client.list_models()

    with st.form("settings_form"):
        st.markdown("**LLM (로컬 Ollama)**")
        if installed_models:
            options = installed_models
            default_index = (
                options.index(settings.llm_model) if settings.llm_model in options else 0
            )
            llm_model = st.selectbox("LLM 모델", options, index=default_index)
        else:
            llm_model = st.text_input("LLM 모델", value=settings.llm_model)
            st.caption("Ollama 미연결 상태입니다. 모델 이름을 직접 입력하세요.")

        answer_length = st.radio(
            "답변 길이", ["짧게", "보통", "자세히"],
            index=["짧게", "보통", "자세히"].index(settings.answer_length),
            horizontal=True,
        )
        history_turns = st.slider("대화 Context 유지(최근 turn 수)", 0, 6, settings.history_turns)

        st.divider()
        st.markdown("**검색**")
        top_k = st.slider("검색 문서 수 (Top-K)", 1, 15, settings.top_k)
        score_threshold = st.slider(
            "검색 threshold (낮을수록 관대)", 0.0, 1.0, float(settings.score_threshold), 0.05
        )
        vector_weight = st.slider(
            "Vector : Keyword 가중치 (1.0 = Vector 만)", 0.0, 1.0, float(settings.vector_weight), 0.1
        )

        st.divider()
        st.markdown("**Embedding**")
        embedding_model = st.text_input("Embedding 모델", value=settings.embedding_model)
        st.caption(
            "모델을 바꾸면 기존 인덱스를 사용할 수 없어 전체 재색인이 필요합니다. "
            "모델 파일은 `python scripts/prepare_models.py` 로 미리 받아두세요."
        )

        submitted = st.form_submit_button("설정 저장", type="primary")

    if submitted:
        settings.llm_model = llm_model
        settings.answer_length = answer_length
        settings.history_turns = history_turns
        settings.top_k = top_k
        settings.score_threshold = score_threshold
        settings.vector_weight = vector_weight
        settings.embedding_model = embedding_model
        save_settings(settings)
        st.session_state.settings = settings
        get_engine.clear()
        st.success("설정을 저장했습니다.")

    indexed_model = index_model_name()
    if indexed_model and indexed_model != settings.embedding_model:
        st.warning(
            f"현재 인덱스는 `{indexed_model}` 로 생성되었습니다. "
            f"설정된 모델(`{settings.embedding_model}`)로 검색하려면 전체 재색인이 필요합니다."
        )
        if st.button("전체 재색인 실행"):
            with st.spinner("전체 문서를 다시 색인하는 중..."):
                results = current_engine().index.rebuild_all()
            st.success(f"{sum(1 for r in results if r.ok)}건 재색인 완료")

    st.divider()
    st.markdown("**백업 (로컬 저장, 자동 Cloud 백업 없음)**")
    columns = st.columns([1, 3])
    with columns[0]:
        if st.button("백업 생성"):
            path = create_backup()
            st.success(f"백업 생성 완료: {path.name}")
    with columns[1]:
        backups = list_backups()
        if backups:
            st.caption("최근 백업: " + ", ".join(path.name for path in backups[:3]))
        else:
            st.caption("생성된 백업이 없습니다.")

    st.divider()
    with st.expander("고급 설정 (Chunk)"):
        st.caption("변경 후에는 문서 재색인을 권장합니다.")
        chunk_size = st.number_input("Chunk 크기(글자)", 200, 3000, settings.chunk_size, 50)
        chunk_overlap = st.number_input("Chunk Overlap(글자)", 0, 500, settings.chunk_overlap, 10)
        if st.button("Chunk 설정 저장"):
            settings.chunk_size = int(chunk_size)
            settings.chunk_overlap = int(chunk_overlap)
            save_settings(settings)
            st.session_state.settings = settings
            st.success("저장했습니다. 기존 문서는 [Documents] 탭에서 재색인하세요.")


# --------------------------------------------------------------------- main
def main() -> None:
    init_state()
    page = render_sidebar()
    if page == "💬 Chat":
        page_chat()
    elif page == "📁 Documents":
        page_documents()
    else:
        page_settings()


main()
