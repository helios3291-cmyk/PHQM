#!/usr/bin/env python3
"""input/answers/ 정답지 → 프로파일 CSV `정답` 컬럼 백필.

지원:
- 한능검 답지 PDF: `(60회)한국사(심화)답지.pdf` 등
- 모평·수능: `input/answers/mock_answers.json` (PNG 정답표 전사)

```bash
python .cursor/skills/history-exam-analyst/scripts/backfill_answers_from_input.py
```
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from exam_profiles import CSV_COLUMNS, PROFILE_IDS, csv_path_for  # noqa: E402
from normalize_class_code import answer_label_to_number  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]
ANSWERS_DIR = ROOT / "input" / "answers"
MOCK_JSON = ANSWERS_DIR / "mock_answers.json"
HANCERT_PDF_RE = re.compile(
    r"\((\d+)회\)한국사\((심화|기본)\)답지\.pdf$",
    re.IGNORECASE,
)
CIRCLED = {"①": "1", "②": "2", "③": "3", "④": "4", "⑤": "5"}


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


def parse_hancert_answer_pdf(path: Path) -> dict[str, str]:
    import fitz

    doc = fitz.open(path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()

    # 빈도표 이전만 사용 (제목 '…정답표'는 답 뒤에 오는 경우가 많음)
    cut = re.search(r"답지번호별|문항배점별", text)
    text_body = text[: cut.start()] if cut else text

    answers: dict[str, str] = {}
    tokens = [t.strip() for t in re.split(r"[\s\n\r]+", text_body) if t.strip()]
    i = 0
    while i < len(tokens) - 2:
        qn_tok, ans_tok, score_tok = tokens[i], tokens[i + 1], tokens[i + 2]
        if not re.fullmatch(r"[1-9]|[1-4]\d|50", qn_tok):
            i += 1
            continue
        if not re.fullmatch(r"[123]", score_tok):
            i += 1
            continue
        # 원문자(①~⑤) 또는 숫자(1~5) 정답
        if ans_tok in CIRCLED:
            ans = CIRCLED[ans_tok]
        elif ans_tok in {"1", "2", "3", "4", "5"}:
            ans = ans_tok
        else:
            i += 1
            continue
        qn = int(qn_tok)
        if 1 <= qn <= 50:
            answers[str(qn)] = ans
        i += 3
    return answers


def load_hancert_keys() -> dict[str, dict[str, str]]:
    """문형 key `60회심화` → {문항번호: 정답}."""
    out: dict[str, dict[str, str]] = {}
    if not ANSWERS_DIR.is_dir():
        return out
    for path in sorted(ANSWERS_DIR.glob("*.pdf")):
        m = HANCERT_PDF_RE.search(path.name)
        if not m:
            continue
        round_no, level = m.group(1), m.group(2)
        exam_type = f"{round_no}회{level}"
        parsed = parse_hancert_answer_pdf(path)
        if len(parsed) < 40:
            print(f"경고: {path.name} 파싱 문항 수={len(parsed)}", file=sys.stderr)
        out[exam_type] = parsed
        print(f"한능검 정답 로드: {exam_type} ({len(parsed)}문항) ← {path.name}")
    return out


def load_mock_keys() -> list[dict]:
    """mock_answers.json entries with year/exam_type/answers."""
    if not MOCK_JSON.exists():
        print(f"경고: {MOCK_JSON} 없음 — 모평·수능 백필 생략", file=sys.stderr)
        return []
    data = json.loads(MOCK_JSON.read_text(encoding="utf-8"))
    return list(data.get("exams", []))


def normalize_answer_cell(value) -> str:
    s = str(value or "").strip()
    if not s or s.lower() == "nan":
        return ""
    if s in CIRCLED:
        return CIRCLED[s]
    try:
        n = int(float(s))
        if 1 <= n <= 5:
            return str(n)
    except ValueError:
        pass
    return answer_label_to_number(s) if s else ""


def apply_answers(df: pd.DataFrame, mask: pd.Series, answers: dict[str, str]) -> int:
    n = 0
    for idx in df.index[mask]:
        qn = str(df.at[idx, "문항번호"]).strip()
        try:
            qn = str(int(float(qn)))
        except ValueError:
            continue
        ans = normalize_answer_cell(answers.get(qn, ""))
        if ans:
            df.at[idx, "정답"] = ans
            n += 1
    return n


def main() -> int:
    hancert_keys = load_hancert_keys()
    mock_exams = load_mock_keys()

    for pid in PROFILE_IDS:
        path = csv_path_for(pid, ROOT)
        if not path.exists():
            print(f"skip missing {path}")
            continue
        df = pd.read_csv(path, encoding="utf-8-sig", dtype=str).fillna("")
        df = ensure_answer_column(df)
        # normalize any legacy float-like values (2.0 → 2)
        df["정답"] = df["정답"].map(normalize_answer_cell)
        filled_before = int((df["정답"].astype(str).str.strip() != "").sum())
        added = 0

        if pid == "hancert":
            for exam_type, answers in hancert_keys.items():
                mask = df["문형"].astype(str) == exam_type
                added += apply_answers(df, mask, answers)

        elif pid == "mock":
            for exam in mock_exams:
                year = str(exam.get("year", ""))
                exam_type = str(exam.get("exam_type", ""))
                answers_list = exam.get("answers", [])
                answers = {str(i + 1): str(a) for i, a in enumerate(answers_list)}
                mask = (df["연도"].astype(str) == year) & (df["문형"].astype(str) == exam_type)
                n = apply_answers(df, mask, answers)
                added += n
                print(f"모평 정답: {year} {exam_type} → {n}행 ({exam.get('source', '')})")

        elif pid == "basic":
            print("basic: input/answers에 기초학력 정답지 없음 — 빈칸 유지")

        df.to_csv(path, index=False, encoding="utf-8-sig")
        filled = int((df["정답"].astype(str).str.strip() != "").sum())
        print(
            f"[{pid}] rows={len(df)} 정답={filled} "
            f"(+{filled - filled_before} from this run, matched={added})"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
