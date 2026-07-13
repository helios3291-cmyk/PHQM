#!/usr/bin/env python3
"""exam_analysis_*.json 샤드를 canonical exam_analysis.json에 안전 병합.

- 기존 exam_analysis.json을 유지한 채 샤드만 병합 (덮어쓰기 금지 모드가 기본)
- PDF 키 형태의 샤드 / 문항번호 flat 샤드는 매핑 가능한 경우만 병합
- --archive 시 병합한 샤드를 output/work/archive/로 이동
- --diff 시 canonical에 없는 샤드 키만 출력
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _is_pdf_keyed(obj: dict) -> bool:
    if not obj:
        return False
    return any(str(k).endswith(".pdf") for k in obj)


def _is_num_keyed(obj: dict) -> bool:
    if not obj:
        return False
    return all(re.fullmatch(r"\d{1,2}", str(k)) for k in obj)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def infer_pdf_key_from_shard_name(name: str, extracted_keys: set[str]) -> str | None:
    """exam_analysis_61회심화.json → (61회)한국사(심화)검사지.pdf 등."""
    stem = name
    if stem.startswith("exam_analysis_"):
        stem = stem[len("exam_analysis_") :]
    if re.search(r"_q\d+", stem):
        # q 범위: 앞부분으로 PDF 추론
        base = re.sub(r"_q\d+.*$", "", stem)
        return infer_pdf_key_from_shard_name("exam_analysis_" + base, extracted_keys)

    aliases = {
        "2024_na": "(2024)고2한국사(나형)검사지.pdf",
        "2025_ga": "(2025)고2한국사(가형)검사지.pdf",
        "2025_na": "(2025)고2한국사(나형)검사지.pdf",
        "2026_a": "(2026)고1한국사(A형)검사지.pdf",
        "2026_b": "(2026)고1한국사(B형)검사지.pdf",
    }
    if stem in aliases and aliases[stem] in extracted_keys:
        return aliases[stem]
    for alias, key in aliases.items():
        if stem.startswith(alias) and key in extracted_keys:
            return key

    round_m = re.search(r"(\d{1,3})회", stem)
    level_m = re.search(r"(심화|기본)", stem)
    if round_m and level_m:
        needle_round = f"({round_m.group(1)}회)"
        needle_level = f"({level_m.group(1)})"
        for key in extracted_keys:
            if needle_round in key and needle_level in key:
                return key

    for key in extracted_keys:
        compact = re.sub(r"[()_\s]", "", key.replace(".pdf", ""))
        hint = re.sub(r"[()_\s]", "", stem)
        if hint and hint in compact:
            return key
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="exam_analysis 샤드 병합")
    parser.add_argument("--diff", action="store_true", help="미반영 샤드만 보고 종료")
    parser.add_argument("--archive", action="store_true", help="병합 후 샤드를 archive/로 이동")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = project_root()
    work = root / "output" / "work"
    canonical_path = work / "exam_analysis.json"
    extracted_path = work / "extracted_questions.json"
    extracted_keys: set[str] = set()
    if extracted_path.exists():
        extracted_keys = set(json.loads(extracted_path.read_text(encoding="utf-8")).keys())

    canonical: dict = {}
    if canonical_path.exists():
        canonical = load_json(canonical_path)

    shards = sorted(
        p
        for p in work.glob("exam_analysis_*.json")
        if p.name != "exam_analysis.json"
    )
    unmatched: list[str] = []
    merged_files: list[Path] = []
    updates = 0

    for shard in shards:
        data = load_json(shard)
        if _is_pdf_keyed(data):
            for pdf_key, meta in data.items():
                if not isinstance(meta, dict):
                    continue
                before = canonical.get(pdf_key, {})
                if before != meta:
                    updates += 1
                    if not args.diff and not args.dry_run:
                        merged = dict(before)
                        merged.update(meta)
                        canonical[pdf_key] = merged
            merged_files.append(shard)
            continue

        if _is_num_keyed(data):
            pdf_key = infer_pdf_key_from_shard_name(shard.stem, extracted_keys)
            if not pdf_key:
                unmatched.append(shard.name)
                continue
            before = canonical.get(pdf_key, {})
            if before != data:
                updates += 1
                if not args.diff and not args.dry_run:
                    merged = dict(before)
                    merged.update({str(k): v for k, v in data.items()})
                    canonical[pdf_key] = merged
            merged_files.append(shard)
            continue

        unmatched.append(shard.name)

    if args.diff:
        print(f"샤드 {len(shards)}개, 갱신 후보 {updates}, 미매칭 {len(unmatched)}")
        for n in unmatched:
            print(f"  unmatched: {n}")
        return 0 if not unmatched else 1

    if args.dry_run:
        print(f"dry-run: 갱신 {updates}, 병합파일 {len(merged_files)}, 미매칭 {len(unmatched)}")
        return 0

    canonical_path.write_text(
        json.dumps(canonical, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"저장: {canonical_path} (PDFs={len(canonical)}, updates={updates})")

    if args.archive and merged_files:
        arch = work / "archive"
        arch.mkdir(parents=True, exist_ok=True)
        for p in merged_files:
            dest = arch / p.name
            shutil.move(str(p), str(dest))
            print(f"archive: {p.name}")

    if unmatched:
        print("미매칭 샤드:", file=sys.stderr)
        for n in unmatched:
            print(f"  - {n}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
