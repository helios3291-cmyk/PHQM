"""교차검증 보고서(2026-10_기초학력_교차검증.md) 승인분을 exam_basic.csv에 적용.

사용자 결정 (2026-10-26):
 1. 기초학력 성취기준·정답은 내용분류표 원문 기준 (고2는 2015 코드 그대로)
 2. 초기 고구려 → 삼국시대   3. 위화도 회군 → 고려   4. 여러 시대 주제 → 통사
 5. 왕과 신하의 대화 → 역사 장면형
변경 내역은 applied_changes.csv에 남긴다.
"""
import csv, io, json, re, sys, collections
import pymupdf

sys.stdout.reconfigure(encoding='utf-8')
B = 'output/review/basic_raw'
CSV = 'output/data/exam_basic.csv'
sys.path.insert(0, B)
from build_report_data import TABLE, official, centroid, sim, norm  # noqa: E402

P = json.load(open(f'{B}/proposals.json', encoding='utf-8'))
R = 'ABCDE'
# §8 갈린 문항: 직접 확인한 추천값 (결정 5 반영)
SPLIT = {
    ('2024_고2_한국사_나형', 11): '실내전시형',
    ('2025_고1_역사_가형', 19): '자료 제시형',
    ('2026_고1_한국사_B형', 8): '역사 장면형',
    ('2024_고1_역사_가형', 22): '역사 장면형',
}
# 결정 5: 왕과 신하 대화 → 역사 장면형 (CSV 대화형이고 합의로 바뀌지 않는 행 포함)
KING = {('2024_고1_역사_나형', 11), ('2024_고1_역사_가형', 22), ('2025_고1_역사_가형', 13),
        ('2025_고1_역사_가형', 16), ('2025_고1_역사_나형', 16), ('2025_고2_한국사_나형', 7),
        ('2026_고1_한국사_B형', 8)}
KING_SUB = '왕과 신하 대화 장면'


def terms(s):
    return [t.strip() for t in re.split(r'[,，]', s or '') if t.strip()]


raw = open(CSV, encoding='utf-8-sig', newline='').read()
reader = csv.DictReader(io.StringIO(raw))
fields = reader.fieldnames
rows = list(reader)
off = {p: official(p) for p in TABLE}
items = {(p, it['문항번호']): it for p in P for it in P[p]}
log = []


def setv(r, key, col, new, why):
    if r[col] != new:
        log.append({'시험지': key[0], '문항': key[1], '필드': col, '이전': r[col], '변경': new, '근거': why})
        r[col] = new


for r in rows:
    key = (f"{r['연도']}_{r['학년']}_{r['과목']}_{r['문형']}", int(r['문항번호']))
    it = items[key]
    codes, answers = off[key[0]]
    n = key[1]
    setv(r, key, '정답', answers[n - 1], '내용분류표 정답')
    setv(r, key, '성취기준_코드', codes[n - 1], '내용분류표 원문 코드')
    e = it['시대']
    if e['count'] >= 4 and not e['csv_match']:
        setv(r, key, '시대', e['top'], f"리뷰어 {e['count']}/5")
    f = it['문제형식']
    if key in KING:
        setv(r, key, '문제형식', '역사 장면형', '결정 5 (왕과 신하 대화)')
        setv(r, key, '세부형식', KING_SUB, '결정 5 (왕과 신하 대화)')
    elif key in SPLIT:
        tgt = SPLIT[key]
        sub = centroid([it['reviewers'][k]['세부형식'] for k in R if it['reviewers'][k]['문제형식'] == tgt])
        setv(r, key, '문제형식', tgt, '갈림 문항 직접 확인 추천')
        if sub:
            setv(r, key, '세부형식', sub, '갈림 문항 직접 확인 추천')
    elif f['count'] >= 4 and not f['csv_match']:
        setv(r, key, '문제형식', f['top'], f"리뷰어 {f['count']}/5")
        setv(r, key, '세부형식', it['세부형식_제안'], f"리뷰어 {f['count']}/5")
    if it['정답핵심_csv유사'] < 0.34:
        setv(r, key, '정답핵심요소', it['정답핵심_합의'], '정답 선지와 불일치 → 리뷰어 대표값')
    old = terms(r['자료핵심요소'])
    # 기존 용어를 고쳐 쓴 것뿐인 용어는 넣지 않음 (긴 문장에서 뽑은 짧은 개념명은 추가)
    add = [m for m in it['자료_missing']
           if not any(sim(m, o) >= 0.7 and len(norm(m)) >= 0.6 * len(norm(o)) for o in old)]
    if add:
        setv(r, key, '자료핵심요소', ', '.join(old + add), '리뷰어 4명 이상 공통 용어 병합')

out = io.StringIO(newline='')
w = csv.DictWriter(out, fieldnames=fields, lineterminator='\n')
w.writeheader()
w.writerows(rows)
data = out.getvalue()
open(CSV, 'w', encoding='utf-8-sig', newline='').write(data)
open('output/data/exam_questions.csv', 'w', encoding='utf-8-sig', newline='').write(data)
with open(f'{B}/applied_changes.csv', 'w', encoding='utf-8-sig', newline='') as fh:
    lw = csv.DictWriter(fh, fieldnames=['시험지', '문항', '필드', '이전', '변경', '근거'], lineterminator='\n')
    lw.writeheader()
    lw.writerows(log)
c = collections.Counter(x['필드'] for x in log)
print(dict(c), 'rows touched', len({(x['시험지'], x['문항']) for x in log}))
