#!/usr/bin/env python3
"""기존 exam_questions.csv·output/images 루트를 basic 프로파일로 이관."""

from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

import pandas as pd

from exam_profiles import CSV_COLUMNS, ensure_profile_dirs, images_dir_for, csv_path_for

ROOT = Path(__file__).resolve().parents[4]


def write_csv(path: Path, df: pd.DataFrame) -> None:
    tmp = path.with_suffix(".csv.tmp")
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    data = tmp.read_bytes()
    for _ in range(25):
        try:
            path.write_bytes(data)
            tmp.unlink(missing_ok=True)
            return
        except PermissionError:
            time.sleep(1)
    raise PermissionError(f"CSV locked: {path}")


def migrate() -> None:
    ensure_profile_dirs(ROOT)
    old_csv = ROOT / "output/data/exam_questions.csv"
    basic_csv = csv_path_for("basic", ROOT)
    basic_img = images_dir_for("basic", ROOT)

    # 1) images: root PNG → basic/
    images_root = ROOT / "output/images"
    moved = 0
    if images_root.exists():
        for p in images_root.iterdir():
            if p.is_file() and p.suffix.lower() == ".png":
                dest = basic_img / p.name
                if dest.exists():
                    p.unlink()
                else:
                    shutil.move(str(p), str(dest))
                moved += 1
    print(f"images moved to basic/: {moved}")

    # 2) CSV
    if old_csv.exists() and old_csv.stat().st_size > 0:
        df = pd.read_csv(old_csv, encoding="utf-8-sig")
    elif basic_csv.exists() and basic_csv.stat().st_size > 0:
        df = pd.read_csv(basic_csv, encoding="utf-8-sig")
    else:
        df = pd.DataFrame(columns=CSV_COLUMNS)

    for col in CSV_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[CSV_COLUMNS]

    def fix_img(path: str) -> str:
        s = str(path).replace("\\", "/").strip()
        if not s or s == "nan":
            return s
        if s.startswith("output/images/basic/"):
            return s
        if s.startswith("output/images/"):
            name = s[len("output/images/") :]
            if "/" in name:  # already under another profile
                return s
            return f"output/images/basic/{name}"
        return s

    df["이미지경로"] = df["이미지경로"].map(fix_img)
    write_csv(basic_csv, df)
    print(f"wrote {basic_csv.relative_to(ROOT)} rows={len(df)}")

    # keep old file as pointer note: copy of basic for short compat, then leave deprecated copy
    if old_csv.resolve() != basic_csv.resolve():
        try:
            write_csv(old_csv, df)
            print(f"compat copy: {old_csv.name} (deprecated, use exam_basic.csv)")
        except PermissionError:
            print("warn: could not update exam_questions.csv (locked)", file=sys.stderr)

    # empty mock/hancert already via ensure_profile_dirs
    print("done")


if __name__ == "__main__":
    migrate()
