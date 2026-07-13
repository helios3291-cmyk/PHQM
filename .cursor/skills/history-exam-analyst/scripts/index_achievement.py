#!/usr/bin/env python3
"""성취기준 폴더를 인덱싱하여 achievement_index.json을 생성합니다."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CODE_PATTERN_MIDDLE = re.compile(
    r"\[(\d[가-힣]\d{2}-\d{2})\]",
    re.UNICODE,
)
CODE_PATTERN_HIGH = re.compile(
    r"\[(10한사\d-\d{2}-\d{2}|10[12]\d-\d{2}-\d{2})\]",
    re.UNICODE,
)
EVAL_CRITERIA_CODE = re.compile(
    r"\[\d[가-힣]\d{2}-\d{2}-\d{2}\]",
    re.UNICODE,
)


def normalize_text(text: str) -> str:
    """PDF 추출 텍스트에서 줄바꿈으로 분리된 성취기준 코드를 복원합니다."""
    text = re.sub(
        r"\[10\s*\n\s*([12])-(\d{2})-(\d{2})\]",
        r"[10한사\1-\2-\3]",
        text,
    )
    text = re.sub(
        r"\[(\d{2})\s*\n\s*(\d)-(\d{2})-(\d{2})\]",
        r"[\1\2-\3-\4]",
        text,
    )
    text = re.sub(
        r"\[(\d)\s*\n\s*([가-힣]\d{2}-\d{2})\]",
        r"[\1\2]",
        text,
    )
    return text


def extract_content_after_code(text: str, code_end: int) -> str:
    snippet = text[code_end : code_end + 600]
    next_code = re.search(r"\[\d", snippet)
    if next_code:
        snippet = snippet[: next_code.start()]
    level_match = re.search(r"\n([A-E])\n", snippet)
    if level_match:
        snippet = snippet[: level_match.start()]
    content = re.sub(r"\s+", " ", snippet).strip()
    return content


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def read_text_file(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp949"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def read_pdf_pages(path: Path, page_range: tuple[int, int] | None = None) -> str:
    import fitz

    parts: list[str] = []
    doc = fitz.open(path)
    try:
        start, end = page_range if page_range else (0, len(doc) - 1)
        for page_index in range(start, min(end + 1, len(doc))):
            parts.append(doc[page_index].get_text())
    finally:
        doc.close()
    return "\n".join(parts)


def find_middle_school_page_range(path: Path) -> tuple[int, int] | None:
    import fitz

    doc = fitz.open(path)
    try:
        start_page: int | None = None
        high_start: int | None = None

        for page_index in range(len(doc)):
            text = doc[page_index].get_text()
            compact = text.replace(" ", "")

            if start_page is None and CODE_PATTERN_MIDDLE.search(text):
                start_page = page_index

            if (
                start_page is not None
                and high_start is None
                and re.search(r"2\.?고등학교", compact)
            ):
                high_start = page_index
                break

        if start_page is None:
            return None

        end_page = (high_start - 1) if high_start and high_start > start_page else len(doc) - 1
        return start_page, end_page
    finally:
        doc.close()


def classify_source(path: Path) -> dict[str, str] | None:
    name = path.name
    if "샘플" in name:
        return None

    if "2022" in name or "고등학교" in name:
        return {"curriculum": "2022", "school_level": "고등"}

    if "2015" in name or "평가기준" in name or "1205" in name:
        return {"curriculum": "2015", "school_level": "중학"}

    return None


def load_file_text(path: Path, meta: dict[str, str]) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        if meta["curriculum"] == "2015" and meta["school_level"] == "중학":
            page_range = find_middle_school_page_range(path)
            if page_range:
                print(f"    중학교 구간: p{page_range[0] + 1}~p{page_range[1] + 1}")
                return read_pdf_pages(path, page_range)
        return read_pdf_pages(path)
    if suffix == ".docx":
        from docx import Document

        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return read_text_file(path)


def extract_entries(text: str, source_file: str, meta: dict[str, str]) -> list[dict]:
    from fix_achievement_text import fix_achievement_text
    from normalize_class_code import normalize_class_code

    text = normalize_text(text)
    entries: list[dict] = []
    seen_codes: set[str] = set()

    if meta["school_level"] == "중학":
        patterns = [CODE_PATTERN_MIDDLE]
    else:
        patterns = [CODE_PATTERN_HIGH]

    matches: list[re.Match[str]] = []
    for pattern in patterns:
        matches.extend(pattern.finditer(text))
    matches.sort(key=lambda m: m.start())

    for match in matches:
        full = match.group(0)
        if EVAL_CRITERIA_CODE.fullmatch(full):
            continue

        code_raw = f"[{match.group(1)}]"
        code = normalize_class_code(code_raw) or code_raw
        if code in seen_codes:
            continue

        content = extract_content_after_code(text, match.end())
        if not content:
            continue

        content = fix_achievement_text(code, content)
        entries.append(
            {
                "code": code,
                "text": content,
                "source_file": source_file,
                "curriculum": meta["curriculum"],
                "school_level": meta["school_level"],
            }
        )
        seen_codes.add(code)

    return entries


def index_achievement(root: Path, standards_dir: Path | None = None) -> Path:
    standards_dir = standards_dir or (root / "성취기준")
    if not standards_dir.exists():
        raise FileNotFoundError(f"성취기준 폴더를 찾을 수 없습니다: {standards_dir}")

    extensions = {".txt", ".md", ".pdf", ".docx"}
    all_entries: list[dict] = []

    for path in sorted(standards_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        if path.name.startswith("."):
            continue

        meta = classify_source(path)
        if meta is None:
            print(f"  건너뜀: {path.relative_to(root).as_posix()}")
            continue

        try:
            text = load_file_text(path, meta)
        except Exception as exc:
            print(f"경고: {path} 읽기 실패 — {exc}", file=sys.stderr)
            continue

        rel = path.relative_to(root).as_posix()
        entries = extract_entries(text, rel, meta)
        all_entries.extend(entries)
        print(
            f"  {rel}: {len(entries)}개 항목 "
            f"({meta['curriculum']} 개정 / {meta['school_level']})"
        )

    output_dir = root / "output" / "work"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "achievement_index.json"
    payload = {"entries": all_entries, "count": len(all_entries)}
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장: {output_path} (총 {len(all_entries)}개)")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="성취기준 폴더 인덱싱")
    parser.add_argument("--root", type=Path, default=None, help="프로젝트 루트")
    parser.add_argument("--standards-dir", type=Path, default=None, help="성취기준 폴더")
    args = parser.parse_args()

    root = args.root or project_root()
    try:
        index_achievement(root, args.standards_dir)
    except Exception as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
