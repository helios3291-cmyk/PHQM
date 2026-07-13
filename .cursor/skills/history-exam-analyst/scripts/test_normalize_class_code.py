#!/usr/bin/env python3
"""normalize_class_code 회귀 테스트."""

from __future__ import annotations

from normalize_class_code import normalize_class_code, strip_code_brackets


def test_high_from_table() -> None:
    assert normalize_class_code("10한사01-01") == "10한사1-01-01"
    assert normalize_class_code("10한사02-04") == "10한사1-02-04"
    assert normalize_class_code("10한사03-04") == "10한사2-01-04"
    assert normalize_class_code("10한사04-01") == "10한사2-02-01"


def test_canonical() -> None:
    assert normalize_class_code("10한사1-01-01") == "10한사1-01-01"
    assert normalize_class_code("10한사2-03-02") == "10한사2-03-02"
    assert normalize_class_code("[10한사1-01-01]") == "10한사1-01-01"


def test_legacy() -> None:
    assert normalize_class_code("[101-01-01]") == "10한사1-01-01"
    assert normalize_class_code("101-01-01") == "10한사1-01-01"
    assert normalize_class_code("[102-01-04]") == "10한사2-01-04"


def test_middle() -> None:
    assert normalize_class_code("9역07-01") == "9역07-01"
    assert normalize_class_code("[9역07-01]") == "9역07-01"


def test_strip() -> None:
    assert strip_code_brackets("[9역07-01]") == "9역07-01"
    assert strip_code_brackets("9역07-01") == "9역07-01"


if __name__ == "__main__":
    test_high_from_table()
    test_canonical()
    test_legacy()
    test_middle()
    test_strip()
    print("test_normalize_class_code: OK")
