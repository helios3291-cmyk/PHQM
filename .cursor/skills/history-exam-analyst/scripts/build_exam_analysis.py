#!/usr/bin/env python3
"""exam_analysis.json 안전 빌드 — 기존 canonical을 유지한 채 지정 파트만 병합.

구버전처럼 4개 파트만으로 전체를 덮어쓰지 않는다.
샤드 일괄 병합은 merge_exam_analysis_shards.py 를 사용.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def main() -> int:
    parser = argparse.ArgumentParser(description="exam_analysis.json merge-safe 빌드")
    parser.add_argument(
        "--parts",
        nargs="*",
        default=None,
        help="병합할 JSON 파일명 (work/ 기준). 미지정 시 레거시 4파트",
    )
    parser.add_argument(
        "--replace-all",
        action="store_true",
        help="기존 canonical을 버리고 parts만으로 재작성 (위험)",
    )
    args = parser.parse_args()

    root = project_root()
    work = root / "output" / "work"
    out = work / "exam_analysis.json"

    analysis: dict = {}
    if out.exists() and not args.replace_all:
        analysis = json.loads(out.read_text(encoding="utf-8"))

    default_parts = [
        "exam_analysis_part1.json",
        "exam_analysis_2024_na.json",
        "exam_analysis_2025_ga.json",
        "exam_analysis_2025_na.json",
    ]
    part_names = args.parts if args.parts is not None else default_parts

    for name in part_names:
        path = work / name
        if not path.exists():
            print(f"skip missing: {name}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        # PDF 키면 그대로, 아니면 파일명 매핑이 필요 → part1 등 PDF 키 구조만 지원
        if any(str(k).endswith(".pdf") for k in data):
            for k, v in data.items():
                if isinstance(v, dict):
                    analysis.setdefault(k, {}).update(v)
        elif name == "exam_analysis_2024_na.json":
            key = "(2024)고2한국사(나형)검사지.pdf"
            analysis[key] = data if not any(str(x).endswith(".pdf") for x in data) else data.get(key, data)
        elif name == "exam_analysis_2025_ga.json":
            key = "(2025)고2한국사(가형)검사지.pdf"
            analysis[key] = data
        elif name == "exam_analysis_2025_na.json":
            key = "(2025)고2한국사(나형)검사지.pdf"
            analysis[key] = data
        else:
            print(f"skip unsupported shard shape: {name}")

    out.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(len(v) for v in analysis.values() if isinstance(v, dict))
    print(f"saved {out} ({len(analysis)} PDFs, {total} questions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
