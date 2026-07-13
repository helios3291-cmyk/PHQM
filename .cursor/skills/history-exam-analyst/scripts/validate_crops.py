#!/usr/bin/env python3
"""크롭 결과 QA용 미리보기 그리드 PNG를 생성합니다."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def load_font(size: int = 14):
    for name in ("malgun.ttf", "Malgun.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_grid(
    questions: list[dict],
    root: Path,
    cols: int = 5,
    thumb_width: int = 280,
) -> Image.Image:
    font = load_font(12)
    rows = math.ceil(len(questions) / cols)
    label_h = 22
    cell_h = thumb_width + label_h
    grid = Image.new("RGB", (cols * thumb_width, rows * cell_h), "white")
    draw = ImageDraw.Draw(grid)

    for i, q in enumerate(sorted(questions, key=lambda x: int(x["number"]))):
        row, col = divmod(i, cols)
        x_off = col * thumb_width
        y_off = row * cell_h

        page_img = root / q["page_image"]
        if not page_img.exists():
            draw.text((x_off + 4, y_off + 4), f"Q{q['number']} missing", fill="red")
            continue

        with Image.open(page_img) as page:
            x0, y0, x1, y1 = q["bbox"]
            crop = page.crop((x0, y0, x1, y1))
            scale = thumb_width / max(crop.width, 1)
            thumb_h = int(crop.height * scale)
            thumb = crop.resize((thumb_width, thumb_h), Image.Resampling.LANCZOS)
            grid.paste(thumb, (x_off, y_off))

        draw.rectangle(
            [x_off, y_off, x_off + thumb_width - 1, y_off + thumb_h - 1],
            outline="red",
            width=2,
        )
        label = f"Q{q['number']} ({x1 - x0}x{y1 - y0})"
        draw.text((x_off + 4, y_off + thumb_h + 2), label, fill="black", font=font)

    return grid


def main() -> int:
    parser = argparse.ArgumentParser(
        description="크롭 QA 미리보기 그리드 생성 (validate_crops = preview)"
    )
    parser.add_argument("--pdf", required=True, help="PDF 파일명 (예: (2024)고2한국사(가형)검사지.pdf)")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    root = project_root()
    extracted = json.loads(
        (root / "output/work/extracted_questions.json").read_text(encoding="utf-8")
    )
    if args.pdf not in extracted:
        print(f"오류: {args.pdf} 없음", file=sys.stderr)
        return 1

    questions = extracted[args.pdf]
    stem = questions[0].get("stem") or Path(args.pdf).stem
    warn_path = root / "output" / "work" / stem / "crop_warnings.json"
    if warn_path.exists():
        warns = json.loads(warn_path.read_text(encoding="utf-8")).get("warnings") or []
        fatal = [w for w in warns if "영역 수" in w or str(w).startswith("FATAL")]
        if fatal:
            print("치명 경고로 미리보기 중단:", file=sys.stderr)
            for w in fatal:
                print(f"  - {w}", file=sys.stderr)
            return 1

    grid = make_grid(questions, root)

    out = args.output or root / "output" / "work" / stem / "crop_preview.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    grid.save(out)
    print(f"저장: {out.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
