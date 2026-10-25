"""5인 블라인드 리뷰 결과(basic_raw/<paper>/A~E.json)를 CSV와 비교해 compare.json을 만든다."""
import csv, json, re, sys, os, collections
sys.stdout.reconfigure(encoding='utf-8')
BASE = 'output/review/basic_raw'
R = 'ABCDE'
rows = list(csv.DictReader(open('output/data/exam_basic.csv', encoding='utf-8-sig')))
def key(r): return f"{r['연도']}_{r['학년']}_{r['과목']}_{r['문형']}"
def norm(s): return re.sub(r'[\s·ㆍ⋅\-\'"“”‘’]', '', s or '')
def terms(s):
    out = []
    for t in re.split(r'[,，/]', s or ''):
        t = t.strip()
        if not t: continue
        out.append(t)
    return out
def core(t): return norm(re.sub(r'\(.*?\)', '', t))
def bigrams(s):
    s = norm(s); return {s[i:i+2] for i in range(len(s)-1)} or ({s} if s else set())
def sim(a, b):
    A, B = bigrams(a), bigrams(b)
    return len(A & B) / max(1, min(len(A), len(B)))
papers = sys.argv[1:] or sorted(d for d in os.listdir(BASE) if os.path.isdir(os.path.join(BASE, d)))
for p in papers:
    revs = {}
    for r in R:
        f = os.path.join(BASE, p, f'{r}.json')
        if os.path.exists(f):
            revs[r] = {int(x['문항번호']): x for x in json.load(open(f, encoding='utf-8'))}
    if len(revs) < 5:
        print(p, 'reviewers', sorted(revs), '- skip'); continue
    out = []
    for r in sorted((x for x in rows if key(x) == p), key=lambda x: int(x['문항번호'])):
        n = int(r['문항번호'])
        v = {k: revs[k].get(n, {}) for k in R}
        item = {'문항번호': n, 'csv': {f: r[f] for f in ['시대', '문제형식', '세부형식', '자료핵심요소', '정답', '정답핵심요소', '성취기준_코드']}, 'reviewers': v}
        for f in ['시대', '문제형식', '정답']:
            c = collections.Counter(str(v[k].get(f, '')).strip() for k in R)
            top, cnt = c.most_common(1)[0]
            item[f] = {'top': top, 'count': cnt, 'dist': dict(c), 'csv_match': str(r[f]).strip() == top}
        # 자료핵심요소: 4명 이상이 쓴 용어(정규화 core 기준 유사 묶음)
        allt = [(k, t) for k in R for t in terms(v[k].get('자료핵심요소', ''))]
        groups = []
        for k, t in allt:
            for g in groups:
                if core(t) and (core(t) == g['core'] or (len(core(t)) >= 2 and (core(t) in g['core'] or g['core'] in core(t)))):
                    g['who'].add(k); g['forms'].append(t); break
            else:
                groups.append({'core': core(t), 'who': {k}, 'forms': [t]})
        csvn = norm(r['자료핵심요소'])
        shared = []
        for g in groups:
            if len(g['who']) >= 4:
                form = collections.Counter(g['forms']).most_common(1)[0][0]
                shared.append({'term': form, 'n': len(g['who']), 'in_csv': bool(g['core']) and (g['core'] in csvn or any(g['core'] in norm(x) or norm(x) in g['core'] for x in terms(r['자료핵심요소']) if norm(x)))})
        item['자료_shared'] = shared
        item['자료_missing'] = [s['term'] for s in shared if not s['in_csv']]
        # 정답핵심요소: CSV 값과 리뷰어 값 유사도
        sims = {k: round(sim(r['정답핵심요소'], v[k].get('정답핵심요소', '')), 2) for k in R}
        item['정답핵심_sim'] = sims
        item['정답핵심_low'] = sum(1 for s in sims.values() if s < 0.34) >= 4
        out.append(item)
    json.dump(out, open(os.path.join(BASE, p, 'compare.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    era_ok = sum(i['시대']['csv_match'] and i['시대']['count'] >= 4 for i in out)
    fmt_ok = sum(i['문제형식']['csv_match'] and i['문제형식']['count'] >= 4 for i in out)
    print(f"{p}: n={len(out)} 시대 확정일치 {era_ok}, 형식 확정일치 {fmt_ok}")
    for i in out:
        n = i['문항번호']; msgs = []
        for f in ['시대', '문제형식']:
            s = i[f]
            if not s['csv_match']:
                tag = '확정불일치' if s['count'] >= 4 else '갈림'
                msgs.append(f"{f}[{tag}] CSV={i['csv'][f]} 리뷰={s['dist']}")
            elif s['count'] < 4:
                msgs.append(f"{f}[CSV=다수지만 갈림] {s['dist']}")
        if not i['정답']['csv_match'] or i['정답']['count'] < 4:
            msgs.append(f"정답 CSV={i['csv']['정답']} 리뷰={i['정답']['dist']}")
        if i['자료_missing']: msgs.append(f"자료 누락어 {i['자료_missing']} (CSV: {i['csv']['자료핵심요소']})")
        if i['정답핵심_low']: msgs.append(f"정답핵심 CSV='{i['csv']['정답핵심요소']}' 리뷰={[i['reviewers'][k].get('정답핵심요소') for k in R]}")
        if msgs: print(f"  Q{n}: " + ' | '.join(msgs))
