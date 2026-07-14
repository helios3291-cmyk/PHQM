#!/usr/bin/env python3
"""크롭 PNG → A4 2단 조합 문제지·정답지 PDF."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image

# A4 in points
PAGE_W = 595.0
PAGE_H = 842.0
MARGIN = 36.0
GUTTER = 14.0
HEADER_H = 40.0
GAP_Y = 8.0
NUMBER_GAP = 4.0
LABEL_H = 16.0  # 새번호 + 출처 라벨 높이


@dataclass
class ComposeItem:
    image_path: Path
    new_number: int
    era: str = ""
    achievement_code: str = ""
    answer: str = ""
    answer_key: str = ""
    source_year: str = ""
    source_exam_type: str = ""
    source_number: str = ""
    profile_label: str = ""
    subject: str = ""


def _item_source_bracket(item: ComposeItem) -> str:
    """예: [모의고사 · 2025(2026) · 6월모평 #12]"""
    parts = [
        p
        for p in (item.profile_label, item.source_year, item.source_exam_type)
        if str(p).strip()
    ]
    mid = " · ".join(parts) if parts else "출처미상"
    num = str(item.source_number).strip() or "?"
    return f"[{mid} #{num}]"


def _answer_display(answer: str) -> str:
    """CSV 정답(1~5) → PDF 표시. NanumGothic에 원문자 글리프가 없어 (n)만 사용."""
    key = str(answer or "").strip()
    mapping = {"①": "1", "②": "2", "③": "3", "④": "4", "⑤": "5"}
    if key in mapping:
        key = mapping[key]
    if key in {"1", "2", "3", "4", "5"}:
        return f"({key})"
    return "—"


def _item_label(item: ComposeItem) -> str:
    return f"{item.new_number}.  {_item_source_bracket(item)}"


def _column_width() -> float:
    return (PAGE_W - 2 * MARGIN - GUTTER) / 2


def _content_top() -> float:
    return MARGIN + HEADER_H


def _content_bottom() -> float:
    return PAGE_H - MARGIN


def _content_height() -> float:
    return _content_bottom() - _content_top()


def _scaled_size(img_w: int, img_h: int, max_w: float, max_h: float) -> tuple[float, float]:
    if img_w <= 0 or img_h <= 0:
        return max_w, max_h * 0.2
    scale = min(max_w / img_w, max_h / img_h, 1.0)
    return img_w * scale, img_h * scale


def _measure_height(path: Path, col_w: float, max_h: float) -> float:
    with Image.open(path) as im:
        w, h = im.size
    label_block = LABEL_H + NUMBER_GAP
    avail = max(20.0, max_h - label_block)
    _sw, sh = _scaled_size(w, h, col_w, avail)
    return sh + label_block


def pack_pages(items: list[ComposeItem]) -> list[list[ComposeItem]]:
    """가변 2~4문항/페이지. 좌→우 단, 위에서 아래로."""
    if not items:
        return []

    col_w = _column_width()
    content_h = _content_height()
    half_h = content_h / 2 - GAP_Y / 2

    pages: list[list[ComposeItem]] = []
    i = 0
    n = len(items)

    while i < n:
        remaining = n - i
        # Prefer 4, then 3, then 2, then 1
        chosen: list[ComposeItem] | None = None
        for count in (4, 3, 2, 1):
            if count > remaining:
                continue
            chunk = items[i : i + count]
            heights = [_measure_height(it.image_path, col_w, content_h) for it in chunk]
            # Tall item → prefer at most 2 on page
            if any(h > half_h * 1.05 for h in heights) and count > 2:
                continue
            if count == 4:
                # 2 left + 2 right
                left_ok = heights[0] + GAP_Y + heights[1] <= content_h + 1
                right_ok = heights[2] + GAP_Y + heights[3] <= content_h + 1
                if left_ok and right_ok:
                    chosen = chunk
                    break
            elif count == 3:
                # left 2, right 1 (or left 1 right 2 if first is taller)
                if heights[0] + GAP_Y + heights[1] <= content_h + 1 and heights[2] <= content_h + 1:
                    chosen = chunk
                    break
                if heights[0] <= content_h + 1 and heights[1] + GAP_Y + heights[2] <= content_h + 1:
                    chosen = chunk
                    break
            elif count == 2:
                if heights[0] <= content_h + 1 and heights[1] <= content_h + 1:
                    chosen = chunk
                    break
            else:
                if heights[0] <= content_h + 1:
                    chosen = chunk
                    break
                # Force fit by allowing full column height clamp later
                chosen = chunk
                break

        if chosen is None:
            chosen = items[i : i + 1]
        pages.append(chosen)
        i += len(chosen)

    return pages


def _draw_header(page: fitz.Page, title: str, page_no: int, page_count: int) -> None:
    _insert_cjk(
        page,
        fitz.Rect(MARGIN, MARGIN, PAGE_W - MARGIN - 70, MARGIN + 20),
        title,
        12,
    )
    page.insert_text(
        (PAGE_W - MARGIN - 50, MARGIN + 16),
        f"{page_no}/{page_count}",
        fontsize=9,
        fontname="helv",
    )
    y = MARGIN + 22
    page.draw_line((MARGIN, y), (PAGE_W - MARGIN, y), width=0.8)


def _place_image(
    page: fitz.Page,
    item: ComposeItem,
    x0: float,
    y0: float,
    max_w: float,
    max_h: float,
) -> float:
    """Place numbered question image with source label; return bottom y used."""
    label = _item_label(item)
    _insert_cjk(page, fitz.Rect(x0, y0, x0 + max_w, y0 + LABEL_H), label, 9)
    img_y = y0 + LABEL_H + NUMBER_GAP
    avail_h = max(20.0, max_h - (LABEL_H + NUMBER_GAP))

    with Image.open(item.image_path) as im:
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        elif im.mode == "L":
            im = im.convert("RGB")
        w, h = im.size
        sw, sh = _scaled_size(w, h, max_w, avail_h)
        target_px_w = max(1, int(sw * 1.5))
        if w > target_px_w * 1.2:
            ratio = target_px_w / w
            im = im.resize((target_px_w, max(1, int(h * ratio))), Image.Resampling.LANCZOS)
        buf = BytesIO()
        im.save(buf, format="JPEG", quality=85)
        buf.seek(0)

    rect = fitz.Rect(x0, img_y, x0 + sw, img_y + sh)
    page.insert_image(rect, stream=buf.getvalue(), keep_proportion=True)
    return img_y + sh


def _layout_page_items(chunk: list[ComposeItem]) -> list[tuple[ComposeItem, float, float, float, float]]:
    """Return list of (item, x0, y0, max_w, max_h) for placement."""
    col_w = _column_width()
    top = _content_top()
    bottom = _content_bottom()
    content_h = bottom - top
    left_x = MARGIN
    right_x = MARGIN + col_w + GUTTER
    placements: list[tuple[ComposeItem, float, float, float, float]] = []

    count = len(chunk)
    if count == 1:
        placements.append((chunk[0], left_x, top, col_w * 2 + GUTTER, content_h))
    elif count == 2:
        placements.append((chunk[0], left_x, top, col_w, content_h))
        placements.append((chunk[1], right_x, top, col_w, content_h))
    elif count == 3:
        h0 = _measure_height(chunk[0].image_path, col_w, content_h)
        h1 = _measure_height(chunk[1].image_path, col_w, content_h)
        if h0 + GAP_Y + h1 <= content_h + 1:
            # left stack 2, right 1
            placements.append((chunk[0], left_x, top, col_w, content_h / 2 - GAP_Y / 2))
            placements.append((chunk[1], left_x, top + content_h / 2 + GAP_Y / 2, col_w, content_h / 2 - GAP_Y / 2))
            placements.append((chunk[2], right_x, top, col_w, content_h))
        else:
            # left 1, right stack 2
            placements.append((chunk[0], left_x, top, col_w, content_h))
            placements.append((chunk[1], right_x, top, col_w, content_h / 2 - GAP_Y / 2))
            placements.append((chunk[2], right_x, top + content_h / 2 + GAP_Y / 2, col_w, content_h / 2 - GAP_Y / 2))
    else:  # 4
        half = content_h / 2 - GAP_Y / 2
        placements.append((chunk[0], left_x, top, col_w, half))
        placements.append((chunk[1], left_x, top + half + GAP_Y, col_w, half))
        placements.append((chunk[2], right_x, top, col_w, half))
        placements.append((chunk[3], right_x, top + half + GAP_Y, col_w, half))

    return placements


def build_exam_pdf(
    items: list[ComposeItem],
    out_path: Path,
    *,
    title: str = "한국사 기출 조합 문제지",
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pages = pack_pages(items)
    doc = fitz.open()
    _register_cjk(doc)
    page_count = max(len(pages), 1)

    if not pages:
        page = doc.new_page(width=PAGE_W, height=PAGE_H)
        _draw_header(page, title, 1, 1)
        _insert_cjk(page, fitz.Rect(MARGIN, _content_top() + 10, PAGE_W - MARGIN, _content_top() + 30), "(선택된 문항 없음)", 11)
    else:
        for pi, chunk in enumerate(pages, start=1):
            page = doc.new_page(width=PAGE_W, height=PAGE_H)
            _draw_header(page, title, pi, page_count)
            for item, x0, y0, max_w, max_h in _layout_page_items(chunk):
                _place_image(page, item, x0, y0, max_w, max_h)

    doc.save(out_path, deflate=True, garbage=4)
    doc.close()
    return out_path


def build_answer_pdf(
    items: list[ComposeItem],
    out_path: Path,
    *,
    title: str = "한국사 기출 조합 정답지",
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    has_cjk = _register_cjk(doc)

    def new_ans_page() -> fitz.Page:
        page = doc.new_page(width=PAGE_W, height=PAGE_H)
        _draw_header(page, title, doc.page_count, 0)
        return page

    page = new_ans_page()
    y = _content_top() + 8
    fontsize = 9
    line_h = 14

    for item in items:
        source = _item_source_bracket(item)
        label = _answer_display(item.answer)
        line1 = f"{item.new_number}.  {label}    {source}"
        era = str(item.era).strip()
        key = str(item.answer_key).strip()
        if era and key:
            line2 = f"    [{era}] {key}"
        elif key:
            line2 = f"    {key}"
        elif era:
            line2 = f"    [{era}]"
        else:
            line2 = ""
        if y + line_h * (2 if line2 else 1) > _content_bottom():
            page = new_ans_page()
            y = _content_top() + 8
        rect1 = fitz.Rect(MARGIN, y, PAGE_W - MARGIN, y + line_h)
        _insert_cjk(page, rect1, line1, fontsize)
        if line2:
            rect2 = fitz.Rect(MARGIN, y + line_h, PAGE_W - MARGIN, y + line_h * 2)
            _insert_cjk(page, rect2, line2, fontsize - 1)
            y += line_h * 2 + 2
        else:
            y += line_h + 2

    total = doc.page_count
    for i in range(total):
        p = doc[i]
        p.insert_text(
            (PAGE_W - MARGIN - 50, MARGIN + 16),
            f"{i + 1}/{total}",
            fontsize=9,
            fontname="helv",
        )

    doc.save(out_path, deflate=True, garbage=4)
    doc.close()
    return out_path


_CJK_FONT: str | None = None
_CJK_MISSING_WARNED = False


def _project_root() -> Path:
    """scripts → history-exam-analyst → skills → .cursor → repo root"""
    return Path(__file__).resolve().parents[4]


def _find_cjk_font() -> str | None:
    """저장소 번들 폰트 우선 (Streamlit Cloud에 시스템 한글 폰트 없음)."""
    global _CJK_FONT, _CJK_MISSING_WARNED
    if _CJK_FONT is not None:
        return _CJK_FONT or None
    root = _project_root()
    candidates = [
        root / "assets" / "fonts" / "NanumGothic.ttf",
        root / "assets" / "fonts" / "NanumGothic-Regular.ttf",
        Path(r"C:\Windows\Fonts\malgun.ttf"),
        Path(r"C:\Windows\Fonts\malgunbd.ttf"),
        Path(r"C:\Windows\Fonts\NanumGothic.ttf"),
        Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
    ]
    for p in candidates:
        if p.is_file():
            _CJK_FONT = str(p)
            return _CJK_FONT
    _CJK_FONT = ""
    if not _CJK_MISSING_WARNED:
        _CJK_MISSING_WARNED = True
        print(
            "경고: 한글 폰트 없음 — PDF 제목/라벨이 깨질 수 있습니다. "
            "assets/fonts/NanumGothic.ttf 를 저장소에 두세요.",
            flush=True,
        )
    return None


def _register_cjk(doc: fitz.Document) -> bool:
    """CJK 폰트 파일 존재 여부. Document.insert_font는 PyMuPDF 1.28+에서 제거됨."""
    return bool(_find_cjk_font())


def _ensure_page_cjk(page: fitz.Page) -> bool:
    """페이지에 CJK 폰트 등록 (가능하면). 실패해도 fontfile= 경로로 그릴 수 있음."""
    font = _find_cjk_font()
    if not font:
        return False
    try:
        # PyMuPDF 1.28+: Page.insert_font
        page.insert_font(fontname="cjk", fontfile=font)
        return True
    except Exception:
        pass
    try:
        # 구버전: Document.insert_font
        doc = page.parent
        if doc is not None and hasattr(doc, "insert_font"):
            doc.insert_font(fontname="cjk", fontfile=font)
            return True
    except Exception:
        pass
    return False


def _insert_cjk(page: fitz.Page, rect: fitz.Rect, text: str, fontsize: float) -> None:
    font = _find_cjk_font()
    if font:
        # 1) fontfile 직접 지정 — insert_font API에 의존하지 않음 (Cloud/최신 PyMuPDF 안전)
        try:
            page.insert_textbox(
                rect,
                text,
                fontsize=fontsize,
                fontfile=font,
                fontname="nanum",
                align=fitz.TEXT_ALIGN_LEFT,
            )
            return
        except Exception:
            pass
        # 2) 페이지/문서에 등록 후 fontname="cjk"
        _ensure_page_cjk(page)
        try:
            page.insert_textbox(
                rect,
                text,
                fontsize=fontsize,
                fontname="cjk",
                align=fitz.TEXT_ALIGN_LEFT,
            )
            return
        except Exception:
            pass
    page.insert_textbox(rect, text, fontsize=fontsize, fontname="helv", align=fitz.TEXT_ALIGN_LEFT)


def find_cjk_font_path() -> str | None:
    """UI/진단용: 현재 선택된 CJK 폰트 경로."""
    return _find_cjk_font()


def items_from_rows(
    rows: list[dict],
    root: Path,
    *,
    require_image: bool = True,
) -> list[ComposeItem]:
    try:
        from drive_images import resolve_image
    except ImportError:
        resolve_image = None  # type: ignore

    try:
        from normalize_class_code import answer_label_to_number
    except ImportError:
        answer_label_to_number = None  # type: ignore

    items: list[ComposeItem] = []
    for i, row in enumerate(rows, start=1):
        rel = str(row.get("이미지경로", "")).replace("\\", "/")
        path: Path | None = None
        if resolve_image is not None:
            path = resolve_image(root, rel)
        if path is None and rel:
            candidate = root / rel
            path = candidate if candidate.is_file() else None
        if require_image and (path is None or not path.is_file()):
            continue
        raw_answer = str(row.get("정답", "") or "").strip()
        if raw_answer.lower() == "nan":
            raw_answer = ""
        if answer_label_to_number is not None and raw_answer:
            normalized = answer_label_to_number(raw_answer)
            if normalized:
                raw_answer = normalized
        items.append(
            ComposeItem(
                image_path=path if path is not None else Path(rel or ""),
                new_number=i,
                era=str(row.get("시대", "")),
                achievement_code=str(row.get("성취기준_코드", "")),
                answer=raw_answer,
                answer_key=str(row.get("정답핵심요소", "")),
                source_year=str(row.get("연도", "")),
                source_exam_type=str(row.get("문형", "")),
                source_number=str(row.get("문항번호", "")),
                profile_label=str(row.get("프로파일라벨", row.get("프로파일", ""))),
                subject=str(row.get("과목", "")),
            )
        )
    return items


def compose_to_files(
    rows: list[dict],
    root: Path,
    out_dir: Path,
    *,
    title: str = "한국사 기출 조합 문제지",
) -> tuple[Path, Path]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    exam_items = items_from_rows(rows, root, require_image=True)
    # 정답지는 이미지 없어도 선지 번호·출처를 출력
    answer_items = items_from_rows(rows, root, require_image=False)
    # 새 번호는 바구니 순서를 따르되, 문제지에 실제로 실린 문항만 맞추려면
    # 이미지 있는 행 기준으로 번호를 다시 매긴다.
    present_uids = {
        (it.source_year, it.source_exam_type, it.source_number, it.subject)
        for it in exam_items
    }
    if exam_items:
        renumbered: list[ComposeItem] = []
        n = 0
        for it in answer_items:
            key = (it.source_year, it.source_exam_type, it.source_number, it.subject)
            if key not in present_uids:
                continue
            n += 1
            it.new_number = n
            renumbered.append(it)
        answer_items = renumbered or answer_items
    exam_path = out_dir / f"{stamp}_문제지.pdf"
    answer_path = out_dir / f"{stamp}_정답지.pdf"
    build_exam_pdf(exam_items, exam_path, title=title)
    build_answer_pdf(answer_items, answer_path, title=f"{title} — 정답")
    return exam_path, answer_path
