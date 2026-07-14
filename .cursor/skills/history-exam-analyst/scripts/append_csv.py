#!/usr/bin/env python3
"""추출 결과를 프로파일별 CSV에 추가합니다."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from exam_profiles import (
    CSV_COLUMNS,
    csv_path_for,
    ensure_profile_dirs,
    get_profile,
)
from normalize_class_code import answer_label_to_number


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def resolve_path(path: Path, root: Path) -> Path:
    return path if path.is_absolute() else root / path


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=CSV_COLUMNS)
    df = pd.read_csv(path, encoding="utf-8-sig")
    if "문형" not in df.columns:
        df.insert(3, "문형", "")
    for col in CSV_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[CSV_COLUMNS]


def check_duplicate(df: pd.DataFrame, row: dict) -> bool:
    if df.empty:
        return False
    mask = (
        (df["연도"].astype(str) == str(row["연도"]))
        & (df["학년"].astype(str) == str(row["학년"]))
        & (df["과목"].astype(str) == str(row["과목"]))
        & (df["문형"].astype(str) == str(row["문형"]))
        & (df["문항번호"].astype(str) == str(row["문항번호"]))
    )
    return bool(mask.any())


def append_row(
    root: Path,
    row: dict,
    profile_id: str = "basic",
    force: bool = False,
) -> None:
    get_profile(profile_id)
    ensure_profile_dirs(root, profile_id)
    path = csv_path_for(profile_id, root)
    path.parent.mkdir(parents=True, exist_ok=True)

    df = load_csv(path)
    if check_duplicate(df, row) and not force:
        print(
            f"경고: 중복 문항 — {row['연도']}/{row['학년']}/{row['과목']}/"
            f"{row['문형']}/{row['문항번호']}",
            file=sys.stderr,
        )
        print("덮어쓰려면 --force 옵션을 사용하세요.", file=sys.stderr)
        raise SystemExit(2)

    if check_duplicate(df, row) and force:
        mask = ~(
            (df["연도"].astype(str) == str(row["연도"]))
            & (df["학년"].astype(str) == str(row["학년"]))
            & (df["과목"].astype(str) == str(row["과목"]))
            & (df["문형"].astype(str) == str(row["문형"]))
            & (df["문항번호"].astype(str) == str(row["문항번호"]))
        )
        df = df[mask]

    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"저장 [{profile_id}]: {path.relative_to(root).as_posix()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="CSV에 문항 행 추가")
    parser.add_argument("--profile", default="basic", help="basic|mock|hancert")
    parser.add_argument("--year", required=True)
    parser.add_argument("--grade", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--exam-type", required=True, help="문형 (예: 가형, 나형, A형)")
    parser.add_argument("--number", required=True)
    parser.add_argument("--achievement-code", required=True)
    parser.add_argument("--era", required=True)
    parser.add_argument("--format", dest="problem_format", required=True)
    parser.add_argument("--sub-format", required=True)
    parser.add_argument("--source-key", required=True, help="자료핵심요소")
    parser.add_argument(
        "--answer",
        default="",
        help="정답 선지 번호 1~5 (또는 ①~⑤)",
    )
    parser.add_argument("--answer-key", required=True, help="정답핵심요소")
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--source-pdf", type=Path, required=True)
    parser.add_argument("--force", action="store_true", help="중복 시 덮어쓰기")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args()

    root = args.root or project_root()
    image = resolve_path(args.image, root)
    source_pdf = resolve_path(args.source_pdf, root)

    answer = answer_label_to_number(str(args.answer)) if args.answer else ""
    if args.answer and answer not in {"1", "2", "3", "4", "5"}:
        print(f"오류: --answer는 1~5 또는 ①~⑤여야 함 (입력: {args.answer})", file=sys.stderr)
        return 1

    row = {
        "연도": args.year,
        "학년": args.grade,
        "과목": args.subject,
        "문형": args.exam_type,
        "문항번호": args.number,
        "성취기준_코드": args.achievement_code,
        "시대": args.era,
        "문제형식": args.problem_format,
        "세부형식": args.sub_format,
        "자료핵심요소": args.source_key,
        "정답": answer,
        "정답핵심요소": args.answer_key,
        "이미지경로": image.relative_to(root).as_posix() if image.is_relative_to(root) else str(args.image),
        "원본PDF": source_pdf.relative_to(root).as_posix() if source_pdf.is_relative_to(root) else str(args.source_pdf),
        "처리일시": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }

    try:
        append_row(root, row, profile_id=args.profile, force=args.force)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
