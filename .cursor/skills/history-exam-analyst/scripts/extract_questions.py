#!/usr/bin/env python3
"""기출 PDF에서 문항을 추출합니다."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from compute_crop_bbox import compute_all_bboxes
from compute_hancert_crop_bbox import (
    MAX_QUESTION_NUM,
    compute_all_bboxes_hancert,
    should_use_hancert_crop,
)
from exam_profiles import detect_profile_from_name, format_exam_year


@dataclass
class QuestionRegion:
    number: int
    page: int
    page_image: str
    bbox: list[int]
    text: str


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def load_hancert_round_years() -> dict[str, str]:
    path = Path(__file__).with_name("hancert_round_years.json")
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def find_exam_pdfs(root: Path) -> list[Path]:
    """input/pdf 이하 검사지만 수집."""
    pdfs: list[Path] = []
    for path in sorted(root.rglob("*.pdf")):
        if "내용분류표" in path.name:
            continue
        if "검사지" not in path.name:
            continue
        pdfs.append(path)
    return pdfs


def parse_pdf_meta(pdf_path: Path, root: Path) -> dict:
    rel = pdf_path.relative_to(root).as_posix()
    filename = pdf_path.name
    year_m = re.search(r"\((\d{4})\)", filename) or re.search(r"(20\d{2})학년도", filename)
    round_m = re.search(r"\((\d{1,3})회\)", filename) or re.search(r"(\d{1,3})회", filename)
    type_m = re.search(
        r"\((공통|나형|가형|A형|B형|C형|C\d+형|\d+월모평|\d+월학평|수능|심화|기본)\)",
        filename,
    )
    if not type_m:
        if "6월모평" in filename or "6월 모평" in filename:
            exam_type = "6월모평"
        elif "9월모평" in filename or "9월 모평" in filename:
            exam_type = "9월모평"
        elif "수능" in filename and "모평" not in filename:
            exam_type = "수능"
        elif "심화" in filename:
            exam_type = "심화"
        elif "기본" in filename and "기초학력" not in filename:
            exam_type = "기본"
        else:
            exam_type = ""
    else:
        exam_type = type_m.group(1)

    if round_m and exam_type in {"심화", "기본"}:
        exam_type = f"{round_m.group(1)}회{exam_type}"
    elif round_m and not exam_type:
        exam_type = f"{round_m.group(1)}회"

    if "고1" in filename:
        grade = "고1"
        school_level = "중학" if "역사" in filename and "한국사" not in filename else "고등"
    elif "고2" in filename:
        grade = "고2"
        school_level = "고등"
    elif "고3" in filename:
        grade = "고3"
        school_level = "고등"
    elif any(k in filename for k in ("모평", "학평", "수능", "대수능")):
        grade = "고3"
        school_level = "고등"
    elif any(k in filename for k in ("회", "심화", "능력검정", "한능검")) or "한국사능력" in filename:
        grade = "공통"
        school_level = "고등"
    else:
        grade = ""
        school_level = ""

    if "한국사" in filename:
        subject = "한국사"
    elif re.search(r"역사\d|역사Ⅰ|역사Ⅱ|역사2", filename):
        subject = "역사"
    else:
        subject = ""

    labeled_year = year_m.group(1) if year_m else ""
    if not labeled_year and round_m:
        round_years = load_hancert_round_years()
        labeled_year = round_years.get(round_m.group(1), "")
        if not labeled_year:
            raise ValueError(
                f"한능검 회차 {round_m.group(1)}회 연도 미등록 "
                f"(hancert_round_years.json에 추가 필요)"
            )
    year = format_exam_year(labeled_year, exam_type=exam_type, name=filename)
    if not year:
        raise ValueError(f"연도 추론 실패: {filename}")

    return {
        "year": year,
        "grade": grade,
        "subject": subject,
        "exam_type": exam_type,
        "school_level": school_level,
        "source_pdf": rel,
        "stem": pdf_path.stem,
    }


def extract_questions(
    text_json_path: Path,
    *,
    profile_id: str = "",
    root: Path | None = None,
) -> tuple[list[QuestionRegion], list[str], str]:
    """문항 추출. 반환: (regions, warnings, crop_engine)."""
    data = json.loads(text_json_path.read_text(encoding="utf-8"))
    root = root or project_root()

    # OCR 실패 페이지가 있으면 한능검 경로 중단
    if any((p.get("source") or "") == "ocr_failed" for p in data.get("pages") or []):
        raise ValueError(f"OCR 실패 페이지 포함: {text_json_path}")

    use_hancert = should_use_hancert_crop(data, profile_id)
    crop_engine = "hancert" if use_hancert else "text"
    if use_hancert:
        raw_results, warnings = compute_all_bboxes_hancert(data, root)
        if len(raw_results) != MAX_QUESTION_NUM:
            fatal = f"FATAL: 영역 수 {len(raw_results)} ≠ {MAX_QUESTION_NUM}"
            if not any("영역 수" in w for w in warnings):
                warnings.append(fatal)
            raise ValueError(fatal)
    else:
        raw_results, warnings = compute_all_bboxes(data, root=root)
    regions = [
        QuestionRegion(
            number=r["number"],
            page=r["page"],
            page_image=r["page_image"],
            bbox=r["bbox"],
            text=r.get("text") or "",
        )
        for r in raw_results
    ]
    return regions, warnings, crop_engine


def main() -> int:
    parser = argparse.ArgumentParser(description="text.json에서 문항 추출")
    parser.add_argument("--stem", type=str, default=None, help="특정 PDF stem만 처리")
    parser.add_argument(
        "--merge",
        action="store_true",
        help="기존 extracted_questions.json에 병합 (--stem 시 기본 병합)",
    )
    parser.add_argument(
        "--replace-all",
        action="store_true",
        help="기존 JSON을 버리고 이번 실행 결과만 저장",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="해당 프로파일 PDF만 처리 (필터). 크롭 엔진은 PDF명·text.json으로 추론",
    )
    args = parser.parse_args()

    if args.replace_all and args.merge:
        print("오류: --replace-all 과 --merge 동시 사용 불가", file=sys.stderr)
        return 1

    root = project_root()
    out = root / "output" / "work" / "extracted_questions.json"
    all_questions: dict[str, list[dict]] = {}

    # --replace-all 만 전체 교체. 그 외(특히 --stem)는 기존 JSON 병합
    if args.replace_all:
        all_questions = {}
    elif out.exists():
        all_questions = json.loads(out.read_text(encoding="utf-8"))
    else:
        all_questions = {}

    pdfs = find_exam_pdfs(root / "input" / "pdf")
    if args.stem:
        pdfs = [p for p in pdfs if p.stem == args.stem]
        if not pdfs:
            print(f"오류: stem 없음 — {args.stem}", file=sys.stderr)
            return 1

    failed = 0
    for pdf in pdfs:
        auto_profile = detect_profile_from_name(str(pdf), default=None)
        if auto_profile is None:
            print(f"오류: 프로파일 추론 실패 — {pdf.name}", file=sys.stderr)
            failed += 1
            continue
        if args.profile and auto_profile != args.profile:
            print(f"skip {pdf.name}: auto={auto_profile}, filter={args.profile}")
            continue

        try:
            meta = parse_pdf_meta(pdf, root)
        except ValueError as exc:
            print(f"오류: {pdf.name}: {exc}", file=sys.stderr)
            failed += 1
            continue

        text_json = root / "output" / "work" / meta["stem"] / "text.json"
        if not text_json.exists():
            print(f"skip {pdf.name}: text.json 없음", file=sys.stderr)
            continue

        try:
            regions, warnings, crop_engine = extract_questions(
                text_json, profile_id=auto_profile, root=root
            )
        except ValueError as exc:
            print(f"오류: {pdf.name}: {exc}", file=sys.stderr)
            failed += 1
            warn_path = root / "output" / "work" / meta["stem"] / "crop_warnings.json"
            warn_path.parent.mkdir(parents=True, exist_ok=True)
            existing: list[str] = []
            if warn_path.exists():
                try:
                    existing = json.loads(warn_path.read_text(encoding="utf-8")).get(
                        "warnings", []
                    )
                except Exception:
                    existing = []
            warn_path.write_text(
                json.dumps(
                    {"warnings": existing + [str(exc)]},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            continue

        rows = []
        for r in regions:
            rows.append(
                {
                    **asdict(r),
                    **meta,
                    "profile_id": auto_profile,
                    "crop_engine": crop_engine,
                }
            )
        all_questions[pdf.name] = rows
        print(
            f"{meta['source_pdf']}: {len(regions)} questions "
            f"(profile={auto_profile}, engine={crop_engine})"
        )

        if warnings:
            warn_path = root / "output" / "work" / meta["stem"] / "crop_warnings.json"
            warn_path.write_text(
                json.dumps({"warnings": warnings}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"  경고 {len(warnings)}건 → {warn_path.relative_to(root)}")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(all_questions, ensure_ascii=False, indent=2), encoding="utf-8")
    if failed:
        print(f"완료 (실패 {failed}건)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
