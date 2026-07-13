#!/usr/bin/env python3
"""extracted_questions.json + exam_analysis/classification → 이미지 크롭 및 CSV 저장."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from crop_question import crop_question
from exam_profiles import (
    CSV_COLUMNS,
    csv_path_for,
    detect_profile_from_name,
    ensure_profile_dirs,
    image_rel_path,
)
from index_classification import classification_path_for_exam, parse_classification_pdf
from normalize_class_code import normalize_class_code


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def load_classification(root: Path, source_pdf: str) -> dict | None:
    exam_pdf = root / source_pdf
    cls_pdf = classification_path_for_exam(exam_pdf, root)
    if cls_pdf is None:
        return None

    stem = exam_pdf.stem
    cls_json = root / "output" / "work" / stem / "classification.json"
    ach_index = root / "output" / "work" / "achievement_index.json"
    needs_reindex = (
        (not cls_json.exists())
        or (cls_json.stat().st_mtime < cls_pdf.stat().st_mtime)
        or (ach_index.exists() and cls_json.stat().st_mtime < ach_index.stat().st_mtime)
    )
    if needs_reindex:
        result = parse_classification_pdf(cls_pdf, root)
        cls_json.parent.mkdir(parents=True, exist_ok=True)
        cls_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"분류표 인덱싱: {cls_pdf.name} → {len(result['entries'])}문항")

    return json.loads(cls_json.read_text(encoding="utf-8"))


def build_meta(
    num: str,
    pdf_analysis: dict,
    classification: dict | None,
) -> dict | None:
    cls_entry = None
    if classification:
        for e in classification.get("entries", []):
            if str(e["number"]) == num:
                cls_entry = e
                break

    ai_meta = pdf_analysis.get(num)
    if not ai_meta:
        return None

    achievement_code = ai_meta.get("achievement_code", "")

    if cls_entry:
        achievement_code = cls_entry.get("achievement_code") or achievement_code

    normalized = normalize_class_code(achievement_code) if achievement_code else None
    if normalized:
        achievement_code = normalized

    return {
        "achievement_code": achievement_code,
        "era": ai_meta.get("era", ""),
        "problem_format": ai_meta.get("problem_format", ""),
        "sub_format": ai_meta.get("sub_format", ""),
        "source_key": ai_meta.get("source_key", ""),
        "answer_key": ai_meta.get("answer_key", ""),
        "from_classification": bool(cls_entry),
    }


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=CSV_COLUMNS)
    df = pd.read_csv(path, encoding="utf-8-sig")
    for col in CSV_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[CSV_COLUMNS]


def merge_rows(df: pd.DataFrame, new_rows: list[dict]) -> pd.DataFrame:
    if not new_rows:
        return df
    new_df = pd.DataFrame(new_rows)
    if df.empty:
        return new_df[CSV_COLUMNS]

    keys = ["연도", "학년", "과목", "문형", "문항번호"]
    df = df.copy()
    df["_k"] = df[keys].astype(str).agg("|".join, axis=1)
    new_df["_k"] = new_df[keys].astype(str).agg("|".join, axis=1)
    df = df[~df["_k"].isin(set(new_df["_k"]))]
    out = pd.concat([df.drop(columns=["_k"]), new_df.drop(columns=["_k"])], ignore_index=True)
    return out[CSV_COLUMNS]


def save_csv(df: pd.DataFrame, path: Path) -> Path:
    """temp+rename 원자 쓰기. 잠금 시 실패(사이드 파일 성공 금지)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    data = tmp.read_bytes()
    last_err: Exception | None = None
    for _ in range(25):
        try:
            path.write_bytes(data)
            tmp.unlink(missing_ok=True)
            return path
        except PermissionError as exc:
            last_err = exc
            time.sleep(1)
    tmp.unlink(missing_ok=True)
    raise PermissionError(f"CSV locked: {path}") from last_err


