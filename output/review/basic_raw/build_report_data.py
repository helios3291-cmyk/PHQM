"""compare.json(문항별) + 공식 정답 대조 결과를 합쳐 보고서용 proposals.json 생성."""
import json, os, re, sys, collections, csv
import pymupdf
sys.stdout.reconfigure(encoding='utf-8')
BASE = 'output/review/basic_raw'
R = 'ABCDE'
PAPERS = ['2024_고1_역사_가형', '2024_고1_역사_나형', '2025_고1_역사_가형', '2025_고1_역사_나형',
          '2024_고2_한국사_가형', '2024_고2_한국사_나형', '2025_고2_한국사_가형', '2025_고2_한국사_나형',
          '2026_고1_한국사_A형', '2026_고1_한국사_B형']
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
CIRC = {'①': '1', '②': '2', '③': '3', '④': '4', '⑤': '5'}
CODE = re.compile(r'(9역\d{2}-\d{2}|10한사\d-\d{2}-\d{2}|10한사\d{2}-\d{2})')
def official(p):
    t = '\n'.join(pg.get_text() for pg in pymupdf.open(TABLE[p])).replace('역사②', '역사2')
    return CODE.findall(t), [CIRC[c] for c in re.findall('[①②③④⑤]', t)]
def norm(s): return re.sub(r'[\s·ㆍ⋅\-]', '', s or '')
def bigrams(s):
    s = norm(s); return {s[i:i+2] for i in range(len(s)-1)} or ({s} if s else set())
def sim(a, b):
    A, B = bigrams(a), bigrams(b); return len(A & B) / max(1, min(len(A), len(B)))
def centroid(vals):
    vals = [v for v in vals if v]
    if not vals: return ''
    c = collections.Counter(norm(v) for v in vals)
    top, n = c.most_common(1)[0]
    if n >= 2: return next(v for v in vals if norm(v) == top)
    return max(vals, key=lambda v: (sum(sim(v, w) for w in vals), -len(v)))
out = {}
for p in PAPERS:
    f = os.path.join(BASE, p, 'compare.json')
    if not os.path.exists(f): continue
    codes, answers = official(p)
    items = []
    for it in json.load(open(f, encoding='utf-8')):
        n = it['문항번호']; v = it['reviewers']; c = it['csv']
        e = {'문항번호': n, 'csv': c, 'reviewers': {k: {x: v[k].get(x) for x in ['시대', '문제형식', '세부형식', '자료핵심요소', '정답', '정답핵심요소', '확신도', '메모']} for k in R}}
        e['공식정답'] = answers[n-1]; e['공식코드'] = codes[n-1]
        e['정답오류'] = answers[n-1] != c['정답']
        e['리뷰정답'] = it['정답']['dist']
        for fld in ['시대', '문제형식']:
            s = it[fld]
            e[fld] = {'top': s['top'], 'count': s['count'], 'dist': s['dist'], 'csv_match': s['csv_match']}
        # 세부형식 제안: 다수 형식을 고른 리뷰어들의 세부형식 대표값
        topf = it['문제형식']['top']
        e['세부형식_제안'] = centroid([v[k].get('세부형식', '') for k in R if v[k].get('문제형식') == topf])
        # 정답핵심요소 대표값: 공식 정답을 고른 리뷰어 기준
        right = [k for k in R if str(v[k].get('정답')) == answers[n-1]]
        e['정답핵심_합의'] = centroid([v[k].get('정답핵심요소', '') for k in right])
        e['정답핵심_csv유사'] = round(max([sim(c['정답핵심요소'], v[k].get('정답핵심요소', '')) for k in right] or [0]), 2)
        e['자료_shared'] = it['자료_shared']; e['자료_missing'] = it['자료_missing']
        items.append(e)
    out[p] = items
json.dump(out, open(os.path.join(BASE, 'proposals.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print({p: len(v) for p, v in out.items()})
