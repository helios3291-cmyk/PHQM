#!/usr/bin/env python3
"""내용분류표 PDF를 파싱하여 classification.json을 생성합니다."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import fitz

from normalize_class_code import (
    answer_label_to_number,
    LEGACY_CODE_MAP,
    normalize_class_code,
    number_to_answer_label,
    strip_code_brackets,
)

CODE_RE = re.compile(r"(?:10한사\d|9역\d)")
ANSWER_RE = re.compile(r"^[①②③④⑤]$")
QUESTION_NUM_RE = re.compile(r"^\d{1,2}$")
HEADER_SKIP = re.compile(
    r"내용분류표|문항\s*번호|^번호$|^문항$|성취기준|평가요소|내용\s*영역|^정답$|"
    r"^역사$|^지식$|^이해$|^자료$|^분석$|^결론$|^도출$|^문제$|^해결$|합계|"
    r"기초학력|향상도|최소한|준거|고등학교|한국사|역사Ⅰ|역사2|"
    r"^\(?\d{4}\)?|검사|협의회|C\d+형|A형|B형|C형|가형|나형|공통"
)
CONTENT_AREAS = ["역사지식", "역사이해", "자료분석", "결론도출", "문제해결"]
AREA_X_CENTERS = [462, 502, 542, 583, 623]


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def extract_lines(pdf_path: Path) -> list[dict]:
    lines: list[dict] = []
    doc = fitz.open(pdf_path)
    try:
        for page_index, page in enumerate(doc):
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    text = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
                    if not text:
                        continue
                    bbox = line["bbox"]
                    lines.append(
                        {
                            "page": page_index + 1,
                            "text": text,
                            "x0": bbox[0],
                            "y0": bbox[1],
                            "x1": bbox[2],
                            "y1": bbox[3],
                        }
                    )
    finally:
        doc.close()
    return lines


def is_question_anchor(line: dict) -> int | None:
    if line["x0"] > 75:
        return None
    if not QUESTION_NUM_RE.match(line["text"]):
        return None
    num = int(line["text"])
    if 1 <= num <= 30:
        return num
    return None


def detect_exam_format(lines: list[dict]) -> str:
    joined = "\n".join(l["text"] for l in lines)
    if re.search(r"9역\d{2}-\d{2}", joined):
        return "diagnostic_g1_middle"
    if "최소한의 성취기준" in joined or re.search(r"10한사[12]-\d{2}-\d{2}", joined):
        return "enhancement_c01"
    return "diagnostic_g2"


def school_level_for_format(exam_format: str) -> str:
    if exam_format == "diagnostic_g1_middle":
        return "중학"
    return "고등"


def nearest_content_area(x0: float) -> str:
    xc = x0
    best = CONTENT_AREAS[0]
    best_dist = 9999.0
    for area, center in zip(CONTENT_AREAS, AREA_X_CENTERS):
        dist = abs(xc - center)
        if dist < best_dist:
            best_dist = dist
            best = area
    return best


def load_achievement_index(root: Path) -> dict[str, dict]:
    path = root / "output" / "work" / "achievement_index.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for e in data.get("entries", []):
        code = normalize_class_code(e.get("code", "")) or strip_code_brackets(e.get("code", ""))
        if not code:
            continue
        entry = dict(e)
        entry["code"] = code
        out[code] = entry
    return out


def fuzzy_match_code(
    evaluation: str, index: dict[str, dict], school_level: str = "고등"
) -> str | None:
    if not evaluation:
        return None
    eval_compact = re.sub(r"\s+", "", evaluation)
    for code, entry in index.items():
        if entry.get("school_level") != school_level:
            continue
        text_compact = re.sub(r"\s+", "", entry.get("text", ""))
        if eval_compact[:8] in text_compact or text_compact[:8] in eval_compact:
            return code
    return None


def verify_code(
    code: str | None,
    evaluation: str,
    index: dict[str, dict],
    warnings: list[str],
    number: int,
    school_level: str = "고등",
) -> tuple[str | None, str]:
    def _lookup(c: str | None) -> dict | None:
        if not c:
            return None
        key = normalize_class_code(c) or strip_code_brackets(c)
        return index.get(key)

    if code:
        norm = normalize_class_code(code) or strip_code_brackets(code)
        entry = _lookup(norm)
        if entry is None and strip_code_brackets(code) in LEGACY_CODE_MAP:
            mapped = LEGACY_CODE_MAP[strip_code_brackets(code)]
            entry = _lookup(mapped)
            if entry is not None:
                norm = mapped

        if entry is not None:
            if entry.get("school_level") == school_level:
                return norm, entry["text"]
            warnings.append(f"Q{number}: 코드 {norm} 학교급 불일치")
        code = norm

    alt = fuzzy_match_code(evaluation, index, school_level)
    if alt:
        warnings.append(f"Q{number}: 코드 {code} 미일치 → {alt} fuzzy 매칭")
        return alt, index[alt]["text"]

    if code:
        warnings.append(f"Q{number}: 코드 {code} 인덱스 미존재")
    return code, ""


def parse_question_block(
    block_lines: list[dict],
    exam_format: str,
    index: dict[str, dict],
    warnings: list[str],
    school_level: str,
) -> dict | None:
    if not block_lines:
        return None

    number = is_question_anchor(block_lines[0])
    if number is None:
        return None

    achievement_code_raw = ""
    evaluation_element = ""
    minimum_achievement = ""
    answer_label = ""
    content_area = ""
    raw_parts: list[str] = []

    for line in block_lines:
        text = line["text"].strip()
        raw_parts.append(text)
        if HEADER_SKIP.search(text) and not CODE_RE.search(text):
            continue
        if CODE_RE.search(text):
            achievement_code_raw = text.replace(" ", "")
            continue
        if ANSWER_RE.match(text):
            answer_label = text
            continue
        if text == "○":
            content_area = nearest_content_area(line["x0"])
            continue
        if re.match(r"^[1-5]$", text) and line["x0"] > 600:
            answer_label = number_to_answer_label(text)
            continue

    if exam_format == "enhancement_c01":
        min_lines: list[str] = []
        eval_lines: list[str] = []
        phase = "min"
        for line in block_lines[1:]:
            text = line["text"].strip()
            if CODE_RE.search(text):
                phase = "min"
                continue
            if phase == "min" and CODE_RE.search(achievement_code_raw):
                if 150 < line["x0"] < 400 and not ANSWER_RE.match(text) and text != "○":
                    if "이해하기" in text or "파악하기" in text or "분석하기" in text or "설명하기" in text or "알기" in text:
                        phase = "eval"
                        eval_lines.append(text)
                    else:
                        min_lines.append(text)
                elif phase == "min":
                    min_lines.append(text)
            elif phase == "eval" and 150 < line["x0"] < 400:
                if "이해하기" in text or "파악하기" in text or "분석하기" in text or "설명하기" in text or "알기" in text:
                    eval_lines.append(text)
        minimum_achievement = " ".join(min_lines).strip()
        if eval_lines:
            evaluation_element = " ".join(eval_lines).strip()

    if not evaluation_element:
        eval_candidates: list[str] = []
        for line in block_lines:
            text = line["text"].strip()
            if not (130 < line["x0"] < 430 and len(text) > 5):
                continue
            if CODE_RE.search(text) or ANSWER_RE.match(text) or text == "○":
                continue
            if HEADER_SKIP.search(text):
                continue
            eval_candidates.append(text)
        if eval_candidates:
            evaluation_element = max(eval_candidates, key=len)

    if not achievement_code_raw:
        warnings.append(f"Q{number}: 성취기준 코드 미검출")
        return None

    achievement_code = normalize_class_code(achievement_code_raw)
    achievement_code, achievement_text_index = verify_code(
        achievement_code, evaluation_element, index, warnings, number, school_level
    )

    answer = answer_label_to_number(answer_label)

    entry: dict = {
        "number": number,
        "achievement_code_raw": achievement_code_raw,
        "achievement_code": achievement_code or "",
        "achievement_text_index": achievement_text_index,
        "evaluation_element": evaluation_element,
        "content_area": content_area,
        "answer": answer,
        "answer_label": answer_label or number_to_answer_label(answer),
        "raw_row": " | ".join(raw_parts),
    }
    if exam_format == "enhancement_c01" and minimum_achievement:
        entry["minimum_achievement"] = minimum_achievement

    return entry


def parse_classification_pdf(pdf_path: Path, root: Path) -> dict:
    lines = extract_lines(pdf_path)
    lines.sort(key=lambda l: (l["page"], l["y0"], l["x0"]))

    exam_format = detect_exam_format(lines)
    school_level = school_level_for_format(exam_format)
    index = load_achievement_index(root)
    warnings: list[str] = []

    anchors: list[tuple[int, int]] = []
    for i, line in enumerate(lines):
        num = is_question_anchor(line)
        if num is not None:
            anchors.append((i, num))

    entries: list[dict] = []
    for ai, (start_idx, _) in enumerate(anchors):
        end_idx = anchors[ai + 1][0] if ai + 1 < len(anchors) else len(lines)
        block = lines[start_idx:end_idx]
        if block and block[-1]["text"].strip() == "합계":
            block = block[:-1]
        entry = parse_question_block(block, exam_format, index, warnings, school_level)
        if entry:
            entries.append(entry)

    entries.sort(key=lambda e: e["number"])

    return {
        "source_file": str(pdf_path.relative_to(root)).replace("\\", "/")
        if pdf_path.is_relative_to(root)
        else str(pdf_path),
        "exam_format": exam_format,
        "school_level": school_level,
        "entries": entries,
        "warnings": warnings,
    }


def classification_path_for_exam(exam_pdf: Path, root: Path) -> Path | None:
    stem = exam_pdf.stem.replace("검사지", "내용분류표")
    same_dir = exam_pdf.parent / f"{stem}.pdf"
    if same_dir.exists():
        return same_dir

    candidate = root / "input" / "classification" / f"{stem}.pdf"
    if candidate.exists():
        return candidate

    manifest_path = root / "input" / "classification" / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        exam_rel = exam_pdf.relative_to(root).as_posix() if exam_pdf.is_relative_to(root) else str(exam_pdf)
        for pair in manifest.get("pairs", []):
            if pair.get("exam", "").replace("\\", "/") == exam_rel:
                cls = root / pair["classification"]
                if cls.exists():
                    return cls
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="내용분류표 PDF 인덱싱")
    parser.add_argument("--pdf", type=Path, required=True, help="내용분류표 PDF 경로")
    parser.add_argument("--exam-stem", type=str, default=None, help="출력 폴더 stem (검사지 stem)")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args()

    root = args.root or project_root()
    pdf_path = args.pdf if args.pdf.is_absolute() else root / args.pdf
    if not pdf_path.exists():
        print(f"오류: PDF 없음 — {pdf_path}", file=sys.stderr)
        return 1

    result = parse_classification_pdf(pdf_path, root)
    stem = args.exam_stem or pdf_path.stem.replace("내용분류표", "검사지")
    out_dir = root / "output" / "work" / stem
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "classification.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"저장: {out_path.relative_to(root)} ({len(result['entries'])}문항)")
    if result["warnings"]:
        print(f"경고: {len(result['warnings'])}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
