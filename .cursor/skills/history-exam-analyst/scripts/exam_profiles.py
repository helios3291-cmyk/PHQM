#!/usr/bin/env python3
"""시험 프로파일(basic / mock / hancert) — CSV·이미지 경로 분기."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

PROFILE_IDS = ("basic", "mock", "hancert")

PROFILES: dict[str, dict[str, Any]] = {
    "basic": {
        "id": "basic",
        "label": "기초학력",
        "csv": "output/data/exam_basic.csv",
        "images_dir": "output/images/basic",
        "achievement": "classification_or_index",
        "code_validators": ("middle_9yeok", "high_10hans"),
        # 진단·향상도 검사지
        "pdf_name_hints": ("검사지", "기초학력", "향상도"),
    },
    "mock": {
        "id": "mock",
        "label": "모의고사",
        "csv": "output/data/exam_mock.csv",
        "images_dir": "output/images/mock",
        "achievement": "curriculum_index_ai",
        "code_validators": ("high_10hans",),
        "pdf_name_hints": ("학평", "모평", "수능", "전국연합", "평가원"),
    },
    "hancert": {
        "id": "hancert",
        "label": "한국사능력검정시험",
        "csv": "output/data/exam_hancert.csv",
        "images_dir": "output/images/hancert",
        "achievement": "hancert_or_none",
        "code_validators": (),
        "pdf_name_hints": ("한국사능력", "한능검", "능력검정", "회)", "심화", "기본"),
    },
}

CSV_COLUMNS = [
    "연도",
    "학년",
    "과목",
    "문형",
    "문항번호",
    "성취기준_코드",
    "시대",
    "문제형식",
    "세부형식",
    "자료핵심요소",
    "정답핵심요소",
    "이미지경로",
    "원본PDF",
    "처리일시",
]


def get_profile(profile_id: str) -> dict[str, Any]:
    key = (profile_id or "basic").strip().lower()
    if key not in PROFILES:
        raise ValueError(f"알 수 없는 프로파일: {profile_id} (허용: {', '.join(PROFILE_IDS)})")
    return PROFILES[key]


def csv_path_for(profile_id: str, root: Path) -> Path:
    return root / get_profile(profile_id)["csv"]


def images_dir_for(profile_id: str, root: Path) -> Path:
    return root / get_profile(profile_id)["images_dir"]


def _sanitize(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\s]+', "_", str(value).strip())
    return cleaned.strip("_") or "unknown"


def is_mock_or_suneung(exam_type: str = "", name: str = "") -> bool:
    """모평·수능 여부. 학평은 False."""
    et = exam_type or ""
    text = name or ""
    if "학평" in et or ("학평" in text and "모평" not in et and "모평" not in text):
        return False
    return (
        "모평" in et
        or et == "수능"
        or "모평" in text
        or ("수능" in text and "모평" not in text)
    )


def format_exam_year(labeled_year: str, exam_type: str = "", name: str = "") -> str:
    """연도 표기 규칙.

    - 학평·기초학력 등: 표기연도만 (예: ``2026``)
    - 모평·수능: ``시행연도(학년도)`` (예: ``2026(2027)``)
      PDF 파일명의 ``(YYYY)`` / ``YYYY학년도``는 표기 연도(학년도)로 본다.
      시행 연도 = 학년도 − 1 (예: 2027학년도 6월 모평·수능 → 2026년 시행).
    """
    labeled = str(labeled_year or "").strip()
    if not labeled:
        return ""
    if re.fullmatch(r"\d{4}\(\d{4}\)", labeled):
        return labeled
    if not labeled.isdigit():
        return labeled
    if is_mock_or_suneung(exam_type, name):
        return f"{int(labeled) - 1}({labeled})"
    return labeled


def image_rel_path(
    profile_id: str,
    year: str,
    grade: str,
    subject: str,
    exam_type: str,
    number: str,
) -> str:
    """CSV·디스크에 쓰는 상대 이미지 경로."""
    parts = [
        _sanitize(year),
        _sanitize(grade),
        _sanitize(subject),
        _sanitize(exam_type),
        _sanitize(number),
    ]
    filename = "_".join(parts) + ".png"
    rel_dir = get_profile(profile_id)["images_dir"].replace("\\", "/")
    return f"{rel_dir}/{filename}"


def detect_profile_from_name(name: str, *, default: str | None = "basic") -> str | None:
    """파일명·경로 문자열로 프로파일 추론.

    default=None 이면 미매칭 시 None (호출측에서 실패 처리).
    """
    text = name or ""
    # 한능검 우선 (폴더명·회차·심화/기본)
    if (
        "한국사능력" in text
        or "한능검" in text
        or "능력검정" in text
        or re.search(r"\(\d{1,3}회\)", text)
        or (re.search(r"(심화|기본)", text) and "한국사" in text and "기초학력" not in text)
    ):
        return "hancert"
    for hint in PROFILES["mock"]["pdf_name_hints"]:
        if hint in text:
            return "mock"
    # 기초학력 검사지 / 향상도
    if "기초학력" in text or "향상도" in text:
        return "basic"
    if re.search(r"\((가형|나형|A형|B형|C형|C\d+형)\)", text):
        return "basic"
    if "검사지" in text and "한국사" in text and re.search(r"고[123]", text):
        return "basic"
    if "검사지" in text and "역사" in text:
        return "basic"
    return default


def ensure_profile_dirs(root: Path, profile_id: str | None = None) -> None:
    ids = (profile_id,) if profile_id else PROFILE_IDS
    for pid in ids:
        images_dir_for(pid, root).mkdir(parents=True, exist_ok=True)
        path = csv_path_for(pid, root)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            import pandas as pd

            pd.DataFrame(columns=CSV_COLUMNS).to_csv(path, index=False, encoding="utf-8-sig")
