#!/usr/bin/env python3
"""내용분류표 성취기준 코드를 CSV 형식으로 정규화합니다.

출력 형식: 대괄호 없음 (예: 9역07-01, 10한사1-01-01)
"""

from __future__ import annotations

import re

C01_PATTERN = re.compile(r"10한사([12])-(\d{2})-(\d{2})")
G2_PATTERN = re.compile(r"10한사(\d{2})-(\d{2})")
MIDDLE_PATTERN = re.compile(r"9역(\d{2})-(\d{2})")


LEGACY_CODE_MAP: dict[str, str] = {
    # 레거시 축약 → canonical (대괄호 없음)
    "101-01-01": "10한사1-01-01",
    "101-01-02": "10한사1-01-02",
    "101-01-03": "10한사1-01-03",
    "101-01-04": "10한사1-01-04",
    "101-01-05": "10한사1-01-05",
    "101-01-06": "10한사1-01-06",
    "101-02-01": "10한사1-02-01",
    "101-02-02": "10한사1-02-02",
    "101-02-03": "10한사1-02-03",
    "101-02-04": "10한사1-02-04",
    "101-02-05": "10한사1-02-05",
    "101-02-06": "10한사1-02-06",
    "101-03-01": "10한사1-03-01",
    "101-03-02": "10한사1-03-02",
    "101-03-03": "10한사1-03-03",
    "101-03-04": "10한사1-03-04",
    "101-03-05": "10한사1-03-05",
    "101-03-06": "10한사1-03-06",
    "101-04-01": "10한사1-04-01",
    "101-04-02": "10한사1-04-02",
    "101-04-03": "10한사1-04-03",
    "101-04-04": "10한사1-04-04",
    "101-04-05": "10한사1-04-05",
    "101-04-06": "10한사1-04-06",
    "102-01-01": "10한사2-01-01",
    "102-01-02": "10한사2-01-02",
    "102-01-03": "10한사2-01-03",
    "102-01-04": "10한사2-01-04",
    "102-01-05": "10한사2-01-05",
    "102-01-06": "10한사2-01-06",
    "102-02-01": "10한사2-02-01",
    "102-02-02": "10한사2-02-02",
    "102-02-03": "10한사2-02-03",
    "102-02-04": "10한사2-02-04",
    "102-02-05": "10한사2-02-05",
    "102-02-06": "10한사2-02-06",
    "102-03-01": "10한사2-03-01",
    "102-03-02": "10한사2-03-02",
    "102-03-03": "10한사2-03-03",
    "102-03-04": "10한사2-03-04",
    "102-03-05": "10한사2-03-05",
    "102-03-06": "10한사2-03-06",
}

CANONICAL_HIGH_PATTERN = re.compile(r"^10한사[12]-\d{2}-\d{2}$")
CANONICAL_MIDDLE_PATTERN = re.compile(r"^9역\d{2}-\d{2}$")
LEGACY_COMPRESSED_PATTERN = re.compile(r"^(101|102)-(\d{2})-(\d{2})$")


def strip_code_brackets(raw: str) -> str:
    s = raw.strip().replace(" ", "")
    if s.startswith("[") and s.endswith("]") and len(s) >= 2:
        return s[1:-1]
    return s


def normalize_class_code(raw: str) -> str | None:
    raw = strip_code_brackets(raw)
    if not raw:
        return None

    if CANONICAL_MIDDLE_PATTERN.fullmatch(raw):
        return raw
    if CANONICAL_HIGH_PATTERN.fullmatch(raw):
        return raw
    if raw in LEGACY_CODE_MAP:
        return LEGACY_CODE_MAP[raw]

    m = LEGACY_COMPRESSED_PATTERN.fullmatch(raw)
    if m:
        group, mid, sub = m.group(1), m.group(2), m.group(3)
        course = "1" if group == "101" else "2"
        return f"10한사{course}-{mid}-{sub}"

    m = MIDDLE_PATTERN.fullmatch(raw) or MIDDLE_PATTERN.match(raw)
    if m:
        return f"9역{m.group(1)}-{m.group(2)}"

    m = C01_PATTERN.fullmatch(raw) or C01_PATTERN.match(raw)
    if m:
        return f"10한사{m.group(1)}-{m.group(2)}-{m.group(3)}"

    m = G2_PATTERN.fullmatch(raw) or G2_PATTERN.match(raw)
    if m:
        unit, sub = m.group(1), m.group(2)
        unit_int = int(unit)
        course = "1" if unit_int <= 2 else "2"
        mid = unit if unit_int <= 2 else f"{unit_int - 2:02d}"
        return f"10한사{course}-{mid}-{sub}"

    return None


def answer_label_to_number(label: str) -> str:
    mapping = {"①": "1", "②": "2", "③": "3", "④": "4", "⑤": "5"}
    for ch, num in mapping.items():
        if ch in label:
            return num
    m = re.search(r"[1-5]", label)
    return m.group(0) if m else ""


def number_to_answer_label(num: str) -> str:
    mapping = {"1": "①", "2": "②", "3": "③", "4": "④", "5": "⑤"}
    return mapping.get(str(num).strip(), "")
