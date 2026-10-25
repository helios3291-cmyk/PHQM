"""고2 한국사 진단(내용분류표=2015 개정 코드)의 2022 개정 코드 제안.
규칙: 2015 단원·평가요소를 2022 성취기준 내용에 맞춤. 2026 고1 향상도 공식 분류표(C01)의 배정을 선례로 사용
(강화도 조약→1-03-01, 갑신정변·동학→1-03-02, 근대 문물→1-03-03, 국채 보상·을사늑약→1-03-04,
 흥선 대원군→1-01-04, 조선 후기 농업→1-02-02, 정조→1-01-04)."""
import csv, json, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')
rows = [r for r in csv.DictReader(open('output/data/exam_basic.csv', encoding='utf-8-sig')) if r['학년'] == '고2']
def has(r, e, *ws): return any(w in (e + r['자료핵심요소'] + r['정답핵심요소']) for w in ws)
def propose(raw, e, r):
    u, s = raw[4:6], raw[7:9]
    if u == '01':
        if s in ('01',): return '10한사1-01-01'
        if s == '02': return '10한사1-02-04'                      # 고대 사상
        if s == '03': return '10한사1-02-01' if any(w in e for w in ('대외', '여진', '거란')) else '10한사1-01-02'
        if s == '04': return '10한사1-02-04'                      # 고려 문화·사상
        if s == '05': return '10한사1-02-01' if any(w in e for w in ('국제', '왜란', '호란', '대외')) else '10한사1-01-03'
        if s == '06': return '10한사1-02-02'                      # 조선 후기 경제
    if u == '02':
        if s == '01': return '10한사1-01-04'                      # 흥선 대원군 (C01 선례)
        if s == '02': return '10한사1-03-01' if has(r, e, '강화도') else '10한사1-03-02'
        if s == '03': return '10한사1-03-02'
        if s == '04': return '10한사1-03-04'
        if s == '05': return '10한사1-03-03' if has(r, e, '방곡령') else '10한사1-03-04'
        if s == '06': return '10한사1-03-03'
    if u == '03':
        if s == '01': return '10한사2-01-02' if has(r, e, '산미', '토지 조사', '토지조사') else '10한사2-01-01'
        if s in ('02', '03'): return '10한사2-01-04' if has(r, e, '농촌 계몽', '브나로드') else '10한사2-01-03'
        if s == '04': return '10한사2-01-03' if has(r, e, '물산', '실력양성') else '10한사2-01-04'
        if s == '05': return '10한사2-01-01'
        if s == '06': return '10한사2-01-05'
    if u == '04':
        if s in ('01', '02'): return '10한사2-02-01'
        if s == '03': return '10한사2-02-02'
        if s == '04': return '10한사2-02-03'
        if s == '05': return '10한사2-02-03' if has(r, e, '유신 헌법') and not has(r, e, '경제 정책', '수출', '전태일', '노동') else '10한사2-02-04'
        if s == '06': return '10한사2-03-01' if '이후' in e else '10한사2-02-03'
        if s in ('07', '08'): return '10한사2-03-03'
    return '?'
out = []
for r in rows:
    stem = os.path.splitext(os.path.basename(r['원본PDF']))[0]
    ent = {x['number']: x for x in json.load(open(f'output/work/{stem}/classification.json', encoding='utf-8'))['entries']}[int(r['문항번호'])]
    raw, e = ent['achievement_code_raw'], ent.get('evaluation_element') or ''
    out.append({'paper': f"{r['연도']}_고2_한국사_{r['문형']}", 'no': int(r['문항번호']), 'raw': raw, 'csv': r['성취기준_코드'], 'eval': e, 'proposal': propose(raw, e, r)})
json.dump(out, open('output/review/basic_raw/g2_code_proposal.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for o in out: print(o['paper'][:10], o['no'], o['raw'], o['csv'], '→', o['proposal'], '|', o['eval'])
print(sum(o['csv'] != o['proposal'] for o in out), 'differ')
