#!/usr/bin/env python3
"""format_exam_year 단위 테스트."""

from __future__ import annotations

from exam_profiles import format_exam_year, is_mock_or_suneung


def test_hakpyeong_unchanged() -> None:
    assert format_exam_year("2026", exam_type="3월학평") == "2026"
    assert format_exam_year("2026", name="(2026)고3한국사(3월학평)검사지.pdf") == "2026"
    assert not is_mock_or_suneung("3월학평", "")


def test_mopyeong_dual_year() -> None:
    assert format_exam_year("2027", exam_type="6월모평") == "2026(2027)"
    assert format_exam_year("2027", exam_type="9월모평") == "2026(2027)"
    assert format_exam_year(
        "2027", name="(2027)한국사(6월모평)검사지.pdf"
    ) == "2026(2027)"


def test_suneung_dual_year() -> None:
    assert format_exam_year("2027", exam_type="수능") == "2026(2027)"
    assert format_exam_year("2027", name="(2027)한국사(수능)검사지.pdf") == "2026(2027)"


def test_idempotent() -> None:
    assert format_exam_year("2026(2027)", exam_type="6월모평") == "2026(2027)"


def test_basic_unchanged() -> None:
    assert format_exam_year("2024", exam_type="가형") == "2024"


if __name__ == "__main__":
    test_hakpyeong_unchanged()
    test_mopyeong_dual_year()
    test_suneung_dual_year()
    test_idempotent()
    test_basic_unchanged()
    print("ok")
