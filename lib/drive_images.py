#!/usr/bin/env python3
"""Google Drive 문항 이미지 해석·캐시.

로컬 파일이 있으면 그대로 쓰고, 없으면 Drive(images 루트)에서
동일한 상대경로로 찾아 캐시 디렉터리에 받은 뒤 경로를 반환한다.

Secrets / 환경변수:
  GDRIVE_FOLDER_ID              — images 루트 폴더 ID
  GDRIVE_SERVICE_ACCOUNT_JSON   — 서비스 계정 JSON 문자열 또는 TOML 테이블
  COMPOSE_CACHE_DIR             — 캐시 디렉터리 (Cloud 기본: /tmp/phqm_drive_images)
  COMPOSE_DATA_ROOT             — 데이터 루트 (compose_app에서 사용)
"""

from __future__ import annotations

import json
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

# 최근 실패 원인 (UI 진단용)
_LAST_ERROR: str = ""


def get_last_error() -> str:
    return _LAST_ERROR


def _set_error(msg: str) -> None:
    global _LAST_ERROR
    _LAST_ERROR = msg


def _secret_raw(key: str) -> Any:
    """Streamlit secrets 또는 환경변수. 값은 str / Mapping 가능."""
    try:
        import streamlit as st

        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, "")


def _secret_or_env(key: str, default: str = "") -> str:
    val = _secret_raw(key)
    if val is None or val == "":
        return default
    if isinstance(val, dict):
        return json.dumps(dict(val), ensure_ascii=False)
    return str(val)


def drive_configured() -> bool:
    return bool(_secret_or_env("GDRIVE_FOLDER_ID").strip()) and bool(
        _secret_or_env("GDRIVE_SERVICE_ACCOUNT_JSON").strip()
    )


def cache_dir(root: Path) -> Path:
    """Streamlit Cloud는 앱 루트가 읽기전용 → /tmp 우선."""
    override = _secret_or_env("COMPOSE_CACHE_DIR").strip()
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override))
    candidates.append(Path(tempfile.gettempdir()) / "phqm_drive_images")
    candidates.append(Path("/tmp") / "phqm_drive_images")
    candidates.append(root / ".cache" / "drive_images")

    last_exc: Exception | None = None
    for path in candidates:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return path
        except Exception as exc:
            last_exc = exc
            continue
    raise RuntimeError(f"캐시 디렉터리를 만들 수 없습니다: {last_exc}")


def _normalize_rel(rel_path: str) -> str:
    return str(rel_path or "").replace("\\", "/").lstrip("/")


def _sa_info() -> dict[str, Any]:
    """서비스 계정 정보. Secrets에 문자열·TOML 테이블 모두 허용.

    Cloud에서 private_key에 실제 개행이 들어가면 JSONDecodeError(Invalid control
    character)가 나므로 strict=False + 키 정규화를 한다.
    """
    raw = _secret_raw("GDRIVE_SERVICE_ACCOUNT_JSON")
    if raw is None or raw == "":
        raise RuntimeError("GDRIVE_SERVICE_ACCOUNT_JSON 이 없습니다.")

    info: dict[str, Any]
    if isinstance(raw, dict):
        info = {str(k): v for k, v in dict(raw).items()}
    else:
        text = str(raw).lstrip("\ufeff").strip()
        if text.startswith("{"):
            # Secrets 붙여넣기 시 private_key 안 실제 개행 허용
            try:
                info = json.loads(text, strict=False)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    "GDRIVE_SERVICE_ACCOUNT_JSON 파싱 실패. "
                    "다운로드한 JSON을 그대로 붙이거나, TOML 테이블로 넣으세요. "
                    f"({exc})"
                ) from exc
        else:
            p = Path(text)
            if p.is_file():
                info = json.loads(p.read_text(encoding="utf-8"), strict=False)
            else:
                raise RuntimeError(
                    "GDRIVE_SERVICE_ACCOUNT_JSON 이 JSON 객체가 아닙니다. "
                    "Streamlit Secrets에 JSON 전체(또는 TOML 테이블)로 넣으세요."
                )

    pk = info.get("private_key")
    if isinstance(pk, str) and "\\n" in pk:
        info["private_key"] = pk.replace("\\n", "\n")
    return info


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
    safe = name.replace("\\", "\\\\").replace("'", "\\'")
    q = f"name = '{safe}' and '{parent_id}' in parents and trashed = false"
    resp = (
        service.files()
        .list(
            q=q,
            spaces="drive",
            fields="files(id, name, mimeType)",
            pageSize=10,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            corpora="allDrives",
        )
        .execute()
    )
    files = resp.get("files") or []
    if not files:
        resp = (
            service.files()
            .list(
                q=q,
                spaces="drive",
                fields="files(id, name, mimeType)",
                pageSize=10,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora="user",
            )
            .execute()
        )
        files = resp.get("files") or []
    if not files:
        return None
    return files[0]["id"]


