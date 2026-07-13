#!/usr/bin/env python3
"""Google Drive 문항 이미지 해석·캐시.

로컬 파일이 있으면 그대로 쓰고, 없으면 Drive(images 루트)에서
동일한 상대경로로 찾아 캐시 디렉터리에 받은 뒤 경로를 반환한다.

Secrets / 환경변수:
  GDRIVE_FOLDER_ID              — images 루트 폴더 ID
  GDRIVE_SERVICE_ACCOUNT_JSON   — 서비스 계정 JSON 문자열
  COMPOSE_CACHE_DIR             — 캐시 디렉터리 (기본: <root>/.cache/drive_images)
  COMPOSE_DATA_ROOT             — 데이터 루트 (compose_app에서 사용)
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


def _secret_or_env(key: str, default: str = "") -> str:
    try:
        import streamlit as st

        if hasattr(st, "secrets") and key in st.secrets:
            val = st.secrets[key]
            if isinstance(val, dict):
                return json.dumps(val, ensure_ascii=False)
            return str(val)
    except Exception:
        pass
    return os.environ.get(key, default)


def drive_configured() -> bool:
    return bool(_secret_or_env("GDRIVE_FOLDER_ID").strip()) and bool(
        _secret_or_env("GDRIVE_SERVICE_ACCOUNT_JSON").strip()
    )


def cache_dir(root: Path) -> Path:
    override = _secret_or_env("COMPOSE_CACHE_DIR").strip()
    if override:
        path = Path(override)
    else:
        path = root / ".cache" / "drive_images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _normalize_rel(rel_path: str) -> str:
    return str(rel_path or "").replace("\\", "/").lstrip("/")


def _sa_info() -> dict[str, Any]:
    raw = _secret_or_env("GDRIVE_SERVICE_ACCOUNT_JSON").strip()
    if not raw:
        raise RuntimeError("GDRIVE_SERVICE_ACCOUNT_JSON 이 없습니다.")
    if raw.startswith("{"):
        return json.loads(raw)
    # 파일 경로로도 허용
    p = Path(raw)
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    raise RuntimeError("GDRIVE_SERVICE_ACCOUNT_JSON 형식이 올바르지 않습니다.")


@lru_cache(maxsize=1)
def _drive_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    info = _sa_info()
    creds = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _list_children(parent_id: str, name: str) -> str | None:
    """부모 폴더에서 이름 일치 파일/폴더 ID (trashed 제외)."""
    service = _drive_service()
    # Drive API: name = 'x' and 'parent' in parents
    safe = name.replace("\\", "\\\\").replace("'", "\\'")
    q = (
        f"name = '{safe}' and '{parent_id}' in parents and trashed = false"
    )
    resp = (
        service.files()
        .list(
            q=q,
            spaces="drive",
            fields="files(id, name, mimeType)",
            pageSize=10,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    files = resp.get("files") or []
    if not files:
        return None
    return files[0]["id"]


@lru_cache(maxsize=512)
def _resolve_drive_file_id(rel_path: str) -> str | None:
    """output/images/basic/foo.png → Drive file id (images 루트 기준)."""
    folder_id = _secret_or_env("GDRIVE_FOLDER_ID").strip()
    if not folder_id:
        return None
    rel = _normalize_rel(rel_path)
    # CSV 경로는 output/images/... 형태. Drive 루트가 images 이면 접두 제거
    for prefix in ("output/images/", "images/"):
        if rel.startswith(prefix):
            rel = rel[len(prefix) :]
            break
    parts = [p for p in rel.split("/") if p]
    if not parts:
        return None
    parent = folder_id
    for i, part in enumerate(parts):
        found = _list_children(parent, part)
        if not found:
            return None
        if i == len(parts) - 1:
            return found
        parent = found
    return None


def _download_file(file_id: str, dest: Path) -> Path:
    from googleapiclient.http import MediaIoBaseDownload
    import io

    dest.parent.mkdir(parents=True, exist_ok=True)
    service = _drive_service()
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    dest.write_bytes(buf.getvalue())
    return dest


def resolve_image(root: Path, rel_path: str) -> Path | None:
    """로컬 우선, 없으면 Drive → 캐시. 실패 시 None."""
    rel = _normalize_rel(rel_path)
    if not rel:
        return None
    local = root / rel
    if local.is_file():
        return local

    if not drive_configured():
        return None

    cached = cache_dir(root) / rel
    if cached.is_file():
        return cached

    try:
        file_id = _resolve_drive_file_id(rel)
        if not file_id:
            return None
        return _download_file(file_id, cached)
    except Exception:
        return None


def image_available(root: Path, rel_path: str, *, probe_drive: bool = False) -> bool:
    """존재 여부. probe_drive=False 이면 로컬/캐시만(목록용, API 폭주 방지)."""
    rel = _normalize_rel(rel_path)
    if not rel:
        return False
    if (root / rel).is_file():
        return True
    if (cache_dir(root) / rel).is_file():
        return True
    if not probe_drive:
        # Drive 설정 시 CSV 경로가 있으면 '있을 수 있음'으로 표시 → 필터에서 통과
        return drive_configured() and bool(rel)
    return resolve_image(root, rel) is not None
