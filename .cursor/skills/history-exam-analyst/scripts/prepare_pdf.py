#!/usr/bin/env python3
"""PDF를 페이지 PNG와 text.json으로 전처리합니다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import fitz  # PyMuPDF

TEXT_THRESHOLD = 30
DEFAULT_DPI = 200
SCALE = DEFAULT_DPI / 72.0


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def resolve_path(path: Path, root: Path) -> Path:
    return path if path.is_absolute() else root / path


def extract_text_blocks(page: fitz.Page) -> list[dict]:
    blocks: list[dict] = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        lines: list[str] = []
        for line in block.get("lines", []):
            spans = [span.get("text", "") for span in line.get("spans", [])]
            line_text = "".join(spans).strip()
            if line_text:
                lines.append(line_text)
        text = "\n".join(lines).strip()
        if not text:
            continue
        x0, y0, x1, y1 = block["bbox"]
        blocks.append(
            {
                "text": text,
                "bbox": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)],
            }
        )
    return blocks


def _configure_tesseract(pytesseract_module) -> None:
    """PATH에 없거나 Program Files에만 있을 때 tesseract·언어팩을 찾는다."""
    import os
    import shutil

    root = project_root()
    local_tessdata = root / ".tools" / "tessdata"
    if local_tessdata.is_dir() and (local_tessdata / "kor.traineddata").exists():
        os.environ["TESSDATA_PREFIX"] = str(local_tessdata)

    if shutil.which("tesseract"):
        return
    for candidate in (
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ):
        if candidate.exists():
            pytesseract_module.pytesseract.tesseract_cmd = str(candidate)
            return


def ocr_page(page_image_path: Path, dpi: int = DEFAULT_DPI) -> list[dict]:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "OCR에 pytesseract와 Pillow가 필요합니다. pip install -r requirements.txt"
        ) from exc

    _configure_tesseract(pytesseract)
    scale = dpi / 72.0
    image = Image.open(page_image_path)
    data = pytesseract.image_to_data(
        image, lang="kor+eng", config="--psm 6", output_type=pytesseract.Output.DICT
    )
    blocks: list[dict] = []
    n = len(data["text"])
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        conf = int(data["conf"][i]) if data["conf"][i] != "-1" else -1
        if conf >= 0 and conf < 30:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        blocks.append(
            {
                "text": normalize_ocr_text(text),
                "bbox": [
                    float(x) / scale,
                    float(y) / scale,
                    float(x + w) / scale,
                    float(y + h) / scale,
                ],
            }
        )
    return merge_ocr_blocks(blocks)


def normalize_ocr_text(text: str) -> str:
    """한글 음절 사이 공백 등 OCR 잡음을 줄인다."""
    import re

    text = re.sub(r"(?<=[가-힣])\s+(?=[가-힣])", "", text)
    text = re.sub(r"(?<=\d)\s*[.,]\s*(?=\s|$|[가-힣〈\[\(다음밑줄])", r". ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def merge_ocr_blocks(
    blocks: list[dict],
    y_tolerance: float = 10.0,
    max_x_gap: float = 45.0,
) -> list[dict]:
    """같은 줄·같은 단의 OCR 토큰만 병합. 좌·우단을 가로로 잇지 않는다."""
    if not blocks:
        return []

    sorted_blocks = sorted(blocks, key=lambda b: (b["bbox"][1], b["bbox"][0]))
    merged: list[dict] = []
    current = dict(sorted_blocks[0])
    current["text"] = normalize_ocr_text(current["text"])
    current["bbox"] = list(current["bbox"])

    for block in sorted_blocks[1:]:
        cy0, cy1 = current["bbox"][1], current["bbox"][3]
        by0, by1 = block["bbox"][1], block["bbox"][3]
        x_gap = block["bbox"][0] - current["bbox"][2]
        same_line = abs(by0 - cy0) <= y_tolerance or (by0 <= cy1 and by1 >= cy0)
        same_column = x_gap <= max_x_gap
        if same_line and same_column and x_gap >= -20:
            joined = f"{current['text']} {block['text']}".strip()
            current["text"] = normalize_ocr_text(joined)
            current["bbox"] = [
                min(current["bbox"][0], block["bbox"][0]),
                min(current["bbox"][1], block["bbox"][1]),
                max(current["bbox"][2], block["bbox"][2]),
                max(current["bbox"][3], block["bbox"][3]),
            ]
        else:
            merged.append(current)
            current = {
                "text": normalize_ocr_text(block["text"]),
                "bbox": list(block["bbox"]),
            }
    merged.append(current)
    return split_inline_question_blocks(merged)


def split_inline_question_blocks(blocks: list[dict]) -> list[dict]:
    """한 블록에 문항번호가 중간에 끼면 분리한다."""
    import re

    pat = re.compile(
        r"(?P<num>\d{1,2})\s*[.,]\s*(?=다음|밑줄|학생|장면|자료|가상|인물|옳은|적절한|고른|해당|"
        r"설명|시기|검색|상황|사실|사회|문화|제도|인터뷰|대화|뉴스|카드|전시|탐구)"
    )
    out: list[dict] = []
    for block in blocks:
        text = block["text"]
        matches = list(pat.finditer(text))
        if len(matches) <= 1 and (not matches or matches[0].start() < 3):
            out.append(block)
            continue
        x0, y0, x1, y1 = block["bbox"]
        width = max(x1 - x0, 1.0)
        starts = [0] + [m.start() for m in matches if m.start() > 2]
        starts = sorted(set(starts))
        for i, start in enumerate(starts):
            end = starts[i + 1] if i + 1 < len(starts) else len(text)
            part = text[start:end].strip()
            if not part:
                continue
            # x는 문자 비율로 대략 분할
            sx0 = x0 + width * (start / max(len(text), 1))
            sx1 = x0 + width * (end / max(len(text), 1))
            out.append({"text": part, "bbox": [sx0, y0, max(sx1, sx0 + 20), y1]})
    return out


def render_page(page: fitz.Page, output_path: Path, dpi: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    pix.save(str(output_path))


def prepare_pdf(
    pdf_path: Path,
    root: Path,
    dpi: int = DEFAULT_DPI,
    *,
    skip_ocr: bool = False,
) -> Path:
    pdf_path = resolve_path(pdf_path, root)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF를 찾을 수 없습니다: {pdf_path}")

    stem = pdf_path.stem
    work_dir = root / "output" / "work" / stem
    pages_dir = work_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    rel_pdf = pdf_path.relative_to(root).as_posix()
    result = {"source_pdf": rel_pdf, "pdf_stem": stem, "dpi": dpi, "pages": []}

    doc = fitz.open(pdf_path)
    try:
        for page_index in range(len(doc)):
            page = doc[page_index]
            page_num = page_index + 1
            page_image = pages_dir / f"page_{page_num:03d}.png"
            render_page(page, page_image, dpi)

            blocks = extract_text_blocks(page)
            page_text = "\n".join(b["text"] for b in blocks)
            source = "text"

            if len(page_text.strip()) < TEXT_THRESHOLD:
                if skip_ocr:
                    # 한능검 등: 페이지 PNG만 (이미지 전용; OCR 미실행)
                    blocks = []
                    source = "image_only"
                else:
                    try:
                        blocks = ocr_page(page_image, dpi=dpi)
                        source = "ocr"
                    except Exception as exc:
                        print(f"경고: 페이지 {page_num} OCR 실패 — {exc}", file=sys.stderr)
                        blocks = []
                        source = "ocr_failed"

            rel_page_image = page_image.relative_to(root).as_posix()
            result["pages"].append(
                {
                    "page": page_num,
                    "source": source,
                    "page_image": rel_page_image,
                    "blocks": blocks,
                }
            )
    finally:
        doc.close()

    text_json_path = work_dir / "text.json"
    text_json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장: {text_json_path}")
    print(f"페이지 수: {len(result['pages'])}")
    return text_json_path


def main() -> int:
    parser = argparse.ArgumentParser(description="PDF를 페이지 PNG와 text.json으로 전처리")
    parser.add_argument("pdf", type=Path, help="입력 PDF 경로")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI, help="렌더링 DPI (기본 200)")
    parser.add_argument("--root", type=Path, default=None, help="프로젝트 루트")
    parser.add_argument(
        "--skip-ocr",
        action="store_true",
        help="텍스트 레이어 없을 때 OCR 생략(페이지 PNG만; 한능검 크롭용)",
    )
    args = parser.parse_args()

    root = args.root or project_root()
    try:
        prepare_pdf(args.pdf, root, dpi=args.dpi, skip_ocr=args.skip_ocr)
    except Exception as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
