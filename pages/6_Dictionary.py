"""Page 6 — Dictionary.

Look up every term and concept used in the app: definitions, what each
metric measures, how it's calculated (formula + worked example), how to read
it, how this app computes it, and related concepts. Content lives in
``glossary/entries.py``; link to an entry with ``?term=<id>``.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import glossary
from ui import theme

st.set_page_config(page_title="Dictionary", page_icon="📖", layout="wide")
theme.register_theme()

st.title("📖 Dictionary")
st.caption(f"{len(glossary.ENTRIES)} terms and concepts used in this app — factors, "
           "financial metrics, leader rules, backtesting, sectors and data. Search in "
           "English or Korean (e.g. PER, PBR, 주가순자산비율, Sharpe).")

DEFAULT_TERM = "pe"


def select(entry_id: str) -> None:
    """Callback: show an entry and keep it in the URL so it can be shared."""
    st.session_state["dict_term"] = entry_id
    st.query_params["term"] = entry_id


# Deep link (?term=pb) on first load; afterwards the session state wins.
if "dict_term" not in st.session_state:
    linked = st.query_params.get("term", DEFAULT_TERM)
    st.session_state["dict_term"] = linked if glossary.get(linked) else DEFAULT_TERM

# ---------------------------------------------------------------------------
# Search + category filter (apply to both tabs)
# ---------------------------------------------------------------------------
s1, s2 = st.columns([3, 2])
query = s1.text_input("🔍 Search", key="dict_query",
                      placeholder="e.g. P/B, PER, ROE, 샤프, drawdown, carry")
category = s2.selectbox("Category", ["All", *glossary.CATEGORIES], key="dict_category")
matches = glossary.search(query, category)

# A search with results jumps to the best match, so typing "PBR" shows P/B at once.
if query.strip() and matches and st.session_state.get("_dict_last_query") != query:
    select(matches[0].id)
st.session_state["_dict_last_query"] = query

tab_lookup, tab_list = st.tabs(["🔎 Look up", "🔤 A–Z list"])


def render_entry(e: glossary.Entry) -> None:
    st.subheader(e.term)
    meta = " · ".join(x for x in (e.korean, ", ".join(e.aliases)) if x)
    st.caption(f"**{e.category}**" + (f" · {meta}" if meta else ""))
    st.markdown(e.definition)

    if e.measures:
        st.markdown("**What it measures**")
        st.markdown(e.measures)
    if e.formula:
        st.markdown("**How it's calculated**")
        st.latex(e.formula)
    if e.example:
        st.markdown("**Example**")
        st.info(e.example, icon="🧮")
    if e.interpret:
        st.markdown("**How to read it**")
        st.markdown(e.interpret)
    if e.in_app:
        st.markdown("**In this app**")
        st.markdown(e.in_app)

    links = glossary.related(e)
    if links:
        st.markdown("**Related concepts**")
        cols = st.columns(min(len(links), 3))  # 3 per row keeps longer names readable
        for i, r in enumerate(links):
            cols[i % len(cols)].button(r.term, key=f"rel_{e.id}_{r.id}", on_click=select,
                                       args=(r.id,), width="stretch", help=r.summary)
    back = glossary.referenced_by(e)
    if back:
        st.caption("Also referenced by: " + ", ".join(b.term for b in back))


# ---------------------------------------------------------------------------
# Look up: term list + entry card
# ---------------------------------------------------------------------------
with tab_lookup:
    left, right = st.columns([1, 2.4], gap="large")
    with left:
        st.caption(f"{len(matches)} of {len(glossary.ENTRIES)} terms"
                   + (f" matching “{query.strip()}”" if query.strip() else ""))
        with st.container(height=640):
            if not matches:
                st.info("No terms match. Try a shorter word, an abbreviation "
                        "(PER, MDD) or the Korean name.")
            for e in matches:
                current = e.id == st.session_state["dict_term"]
                st.button(e.term, key=f"term_{e.id}", on_click=select, args=(e.id,),
                          type="primary" if current else "secondary", width="stretch",
                          help=e.summary)
    with right:
        entry = glossary.get(st.session_state["dict_term"]) or glossary.get(DEFAULT_TERM)
        with st.container(border=True):
            render_entry(entry)

# ---------------------------------------------------------------------------
# A–Z overview
# ---------------------------------------------------------------------------
with tab_list:
    table = pd.DataFrame([{
        "Term": e.term, "Korean": e.korean, "Category": e.category,
        "Definition": e.summary, "Formula": "✓" if e.formula else "",
    } for e in matches])
    if table.empty:
        st.info("No terms match the current search.")
    else:
        st.dataframe(table, hide_index=True, width="stretch", height=640,
                     column_config={
                         "Definition": st.column_config.TextColumn(width="large"),
                         "Formula": st.column_config.TextColumn(
                             width="small", help="✓ = the entry includes a formula"),
                     })
        st.caption("Pick a term in *Look up* for the full entry: formula, example, "
                   "interpretation and related concepts.")
