"""내용분류표 PDF 원문에서 문항번호·성취기준(raw)·정답을 직접 읽어 CSV와 대조."""
import csv, re, sys, glob, os
import pymupdf
sys.stdout.reconfigure(encoding='utf-8')
CIRC = {'①': '1', '②': '2', '③': '3', '④': '4', '⑤': '5'}
tables = {
 ('2024','고1','가형'): 'input/pdf/고1한국사/(2024)고1역사2(가형)내용분류표.pdf',
 ('2024','고1','나형'): 'input/pdf/고1한국사/(2024)고1역사2(나형)내용분류표.pdf',
 ('2025','고1','가형'): 'input/pdf/고1한국사/(2025)고1역사2(가형)내용분류표.pdf',
 ('2025','고1','나형'): 'input/pdf/고1한국사/(2025)고1역사2(나형)내용분류표.pdf',
 ('2024','고2','가형'): 'input/pdf/(2024)고2한국사(가형)내용분류표.pdf',
 ('2024','고2','나형'): 'input/pdf/(2024)고2한국사(나형)내용분류표.pdf',
 ('2025','고2','가형'): 'input/pdf/(2025)고2한국사(가형)내용분류표.pdf',
 ('2025','고2','나형'): 'input/pdf/(2025)고2한국사(나형)내용분류표.pdf',
 ('2026','고1','A형'): 'input/classification/(2026)고1한국사(A형)내용분류표.pdf',
 ('2026','고1','B형'): 'input/classification/(2026)고1한국사(B형)내용분류표.pdf',
}
code_re = re.compile(r'(9역\d{2}-\d{2}|10한사\d-?\d{2}-\d{2}|10한사\d{2}-\d{2})')
parsed = {}
for k, p in tables.items():
    text = '\n'.join(pg.get_text() for pg in pymupdf.open(p)).replace('역사②', '역사2')  # 제목의 ② 제외
    codes = code_re.findall(text)
    answers = [CIRC[c] for c in re.findall('[①②③④⑤]', text)]
    parsed[k] = (codes, answers)
    print(k, 'codes', len(codes), 'answers', len(answers))
rows = list(csv.DictReader(open('output/data/exam_basic.csv', encoding='utf-8-sig')))
for k, (codes, answers) in parsed.items():
    rs = [r for r in rows if (r['연도'], r['학년'], r['문형']) == k]
    rs.sort(key=lambda r: int(r['문항번호']))
    for i, r in enumerate(rs):
        c = codes[i] if i < len(codes) else None
        a = answers[i] if i < len(answers) else None
        flag = []
        if a != r['정답']: flag.append(f'정답 CSV={r["정답"]} PDF={a}')
        norm = c.replace('-', '') if c else ''
        if c and r['성취기준_코드'] != c and not c.startswith('10한사0'):
            flag.append(f'코드 CSV={r["성취기준_코드"]} PDF={c}')  # 고2 2015 코드(10한사0X-YY) 차이는 별도 보고
        if flag: print(k, r['문항번호'], *flag)
