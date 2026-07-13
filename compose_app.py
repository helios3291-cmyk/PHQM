#!/usr/bin/env python3
"""기출 조합 시험지 — Streamlit UI (로컬 / Streamlit Cloud).

실행:
  streamlit run compose_app.py

배포: GitHub 코드 + (선택) Google Drive 이미지.
  secrets: COMPOSE_APP_PASSWORD, GDRIVE_FOLDER_ID, GDRIVE_SERVICE_ACCOUNT_JSON
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(os.environ.get("COMPOSE_DATA_ROOT", Path(__file__).resolve().parent))
SCRIPTS = Path(__file__).resolve().parent / ".cursor" / "skills" / "history-exam-analyst" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from compose_pdf import compose_to_files  # noqa: E402
from compose_query import (  # noqa: E402
    ERAS,
    PROFILE_LABELS,
    filter_questions,
    list_achievement_codes,
    load_all_questions,
    question_uid,
)
from drive_images import drive_configured, resolve_image  # noqa: E402
from exam_profiles import PROFILE_IDS  # noqa: E402


st.set_page_config(page_title="기출 조합 시험지", layout="wide")


def _secret(key: str, default: str = "") -> str:
    try:
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.environ.get(key, default)


def _check_password() -> bool:
    """비밀번호가 설정되어 있으면 게이트. 미설정 시 로컬 개발용으로 통과."""
    expected = _secret("COMPOSE_APP_PASSWORD", "").strip()
    if not expected:
        return True
    if st.session_state.get("authed"):
        return True
    st.title("기출 조합 시험지")
    st.caption("접근 비밀번호를 입력하세요.")
    pwd = st.text_input("비밀번호", type="password")
    if st.button("입장", type="primary"):
        if pwd == expected:
            st.session_state.authed = True
            st.rerun()
        st.error("비밀번호가 올바르지 않습니다.")
    return False


def _ensure_state() -> None:
    if "basket" not in st.session_state:
        st.session_state.basket = []
    if "last_exam_pdf" not in st.session_state:
        st.session_state.last_exam_pdf = None
    if "last_answer_pdf" not in st.session_state:
        st.session_state.last_answer_pdf = None


@st.cache_data(show_spinner=False)
def _cached_all() -> pd.DataFrame:
    return load_all_questions(ROOT)


def _basket_uids() -> set[str]:
    return {str(r.get("uid")) for r in st.session_state.basket}


def _add_to_basket(rows: list[dict]) -> int:
    existing = _basket_uids()
    added = 0
    for row in rows:
        uid = str(row.get("uid") or question_uid(row))
        if uid in existing:
            continue
        item = dict(row)
        item["uid"] = uid
        st.session_state.basket.append(item)
        existing.add(uid)
        added += 1
    return added


def _remove_from_basket(uid: str) -> None:
    st.session_state.basket = [r for r in st.session_state.basket if str(r.get("uid")) != uid]


def _move_basket(uid: str, delta: int) -> None:
    basket = st.session_state.basket
    idxs = [i for i, r in enumerate(basket) if str(r.get("uid")) == uid]
    if not idxs:
        return
    i = idxs[0]
    j = i + delta
    if j < 0 or j >= len(basket):
        return
    basket[i], basket[j] = basket[j], basket[i]


def _preview_image(rel: str):
    path = resolve_image(ROOT, rel)
    if path and path.is_file():
        st.image(str(path), use_container_width=True)
    else:
        st.caption("이미지 없음" + (" (Drive 확인)" if drive_configured() else ""))


def main() -> None:
    if not _check_password():
        return

    _ensure_state()
    st.title("기출 조합 시험지")
    st.caption("성취기준 · 시대 · 키워드 · 프로파일을 자유롭게 조합해 A4 2단 문제지를 만듭니다.")
    if drive_configured():
        st.caption("Google Drive 이미지 연동: 사용 중 (온디맨드 캐시)")
    else:
        st.caption("이미지: 로컬 `output/images` (Drive secrets 미설정)")

    all_df = _cached_all()
    if all_df.empty:
        st.warning("문항 데이터가 없습니다. `output/data/exam_*.csv`를 확인하세요.")
        return

    with st.sidebar:
        st.header("필터")
        profile_options = {PROFILE_LABELS[p]: p for p in PROFILE_IDS}
        selected_labels = st.multiselect(
            "프로파일",
            options=list(profile_options.keys()),
            default=[],
            help="비우면 전체 프로파일",
        )
        profiles = [profile_options[l] for l in selected_labels]

        eras = st.multiselect("시대", options=list(ERAS), default=[])
        codes = list_achievement_codes(all_df)
        achievement_codes = st.multiselect(
            "성취기준",
            options=codes,
            default=[],
            help="코드 또는 접두 일치 (예: 10한사1-03)",
        )
        achievement_prefix = st.text_input("성취기준 직접 입력(접두 가능)", value="")
        if achievement_prefix.strip():
            achievement_codes = list(
                dict.fromkeys(achievement_codes + [achievement_prefix.strip()])
            )

        keyword = st.text_input("키워드 (쉼표=OR)", value="", placeholder="예: 대동법, 임진왜란")
        require_image = st.checkbox("이미지 있는 문항만", value=True)

        filtered = filter_questions(
            all_df,
            profiles=profiles or None,
            eras=eras or None,
            achievement_codes=achievement_codes or None,
            keyword=keyword or None,
            require_image=require_image,
        )
        st.metric("후보 문항", len(filtered))

    col_cand, col_basket = st.columns([1.35, 1], gap="large")

    with col_cand:
        st.subheader("후보 목록")
        if filtered.empty:
            st.info("조건에 맞는 문항이 없습니다. 필터를 완화해 보세요.")
        else:
            n_total = len(filtered)
            if n_total <= 10:
                show_n = n_total
                st.caption(f"후보 {n_total}문항 전체 표시")
            else:
                show_n = st.slider(
                    "표시 개수",
                    min_value=1,
                    max_value=min(100, n_total),
                    value=min(30, n_total),
                )
            view = filtered.head(show_n)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("표시분 전부 바구니에 추가", use_container_width=True):
                    n = _add_to_basket(view.to_dict(orient="records"))
                    st.success(f"{n}문항 추가")
                    st.rerun()
            with c2:
                if st.button("필터 결과 전부 추가", use_container_width=True):
                    n = _add_to_basket(filtered.to_dict(orient="records"))
                    st.success(f"{n}문항 추가")
                    st.rerun()

            in_basket = _basket_uids()
            for _, row in view.iterrows():
                uid = str(row["uid"])
                already = uid in in_basket
                with st.container(border=True):
                    left, right = st.columns([1, 3])
                    with left:
                        _preview_image(str(row["이미지경로"]))
                    with right:
                        st.markdown(
                            f"**{row['프로파일라벨']}** · {row['연도']} · {row['문형']} #{row['문항번호']}  \n"
                            f"`{row['성취기준_코드']}` · {row['시대']} · {row['문제형식']}  \n"
                            f"자료: {row['자료핵심요소'][:80]}"
                        )
                        if already:
                            st.caption("바구니에 있음")
                        elif st.button("추가", key=f"add_{uid}", use_container_width=True):
                            _add_to_basket([row.to_dict()])
                            st.rerun()

    with col_basket:
        st.subheader(f"바구니 ({len(st.session_state.basket)}문항)")
        title = st.text_input("문제지 제목", value="한국사 기출 조합 문제지")
        b1, b2 = st.columns(2)
        with b1:
            if st.button(
                "바구니 비우기", use_container_width=True, disabled=not st.session_state.basket
            ):
                st.session_state.basket = []
                st.rerun()
        with b2:
            generate = st.button(
                "PDF 생성",
                type="primary",
                use_container_width=True,
                disabled=not st.session_state.basket,
            )

        if generate:
            with st.spinner("A4 2단 문제지 생성 중… (Drive면 이미지 다운로드 포함)"):
                out_dir = ROOT / "output" / "composed"
                exam_pdf, answer_pdf = compose_to_files(
                    st.session_state.basket,
                    ROOT,
                    out_dir,
                    title=title.strip() or "한국사 기출 조합 문제지",
                )
                st.session_state.last_exam_pdf = str(exam_pdf)
                st.session_state.last_answer_pdf = str(answer_pdf)
            st.success("생성 완료")

        if st.session_state.last_exam_pdf and Path(st.session_state.last_exam_pdf).is_file():
            exam_p = Path(st.session_state.last_exam_pdf)
            ans_p = (
                Path(st.session_state.last_answer_pdf)
                if st.session_state.last_answer_pdf
                else None
            )
            st.download_button(
                "문제지 PDF 다운로드",
                data=exam_p.read_bytes(),
                file_name=exam_p.name,
                mime="application/pdf",
                use_container_width=True,
            )
            if ans_p and ans_p.is_file():
                st.download_button(
                    "정답지 PDF 다운로드",
                    data=ans_p.read_bytes(),
                    file_name=ans_p.name,
                    mime="application/pdf",
                    use_container_width=True,
                )
            st.caption(f"저장 위치: `{exam_p}`")

        for row in st.session_state.basket:
            uid = str(row.get("uid"))
            with st.container(border=True):
                st.markdown(
                    f"**{row.get('프로파일라벨', '')}** {row.get('연도', '')} "
                    f"{row.get('문형', '')} #{row.get('문항번호', '')} · {row.get('시대', '')}"
                )
                st.caption(str(row.get("자료핵심요소", ""))[:100])
                a, b, c = st.columns(3)
                with a:
                    if st.button("▲", key=f"up_{uid}"):
                        _move_basket(uid, -1)
                        st.rerun()
                with b:
                    if st.button("▼", key=f"dn_{uid}"):
                        _move_basket(uid, 1)
                        st.rerun()
                with c:
                    if st.button("삭제", key=f"rm_{uid}"):
                        _remove_from_basket(uid)
                        st.rerun()


if __name__ == "__main__":
    main()
