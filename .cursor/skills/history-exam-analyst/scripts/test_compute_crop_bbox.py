#!/usr/bin/env python3
"""compute_crop_bbox 회귀 테스트."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from compute_crop_bbox import compute_all_bboxes

ROOT = Path(__file__).resolve().parents[4]


def _load(stem: str) -> list[dict]:
    path = ROOT / "output" / "work" / stem / "text.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    results, _ = compute_all_bboxes(data)
    return results


def test_na_q2_q3():
    results = _load("(2024)고1역사2(나형)검사지")
    by_num = {r["number"]: r for r in results}

    q2 = by_num[2]
    assert "2. 다음" in q2["text"]
    assert all(c in q2["text"] for c in "①②③④⑤")

    q3 = by_num[3]
    assert "3. 다음 학생들" in q3["text"]
    assert "소도라는 신성 지역이 존재" not in q3["text"].split("\n")[0] or "다음 학생들" in q3["text"]
    assert q2["bbox"][3] < q3["bbox"][1] or q3["bbox"][1] < q2["bbox"][1]


def test_ga_q20_image_option():
    results = _load("(2024)고1역사2(가형)검사지")
    q20 = {r["number"]: r for r in results}[20]
    assert "20. 다음" in q20["text"]
    assert "< 정약용>" in q20["text"]
    assert q20["bbox"][3] >= 2700


def test_g2_ga_q3_present():
    results = _load("(2024)고2한국사(가형)검사지")
    assert len(results) == 30
    q3 = {r["number"]: r for r in results}[3]
    assert "3. 다음 (가)" in q3["text"]


def test_all_2024_pdfs_have_30_questions():
    stems = [
        "(2024)고1역사2(나형)검사지",
        "(2024)고1역사2(가형)검사지",
        "(2024)고2한국사(나형)검사지",
        "(2024)고2한국사(가형)검사지",
    ]
    for stem in stems:
        results = _load(stem)
        nums = sorted(r["number"] for r in results)
        assert len(results) == 30, f"{stem}: got {len(results)}"
        assert nums == list(range(1, 31)), f"{stem}: missing {set(range(1,31)) - set(nums)}"


def main() -> int:
    test_na_q2_q3()
    test_ga_q20_image_option()
    test_g2_ga_q3_present()
    test_all_2024_pdfs_have_30_questions()
    print("test_compute_crop_bbox: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