def _path_variants(rel_path: str) -> list[str]:
    """Drive 폴더 구조 차이(루트=images vs 루트에 output/images)를 흡수."""
    rel = _normalize_rel(rel_path)
    variants: list[str] = []

    def add(p: str) -> None:
        p = _normalize_rel(p)
        if p and p not in variants:
            variants.append(p)

    add(rel)
    stripped = rel
    for prefix in ("output/images/", "images/"):
        if stripped.startswith(prefix):
            stripped = stripped[len(prefix) :]
            break
    add(stripped)
    add("output/images/" + stripped)
    add("images/" + stripped)
    return variants


def _walk_to_file_id(folder_id: str, parts: list[str]) -> str | None:
    parent = folder_id
    for i, part in enumerate(parts):
        found = _list_children(parent, part)
        if not found:
            return None
        if i == len(parts) - 1:
            return found
        parent = found
    return None


@lru_cache(maxsize=512)
def _resolve_drive_file_id(rel_path: str) -> str | None:
    """output/images/basic/foo.png → Drive file id."""
    folder_id = _secret_or_env("GDRIVE_FOLDER_ID").strip()
    if not folder_id:
        _set_error("GDRIVE_FOLDER_ID 가 비어 있습니다.")
        return None

    for variant in _path_variants(rel_path):
        parts = [p for p in variant.split("/") if p]
        if not parts:
            continue
        found = _walk_to_file_id(folder_id, parts)
        if found:
            return found

    _set_error(
        f"Drive에서 파일을 찾지 못함: {rel_path} "
        f"(시도 경로: {', '.join(_path_variants(rel_path))}). "
        "폴더 공유·폴더 ID·basic/mock/hancert 구조 확인."
    )
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
        _set_error("Drive secrets(GDRIVE_FOLDER_ID / GDRIVE_SERVICE_ACCOUNT_JSON) 미설정")
        return None

    try:
        cdir = cache_dir(root)
    except Exception as exc:
        _set_error(f"캐시 디렉터리 오류: {exc}")
        return None

    cached = cdir / rel
    if cached.is_file() and cached.stat().st_size > 0:
        return cached

    try:
        file_id = _resolve_drive_file_id(rel)
        if not file_id:
            return None
        return _download_file(file_id, cached)
    except Exception as exc:
        _set_error(f"Drive 다운로드 실패 ({rel}): {type(exc).__name__}: {exc}")
        return None


def list_root_children(limit: int = 20) -> list[dict[str, str]]:
    """진단용: GDRIVE_FOLDER_ID 직하위 항목."""
    if not drive_configured():
        raise RuntimeError("Drive secrets 미설정")
    folder_id = _secret_or_env("GDRIVE_FOLDER_ID").strip()
    service = _drive_service()
    resp = (
        service.files()
        .list(
            q=f"'{folder_id}' in parents and trashed = false",
            spaces="drive",
            fields="files(id, name, mimeType)",
            pageSize=limit,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            corpora="allDrives",
        )
        .execute()
    )
    files = resp.get("files") or []
    if not files:
        resp = (
            service.files()
            .list(
                q=f"'{folder_id}' in parents and trashed = false",
                spaces="drive",
                fields="files(id, name, mimeType)",
                pageSize=limit,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora="user",
            )
            .execute()
        )
        files = resp.get("files") or []
    return [
        {
            "name": f.get("name", ""),
            "mimeType": f.get("mimeType", ""),
            "id": f.get("id", ""),
        }
        for f in files
    ]


def diagnose(root: Path, sample_rel: str = "") -> dict[str, Any]:
    """UI용 진단 결과."""
    out: dict[str, Any] = {
        "configured": drive_configured(),
        "folder_id_set": bool(_secret_or_env("GDRIVE_FOLDER_ID").strip()),
        "sa_json_set": bool(_secret_or_env("GDRIVE_SERVICE_ACCOUNT_JSON").strip()),
        "cache_dir": "",
        "root_children": [],
        "sample_rel": sample_rel,
        "sample_resolved": "",
        "error": "",
    }
    try:
        out["cache_dir"] = str(cache_dir(root))
    except Exception as exc:
        out["error"] = f"cache: {exc}"
        return out
    if not out["configured"]:
        out["error"] = "secrets 미설정"
        return out
    try:
        out["root_children"] = list_root_children()
        if sample_rel:
            _resolve_drive_file_id.cache_clear()
            path = resolve_image(root, sample_rel)
            out["sample_resolved"] = str(path) if path else ""
            if not path:
                out["error"] = get_last_error() or "샘플 이미지 resolve 실패"
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def image_available(root: Path, rel_path: str, *, probe_drive: bool = False) -> bool:
    """존재 여부. probe_drive=False 이면 로컬/캐시만(목록용, API 폭주 방지)."""
    rel = _normalize_rel(rel_path)
    if not rel:
        return False
    if (root / rel).is_file():
        return True
    try:
        if (cache_dir(root) / rel).is_file():
            return True
    except Exception:
        pass
    if not probe_drive:
        return drive_configured() and bool(rel)
    return resolve_image(root, rel) is not None
