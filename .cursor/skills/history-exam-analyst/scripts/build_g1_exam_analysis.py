#!/usr/bin/env python3
"""고1 역사 검사지용 exam_analysis.json 스켈레톤(성취기준·시대만) 생성.

문제형식·자료/정답 핵심요소는 AI 에이전트가 크롭 PNG를 보고 exam_analysis.json에 직접 작성합니다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ERA_BY_UNIT = {
    "07": "삼국시대 이전",
    "08": "남북국시대",
    "09": "조선",
    "10": "개항기",
    "11": "일제강점기",
    "12": "현대",
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def era_from_code(code: str) -> str:
    m = re.search(r"9역(\d{2})-", code)
    if m:
        unit = m.group(1)
        if unit == "07":
            return "삼국시대 이전"
        return ERA_BY_UNIT.get(unit, "현대")
    return ""


def build_skeleton(
    questions: list[dict],
    classification: dict,
    achievement_index: dict[str, dict],
    existing: dict[str, dict] | None = None,
) -> dict[str, dict]:
    cls_by_num = {str(e["number"]): e for e in classification.get("entries", [])}
    existing = existing or {}
    result: dict[str, dict] = {}

    for q in questions:
        num = str(q["number"])
        cls = cls_by_num.get(num, {})
        code = cls.get("achievement_code", "")
        ach_text = cls.get("achievement_text_index", "")
        if not ach_text and code in achievement_index:
            ach_text = achievement_index[code].get("text", "")

        prev = existing.get(num, {})
        result[num] = {
            "achievement_code": code or prev.get("achievement_code", ""),
            "achievement_text": ach_text or prev.get("achievement_text", ""),
            "era": prev.get("era") or era_from_code(code),
            "problem_format": prev.get("problem_format", ""),
            "sub_format": prev.get("sub_format", ""),
            "source_key": prev.get("source_key", ""),
            "answer_key": prev.get("answer_key", ""),
        }

    return result


def main() -> int:
    root = project_root()
    extracted_path = root / "output/work/extracted_questions.json"
    analysis_path = root / "output/work/exam_analysis.json"

    extracted = json.loads(extracted_path.read_text(encoding="utf-8"))
    analysis: dict = {}
    if analysis_path.exists():
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))

    ach_index = {
        e["code"]: e
        for e in json.loads(
            (root / "output/work/achievement_index.json").read_text(encoding="utf-8")
        )["entries"]
    }

    from index_classification import classification_path_for_exam, parse_classification_pdf

    for pdf_name, questions in extracted.items():
        if not any(q.get("grade") == "고1" for q in questions):
            continue
        source_pdf = questions[0]["source_pdf"]
        exam_pdf = root / source_pdf
        cls_pdf = classification_path_for_exam(exam_pdf, root)
        if cls_pdf is None:
            print(f"skip {pdf_name}: 분류표 없음", flush=True)
            continue
        classification = parse_classification_pdf(cls_pdf, root)
        stem = exam_pdf.stem
        cls_out = root / "output/work" / stem / "classification.json"
        cls_out.parent.mkdir(parents=True, exist_ok=True)
        cls_out.write_text(json.dumps(classification, ensure_ascii=False, indent=2), encoding="utf-8")

        analysis[pdf_name] = build_skeleton(
            questions,
            classification,
            ach_index,
            existing=analysis.get(pdf_name, {}),
        )
        print(f"{pdf_name}: 스켈레톤 {len(analysis[pdf_name])}문항", flush=True)

    analysis_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장: {analysis_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
