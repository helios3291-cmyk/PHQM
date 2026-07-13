#!/usr/bin/env python3
"""한능검 크롭 PNG 상·하단 밴드 자동 점검.

- missing_top_number: 상단 밴드 왼쪽 번호 레인에 잉크가 거의 없음
- next_number_bleed: 하단 밴드에 짧은 굵은 blob(다음 문항번호 의심)이 있음
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from compute_hancert_crop_bbox import _project_root, ink_mask

BOTTOM_BAND = 48
NUM_LANE_W = 200


def _score_top(mask: np.ndarray) -> float:
    """상단·번호 레인 밀도. 번호가 약간 아래에서 시작해도 잡히게 80px까지 본다."""
    h, w = mask.shape
    band = mask[: min(80, h), : min(NUM_LANE_W, w)]
    return float(band.mean()) if band.size else 0.0


def _bottom_numberish(mask: np.ndarray) -> bool:
    """하단 왼쪽 레인에 번호 크기 blob이 있으면 True."""
    h, w = mask.shape
    y0 = max(0, h - BOTTOM_BAND)
    band = mask[y0:h, : min(NUM_LANE_W, w)]
    if band.size == 0:
        return False
    row = band.sum(axis=1).astype(np.float64)
    i = 0
    while i < len(row):
        if row[i] < 3:
            i += 1
            continue
        j = i
        while j < len(row) and row[j] >= 3:
            j += 1
        height = j - i
        chunk = band[i:j]
        width = int(chunk.any(axis=0).sum())
        if 14 <= height <= 42 and 8 <= width <= 70:
            xs = np.where(chunk.any(axis=0))[0]
            if len(xs) and int(xs[0]) <= 145:
                dens = float(chunk.mean())
                if dens >= 0.10:
                    return True
        i = max(j, i + 1)
    return False


def audit_image(path: Path) -> dict:
    img = Image.open(path)
    mask = ink_mask(img)
    top = _score_top(mask)
    bleed = _bottom_numberish(mask)
    flags: list[str] = []
    if top < 0.006:
        flags.append("missing_top_number")
    if bleed:
        flags.append("next_number_bleed")
    return {
        "path": path.as_posix(),
        "top_density": round(top, 4),
        "flags": flags,
    }


def parse_name(stem: str) -> dict:
    m = re.match(
        r"(?P<year>\d{4})_공통_한국사_(?P<exam>.+)_(?P<num>\d+)$",
        stem,
    )
    if not m:
        return {"year": "", "exam": "", "number": 0}
    return {
        "year": m.group("year"),
        "exam": m.group("exam"),
        "number": int(m.group("num")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="한능검 크롭 상·하단 audit")
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="크롭 PNG 디렉터리 (기본 output/images/hancert)",
    )
    parser.add_argument(
        "--exam",
        type=str,
        default=None,
        help="문형 필터 예: 78회심화",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="결과 JSON (기본 output/work/hancert_crop_audit.json)",
    )
    args = parser.parse_args()
    root = _project_root()
    img_dir = args.dir or (root / "output" / "images" / "hancert")
    out_path = args.out or (root / "output" / "work" / "hancert_crop_audit.json")

    paths = sorted(img_dir.glob("*.png"))
    if args.exam:
        paths = [p for p in paths if args.exam in p.stem]

    failures: list[dict] = []
    ok = 0
    for path in paths:
        meta = parse_name(path.stem)
        result = audit_image(path)
        result.update(meta)
        if result["flags"]:
            failures.append(result)
        else:
            ok += 1

    summary = {
        "total": len(paths),
        "ok": ok,
        "fail": len(failures),
        "by_flag": {},
        "failures": failures,
    }
    for f in failures:
        for flag in f["flags"]:
            summary["by_flag"][flag] = summary["by_flag"].get(flag, 0) + 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"audit: total={summary['total']} ok={summary['ok']} fail={summary['fail']} "
        f"flags={summary['by_flag']}"
    )
    print(f"저장: {out_path.relative_to(root)}")
    return 0 if summary["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
