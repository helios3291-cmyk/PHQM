#!/usr/bin/env python3
"""한능검(이미지 PDF) 2단 시험지: 번호 개수 우선 크롭 bbox.

단별로 굵은 문항번호 y를 먼저 세어 2/3문항 배치를 확정한 뒤,
top/bottom = 번호 y ± PAD 로 자른다. 전역 합이 50이 되도록만 보정한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

MAX_QUESTION_NUM = 50
TOP_PAD = 32
BOTTOM_PAD = 28
MIN_REGION_H = 140
MIN_GAP = 160
NUM_ZONE_W = 160
ROW_INK_MIN = 2
# 굵은 번호(문항번호) 최소 창 밀도 — 옵션 원보다 높음
BOLD_DENS_MIN = 0.12
# 확정 번호(옵션 원 배제). 63회 '7.'≈0.273 살리기 위해 0.26
BOLD_NUM_DENS = 0.26
LANE_DENS_MIN = 0.22
LOOSE_MIN_GAP = int(MIN_GAP * 0.55)
# 단 왼쪽 기준 번호 시작 x 허용 (구회차는 여백이 더 넓음)
NUM_XS0_MAX = 145
# audit 실패가 집중된 회차 상한 (포함)
LEGACY_ROUND_MAX = 68
HEADER_PAD = 8
# [N~M] 공유자료 표기 (OCR 노이즈 ? 허용)
BRACKET_PAIR_RE = re.compile(
    r"\[\s*(\d{1,2})\s*[~\-～∼\?]+?\s*(\d{1,2})\s*\]"
)


@dataclass(frozen=True)
class DetectParams:
    num_xs0_max: int
    num_zone_w: int


DEFAULT_PARAMS = DetectParams(num_xs0_max=NUM_XS0_MAX, num_zone_w=NUM_ZONE_W)
# 구회차: 넓은 좌여백 (실측 xs0≈147–190)
LEGACY_PARAMS = DetectParams(num_xs0_max=190, num_zone_w=200)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def parse_hancert_round(text_json_data: dict) -> int | None:
    """text.json의 pdf_stem/source_pdf에서 N회를 추출. 실패 시 None."""
    for key in ("pdf_stem", "source_pdf"):
        raw = str(text_json_data.get(key) or "")
        m = re.search(r"\((\d{1,3})회\)", raw) or re.search(r"(\d{1,3})회", raw)
        if m:
            return int(m.group(1))
    pages = text_json_data.get("pages") or []
    if pages:
        rel = str(pages[0].get("page_image") or "")
        m = re.search(r"\((\d{1,3})회\)", rel) or re.search(r"(\d{1,3})회", rel)
        if m:
            return int(m.group(1))
    return None


def detect_params_for_round(round_num: int | None) -> DetectParams:
    if round_num is not None and round_num <= LEGACY_ROUND_MAX:
        return LEGACY_PARAMS
    return DEFAULT_PARAMS


def ink_mask(img: Image.Image, thresh: int = 200) -> np.ndarray:
    return np.asarray(img.convert("L")) < thresh


def find_gutter_x(mask: np.ndarray) -> int:
    h, w = mask.shape
    x0, x1 = int(w * 0.42), int(w * 0.58)
    return x0 + int(np.argmin(mask[:, x0:x1].sum(axis=0).astype(np.float64)))


def content_y_range(mask: np.ndarray, page: int) -> tuple[int, int]:
    """하위 호환용. 신규 경로는 detect_page_margins 사용."""
    return detect_page_margins(mask, page)


def detect_page_margins(mask: np.ndarray, page: int) -> tuple[int, int]:
    """머릿말·꼬릿말 아래/위 본문 y 범위 (가로 구분선 우선)."""
    h, w = mask.shape
    row_sum = mask.sum(axis=1).astype(np.float64)
    top_frac = 0.145 if page == 1 else 0.065
    y_fallback0 = int(h * top_frac)
    y_fallback1 = int(h * 0.955)

    # 상단 15%: 전폭 가로 구분선. 본문 박스선과 구분하기 위해
    # 가장 위 클러스터(연속 ≤50px)만 머릿말로 본다.
    top_limit = int(h * 0.15)
    header_rules: list[int] = []
    for i in range(5, top_limit):
        if row_sum[i] > w * 0.35 and row_sum[i - 1] < w * 0.15:
            header_rules.append(i)
    if header_rules:
        cluster = [header_rules[0]]
        for y in header_rules[1:]:
            if y - cluster[-1] <= 50:
                cluster.append(y)
            else:
                break
        y0 = min(h - 1, cluster[-1] + HEADER_PAD)
        # 1쪽 표지 등은 fallback보다 너무 위면 fallback 유지
        if page == 1:
            y0 = max(y0, y_fallback0)
    else:
        ys = np.where(row_sum > w * 0.012)[0]
        y0 = max(y_fallback0, int(ys.min())) if len(ys) else y_fallback0

    # 하단 8%: 대칭 구분선 (보수적 — 과도하게 올리지 않음)
    bot_start = int(h * 0.92)
    footer_rules: list[int] = []
    for i in range(h - 6, bot_start, -1):
        if row_sum[i] > w * 0.35 and row_sum[i + 1] < w * 0.15:
            footer_rules.append(i)
    if footer_rules:
        # 가장 아래 클러스터
        cluster = [footer_rules[0]]
        for y in footer_rules[1:]:
            if cluster[-1] - y <= 50:
                cluster.append(y)
            else:
                break
        y1 = max(y0 + MIN_REGION_H, min(cluster) - HEADER_PAD)
    else:
        ys = np.where(row_sum > w * 0.012)[0]
        y1 = min(y_fallback1, int(ys.max())) if len(ys) else y_fallback1

    if y1 <= y0 + MIN_REGION_H:
        return y_fallback0, y_fallback1
    return int(y0), int(y1)


def _suppress_vertical_rules(band: np.ndarray) -> np.ndarray:
    if band.size == 0:
        return band
    dens = band.mean(axis=0)
    out = band.copy()
    for x, d in enumerate(dens):
        if d >= 0.45:
            out[:, x] = False
    return out


def detect_question_number_starts(
    mask: np.ndarray,
    col_x0: int,
    y0: int,
    y1: int,
    params: DetectParams | None = None,
) -> list[int]:
    """단 왼쪽 번호 레인의 굵은 문항번호 blob y_top 목록."""
    params = params or DEFAULT_PARAMS
    zone_x1 = min(col_x0 + params.num_zone_w, mask.shape[1])
    band = _suppress_vertical_rules(mask[y0:y1, col_x0:zone_x1])
    if band.size == 0:
        return []
    row = band.sum(axis=1).astype(np.float64)
    cands: list[tuple[int, int, float]] = []  # y, xs0, dens
    i = 0
    h = len(row)
    while i < h:
        if row[i] < ROW_INK_MIN:
            i += 1
            continue
        j = i
        while j < h and row[j] >= ROW_INK_MIN:
            j += 1
        height = j - i
        chunk = band[i:j]
        if 16 <= height <= 50:
            col_ink = chunk.any(axis=0)
            if col_ink.any():
                xs = np.where(col_ink)[0]
                xs0 = int(xs[0])
                if xs0 <= params.num_xs0_max:
                    win = chunk[:, xs0 : xs0 + 36]
                    ink_cols = int(win.any(axis=0).sum())
                    dens = float(win.mean())
                    if 10 <= ink_cols <= 36 and dens >= BOLD_DENS_MIN:
                        cands.append((y0 + i, xs0, dens))
        i = max(j, i + 1)

    if not cands:
        return []

    # 굵은 번호(고밀도)를 우선해 옵션(①) 레인 제거
    bold = [(y, x, d) for y, x, d in cands if d >= BOLD_NUM_DENS]
    if bold:
        min_x = min(x for _, x, _ in bold)
        lane = [
            (y, x, d)
            for y, x, d in cands
            if x <= min_x + 22 and d >= LANE_DENS_MIN
        ]
    else:
        min_x = min(x for _, x, _ in cands)
        lane = [(y, x, d) for y, x, d in cands if x <= min_x + 28]

    merged: list[int] = []
    for y, _x, _d in lane:
        if y > y1 - 160:
            continue
        if merged and y - merged[-1] < 55:
            continue
        merged.append(y)

    # 옵션 원 과다 시: bold만 · MIN_GAP 간격으로 축소
    if len(merged) > 4 and bold:
        bold_ys = sorted(y for y, _x, _d in bold if y <= y1 - 160)
        tight: list[int] = []
        for y in bold_ys:
            if tight and y - tight[-1] < MIN_GAP * 0.5:
                continue
            tight.append(y)
        if 2 <= len(tight) <= 4:
            return tight
    return merged


# 하위 호환 별칭
def margin_start_ys(
    mask: np.ndarray,
    col_x0: int,
    y0: int,
    y1: int,
    params: DetectParams | None = None,
) -> list[int]:
    return detect_question_number_starts(mask, col_x0, y0, y1, params)


def select_n_starts(starts: list[int], y0: int, y1: int, n: int) -> list[int] | None:
    if len(starts) < n:
        return None
    h = y1 - y0
    best = None
    best_sc = 1e18
    for i in range(len(starts) - n + 1):
        use = starts[i : i + n]
        gaps = [use[j + 1] - use[j] for j in range(n - 1)]
        if min(gaps) < MIN_GAP:
            continue
        if use[0] - y0 > h * 0.22:
            continue
        if y1 - use[-1] < MIN_GAP * 0.4:
            continue
        mean = sum(gaps) / len(gaps)
        sc = sum((g - mean) ** 2 for g in gaps) + (use[0] - y0) * 0.15
        if sc < best_sc:
            best_sc = sc
            best = list(use)
    return best


def pick_three_starts_loose(starts: list[int], y0: int, y1: int) -> list[int] | None:
    """엄격 조건 실패 시 간격이 가장 고른 3개 번호 y 선택."""
    tight = select_n_starts(starts, y0, y1, 3)
    if tight is not None:
        return tight
    if len(starts) < 3:
        return None
    h = y1 - y0
    best = None
    best_min = -1.0
    for i in range(len(starts)):
        for j in range(i + 1, len(starts)):
            for k in range(j + 1, len(starts)):
                use = [starts[i], starts[j], starts[k]]
                gaps = [use[1] - use[0], use[2] - use[1]]
                if min(gaps) < LOOSE_MIN_GAP:
                    continue
                if use[0] - y0 > h * 0.35:
                    continue
                if y1 - use[-1] < LOOSE_MIN_GAP * 0.35:
                    continue
                m = float(min(gaps))
                if m > best_min:
                    best_min = m
                    best = use
    return best


def well_spaced_starts(starts: list[int], y0: int, y1: int, n: int = 3) -> bool:
    return select_n_starts(starts, y0, y1, n) is not None


@dataclass(frozen=True)
class BracketPair:
    n0: int
    n1: int
    y_header: int


def _ocr_column_strip(
    img: Image.Image, col_x0: int, col_x1: int, y0: int, y1: int
) -> list[tuple[str, int, int]]:
    """국소 OCR → [(text, y_top_px, y_bottom_px), ...]. 실패 시 [].

    대괄호는 단 상단에 있으므로 높이의 상단 45%·좌측 좁은 레인만 본다.
    """
    try:
        import pytesseract
    except ImportError:
        return []
    try:
        from prepare_pdf import _configure_tesseract
    except ImportError:
        _configure_tesseract = None  # type: ignore
    try:
        if _configure_tesseract:
            _configure_tesseract(pytesseract)
        x0 = max(0, col_x0)
        # 번호·대괄호 레인만 (전체 단 OCR 비용 회피)
        x1 = min(img.size[0], x0 + max(220, min(280, col_x1 - col_x0)))
        y_ocr1 = min(img.size[1], y0 + max(400, int((y1 - y0) * 0.45)))
        crop = img.crop((x0, max(0, y0), x1, y_ocr1))
        if crop.size[0] < 20 or crop.size[1] < 20:
            return []
        data = pytesseract.image_to_data(
            crop,
            lang="kor+eng",
            config="--psm 6",
            output_type=pytesseract.Output.DICT,
        )
    except Exception:
        return []
    rows: dict[int, list[tuple[int, str]]] = {}
    n = len(data["text"])
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        conf = int(data["conf"][i]) if str(data["conf"][i]) != "-1" else -1
        if conf >= 0 and conf < 25:
            continue
        # Tesseract top은 크롭 상대 좌표 — y0는 양자화 후 한 번만 가산
        top_rel = int(data["top"][i])
        left = int(data["left"][i])
        key = top_rel // 12
        rows.setdefault(key, []).append((left, text))
    out: list[tuple[str, int, int]] = []
    for key in sorted(rows):
        parts = sorted(rows[key], key=lambda t: t[0])
        line = "".join(p[1] for p in parts)
        y_top = key * 12 + y0
        out.append((line, y_top, y_top + 24))
    return out


def _normalize_bracket_compact(compact: str) -> str:
    """OCR 틸드 누락 `[4950]` → `[49~50]`."""
    return re.sub(r"\[(\d{2})(\d{2})\]", r"[\1~\2]", compact)


def _parse_bracket_hits(
    compact: str, y_header: int, seen: set[tuple[int, int]], found: list[BracketPair]
) -> None:
    compact = _normalize_bracket_compact(compact)
    for m in BRACKET_PAIR_RE.finditer(compact):
        n0, n1 = int(m.group(1)), int(m.group(2))
        # OCR 누락: [2?30] → (2,30) 을 (29,30) 으로 보정
        if n1 - n0 > 3 and n0 <= 9 and n1 >= 10:
            n0, n1 = n1 - 1, n1
        if n0 >= n1 or n1 - n0 > 3:
            continue
        if n0 < 1 or n1 > MAX_QUESTION_NUM:
            continue
        key = (n0, n1)
        if key in seen:
            continue
        seen.add(key)
        found.append(BracketPair(n0=n0, n1=n1, y_header=int(y_header)))


def detect_bracket_pairs_from_blocks(
    blocks: list[dict],
    col_x0: int,
    col_x1: int,
    y0: int,
    y1: int,
    dpi: int = 200,
) -> list[BracketPair]:
    """text.json blocks에서 `[N~M]` 탐지. PDF pt → 이미지 px."""
    if not blocks:
        return []
    scale = dpi / 72.0
    found: list[BracketPair] = []
    seen: set[tuple[int, int]] = set()
    for block in blocks:
        text = block.get("text") or ""
        bbox = block.get("bbox")
        if not text or not bbox or len(bbox) < 4:
            continue
        bx0, by0, bx1, by1 = (float(bbox[i]) * scale for i in range(4))
        # 단과 x 겹침, y가 단 본문 구간
        if bx1 < col_x0 or bx0 > col_x1:
            continue
        if by1 < y0 - 20 or by0 > y1 + 20:
            continue
        compact = re.sub(r"\s+", "", text)
        # 유니코드 thin space 등 제거 후에도 ~ 유지
        compact = compact.replace("\u2006", "").replace("\u2009", "")
        _parse_bracket_hits(compact, int(by0), seen, found)
    return found


def detect_bracket_pairs(
    img: Image.Image,
    col_x0: int,
    col_x1: int,
    y0: int,
    y1: int,
) -> list[BracketPair]:
    """단 영역 OCR에서 `[29~30]` / `[29-30]` 공유자료 헤더 탐지."""
    found: list[BracketPair] = []
    seen: set[tuple[int, int]] = set()
    for line, y_top, _y_bot in _ocr_column_strip(img, col_x0, col_x1, y0, y1):
        compact = re.sub(r"\s+", "", line)
        _parse_bracket_hits(compact, y_top, seen, found)
    return found


def filter_starts_around_brackets(
    starts: list[int], brackets: list[BracketPair]
) -> list[int]:
    """대괄호 헤더 숫자에 붙은 가짜 번호 blob 제거. 헤더 위 문항은 충분한 높이만 유지."""
    if not brackets or not starts:
        return starts
    y_h = min(b.y_header for b in brackets)
    out: list[int] = []
    for s in starts:
        if s > y_h + 40:
            out.append(s)
        elif s < y_h - 40 and (y_h - s) >= 400:
            out.append(s)
        # else: 헤더 근처/[N 오검출 또는 비정상적으로 짧은 상단 구간
    return out


def _three_keep_score(plan: "ColumnPlan", edges: list[int] | None) -> float:
    """높을수록 3문항 단으로 유지. 낮으면 강등 우선."""
    if not edges or len(edges) < 3:
        return -1e9
    e = edges[:3]
    gaps = [e[1] - e[0], e[2] - e[1]]
    h = max(plan.y1 - plan.y0, 1)
    # 대괄호 공유자료 단 — 최우선 유지
    if plan.brackets:
        score = 260.0
        if e[0] - plan.y0 < h * 0.18:
            score += 20
        return score

    # 균등 3문항 (분산 페널티 없이 동일 고득점) — 13/14 분리용
    if min(gaps) >= MIN_GAP and max(gaps) / max(min(gaps), 1) < 1.60:
        score = 200.0
        if e[0] - plan.y0 < h * 0.18:
            score += 35
        if len(plan.starts) > 4:
            score -= 40
        return score

    mean = sum(gaps) / 2.0
    variance = sum((g - mean) ** 2 for g in gaps)
    score = 100.0 - variance / 800.0
    if e[0] - plan.y0 < h * 0.18:
        score += 35
    if gaps[-1] < 250:
        score -= 90
    if len(plan.starts) > 4:
        score -= 45
    return score


def apply_bracket_pair_bounds(
    bounds: list[tuple[int, int]],
    edges: list[int],
    y0: int,
    y1: int,
    brackets: list[BracketPair],
) -> tuple[list[tuple[int, int]], list[str]]:
    """`[N~M]` 헤더 기준으로 공유 bbox를 두 슬롯에 넣고 직전 문항을 헤더 전에서 자른다."""
    if not brackets or not bounds or not edges:
        return bounds, []

    out = list(bounds)
    notes: list[str] = []
    for bp in brackets:
        after = [
            i
            for i, e in enumerate(edges[: len(out)])
            if e > bp.y_header + 40
        ]
        if len(after) < 2:
            continue
        i, j = after[0], after[1]
        for a, b in zip(after, after[1:]):
            if b == a + 1:
                i, j = a, b
                break
        y_header = max(y0, bp.y_header - TOP_PAD)
        if i > 0:
            prev_top, _pb = out[i - 1]
            out[i - 1] = (
                prev_top,
                max(prev_top + MIN_REGION_H // 2, y_header - 2),
            )
        if j + 1 < len(edges) and j + 1 < len(out):
            pair_bottom = edges[j + 1] - TOP_PAD
        else:
            pair_bottom = y1
        pair_bottom = max(y_header + MIN_REGION_H, pair_bottom)
        out[i] = (y_header, pair_bottom)
        out[j] = (y_header, pair_bottom)
        notes.append(f"[{bp.n0}~{bp.n1}]@y{bp.y_header} slots={i},{j}")
    return out, notes


def emit_bounds_with_brackets(
    plan: "ColumnPlan",
    n: int,
    edges: list[int] | None,
) -> tuple[list[tuple[int, int]], list[str]]:
    """번호 split 후 대괄호 공유 적용."""
    notes: list[str] = []
    if plan.brackets and plan.starts:
        bp = plan.brackets[0]
        after = [s for s in plan.starts if s > bp.y_header + 40]
        before = [
            s
            for s in plan.starts
            if s < bp.y_header - 40 and (bp.y_header - s) >= 400
        ]
        if len(after) >= 2:
            bounds: list[tuple[int, int]] = []
            y_header = max(plan.y0, bp.y_header - TOP_PAD)
            for i, s in enumerate(before):
                top = max(plan.y0, s - TOP_PAD)
                if i + 1 < len(before):
                    bottom = before[i + 1] - TOP_PAD
                else:
                    bottom = y_header - 2
                if bottom - top >= MIN_REGION_H // 2:
                    bounds.append((top, max(top + MIN_REGION_H // 2, bottom)))
            pair_bottom = plan.y1
            if len(after) > 2:
                pair_bottom = after[2] - TOP_PAD
            pair_bottom = max(y_header + MIN_REGION_H, pair_bottom)
            bounds.append((y_header, pair_bottom))
            bounds.append((y_header, pair_bottom))
            notes.append(
                f"[{bp.n0}~{bp.n1}]@y{bp.y_header} "
                f"before={before} after={after[:2]}"
            )
            return bounds, notes

    bounds = split_n(
        plan.seps,
        plan.y0,
        plan.y1,
        n,
        plan.starts,
        mask=plan.mask_ref,
        col_x0=plan.x0,
        col_x1=plan.x1,
        edges=edges,
    )
    if n == 3 and len(bounds) < 3:
        h = plan.y1 - plan.y0
        a, b = plan.y0 + h // 3, plan.y0 + 2 * h // 3
        bounds = [
            (plan.y0, a - BOTTOM_PAD),
            (a + TOP_PAD // 2, b - BOTTOM_PAD),
            (b + TOP_PAD // 2, plan.y1),
        ]
        notes.append("3문항 균등 재분할")
    edge_list = list(edges) if edges else list(plan.starts or [])
    if plan.brackets and edge_list and len(bounds) >= 2:
        bounds, bnotes = apply_bracket_pair_bounds(
            bounds, edge_list[: len(bounds)], plan.y0, plan.y1, plan.brackets
        )
        notes.extend(bnotes)
    return bounds, notes


def column_dotted_seps(
    mask: np.ndarray, x0: int, x1: int, y0: int, y1: int
) -> list[int]:
    band = mask[y0:y1, x0:x1]
    if band.size == 0:
        return []
    h, w = band.shape
    hits: list[int] = []
    for i in range(int(h * 0.15), int(h * 0.85)):
        row = band[i] > 0
        ink = float(row.mean())
        if not (0.06 <= ink <= 0.28):
            continue
        toggles = int(np.sum(np.abs(np.diff(row.astype(np.int8)))))
        if toggles < w * 0.12:
            continue
        above = float(band[max(0, i - 30) : i - 5].mean()) if i > 5 else 0
        below = float(band[i + 5 : min(h, i + 30)].mean()) if i + 5 < h else 0
        if above < 0.02 or below < 0.02:
            continue
        hits.append(y0 + i)

    merged: list[int] = []
    for y in hits:
        if merged and y - merged[-1] < 40:
            continue
        merged.append(y)
    if len(merged) <= 4:
        return merged
    scored = []
    for i, y in enumerate(merged):
        prev = merged[i - 1] if i else y0
        nxt = merged[i + 1] if i + 1 < len(merged) else y1
        scored.append((min(y - prev, nxt - y), y))
    scored.sort(reverse=True)
    return sorted(y for _, y in scored[:3])


def separator_candidates(
    mask: np.ndarray, x0: int, x1: int, y0: int, y1: int
) -> list[tuple[int, float]]:
    band = mask[y0:y1, x0:x1].astype(np.float64)
    if band.size == 0:
        return []
    h, w = band.shape
    row_sum = band.sum(axis=1)
    smooth = np.convolve(row_sum, np.ones(9) / 9, mode="same")
    med = float(np.median(smooth[smooth > 0])) if np.any(smooth > 0) else 1.0
    out: list[tuple[int, float]] = []
    for i in range(int(h * 0.12), int(h * 0.88)):
        if smooth[i] > med * 0.45:
            continue
        above = smooth[max(0, i - 50) : i - 8]
        below = smooth[i + 8 : min(h, i + 50)]
        if len(above) < 5 or len(below) < 5:
            continue
        if above.mean() < med * 0.55 or below.mean() < med * 0.55:
            continue
        toggles = float(np.sum(np.abs(np.diff((band[i] > 0).astype(np.int8)))))
        score = float(smooth[i]) - min(toggles / max(w * 0.04, 1), 4.0) * 12
        out.append((y0 + i, score))

    out.sort(key=lambda t: t[0])
    merged: list[tuple[int, float]] = []
    group: list[tuple[int, float]] = []
    for c in out:
        if not group or c[0] - group[-1][0] < 28:
            group.append(c)
        else:
            merged.append(min(group, key=lambda t: t[1]))
            group = [c]
    if group:
        merged.append(min(group, key=lambda t: t[1]))
    return merged


def best_split_y(seps: list[tuple[int, float]], y0: int, y1: int) -> int:
    mid = (y0 + y1) / 2
    if not seps:
        return int(mid)
    return min(seps, key=lambda t: abs(t[0] - mid) * 0.5 + t[1] * 2)[0]


def expand_top_to_stem(
    mask: np.ndarray,
    col_x0: int,
    col_x1: int,
    top: int,
    floor_y: int,
    ceiling_y: int,
    params: DetectParams | None = None,
) -> int:
    """상단 밴드에 번호/줄기 잉크가 약하면 위로 확장."""
    params = params or DEFAULT_PARAMS
    band_h = 28
    x0 = col_x0
    x1 = min(col_x0 + params.num_zone_w + 40, col_x1)
    top = max(ceiling_y, top)

    def density(y: int) -> float:
        y1 = min(mask.shape[0], y + band_h)
        if y1 <= y:
            return 0.0
        return float(mask[y:y1, x0:x1].mean())

    if density(top) >= 0.012:
        return top

    y = top
    best = top
    while y > ceiling_y + 2:
        y -= 4
        if density(y) >= 0.015:
            best = y
            while best > ceiling_y + 2 and density(best - 4) >= 0.01:
                best -= 4
            return max(ceiling_y, best - 6)
    return max(ceiling_y, best)


def split_n(
    seps: list[tuple[int, float]],
    y0: int,
    y1: int,
    n: int,
    starts: list[int] | None = None,
    mask: np.ndarray | None = None,
    col_x0: int = 0,
    col_x1: int = 0,
    edges: list[int] | None = None,
) -> list[tuple[int, int]]:
    """[(top, bottom), ...]. 번호 y − TOP_PAD 로 상·하단."""
    if n <= 1:
        return [(y0, y1)]

    selected = edges
    if selected is None:
        selected = select_n_starts(starts or [], y0, y1, n) if starts else None
    if n >= 3 and selected is None:
        starts = None

    first_floor = max(0, y0 - TOP_PAD)

    if selected and len(selected) >= n:
        edges_use = selected[:n]
        bounds: list[tuple[int, int]] = []
        for i, s in enumerate(edges_use):
            if i == 0:
                top = max(first_floor, s - TOP_PAD)
            else:
                top = max(bounds[-1][1] + 2, s - TOP_PAD)
            if i + 1 < len(edges_use):
                bottom = edges_use[i + 1] - TOP_PAD
            else:
                bottom = y1
            bounds.append((top, bottom))
    elif n == 2:
        # starts 1~2개라도 번호 기준으로 상단 고정 (first_floor만 쓰지 않음)
        st = list(starts or [])
        if len(st) >= 2 and st[1] - st[0] >= MIN_GAP * 0.5:
            t0 = max(first_floor, st[0] - TOP_PAD)
            b0 = st[1] - TOP_PAD
            t1 = max(b0 + 2, st[1] - TOP_PAD)
            bounds = [(t0, b0), (t1, y1)]
        elif len(st) >= 1:
            t0 = max(first_floor, st[0] - TOP_PAD)
            s = best_split_y(seps, y0, y1)
            # 번호가 하단에만 있으면 구분선 기준 유지
            if st[0] > (y0 + y1) / 2:
                prev_bottom = s - BOTTOM_PAD
                second_top = max(s - TOP_PAD, prev_bottom + 2)
                bounds = [(first_floor, prev_bottom), (second_top, y1)]
            else:
                prev_bottom = s - BOTTOM_PAD
                second_top = max(s - TOP_PAD, prev_bottom + 2, t0 + MIN_REGION_H // 2)
                bounds = [(t0, prev_bottom), (second_top, y1)]
        else:
            s = best_split_y(seps, y0, y1)
            prev_bottom = s - BOTTOM_PAD
            second_top = max(s - TOP_PAD, prev_bottom + 2)
            bounds = [(first_floor, prev_bottom), (second_top, y1)]
    else:
        ys = [c[0] for c in seps]
        best = None
        best_sc = 1e18
        for i, a in enumerate(ys):
            for b in ys[i + 1 :]:
                parts = [a - y0, b - a, y1 - b]
                if min(parts) < MIN_GAP * 0.65:
                    continue
                mean = sum(parts) / 3
                sc = sum((p - mean) ** 2 for p in parts)
                if sc < best_sc:
                    best_sc = sc
                    best = [a, b]
        if best is None:
            h = y1 - y0
            best = [y0 + h // 3, y0 + 2 * h // 3]
        a, b = best
        b0 = a - BOTTOM_PAD
        t1 = max(a - TOP_PAD, b0 + 2)
        b1 = b - BOTTOM_PAD
        t2 = max(b - TOP_PAD, b1 + 2)
        bounds = [(first_floor, b0), (t1, b1), (t2, y1)]

    refined: list[tuple[int, int]] = []
    for i, (top, bottom) in enumerate(bounds):
        ceiling = first_floor if i == 0 else refined[-1][1] + 2
        if mask is not None:
            top = expand_top_to_stem(mask, col_x0, col_x1, top, bottom, ceiling)
        if bottom - top >= MIN_REGION_H // 2:
            refined.append((int(top), int(bottom)))
    return refined


@dataclass
class ColumnPlan:
    page: int
    col: str
    x0: int
    x1: int
    y0: int
    y1: int
    seps: list
    starts: list
    upgrade_score: float
    page_image: str
    mask_ref: np.ndarray | None = None
    # 번호 개수 우선 배치
    preferred_n: int = 2
    edges: list[int] | None = None
    confidence: float = 0.0
    brackets: list[BracketPair] | None = None


def analyze_column(
    mask: np.ndarray,
    img: Image.Image,
    page: int,
    col: str,
    x0: int,
    x1: int,
    y0: int,
    y1: int,
    page_image: str,
    params: DetectParams | None = None,
    blocks: list[dict] | None = None,
    dpi: int = 200,
) -> ColumnPlan:
    params = params or DEFAULT_PARAMS
    starts = detect_question_number_starts(mask, x0, y0, y1, params)
    seps = separator_candidates(mask, x0, x1, y0, y1)
    dotted = column_dotted_seps(mask, x0, x1, y0, y1)
    # blocks 우선. OCR은 blocks 없거나(이미지 PDF) starts≥3(가짜 [N blob)일 때
    brackets: list[BracketPair] = []
    if blocks:
        brackets = detect_bracket_pairs_from_blocks(
            blocks, x0, x1, y0, y1, dpi=dpi
        )
    need_ocr = not brackets and (
        (not blocks and len(starts) >= 2)
        or len(starts) >= 3
        or (len(starts) >= 2 and starts[0] - y0 < 120)
    )
    if need_ocr:
        brackets = detect_bracket_pairs(img, x0, x1, y0, y1)
    if brackets:
        starts = filter_starts_around_brackets(starts, brackets)
    h = y1 - y0

    e3_strict = select_n_starts(starts, y0, y1, 3)
    e2 = select_n_starts(starts, y0, y1, 2)
    if e3_strict is not None:
        preferred_n, edges, confidence = 3, e3_strict, 100.0
    elif e2 is not None:
        preferred_n, edges, confidence = 2, e2, 80.0
    elif len(starts) >= 2:
        # 간격만 충족하면 상위 2개 채택
        use = [starts[0]]
        for y in starts[1:]:
            if y - use[-1] >= MIN_GAP:
                use.append(y)
            if len(use) == 2:
                break
        if len(use) == 2:
            preferred_n, edges, confidence = 2, use, 40.0
        else:
            preferred_n, edges, confidence = 2, None, 0.0
    else:
        preferred_n, edges, confidence = 2, None, 0.0

    # 대괄호 공유 + 헤더 아래 번호 2개 → n=2 (쌍), emit에서 동일 bbox 복제
    if brackets:
        y_h = min(b.y_header for b in brackets)
        after = [s for s in starts if s > y_h + 40]
        if len(after) >= 2:
            preferred_n, edges, confidence = 2, after[:2], 95.0
        elif preferred_n < 3 and len(starts) >= 3:
            e3 = pick_three_starts_loose(starts, y0, y1) or starts[:3]
            if len(e3) >= 3:
                preferred_n, edges, confidence = 3, e3[:3], 95.0

    # 레거시 score (경고·정렬용)
    score = confidence
    if e3_strict is not None and len(dotted) >= 2:
        score += 20
    elif e2 is not None and len(dotted) >= 2 and h > 2000:
        score = max(score, 55)
    if brackets:
        score += 50

    return ColumnPlan(
        page=page,
        col=col,
        x0=x0,
        x1=x1,
        y0=y0,
        y1=y1,
        seps=seps,
        starts=starts,
        upgrade_score=score,
        page_image=page_image,
        mask_ref=mask,
        preferred_n=preferred_n,
        edges=edges,
        confidence=confidence,
        brackets=brackets or None,
    )


def _assign_layout(
    plans: list[ColumnPlan], warnings: list[str]
) -> dict[tuple[int, str], tuple[int, list[int] | None]]:
    """단별 (n, edges). 검출된 3문항 단을 우선하고 합=50이 되도록 보정."""
    # 초기: 검출 결과 그대로
    assign: dict[tuple[int, str], tuple[int, list[int] | None, float]] = {}
    pages_with_3: set[int] = set()

    # 1) confidence 높은 3문항 단부터 (페이지당 최대 1)
    ranked3 = sorted(
        [p for p in plans if p.preferred_n == 3 and p.edges and len(p.edges) >= 3],
        key=lambda p: p.confidence,
        reverse=True,
    )
    for p in ranked3:
        key = (p.page, p.col)
        if p.page in pages_with_3:
            # 같은 페이지 다른 단은 2로 내림
            e2 = select_n_starts(p.starts, p.y0, p.y1, 2)
            assign[key] = (2, e2, 50.0)
            continue
        assign[key] = (3, p.edges, p.confidence)
        pages_with_3.add(p.page)

    for p in plans:
        key = (p.page, p.col)
        if key in assign:
            continue
        assign[key] = (p.preferred_n, p.edges, p.confidence)

    def total() -> int:
        return sum(v[0] for v in assign.values())

    need = MAX_QUESTION_NUM
    # 2) 부족하면 2문항 단 중 3 starts에 가까운 것 승격
    while total() < need:
        candidates = []
        for p in plans:
            key = (p.page, p.col)
            n, edges, conf = assign[key]
            if n != 2:
                continue
            if p.page in pages_with_3:
                continue
            e3 = pick_three_starts_loose(p.starts, p.y0, p.y1)
            rank = (
                100 if e3 else 0,
                len(p.starts),
                p.y1 - p.y0,
                p.upgrade_score,
            )
            candidates.append((rank, p, e3))
        if not candidates:
            break
        candidates.sort(key=lambda t: t[0], reverse=True)
        _rank, p, e3 = candidates[0]
        key = (p.page, p.col)
        if e3 is not None:
            assign[key] = (3, e3, 60.0)
            warnings.append(f"번호검출 보정 승격: p{p.page}{p.col[0]} starts={e3}")
        else:
            # 최후 수단: 구분선/균등 (경고)
            assign[key] = (3, None, 10.0)
            warnings.append(
                f"잔여 보정 승격(구분선/균등): p{p.page}{p.col[0]} "
                f"(starts={p.starts})"
            )
        pages_with_3.add(p.page)

    # 3) 과다하면 3문항 단 중 keep_score 낮은 것 강등
    while total() > need:
        threes = []
        for p in plans:
            key = (p.page, p.col)
            n, edges, conf = assign[key]
            if n == 3:
                keep = _three_keep_score(p, edges)
                threes.append((keep, conf, p))
        if not threes:
            break
        # keep 낮은 것 우선; 동점이면 뒷페이지 강등(앞쪽 균등 3단 유지)
        threes.sort(key=lambda t: (t[0], -t[2].page, t[1]))
        _keep, _conf, p = threes[0]
        key = (p.page, p.col)
        e2 = select_n_starts(p.starts, p.y0, p.y1, 2)
        assign[key] = (2, e2, 40.0)
        pages_with_3.discard(p.page)
        warnings.append(
            f"번호검출 보정 강등: p{p.page}{p.col[0]} → n=2 (keep={_keep:.1f})"
        )

    out: dict[tuple[int, str], tuple[int, list[int] | None]] = {
        k: (v[0], v[1]) for k, v in assign.items()
    }
    n3 = sorted(f"p{p}{c[0]}" for (p, c), (n, _) in out.items() if n == 3)
    warnings.append("3문항 단: " + (", ".join(n3) if n3 else "없음"))
    return out


def compute_all_bboxes_hancert(
    text_json_data: dict, root: Path | None = None
) -> tuple[list[dict], list[str]]:
    root = root or _project_root()
    pages = text_json_data["pages"]
    warnings: list[str] = []
    plans: list[ColumnPlan] = []
    round_num = parse_hancert_round(text_json_data)
    params = detect_params_for_round(round_num)
    if round_num is not None:
        warnings.append(
            f"detect_params: round={round_num} "
            f"xs0_max={params.num_xs0_max} zone_w={params.num_zone_w}"
        )

    for page in pages:
        page_num = int(page["page"])
        rel = page["page_image"]
        img_path = root / rel if not Path(rel).is_absolute() else Path(rel)
        if not img_path.exists():
            warnings.append(f"page {page_num}: 이미지 없음 {rel}")
            continue
        img = Image.open(img_path)
        mask = ink_mask(img)
        cy0, cy1 = detect_page_margins(mask, page_num)
        # gutter는 원본 마스크 (머릿말 제거 시 좌측 이동 방지)
        gutter = find_gutter_x(mask)
        work = mask.copy()
        work[:cy0, :] = False
        work[cy1:, :] = False
        w, _h = img.size
        page_blocks = page.get("blocks") or []
        plans.append(
            analyze_column(
                work,
                img,
                page_num,
                "left",
                14,
                gutter - 4,
                cy0,
                cy1,
                rel,
                params,
                blocks=page_blocks,
            )
        )
        plans.append(
            analyze_column(
                work,
                img,
                page_num,
                "right",
                gutter + 4,
                w - 14,
                cy0,
                cy1,
                rel,
                params,
                blocks=page_blocks,
            )
        )

    layout = _assign_layout(plans, warnings)

    results: list[dict] = []
    for page_num in sorted({p.page for p in plans}):
        page_plans = [p for p in plans if p.page == page_num]
        page_plans.sort(key=lambda p: 0 if p.col == "left" else 1)
        for plan in page_plans:
            n, edges = layout[(plan.page, plan.col)]
            if n == 3 and edges is None:
                warnings.append(
                    f"page {page_num} {plan.col}: 3문항 번호 y 불확실 → 구분선/균등"
                )
            if plan.brackets:
                warnings.append(
                    f"page {page_num} {plan.col}: 대괄호 "
                    + ", ".join(
                        f"[{b.n0}~{b.n1}]@y{b.y_header}" for b in plan.brackets
                    )
                )
            bounds, bnotes = emit_bounds_with_brackets(plan, n, edges)
            for note in bnotes:
                warnings.append(f"page {page_num} {plan.col}: 공유자료 {note}")
            for top, bottom in bounds:
                if bottom - top < MIN_REGION_H // 2:
                    continue
                results.append(
                    {
                        "number": 0,
                        "page": plan.page,
                        "page_image": plan.page_image,
                        "bbox": [plan.x0, int(top), plan.x1, int(bottom)],
                        "text": "",
                        "_col": plan.col,
                    }
                )
            warnings.append(
                f"page {page_num} {plan.col}: n={n} conf={plan.confidence:.0f} "
                f"starts={plan.starts} edges={edges}"
            )

    ordered: list[dict] = []
    for page_num in sorted({r["page"] for r in results}):
        left = sorted(
            [r for r in results if r["page"] == page_num and r["_col"] == "left"],
            key=lambda r: r["bbox"][1],
        )
        right = sorted(
            [r for r in results if r["page"] == page_num and r["_col"] == "right"],
            key=lambda r: r["bbox"][1],
        )
        ordered.extend(left + right)

    if len(ordered) != MAX_QUESTION_NUM:
        warnings.append(f"FATAL: 영역 수 {len(ordered)} ≠ {MAX_QUESTION_NUM}")
        # 잘못된 순번으로 PNG/CSV를 오염시키지 않도록 빈 결과 반환
        return [], warnings

    out: list[dict] = []
    for i, r in enumerate(ordered, start=1):
        out.append(
            {
                "number": i,
                "page": r["page"],
                "page_image": r["page_image"],
                "bbox": [int(x) for x in r["bbox"]],
                "text": "",
            }
        )
    return out, warnings


def should_use_hancert_crop(text_json_data: dict, profile_id: str = "") -> bool:
    if (profile_id or "").lower() == "hancert":
        return True
    pages = text_json_data.get("pages") or []
    if not pages:
        return False
    # image_only = --skip-ocr 한능검 페이지
    ocr_n = sum(1 for p in pages if p.get("source") in ("ocr", "image_only"))
    return ocr_n >= max(1, int(len(pages) * 0.5))
