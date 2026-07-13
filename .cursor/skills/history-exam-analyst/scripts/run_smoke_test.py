#!/usr/bin/env python3
"""샘플 PDF 생성 및 전체 파이프라인 스모크 테스트."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import fitz


def project_root() -> Path:
    return Path(__file__).resolve().parents[4]


def scripts_dir(root: Path) -> Path:
    return root / ".cursor" / "skills" / "history-exam-analyst" / "scripts"


def run(cmd: list[str], root: Path) -> None:
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout:
        sys.stdout.buffer.write(result.stdout.encode("utf-8", errors="replace"))
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        raise RuntimeError(f"명령 실패 (exit {result.returncode}): {' '.join(cmd)}")


def create_sample_pdf(pdf_path: Path) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    page.insert_text((50, 80), "2024학년도 고등학교 1학년 기말고사", fontsize=14)
    page.insert_text((50, 120), "과목: 한국사", fontsize=12)
    page.insert_text(
        (50, 200),
        "15. 다음 자료를 읽고 물음에 답하시오.\n\n"
        "(가) 1592년 임진왜란 때 이순신은 거북선을 이끌고\n"
        "    명량 해전에서 큰 승리를 거두었다.\n\n"
        "① 이순신  ② 세종대왕  ③ 광개토대왕",
        fontsize=11,
    )

    doc.save(pdf_path)
    doc.close()
    print(f"샘플 PDF 생성: {pdf_path}")


def main() -> int:
    root = project_root()
    scripts = scripts_dir(root)
    py = sys.executable

    sample_pdf = root / "input" / "pdf" / "sample_2024_고1_한국사.pdf"
    create_sample_pdf(sample_pdf)

    run([py, str(scripts / "index_achievement.py")], root)
    run([py, str(scripts / "prepare_pdf.py"), str(sample_pdf.relative_to(root))], root)

    work_dir = root / "output" / "work" / sample_pdf.stem
    text_json = work_dir / "text.json"
    data = json.loads(text_json.read_text(encoding="utf-8"))

    run(
        [
            py,
            str(scripts / "crop_question.py"),
            "--page-image",
            data["pages"][0]["page_image"],
            "--bbox",
            "40,180,560,400",
            "--year",
            "2024",
            "--grade",
            "고1",
            "--subject",
            "한국사",
            "--number",
            "15",
        ],
        root,
    )

    run(
        [
            py,
            str(scripts / "append_csv.py"),
            "--profile",
            "basic",
            "--year",
            "2024",
            "--grade",
            "고1",
            "--subject",
            "한국사",
            "--exam-type",
            "가형",
            "--number",
            "15",
            "--achievement-code",
            "10한사1-01-01",
            "--era",
            "조선",
            "--format",
            "자료 제시형",
            "--sub-format",
            "단일 자료",
            "--source-key",
            "임진왜란, 이순신, 명량 해전",
            "--answer-key",
            "이순신",
            "--image",
            "output/images/basic/2024_고1_한국사_가형_15.png",
            "--source-pdf",
            sample_pdf.relative_to(root).as_posix(),
            "--force",
        ],
        root,
    )

    run([py, str(scripts / "validate_output.py")], root)
    print("스모크 테스트 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
