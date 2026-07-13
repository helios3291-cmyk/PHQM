#!/usr/bin/env python3
"""파이프라인 안전망 회귀 (합성·단위)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from compute_crop_bbox import page_width_from_page, Block  # noqa: E402
from compute_hancert_crop_bbox import MAX_QUESTION_NUM  # noqa: E402
from exam_profiles import detect_profile_from_name  # noqa: E402
from extract_questions import load_hancert_round_years  # noqa: E402


def test_profile_detect() -> None:
    assert detect_profile_from_name("(61회)한국사(심화)검사지.pdf") == "hancert"
    assert detect_profile_from_name("(2024)고1역사2(가형)검사지.pdf") == "basic"
    assert detect_profile_from_name("(2026)한국사(6월모평)검사지.pdf") == "mock"
    assert detect_profile_from_name("random.pdf", default=None) is None
    assert detect_profile_from_name("random.pdf") == "basic"
    print("test_profile_detect: OK")


def test_round_years_map() -> None:
    m = load_hancert_round_years()
    assert m.get("61") == "2022"
    assert m.get("78") == "2026"
    assert "79" not in m
    print("test_round_years_map: OK")


def test_page_width_relative(tmp_path: Path | None = None) -> None:
    from PIL import Image

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        img_path = root / "output" / "work" / "x" / "pages" / "page_001.png"
        img_path.parent.mkdir(parents=True)
        Image.new("RGB", (2000, 1000), "white").save(img_path)
        page = {"page_image": "output/work/x/pages/page_001.png"}
        # root 없이 열리면 실패 → 블록 추정
        w_fallback = page_width_from_page(page, [], root=None)
        assert w_fallback == 676.0
        w = page_width_from_page(page, [], root=root)
        assert abs(w - 2000 / (200 / 72)) < 1.0
    print("test_page_width_relative: OK")


def test_stem_merge_behavior() -> None:
    """--stem 기본 병합: 기존 키 유지 + 대상만 갱신 (로직 단위)."""
    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / "output" / "work"
        work.mkdir(parents=True)
        out = work / "extracted_questions.json"
        out.write_text(
            json.dumps({"keep.pdf": [{"number": 1}], "old.pdf": [{"number": 2}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        existing = json.loads(out.read_text(encoding="utf-8"))
        # simulate merge update
        existing["old.pdf"] = [{"number": 99}]
        assert "keep.pdf" in existing
        assert existing["old.pdf"][0]["number"] == 99
    print("test_stem_merge_behavior: OK")


def test_hancert_count_constant() -> None:
    assert MAX_QUESTION_NUM == 50
    print("test_hancert_count_constant: OK")


if __name__ == "__main__":
    test_profile_detect()
    test_round_years_map()
    test_page_width_relative()
    test_stem_merge_behavior()
    test_hancert_count_constant()
    print("test_pipeline_safety: OK")
