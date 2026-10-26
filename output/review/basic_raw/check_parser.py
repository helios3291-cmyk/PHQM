"""index_classification 파서 결과를 exam_basic.csv(정답·성취기준_코드)와 대조."""
import csv, sys, re
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
root = Path('.').resolve()
sys.path.insert(0, str(root / '.cursor/skills/history-exam-analyst/scripts'))
from index_classification import parse_classification_pdf  # noqa: E402
TABLE = {
 '2024_고1_역사_가형': 'input/pdf/고1한국사/(2024)고1역사2(가형)내용분류표.pdf',
 '2024_고1_역사_나형': 'input/pdf/고1한국사/(2024)고1역사2(나형)내용분류표.pdf',
 '2025_고1_역사_가형': 'input/pdf/고1한국사/(2025)고1역사2(가형)내용분류표.pdf',
 '2025_고1_역사_나형': 'input/pdf/고1한국사/(2025)고1역사2(나형)내용분류표.pdf',
 '2024_고2_한국사_가형': 'input/pdf/(2024)고2한국사(가형)내용분류표.pdf',
 '2024_고2_한국사_나형': 'input/pdf/(2024)고2한국사(나형)내용분류표.pdf',
 '2025_고2_한국사_가형': 'input/pdf/(2025)고2한국사(가형)내용분류표.pdf',
 '2025_고2_한국사_나형': 'input/pdf/(2025)고2한국사(나형)내용분류표.pdf',
 '2026_고1_한국사_A형': 'input/classification/(2026)고1한국사(A형)내용분류표.pdf',
 '2026_고1_한국사_B형': 'input/classification/(2026)고1한국사(B형)내용분류표.pdf',
}
rows = list(csv.DictReader(open('output/data/exam_basic.csv', encoding='utf-8-sig')))
total = bad = 0
for p, pdf in TABLE.items():
    res = parse_classification_pdf(root / pdf, root)
    got = {e['number']: e for e in res['entries']}
    diffs = []
    for r in rows:
        if f"{r['연도']}_{r['학년']}_{r['과목']}_{r['문형']}" != p:
            continue
        total += 1
        e = got.get(int(r['문항번호']), {})
        if str(e.get('answer')) != r['정답'] or e.get('achievement_code') != r['성취기준_코드']:
            diffs.append((r['문항번호'], r['정답'], e.get('answer'), r['성취기준_코드'], e.get('achievement_code')))
    bad += len(diffs)
    print(p, 'entries', len(res['entries']), 'diffs', len(diffs), diffs[:4])
print('total', total, 'mismatch', bad)
