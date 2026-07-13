#!/usr/bin/env python3
"""fix_achievement_text 회귀 테스트."""

from __future__ import annotations

import sys

from fix_achievement_text import fix_achievement_text


def test_override_wins():
    text = fix_achievement_text(
        "[10한사1-01-01]",
        "고대국가의형성과 성장과정을파악한 다.",
    )
    assert text == "고대 국가의 형성과 성장 과정을 파악한다."


def test_fallback_does_not_crash():
    text = fix_achievement_text(
        "[10한사9-99-99]",
        "일제의식민통치로 인한사회및문화의 변화와 대중운동의 양상을파악한다.",
    )
    assert isinstance(text, str) and text.strip()


def main() -> int:
    test_override_wins()
    test_fallback_does_not_crash()
    print("test_achievement_text: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

