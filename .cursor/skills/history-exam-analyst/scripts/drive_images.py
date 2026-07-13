"""Shim — 구현은 저장소 루트 lib/drive_images.py (Streamlit Cloud용)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_LIB_FILE = Path(__file__).resolve().parents[4] / "lib" / "drive_images.py"
if not _LIB_FILE.is_file():
    raise ImportError(f"lib/drive_images.py 없음: {_LIB_FILE}")

_spec = importlib.util.spec_from_file_location("phqm_lib_drive_images", _LIB_FILE)
if _spec is None or _spec.loader is None:
    raise ImportError(f"drive_images 로드 실패: {_LIB_FILE}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["phqm_lib_drive_images"] = _mod
_spec.loader.exec_module(_mod)

# re-export public API
cache_dir = _mod.cache_dir
diagnose = _mod.diagnose
drive_configured = _mod.drive_configured
get_last_error = _mod.get_last_error
image_available = _mod.image_available
list_root_children = _mod.list_root_children
resolve_image = _mod.resolve_image

__all__ = [
    "cache_dir",
    "diagnose",
    "drive_configured",
    "get_last_error",
    "image_available",
    "list_root_children",
    "resolve_image",
]
