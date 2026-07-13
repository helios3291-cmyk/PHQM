#!/usr/bin/env python3
"""페이지 이미지에서 문항 영역을 크롭하여 PNG로 저장합니다."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from PIL import Image


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def resolve_path(path: Path, root: Path) -> Path:
    return path if path.is_absolute() else root / path


def sanitize_filename_part(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\s]+', "_", value.strip())
    return cleaned.strip("_") or "unknown"


def build_output_path(
    year: str,
    grade: str,
    subject: str,
    number: str,
    root: Path,
    *,
    exam_type: str = "",
    profile: str = "basic",
) -> Path:
    from exam_profiles import image_rel_path

    rel = image_rel_path(profile, year, grade, subject, exam_type or "공통", number)
    return root / rel


def parse_bbox(bbox_str: str) -> tuple[int, int, int, int]:
    parts = [p.strip() for p in bbox_str.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox는 x0,y0,x1,y1 형식이어야 합니다.")
    return tuple(int(float(p)) for p in parts)  # type: ignore[return-value]


def crop_question(
    page_image: Path,
    bbox: tuple[int, int, int, int],
    output_path: Path,
    root: Path,
) -> Path:
    page_image = resolve_path(page_image, root)
    output_path = resolve_path(output_path, root)

    if not page_image.exists():
        raise FileNotFoundError(f"페이지 이미지를 찾을 수 없습니다: {page_image}")

    x0, y0, x1, y1 = bbox
    if x1 <= x0 or y1 <= y0:
        raise ValueError(f"유효하지 않은 bbox: {bbox}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(page_image) as image:
        cropped = image.crop((x0, y0, x1, y1))
        cropped.save(output_path)

    rel = output_path.relative_to(root).as_posix()
    print(f"저장: {rel}")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="문항 영역 크롭")
    parser.add_argument("--page-image", type=Path, required=True, help="페이지 PNG 경로")
    parser.add_argument("--bbox", type=str, required=True, help="x0,y0,x1,y1 (픽셀)")
    parser.add_argument("--output", type=Path, default=None, help="출력 PNG 경로")
    parser.add_argument("--year", type=str, default=None)
    parser.add_argument("--grade", type=str, default=None)
    parser.add_argument("--subject", type=str, default=None)
    parser.add_argument("--number", type=str, default=None)
    parser.add_argument("--exam-type", type=str, default="")
    parser.add_argument("--profile", type=str, default="basic")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args()

    root = args.root or project_root()

    if args.output is None:
        missing = [name for name, val in [
            ("year", args.year), ("grade", args.grade),
            ("subject", args.subject), ("number", args.number),
        ] if not val]
        if missing:
            print(f"오류: --output 또는 --year/--grade/--subject/--number가 필요합니다.", file=sys.stderr)
            return 1
        output_path = build_output_path(
            args.year,
            args.grade,
            args.subject,
            args.number,
            root,
            exam_type=args.exam_type,
            profile=args.profile,
        )
    else:
        output_path = args.output

    try:
        bbox = parse_bbox(args.bbox)
        crop_question(args.page_image, bbox, output_path, root)
    except Exception as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
