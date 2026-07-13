#!/usr/bin/env python3
"""한능검 크롭 bbox 회귀 테스트."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from compute_hancert_crop_bbox import (  # noqa: E402
    DEFAULT_PARAMS,
    LEGACY_PARAMS,
    compute_all_bboxes_hancert,
    detect_params_for_round,
    parse_hancert_round,
    should_use_hancert_crop,
)


def _text_json(round_hint: str) -> Path:
    """round_hint 예: '78회', '62회' — 심화 text.json 우선."""
    work = ROOT / "output" / "work"
    prefer = []
    fallback = []
    for d in work.iterdir():
        if not d.is_dir() or round_hint not in d.name:
            continue
        tj = d / "text.json"
        if not tj.exists():
            continue
        if "심화" in d.name:
            prefer.append(tj)
        else:
            fallback.append(tj)
    if prefer:
        return prefer[0]
    if fallback:
        return fallback[0]
    raise FileNotFoundError(f"{round_hint} text.json 없음")


def _load(hint: str) -> tuple[dict, list[dict], list[str]]:
    path = _text_json(hint)
    data = json.loads(path.read_text(encoding="utf-8"))
    results, warnings = compute_all_bboxes_hancert(data, ROOT)
    return data, results, warnings


def test_detect_params_round() -> None:
    assert detect_params_for_round(60) == LEGACY_PARAMS
    assert detect_params_for_round(68) == LEGACY_PARAMS
    assert detect_params_for_round(69) == DEFAULT_PARAMS
    assert detect_params_for_round(78) == DEFAULT_PARAMS
    assert detect_params_for_round(None) == DEFAULT_PARAMS


def test_hancert_78() -> None:
    data, results, warnings = _load("78회")
    assert should_use_hancert_crop(data, "hancert")
    assert parse_hancert_round(data) == 78
    assert len(results) == 50
    join = " ".join(warnings)
    assert "xs0_max=145" in join

    per_page = Counter(r["page"] for r in results)
    assert per_page[6] == 5
    assert per_page[8] == 5
    for p in range(1, 13):
        if p in (6, 8):
            continue
        assert per_page[p] == 4, f"page{p} got {per_page[p]}"

    assert "p6l" in join and "p8r" in join
    q32 = next(r for r in results if r["number"] == 32)
    q31 = next(r for r in results if r["number"] == 31)
    assert q32["bbox"][1] < 250
    assert q31["bbox"][1] <= 1525 - 20
    print("test_hancert_78: OK")


def test_hancert_60_legacy() -> None:
    data, results, warnings = _load("60회")
    assert parse_hancert_round(data) == 60
    assert len(results) == 50
    assert "xs0_max=190" in " ".join(warnings)
    q9 = next(x for x in results if x["number"] == 9)
    assert q9["bbox"][1] < 280, q9["bbox"]
    assert q9["page"] == 3
    print("test_hancert_60_legacy: OK")


def test_hancert_62_no_shift() -> None:
    _data, results, warnings = _load("62회")
    assert len(results) == 50
    join = " ".join(warnings)
    assert "강등: p4r" not in join, warnings
    q16 = next(r for r in results if r["number"] == 16)
    q17 = next(r for r in results if r["number"] == 17)
    assert q16["page"] == 4
    assert q17["page"] == 4
    assert q16["bbox"][3] <= q17["bbox"][1] + 2
    assert q16["bbox"][3] - q16["bbox"][1] < 1500
    print("test_hancert_62_no_shift: OK")


def test_hancert_63_q7_present() -> None:
    _data, results, warnings = _load("63회")
    assert len(results) == 50
    q7 = next(r for r in results if r["number"] == 7)
    assert q7["page"] == 2
    assert q7["bbox"][1] < 320, q7["bbox"]
    join = " ".join(w for w in warnings if "page 2 right" in w)
    assert any(s in join for s in ("289", "290", "291", "288")), warnings
    print("test_hancert_63_q7_present: OK")


def test_hancert_61_q13_14_split() -> None:
    """일반 문항 13·14는 합쳐지지 않음 (공유자료 아님)."""
    _data, results, warnings = _load("61회")
    assert len(results) == 50
    q13 = next(r for r in results if r["number"] == 13)
    q14 = next(r for r in results if r["number"] == 14)
    assert q13["bbox"] != q14["bbox"]
    # 같은 단이면 분리, 아니면 페이지가 갈라져도 OK
    if q13["page"] == q14["page"] and q13["bbox"][0] == q14["bbox"][0]:
        assert q13["bbox"][3] <= q14["bbox"][1] + 2
    assert q13["bbox"][3] - q13["bbox"][1] < 1400, q13["bbox"]
    assert "강등: p3r" not in " ".join(warnings), warnings
    print("test_hancert_61_q13_14_split: OK")


def test_hancert_61_bracket_shared() -> None:
    """[29~30] 대괄호 공유자료 → 동일 bbox; 상단에 헤더 포함."""
    _data, results, warnings = _load("61회")
    join = " ".join(warnings)
    assert "대괄호" in join and "29" in join and "30" in join, warnings
    q28 = next(r for r in results if r["number"] == 28)
    q29 = next(r for r in results if r["number"] == 29)
    q30 = next(r for r in results if r["number"] == 30)
    assert q29["bbox"] == q30["bbox"], (q29["bbox"], q30["bbox"])
    assert q29["bbox"][1] < 320, q29["bbox"]  # OCR y 이중가산 없이 헤더 포함
    assert q29["bbox"][3] - q29["bbox"][1] > 800
    same_col = (
        q28["page"] == q29["page"] and q28["bbox"][0] == q29["bbox"][0]
    )
    if same_col:
        assert q28["bbox"][3] <= q29["bbox"][1] + 2, (q28["bbox"], q29["bbox"])
    print("test_hancert_61_bracket_shared: OK")


def test_hancert_62_bracket_4950() -> None:
    """[49~50] 공유자료 — OCR 틸드 누락/blocks 보강으로 동일 bbox."""
    _data, results, warnings = _load("62회")
    join = " ".join(warnings)
    assert "대괄호" in join and "49" in join and "50" in join, warnings
    q49 = next(r for r in results if r["number"] == 49)
    q50 = next(r for r in results if r["number"] == 50)
    assert q49["bbox"] == q50["bbox"], (q49["bbox"], q50["bbox"])
    assert q49["bbox"][1] < 350, q49["bbox"]
    assert q49["bbox"][3] - q49["bbox"][1] > 1500
    print("test_hancert_62_bracket_4950: OK")


def test_hancert_64_option_noise() -> None:
    _data, results, warnings = _load("64회")
    assert len(results) == 50
    join = " ".join(w for w in warnings if "page 7 right" in w)
    assert "1112, 1167" not in join, warnings
    q28 = next(r for r in results if r["number"] == 28)
    assert q28["bbox"][3] - q28["bbox"][1] > 500, q28["bbox"]
    print("test_hancert_64_option_noise: OK")


if __name__ == "__main__":
    test_detect_params_round()
    test_hancert_78()
    test_hancert_60_legacy()
    test_hancert_62_no_shift()
    test_hancert_63_q7_present()
    test_hancert_61_q13_14_split()
    test_hancert_61_bracket_shared()
    test_hancert_62_bracket_4950()
    test_hancert_64_option_noise()
    print("test_hancert_crop_bbox: OK")
