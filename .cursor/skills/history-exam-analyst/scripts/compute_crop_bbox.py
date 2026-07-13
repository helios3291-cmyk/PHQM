#!/usr/bin/env python3
"""2단 시험지 레이아웃 규칙으로 문항별 크롭 bbox를 계산합니다."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

DPI = 200
SCALE = DPI / 72.0
PAD = 12 * SCALE
OPTION_IMAGE_PAD = 70.0

QUESTION_RE = re.compile(r"^(\d{1,2})\.\s+")
QUESTION_RE_ALT = re.compile(r"^(\d{1,2})\s+(?=[가-힣〈\[\(])")
# 한능검 OCR: "5," / "5 ." 등
QUESTION_RE_OCR = re.compile(r"^(\d{1,2})\s*[.,]\s*(?=[가-힣〈\[\(]|다음|밑줄)")
QUESTION_STEM_RE = re.compile(
    r"다음|밑줄|학생|장면|인터뷰|대화|우표|제도|수업|문화유산|뉴스|카드|전시|검색어|가상|인물|주제|탐구|문화|"
    r"옳은\s*것은|알맞은|해당하지|설명으로|시기에|자료에|자료로|자료의|밑줄\s*친|\[3점\]|보기|"
    r"적절한|들어갈|영향으로|내용으로|결과로|이유로|배경으로|관련|탐구 활동|고른 것은|"
    r"검색\s*어|상황\s*이후|사회\s*모습|사실로"
)
MAX_QUESTION_NUM = 50
OPTION_MARKERS = re.compile(r"[①②③④⑤]")
OPTION5_RE = re.compile(r"⑤")
CAPTION_RE = re.compile(r"^<[^>]+>$", re.MULTILINE)
OPTION_HASH_RE = re.compile(r"^#\s")
HEADER_FOOTER_RE = re.compile(
    r"한국사\([가나AB]형\)|역사2?\([가나공통]+\)|역사Ⅰ|역사Ⅱ|"
    r"^\d+\s*한국사|^\d+\s*역사|8-\d+|검사지의 문항|답안지에|기초학력|"
    r"한국사영역|이 문제지에 관한 저작권|대학수학능력시험|모의평가 문제지|"
    r"제\d\s*교시|\*\s*확인 사항|"
    r"한국사능력검정|능력검정시험|제\s*\d+\s*회",
)


@dataclass
class Block:
    text: str
    bbox: list[float]

    @property
    def x0(self) -> float:
        return self.bbox[0]

    @property
    def y0(self) -> float:
        return self.bbox[1]

    @property
    def x1(self) -> float:
        return self.bbox[2]

    @property
    def y1(self) -> float:
        return self.bbox[3]

    @property
    def x_center(self) -> float:
        return (self.x0 + self.x1) / 2


def is_question_start(text: str) -> int | None:
    text = text.strip()
    m = QUESTION_RE.match(text) or QUESTION_RE_OCR.match(text)
    if m:
        return int(m.group(1))
    m = QUESTION_RE_ALT.match(text)
    if m:
        num = int(m.group(1))
        if len(text) <= 3:
            return None
        return num
    return None


def is_at_column_margin(block: Block, gutter: float) -> bool:
    col = column_of(block, gutter)
    if col == "left":
        # 모평/수능 좌단 문항번호는 x0≈88pt 부근인 경우가 많음
        return block.x0 < max(100.0, gutter * 0.28)
    return gutter - 15 < block.x0 < gutter + 120


def marker_score(block: Block, gutter: float) -> float:
    text = block.text.strip()
    score = 0.0
    if is_at_column_margin(block, gutter):
        score += 2.0
    elif column_of(block, gutter) == "left" and block.x0 > 90:
        score -= 5.0
    if QUESTION_STEM_RE.search(text):
        score += 3.0
    if "다음" in text:
        score += 1.0
    return score


def is_valid_question_marker(block: Block, gutter: float) -> int | None:
    text = block.text.strip()
    if is_header_footer(block):
        return None

    num = is_question_start(text)
    if num is None or num < 1 or num > MAX_QUESTION_NUM:
        return None

    if QUESTION_RE.match(text) or QUESTION_RE_OCR.match(text):
        if not QUESTION_STEM_RE.search(text):
            return None
        if not is_at_column_margin(block, gutter):
            return None
        return num

    if QUESTION_RE_ALT.match(text):
        if len(text) <= 15 or not QUESTION_STEM_RE.search(text):
            return None
        if not is_at_column_margin(block, gutter):
            return None
        return num

    return None


def is_header_footer(block: Block) -> bool:
    text = block.text.strip().replace("\n", " ")
    if not text:
        return True
    if HEADER_FOOTER_RE.search(text):
        return True
    if block.y0 < 75 and ("한국사" in text or "역사" in text):
        return True
    if block.y0 > 980:
        return True
    return False


def _question_marker_blocks(blocks: list[Block]) -> list[Block]:
    """gutter 없이 문항 번호 후보를 수집 (단 경계 추정용)."""
    found: list[Block] = []
    for block in blocks:
        if is_header_footer(block):
            continue
        text = block.text.strip()
        if not (QUESTION_RE.match(text) or QUESTION_RE_OCR.match(text)):
            continue
        if not QUESTION_STEM_RE.search(text):
            continue
        num = is_question_start(text)
        if num is None or num < 1 or num > MAX_QUESTION_NUM:
            continue
        found.append(block)
    return found


def detect_gutter(blocks: list[Block], page_width: float) -> float:
    content = [b for b in blocks if not is_header_footer(b)]
    if not content:
        return page_width * 0.52

    # 문항 번호 마커 기반: 좌단 자료가 이미지라 텍스트 max-x1이 좁은 모평/수능 대응
    markers = _question_marker_blocks(blocks)
    left_m = [b for b in markers if b.x0 < page_width * 0.40]
    right_m = [b for b in markers if b.x0 >= page_width * 0.40]
    if left_m and right_m:
        return min(b.x0 for b in right_m)

    # 좁은 블록만 사용 (와이드 헤더·스패닝 블록 제외)
    narrow = [b for b in content if (b.x1 - b.x0) < page_width * 0.35]
    pool = narrow or content
    left_x1 = max(
        (b.x1 for b in pool if b.x_center < page_width * 0.45),
        default=0.0,
    )
    right_x0 = min(
        (b.x0 for b in pool if b.x_center > page_width * 0.55),
        default=page_width,
    )
    if right_x0 > left_x1 + 15 and right_x0 > page_width * 0.42:
        return (left_x1 + right_x0) / 2

    centers = sorted(b.x_center for b in pool)
    best_gap = 0.0
    best_mid = page_width * 0.52
    for i in range(len(centers) - 1):
        gap = centers[i + 1] - centers[i]
        mid = (centers[i + 1] + centers[i]) / 2
        if gap > best_gap and page_width * 0.35 < mid < page_width * 0.65:
            best_gap = gap
            best_mid = mid
    return best_mid


def column_of(block: Block, gutter: float) -> str:
    return "left" if block.x_center < gutter else "right"


def in_column(block: Block, gutter: float, col: str) -> bool:
    return column_of(block, gutter) == col


def scale_bbox(bbox: list[float]) -> list[int]:
    return [int(round(v * SCALE)) for v in bbox]


def page_width_from_blocks(blocks: list[Block]) -> float:
    if not blocks:
        return 676.0
    return max(b.x1 for b in blocks) + 20


def page_width_from_page(
    page: dict, blocks: list[Block], root: Path | None = None
) -> float:
    """페이지 PNG 너비를 우선 사용해 우단 잘림을 방지한다."""
    page_image = page.get("page_image")
    if page_image:
        try:
            from PIL import Image

            path = Path(page_image)
            if not path.is_absolute() and root is not None:
                path = root / page_image
            return Image.open(path).size[0] / SCALE
        except Exception:
            pass
    return page_width_from_blocks(blocks)


def is_standalone_option_five(text: str) -> bool:
    return text.strip() in ("⑤", "⑤\n")


def _option_x_band(blocks: list[Block], gutter: float, col: str, y_start: float) -> tuple[float, float]:
    xs: list[float] = []
    for block in blocks:
        if not in_column(block, gutter, col):
            continue
        if block.y0 < y_start - 2:
            continue
        t = block.text.strip()
        if t in ("①", "②", "③", "④", "⑤") or (len(t) <= 4 and OPTION_MARKERS.search(t)):
            xs.extend([block.x0, block.x1])
    if not xs:
        return 0.0, 9999.0
    return min(xs) - 40, max(xs) + 320


def _avg_option_image_gap(
    blocks: list[Block], gutter: float, col: str, y_start: float, y_limit: float
) -> float | None:
    markers: list[float] = []
    captions: list[tuple[float, float]] = []
    for block in blocks:
        if not in_column(block, gutter, col):
            continue
        if block.y0 < y_start - 2 or block.y0 >= y_limit - 2:
            continue
        t = block.text.strip()
        if t in ("①", "②", "③", "④"):
            markers.append(block.y0)
        elif CAPTION_RE.match(t) or ("<" in t and ">" in t):
            captions.append((block.y0, block.y1))

    if not markers or not captions:
        return None

    gaps: list[float] = []
    for my0 in markers:
        below = [cy1 for cy0, cy1 in captions if cy0 > my0 + 5]
        if below:
            gaps.append(min(below) - my0)
    return sum(gaps) / len(gaps) if gaps else None


def extend_after_option_five(
    blocks: list[Block],
    gutter: float,
    col: str,
    five_block: Block,
    y_start: float,
    y_limit: float,
) -> float:
    five_y0 = five_block.y0
    x_min, x_max = _option_x_band(blocks, gutter, col, y_start)
    max_y = five_block.y1

    for block in blocks:
        if not in_column(block, gutter, col):
            continue
        if block.y0 <= five_y0 + 2:
            continue
        if block.y0 >= y_limit - 2:
            continue
        if block.x1 < x_min or block.x0 > x_max:
            continue
        if is_valid_question_marker(block, gutter) is not None:
            continue
        t = block.text.strip()
        if CAPTION_RE.search(t) or OPTION_HASH_RE.match(t) or block.y0 > five_y0 + 5:
            max_y = max(max_y, block.y1)

    avg_gap = _avg_option_image_gap(blocks, gutter, col, y_start, y_limit)
    if avg_gap is not None:
        max_y = max(max_y, five_y0 + avg_gap)
    else:
        max_y = max(max_y, five_y0 + OPTION_IMAGE_PAD)

    return max_y


def find_option_bottom(
    blocks: list[Block],
    gutter: float,
    col: str,
    y_start: float,
    y_limit: float,
) -> float | None:
    option_bottom: float | None = None
    five_bottom: float | None = None
    five_block: Block | None = None

    for block in blocks:
        if not in_column(block, gutter, col):
            continue
        if block.y0 < y_start - 2 or block.y0 >= y_limit - 2:
            continue
        if not OPTION_MARKERS.search(block.text):
            continue
        option_bottom = block.y1 if option_bottom is None else max(option_bottom, block.y1)
        if OPTION5_RE.search(block.text):
            five_block = block
            five_bottom = block.y1 if five_bottom is None else max(five_bottom, block.y1)

    if five_block is not None and is_standalone_option_five(five_block.text):
        extended = extend_after_option_five(blocks, gutter, col, five_block, y_start, y_limit)
        five_bottom = extended if five_bottom is None else max(five_bottom, extended)

    return five_bottom if five_bottom is not None else option_bottom


def collect_question_text(
    all_pages: list[dict],
    marker_page: int,
    marker_y: float,
    gutter: float,
    col: str,
    y_end: float,
) -> str:
    texts: list[str] = []
    for page in all_pages:
        if page["page"] < marker_page:
            continue
        blocks = sorted(
            [Block(b["text"], b["bbox"]) for b in page["blocks"]],
            key=lambda b: (b.y0, b.x0),
        )
        for block in blocks:
            if page["page"] == marker_page and block.y0 < marker_y - 2:
                continue
            if page["page"] == marker_page and block.y0 >= y_end:
                continue
            if not in_column(block, gutter, col):
                continue
            if is_header_footer(block):
                continue
            t = block.text.strip()
            if t:
                texts.append(t)
        if page["page"] == marker_page:
            break
    return "\n".join(texts)


def _effective_next_marker(
    marker: dict,
    next_marker: dict | None,
    gutter: float,
    bottom: float | None,
) -> dict | None:
    if next_marker is None:
        return None
    header = Block(marker["text"], marker["bbox"])
    col = column_of(header, gutter)
    nm = Block(next_marker["text"], next_marker["bbox"])
    if next_marker["page"] != marker["page"]:
        return next_marker
    if column_of(nm, gutter) != col:
        return next_marker
    if bottom is not None and nm.y0 < bottom - 5:
        return None
    return next_marker


def compute_question_bbox(
    marker: dict,
    next_marker: dict | None,
    page_blocks: list[Block],
    all_pages: list[dict],
    page_width: float,
) -> tuple[list[int], str, list[str]]:
    warnings: list[str] = []
    gutter = detect_gutter(page_blocks, page_width)
    header = Block(marker["text"], marker["bbox"])
    col = column_of(header, gutter)

    y_start = header.y0
    if next_marker and next_marker["page"] == marker["page"]:
        if column_of(Block(next_marker["text"], next_marker["bbox"]), gutter) == col:
            y_limit = next_marker["bbox"][1]
        else:
            y_limit = 99999.0
    elif next_marker:
        y_limit = 99999.0
    else:
        y_limit = 99999.0

    bottom = find_option_bottom(page_blocks, gutter, col, y_start, y_limit)

    if bottom is None and next_marker:
        if next_marker["page"] == marker["page"]:
            same_col = column_of(
                Block(next_marker["text"], next_marker["bbox"]), gutter
            ) == col
            if same_col:
                bottom = next_marker["bbox"][1] - PAD / SCALE
            else:
                content = [
                    b for b in page_blocks if not is_header_footer(b) and in_column(b, gutter, col)
                ]
                bottom = max((b.y1 for b in content if b.y0 >= y_start), default=header.y1)
        else:
            warnings.append(f"Q{marker['number']}: ⑤ 미검출, 페이지 하단까지 사용")
            content = [
                b for b in page_blocks if not is_header_footer(b) and in_column(b, gutter, col)
            ]
            bottom = max((b.y1 for b in content if b.y0 >= y_start), default=header.y1 + 200)
    elif bottom is None:
        bottom = header.y1 + 200
        warnings.append(f"Q{marker['number']}: 선지 미검출")

    next_marker = _effective_next_marker(marker, next_marker, gutter, bottom)

    if next_marker and next_marker["page"] == marker["page"]:
        nm_col = column_of(Block(next_marker["text"], next_marker["bbox"]), gutter)
        if nm_col == col:
            max_y = next_marker["bbox"][1] - PAD / SCALE
            if bottom > max_y:
                bottom = max_y
                warnings.append(f"Q{marker['number']}: ⑤가 다음 문항과 겹쳐 하단 조정")

    x0 = max(0.0, header.x0 - PAD / SCALE)
    if col == "left":
        x1 = min(page_width, gutter - PAD / SCALE)
    else:
        x1 = page_width - PAD / SCALE
    y0 = max(0.0, y_start - PAD / SCALE)
    y1 = bottom + PAD / SCALE

    text = collect_question_text(
        all_pages,
        marker["page"],
        y_start,
        gutter,
        col,
        y_end=bottom + PAD / SCALE,
    )

    return scale_bbox([x0, y0, x1, y1]), text, warnings


def compute_all_bboxes(
    text_json_data: dict, root: Path | None = None
) -> tuple[list[dict], list[str]]:
    """text.json 데이터에서 문항별 bbox·텍스트·경고를 계산합니다."""
    all_pages = text_json_data["pages"]
    all_warnings: list[str] = []
    if root is None:
        root = Path(__file__).resolve().parents[4]

    candidates: dict[int, list[dict]] = defaultdict(list)
    width_cache: dict[int, float] = {}
    gutter_cache: dict[int, float] = {}

    for page in all_pages:
        page_blocks = [Block(b["text"], b["bbox"]) for b in page["blocks"]]
        page_num = int(page["page"])
        page_width = page_width_from_page(page, page_blocks, root=root)
        if page.get("page_image"):
            path = root / page["page_image"]
            if not path.exists() and not Path(page["page_image"]).is_absolute():
                all_warnings.append(
                    f"page {page_num}: page_image 열기 실패 → 블록 기반 폭 추정"
                )
        width_cache[page_num] = page_width
        gutter = detect_gutter(page_blocks, page_width)
        gutter_cache[page_num] = gutter

        for block in page["blocks"]:
            b = Block(block["text"], block["bbox"])
            num = is_valid_question_marker(b, gutter)
            if num is None:
                continue
            candidates[num].append(
                {
                    "number": num,
                    "page": page["page"],
                    "page_image": page["page_image"],
                    "bbox": block["bbox"],
                    "text": block["text"],
                    "_score": marker_score(b, gutter),
                }
            )

    markers: list[dict] = []
    for num in sorted(candidates):
        best = max(candidates[num], key=lambda m: (m["_score"], -m["bbox"][1]))
        markers.append({k: v for k, v in best.items() if k != "_score"})

    results: list[dict] = []
    for i, marker in enumerate(markers):
        next_marker = markers[i + 1] if i + 1 < len(markers) else None
        page_data = next(p for p in all_pages if p["page"] == marker["page"])
        page_blocks = [Block(b["text"], b["bbox"]) for b in page_data["blocks"]]
        page_num = int(marker["page"])
        page_width = width_cache.get(page_num) or page_width_from_page(
            page_data, page_blocks, root=root
        )

        bbox, text, warnings = compute_question_bbox(
            marker, next_marker, page_blocks, all_pages, page_width
        )
        all_warnings.extend(warnings)

        results.append(
            {
                "number": marker["number"],
                "page": marker["page"],
                "page_image": marker["page_image"],
                "bbox": bbox,
                "text": text,
            }
        )

    return results, all_warnings
