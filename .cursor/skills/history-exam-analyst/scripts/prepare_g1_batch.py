#!/usr/bin/env python3
"""고1한국사 검사지 4종 일괄 전처리."""

from __future__ import annotations

import sys
from pathlib import Path

from prepare_pdf import prepare_pdf


def main() -> int:
    root = Path(__file__).resolve().parents[4]
    pdfs = sorted(Path(root / "input/pdf").rglob("*검사지.pdf"))
    g1 = [p for p in pdfs if p.parent.name != "pdf" and "고1" in p.name]
    if not g1:
        print("고1 검사지 없음", file=sys.stderr)
        return 1
    for pdf in g1:
        print(f"처리: {pdf.relative_to(root)}", flush=True)
        prepare_pdf(pdf, root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