def _crop_warnings_fatal(root: Path, stem: str) -> str | None:
    warn_path = root / "output" / "work" / stem / "crop_warnings.json"
    if not warn_path.exists():
        return None
    try:
        warns = json.loads(warn_path.read_text(encoding="utf-8")).get("warnings") or []
    except Exception:
        return None
    for w in warns:
        if "영역 수" in w or str(w).startswith("FATAL"):
            return str(w)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="문항 크롭 및 CSV 저장")
    parser.add_argument("--crop-only", action="store_true", help="이미지만 재크롭 (CSV 생략)")
    parser.add_argument("--pdf", type=str, default=None, help="특정 PDF만 처리")
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="해당 프로파일 PDF만 처리 (필터). 경로·크롭 대상은 PDF명 자동 추론 유지",
    )
    args = parser.parse_args()

    root = project_root()
    ensure_profile_dirs(root)
    extracted_path = root / "output/work/extracted_questions.json"
    if not extracted_path.exists():
        print("extracted_questions.json 없음", file=sys.stderr)
        return 1

    extracted = json.loads(extracted_path.read_text(encoding="utf-8"))
    analysis_path = root / "output/work/exam_analysis.json"
    analysis: dict = {}
    if analysis_path.exists():
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))

    crop_ok = 0
    crop_fail = 0
    csv_skip = 0
    cls_used = 0
    csv_by_profile: dict[str, list[dict]] = {}
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    pdf_names = sorted(extracted.keys())
    if args.pdf:
        pdf_names = [p for p in pdf_names if p == args.pdf]

    for pdf_name in pdf_names:
        questions = extracted[pdf_name]
        if not questions:
            continue
        pdf_analysis = analysis.get(pdf_name, {})
        source_pdf = questions[0].get("source_pdf") or ""
        stem = questions[0].get("stem") or Path(source_pdf).stem
        stored_profile = questions[0].get("profile_id")
        auto_profile = detect_profile_from_name(pdf_name, default=None)
        if auto_profile is None:
            print(f"{pdf_name}: skip (프로파일 추론 실패)", file=sys.stderr)
            crop_fail += 1
            continue
        if args.profile and auto_profile != args.profile:
            print(f"{pdf_name}: skip (auto={auto_profile}, filter={args.profile})")
            continue
        if stored_profile and stored_profile != auto_profile:
            print(
                f"{pdf_name}: skip (stored profile={stored_profile} ≠ auto={auto_profile})",
                file=sys.stderr,
            )
            crop_fail += 1
            continue

        fatal = _crop_warnings_fatal(root, stem)
        if fatal:
            print(f"{pdf_name}: skip (crop_warnings: {fatal})", file=sys.stderr)
            crop_fail += 1
            continue

        profile_id = auto_profile
        print(f"{pdf_name}: profile={profile_id}")
        classification = load_classification(root, source_pdf) if source_pdf else None
        if classification:
            print(f"{pdf_name}: 분류표(성취기준) ({len(classification.get('entries', []))}문항)")

        for q in questions:
            num = str(q["number"])
            year, grade, subject = q["year"], q["grade"], q["subject"]
            exam_type = q["exam_type"]
            img_rel = image_rel_path(profile_id, year, grade, subject, exam_type, num)

            try:
                crop_question(
                    Path(q["page_image"]),
                    tuple(q["bbox"]),
                    Path(img_rel),
                    root,
                )
            except Exception as exc:
                print(f"crop fail {pdf_name} Q{num}: {exc}", file=sys.stderr)
                crop_fail += 1
                continue
            crop_ok += 1

            if args.crop_only:
                continue

            meta = build_meta(num, pdf_analysis, classification)
            if not meta:
                print(f"csv skip {pdf_name} Q{num}: no analysis", file=sys.stderr)
                csv_skip += 1
                continue

            if meta.get("from_classification"):
                cls_used += 1

            csv_by_profile.setdefault(profile_id, []).append(
                {
                    "연도": year,
                    "학년": grade,
                    "과목": subject,
                    "문형": exam_type,
                    "문항번호": num,
                    "성취기준_코드": meta["achievement_code"],
                    "시대": meta["era"],
                    "문제형식": meta["problem_format"],
                    "세부형식": meta["sub_format"],
                    "자료핵심요소": meta["source_key"],
                    "정답핵심요소": meta["answer_key"],
                    "이미지경로": img_rel,
                    "원본PDF": q["source_pdf"],
                    "처리일시": now,
                }
            )

    csv_error = 0
    if not args.crop_only:
        for profile_id, csv_rows in csv_by_profile.items():
            if not csv_rows:
                continue
            csv_path = csv_path_for(profile_id, root)
            try:
                df = merge_rows(load_csv(csv_path), csv_rows)
                saved = save_csv(df, csv_path)
                print(
                    f"CSV 저장 [{profile_id}]: {saved.relative_to(root)} "
                    f"({len(csv_rows)}행 갱신)"
                )
            except PermissionError as exc:
                print(f"CSV 저장 실패 [{profile_id}]: {exc}", file=sys.stderr)
                csv_error += 1

    mode = "크롭만" if args.crop_only else "크롭+CSV"
    print(
        f"완료 ({mode}): crop_ok={crop_ok}, crop_fail={crop_fail}, "
        f"csv_skip={csv_skip}, 분류표={cls_used}"
    )
    return 0 if crop_fail == 0 and csv_error == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
