"""Compare 5 blind reviewers against exam_hancert.csv. Usage: python3 compare.py [rounds...]"""
import csv, json, os, sys, glob
from collections import Counter

S = os.path.dirname(os.path.abspath(__file__))
REPO = '/home/claude/PHQM'
rows = list(csv.DictReader(open(f'{REPO}/output/data/exam_hancert.csv', encoding='utf-8-sig')))
key = json.load(open(f'{REPO}/output/review/hancert_raw/answer_key.json'))
R = 'ABCDE'
NORM = {'자료제시형': '자료 제시형', '역사장면형': '역사 장면형', '실내 전시형': '실내전시형'}
rev = {x: {} for x in R}
for x in R:
    for f in glob.glob(f'{S}/out/{x}/*.json'):
        try:
            for it in json.load(open(f)):
                for k in ('시대', '문제형식'):
                    it[k] = NORM.get(it.get(k, ''), it.get(k, ''))
                rev[x][it['id']] = it
        except Exception as e:
            print('BAD', f, e)

want = set(sys.argv[1:])
out = []
for r in rows:
    if want and r['문형'] not in want:
        continue
    rid = os.path.basename(r['이미지경로'])[:-4]
    got = {x: rev[x][rid] for x in R if rid in rev[x]}
    if not got:
        continue
    item = {'id': rid, 'n': len(got), 'csv': {k: r[k] for k in ('시대', '문제형식', '세부형식', '자료핵심요소', '정답', '정답핵심요소')},
            'official': key[r['문형']][str(int(r['문항번호']))]}
    for f in ('시대', '문제형식'):
        c = Counter(g[f] for g in got.values())
        top, cnt = c.most_common(1)[0]
        item[f] = {'votes': dict(c), 'top': top, 'cnt': cnt, 'csv_agree': c.get(r[f], 0)}
    c = Counter(str(g.get('풀이정답')) for g in got.values())
    item['정답'] = {'votes': dict(c), 'official_agree': c.get(item['official'], 0)}
    item['왕신하'] = sum(1 for g in got.values() if g.get('왕신하대화'))
    item['세부'] = {x: g['세부형식'] for x, g in got.items()}
    item['자료'] = {x: g['자료핵심요소'] for x, g in got.items()}
    item['정답핵심'] = {x: g['정답핵심요소'] for x, g in got.items()}
    item['메모'] = {x: g.get('메모', '') for x, g in got.items() if g.get('메모')}
    out.append(item)
json.dump(out, open(f'{S}/compare.json', 'w'), ensure_ascii=False, indent=1)

print('items', len(out), 'reviewer coverage', {x: len(rev[x]) for x in R})
for f in ('시대', '문제형식'):
    flag = [i for i in out if i[f]['csv_agree'] < 3]
    sure = [i for i in flag if i[f]['cnt'] >= 4]
    print(f'{f}: csv<3표 {len(flag)} / 4표+ 다른값 {len(sure)}')
print('정답 official<3표', len([i for i in out if i['정답']['official_agree'] < 3]))
print('왕신하 3+', len([i for i in out if i['왕신하'] >= 3]))
