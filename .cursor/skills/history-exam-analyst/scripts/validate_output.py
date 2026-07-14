#!/usr/bin/env python3
"""출력 CSV와 이미지 파일을 검증합니다."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

from exam_profiles import (
    CSV_COLUMNS,
    PROFILE_IDS,
    csv_path_for,
    get_profile,
    is_mock_or_suneung,
)

VALID_ERAS = {
    "삼국시대 이전",
    "삼국시대",
    "남북국시대",
    "고려",
    "조선",
    "개항기",
    "일제강점기",
    "현대",
}

VALID_PROBLEM_FORMATS = {
    "역사 신문형",
    "영상자료형",
    "퀴즈형",
    "마인드맵형",
    "카드형",
    "인터뷰형",
    "답사형",
    "실내전시형",
    "메신저형",
    "챗봇형",
    "수업형",
    "대화형",
    "계획서형",
    "역사 장면형",
    "역사 토론형",
    "자료 제시형",
}

YEAR_SIMPLE_RE = re.compile(r"^\d{4}$")
YEAR_MOCK_RE = re.compile(r"^(\d{4})\((\d{4})\)$")


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


EVAL_ELEMENT_SUFFIX = re.compile(r"(파악하기|이해하기|분석하기|설명하기|알기|탐구하기)$")
HIGH_CODE_RE = re.compile(r"^10한사[12]-\d{2}-\d{2}$")
MIDDLE_CODE_RE = re.compile(r"^9역\d{2}-\d{2}$")


def validate_profile(root: Path, profile_id: str, *, strict: bool = False) -> list[str]:
    errors: list[str] = []
    profile = get_profile(profile_id)
    csv_file = csv_path_for(profile_id, root)
    images_prefix = profile["images_dir"].replace("\\", "/") + "/"

    if not csv_file.exists():
        errors.append(f"[{profile_id}] CSV 없음: {csv_file}")
        return errors

    try:
        df = pd.read_csv(csv_file, encoding="utf-8-sig")
    except Exception as exc:
        errors.append(f"[{profile_id}] CSV 읽기 실패: {exc}")
        return errors

    if df.empty:
        print(f"[{profile_id}] CSV가 비어 있습니다 (헤더만 존재).")
        return errors

    for col in CSV_COLUMNS:
        if col not in df.columns:
            errors.append(f"[{profile_id}] 필수 컬럼 누락: {col}")

    validators = set(profile.get("code_validators") or ())

    for idx, row in df.iterrows():
        row_num = idx + 2
        for col in CSV_COLUMNS:
            if col not in df.columns:
                continue
            value = row.get(col)
            if pd.isna(value) or str(value).strip() == "":
                if profile_id == "hancert" and col == "성취기준_코드":
                    continue
                if col == "정답":
                    continue
                errors.append(f"[{profile_id}] 행 {row_num}: '{col}' 값이 비어 있음")

        era = str(row.get("시대", "")).strip()
        if era and era not in VALID_ERAS:
            errors.append(f"[{profile_id}] 행 {row_num}: 잘못된 시대 '{era}'")

        fmt = str(row.get("문제형식", "")).strip()
        if strict and fmt and fmt not in VALID_PROBLEM_FORMATS:
            errors.append(f"[{profile_id}] 행 {row_num}: 잘못된 문제형식 '{fmt}'")

        grade = str(row.get("학년", "")).strip()
        subject = str(row.get("과목", "")).strip()
        code = str(row.get("성취기준_코드", "")).strip()
        year = str(row.get("연도", "")).strip()
        exam_type = str(row.get("문형", "")).strip()
        pdf_name = str(row.get("원본PDF", "")).strip()

        answer = str(row.get("정답", "")).strip()
        if answer.lower() in {"", "nan", "none"}:
            answer = ""
        if answer and answer not in {"1", "2", "3", "4", "5"}:
            # pandas float 잔존값 (2.0) 허용·정규화 검사
            try:
                n = int(float(answer))
                if 1 <= n <= 5:
                    answer = str(n)
                else:
                    errors.append(f"[{profile_id}] 행 {row_num}: 정답은 1~5여야 함 — {answer}")
            except ValueError:
                errors.append(f"[{profile_id}] 행 {row_num}: 정답은 1~5여야 함 — {answer}")
            else:
                if answer not in {"1", "2", "3", "4", "5"}:
                    errors.append(f"[{profile_id}] 행 {row_num}: 정답은 1~5여야 함 — {answer}")

        if year:
            if is_mock_or_suneung(exam_type, pdf_name):
                m = YEAR_MOCK_RE.fullmatch(year)
                if not m:
                    errors.append(
                        f"[{profile_id}] 행 {row_num}: 모평·수능 연도는 "
                        f"'시행연도(학년도)' 형식이어야 함 — {year}"
                    )
                elif int(m.group(2)) != int(m.group(1)) + 1:
                    errors.append(
                        f"[{profile_id}] 행 {row_num}: 학년도는 시행연도+1이어야 함 — {year}"
                    )
            elif not YEAR_SIMPLE_RE.fullmatch(year) and not YEAR_MOCK_RE.fullmatch(year):
                errors.append(f"[{profile_id}] 행 {row_num}: 연도 형식 오류 — {year}")

        if profile_id == "basic":
            if grade == "고1" and subject not in {"역사", "한국사"}:
                errors.append(
                    f"[{profile_id}] 행 {row_num}: 고1 과목은 '역사' 또는 '한국사'여야 함 (현재: {subject})"
                )
            if "middle_9yeok" in validators and grade == "고1" and subject == "역사":
                if code and not MIDDLE_CODE_RE.fullmatch(code):
                    errors.append(f"[{profile_id}] 행 {row_num}: 고1 역사 성취기준_코드 형식 오류 — {code}")
            elif "high_10hans" in validators and grade.startswith("고"):
                if not (grade == "고1" and subject == "역사"):
                    if code and not HIGH_CODE_RE.fullmatch(code):
                        errors.append(f"[{profile_id}] 행 {row_num}: 고등 성취기준_코드 형식 오류 — {code}")
        elif profile_id == "mock" and "high_10hans" in validators:
            if code and not HIGH_CODE_RE.fullmatch(code):
                errors.append(f"[{profile_id}] 행 {row_num}: 성취기준_코드 형식 오류 — {code}")

        source_key = str(row.get("자료핵심요소", "")).strip()
        if source_key and EVAL_ELEMENT_SUFFIX.search(source_key):
            errors.append(
                f"[{profile_id}] 행 {row_num}: 자료핵심요소가 평가요소 문구로 의심됨 — {source_key[:40]}"
            )

        answer_key = str(row.get("정답핵심요소", "")).strip()
        if answer_key and re.search(r"[①②③④⑤]", answer_key):
            errors.append(f"[{profile_id}] 행 {row_num}: 정답핵심요소에 선지 기호 포함")

        image_path = str(row.get("이미지경로", "")).strip().replace("\\", "/")
        if image_path:
            if not image_path.startswith(images_prefix):
                errors.append(
                    f"[{profile_id}] 행 {row_num}: 이미지경로가 {images_prefix} 밖임 — {image_path}"
                )
            full_image = root / image_path
            if not full_image.exists():
                errors.append(f"[{profile_id}] 행 {row_num}: 이미지 없음 — {image_path}")

        pdf_path = str(row.get("원본PDF", "")).strip()
        if pdf_path:
            full_pdf = root / pdf_path
            if not full_pdf.exists():
                errors.append(f"[{profile_id}] 행 {row_num}: 원본 PDF 없음 — {pdf_path}")

    return errors


def validate_strict_coverage(root: Path) -> list[str]:
    """extracted ∩ analysis ∩ crop_warnings FATAL 검사."""
    errors: list[str] = []
    eq_path = root / "output/work/extracted_questions.json"
    an_path = root / "output/work/exam_analysis.json"
    if not eq_path.exists():
        return errors
    extracted = json.loads(eq_path.read_text(encoding="utf-8"))
    analysis = {}
    if an_path.exists():
        analysis = json.loads(an_path.read_text(encoding="utf-8"))

    for pdf_name, questions in extracted.items():
        if not questions:
            continue
        stem = questions[0].get("stem") or ""
        warn_path = root / "output/work" / stem / "crop_warnings.json"
        if warn_path.exists():
            warns = json.loads(warn_path.read_text(encoding="utf-8")).get("warnings") or []
            for w in warns:
                if "영역 수" in w or str(w).startswith("FATAL"):
                    errors.append(f"[strict] {pdf_name}: crop_warnings — {w}")

        pdf_an = analysis.get(pdf_name) or {}
        for q in questions:
            num = str(q["number"])
            if num not in pdf_an and str(int(num)) not in pdf_an:
                errors.append(f"[strict] {pdf_name} Q{num}: exam_analysis 누락")

        # 한능검: 동일 bbox 공유쌍은 번호가 연속이어야 함
        if questions[0].get("crop_engine") == "hancert" or questions[0].get("profile_id") == "hancert":
            by_bbox: dict[tuple, list[int]] = {}
            for q in questions:
                key = tuple(q.get("bbox") or [])
                by_bbox.setdefault(key, []).append(int(q["number"]))
            for bbox, nums in by_bbox.items():
                if len(nums) == 2 and abs(nums[0] - nums[1]) != 1:
                    errors.append(
                        f"[strict] {pdf_name}: 공유 bbox 번호 비연속 {nums}"
                    )
    return errors


def validate(
    root: Path,
    profile_id: str | None = None,
    all_profiles: bool = False,
    *,
    strict: bool = False,
) -> list[str]:
    if all_profiles:
        errors: list[str] = []
        for pid in PROFILE_IDS:
            errors.extend(validate_profile(root, pid, strict=strict))
        if strict:
            errors.extend(validate_strict_coverage(root))
        return errors
    errors = validate_profile(root, profile_id or "basic", strict=strict)
    if strict:
        errors.extend(validate_strict_coverage(root))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="출력 검증")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--profile", default="basic", help="basic|mock|hancert")
    parser.add_argument("--all", action="store_true", help="모든 프로파일 검증")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="문제형식 enum·분석 커버리지·치명 crop_warnings 검사",
    )
    args = parser.parse_args()

    root = args.root or project_root()
    errors = validate(
        root, profile_id=args.profile, all_profiles=args.all, strict=args.strict
    )

    if errors:
        print("검증 실패:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("검증 통과" + (" (strict)" if args.strict else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
