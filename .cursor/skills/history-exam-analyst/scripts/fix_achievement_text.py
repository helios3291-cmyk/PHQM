#!/usr/bin/env python3
"""성취기준 원문 띄어쓰기 보정 및 override 적용."""

from __future__ import annotations

import json
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _overrides_path(root: Path) -> Path:
    return root / "성취기준" / "reference" / "achievement_text_overrides.json"


def load_overrides(root: Path) -> dict[str, str]:
    path = _overrides_path(root)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if str(k).strip() and str(v).strip()}


def _space_with_kiwi(text: str) -> str:
    from kiwipiepy import Kiwi

    kiwi = Kiwi()
    return kiwi.space(text, reset_whitespace=True)


def fix_achievement_text(code: str, text: str, *, root: Path | None = None) -> str:
    """성취기준 텍스트를 사람이 읽기 좋게 보정합니다.

    우선순위: override(code) > kiwipiepy 자동 띄어쓰기 > 원문(text)
    """
    root = root or project_root()
    overrides = load_overrides(root)

    bare = code.strip()
    if bare.startswith("[") and bare.endswith("]") and len(bare) >= 2:
        bare = bare[1:-1]
    override = overrides.get(code) or overrides.get(bare) or overrides.get(f"[{bare}]")
    if override:
        return override.strip()

    try:
        fixed = _space_with_kiwi(text)
    except Exception:
        fixed = text

    return fixed.strip()

