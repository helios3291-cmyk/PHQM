#!/usr/bin/env python3
"""기초학력(exam_basic.csv) 정답을 내용분류표 PDF에서 백필.

각 행의 원본PDF → classification_path_for_exam → parse → 정답(1~5).

```bash
python .cursor/skills/history-exam-analyst/scripts/backfill_basic_from_classification.py
```
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from exam_profiles import CSV_COLUMNS, csv_path_for  # noqa: E402
from index_classification import (  # noqa: E402
    classification_path_for_exam,
    parse_classification_pdf,
)
from normalize_class_code import answer_label_to_number  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]


def ensure_answer_column(df: pd.DataFrame) -> pd.DataFrame:
    for col in CSV_COLUMNS:
        if col in df.columns:
            continue
        if col == "정답" and "정답핵심요소" in df.columns:
            idx = list(df.columns).index("정답핵심요소")
            df.insert(idx, "정답", "")
        else:
            df[col] = ""
    return df[CSV_COLUMNS]


def normalize_answer(value) -> str:
    s = str(value or "").strip()
    if not s or s.lower() in {"nan", "none"}:
        return ""
    ans = answer_label_to_number(s) or s
    try:
        n = int(float(ans))
        if 1 <= n <= 5:
            return str(n)
    except ValueError:
        pass
    return ans if ans in {"1", "2", "3", "4", "5"} else ""


def load_answers_for_exam(exam_pdf: Path) -> tuple[dict[str, str], Path | None, list[str]]:
    cls_path = classification_path_for_exam(exam_pdf, ROOT)
    if cls_path is None or not cls_path.exists():
        return {}, None, [f"분류표 없음: {exam_pdf}"]

    cache_stem = exam_pdf.stem
    cache_dir = ROOT / "output" / "work" / cache_stem
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_json = cache_dir / "classification.json"

    result = parse_classification_pdf(cls_path, ROOT)
    cache_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    answers: dict[str, str] = {}
    warnings = list(result.get("warnings") or [])
    for entry in result.get("entries", []):
        num = str(entry.get("number", "")).strip()
        ans = normalize_answer(entry.get("answer") or entry.get("answer_label") or "")
        if num and ans:
            answers[num] = ans
        elif num and not ans:
            warnings.append(f"Q{num}: 정답 미검출")
    return answers, cls_path, warnings


def main() -> int:
    path = csv_path_for("basic", ROOT)
    if not path.exists():
        print(f"오류: CSV 없음 — {path}", file=sys.stderr)
        return 1

    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str).fillna("")
    df = ensure_answer_column(df)
    df["정답"] = df["정답"].map(normalize_answer)

    by_pdf = df.groupby(df["원본PDF"].astype(str), sort=True)
    total_filled = 0
    total_missing = 0

    for pdf_rel, group in by_pdf:
        exam_pdf = ROOT / str(pdf_rel).replace("\\", "/")
        answers, cls_path, warnings = load_answers_for_exam(exam_pdf)
        filled = 0
        missing = 0
        for idx in group.index:
            qn = str(df.at[idx, "문항번호"]).strip()
            try:
                qn = str(int(float(qn)))
            except ValueError:
                missing += 1
                continue
            ans = answers.get(qn, "")
            if ans:
                df.at[idx, "정답"] = ans
                filled += 1
            else:
                missing += 1
                df.at[idx, "정답"] = ""

        total_filled += filled
        total_missing += missing
        cls_name = cls_path.name if cls_path else "(없음)"
        print(
            f"{pdf_rel}: 분류표={cls_name} "
            f"파싱={len(answers)} 채움={filled}/{len(group)} 미채움={missing}"
        )
        for w in warnings[:5]:
            print(f"  경고: {w}", file=sys.stderr)

    df = df[CSV_COLUMNS]
    df.to_csv(path, index=False, encoding="utf-8-sig")

    # sync deprecated mirror if present
    mirror = ROOT / "output/data/exam_questions.csv"
    if mirror.exists():
        mirror_df = df.copy()
        mirror_df.to_csv(mirror, index=False, encoding="utf-8-sig")
        print(f"동기화: {mirror.relative_to(ROOT).as_posix()}")

    print(f"완료: 정답 채움 {total_filled}행, 미채움 {total_missing}행 → {path.relative_to(ROOT)}")
    return 0 if total_missing == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
