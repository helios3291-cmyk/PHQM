#!/usr/bin/env python3
"""기출 CSV 병합·유동 필터 (조합 시험지용)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from exam_profiles import PROFILE_IDS, PROFILES, CSV_COLUMNS, csv_path_for

ERAS = (
    "삼국시대 이전",
    "삼국시대",
    "남북국시대",
    "고려",
    "조선",
    "개항기",
    "일제강점기",
    "현대",
)

PROFILE_LABELS = {pid: PROFILES[pid]["label"] for pid in PROFILE_IDS}


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def question_uid(row: pd.Series | dict) -> str:
    """바구니·중복 판별용 안정 키."""
    return "|".join(
        [
            str(row.get("프로파일", "")),
            str(row.get("연도", "")),
            str(row.get("학년", "")),
            str(row.get("과목", "")),
            str(row.get("문형", "")),
            str(row.get("문항번호", "")),
        ]
    )


def load_all_questions(root: Path | None = None) -> pd.DataFrame:
    root = root or project_root()
    frames: list[pd.DataFrame] = []
    for pid in PROFILE_IDS:
        path = csv_path_for(pid, root)
        if not path.exists() or path.stat().st_size == 0:
            continue
        try:
            df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
        except Exception:
            continue
        if df.empty:
            continue
        for col in CSV_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        df = df[CSV_COLUMNS].copy()
        df["프로파일"] = pid
        df["프로파일라벨"] = PROFILE_LABELS[pid]
        frames.append(df)

    if not frames:
        cols = list(CSV_COLUMNS) + ["프로파일", "프로파일라벨", "이미지존재", "uid"]
        return pd.DataFrame(columns=cols)

    out = pd.concat(frames, ignore_index=True)
    out = out.fillna("")
    out["uid"] = out.apply(question_uid, axis=1)
    try:
        from drive_images import image_available

        out["이미지존재"] = out["이미지경로"].map(
            lambda p: image_available(root, str(p), probe_drive=False)
            if str(p).strip()
            else False
        )
    except Exception:
        out["이미지존재"] = out["이미지경로"].map(
            lambda p: (root / str(p).replace("\\", "/")).is_file()
            if str(p).strip()
            else False
        )
    return out


def _parse_keywords(keyword: str | None) -> list[str]:
    if not keyword or not str(keyword).strip():
        return []
    parts = [p.strip() for p in str(keyword).replace(";", ",").split(",")]
    return [p for p in parts if p]


def filter_questions(
    df: pd.DataFrame,
    *,
    profiles: list[str] | None = None,
    eras: list[str] | None = None,
    achievement_codes: list[str] | None = None,
    keyword: str | None = None,
    require_image: bool = True,
) -> pd.DataFrame:
    """제시된 조건만 AND. 미지정 필터는 무시."""
    if df is None or df.empty:
        return df.copy() if df is not None else pd.DataFrame()

    result = df.copy()

    if profiles:
        wanted = {p.strip().lower() for p in profiles if str(p).strip()}
        if wanted:
            result = result[result["프로파일"].str.lower().isin(wanted)]

    if eras:
        wanted_eras = {e.strip() for e in eras if str(e).strip()}
        if wanted_eras:
            result = result[result["시대"].isin(wanted_eras)]

    if achievement_codes:
        codes = [c.strip() for c in achievement_codes if str(c).strip()]
        if codes:

            def code_match(val: str) -> bool:
                v = str(val or "").strip()
                if not v:
                    return False
                for c in codes:
                    if v == c or v.startswith(c):
                        return True
                return False

            result = result[result["성취기준_코드"].map(code_match)]

    keys = _parse_keywords(keyword)
    if keys:

        def kw_match(row: pd.Series) -> bool:
            blob = f"{row.get('자료핵심요소', '')} {row.get('정답핵심요소', '')}"
            return any(k in blob for k in keys)

        result = result[result.apply(kw_match, axis=1)]

    if require_image and "이미지존재" in result.columns:
        result = result[result["이미지존재"] == True]  # noqa: E712

    return result.reset_index(drop=True)


def list_achievement_codes(df: pd.DataFrame) -> list[str]:
    if df is None or df.empty or "성취기준_코드" not in df.columns:
        return []
    codes = sorted({str(c).strip() for c in df["성취기준_코드"] if str(c).strip()})
    return codes
