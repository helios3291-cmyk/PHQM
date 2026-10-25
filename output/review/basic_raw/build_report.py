"""proposals.json + g2_code_proposal.json + notes.json → output/review/2026-10_기초학력_교차검증.md"""
import json, sys, re
sys.stdout.reconfigure(encoding='utf-8')
B = 'output/review/basic_raw'
P = json.load(open(f'{B}/proposals.json', encoding='utf-8'))
G2 = json.load(open(f'{B}/g2_code_proposal.json', encoding='utf-8'))
NOTES = json.load(open(f'{B}/notes.json', encoding='utf-8'))  # 수동 메모: "paper|no|era" 등 + 본문 단락
R = 'ABCDE'


def label(p):
    y, g, s, f = p.split('_')
    return f'{y} {g} {s} {f}'


def esc(s):
    return str(s if s is not None else '').replace('|', '／').replace('\n', ' ')


def views(it, fld):
    if fld == '문제형식':
        return '<br>'.join(f"{k}: {esc(it['reviewers'][k].get(fld))} ({esc(it['reviewers'][k].get('세부형식'))})" for k in R)
    return '<br>'.join(f"{k}: {esc(it['reviewers'][k].get(fld))}" for k in R)


def terms(s):
    return [t.strip() for t in re.split(r'[,，]', s or '') if t.strip()]


def note(p, it, kind, default=''):
    return NOTES.get(f"{p}|{it['문항번호']}|{kind}", default)


all_items = [(p, it) for p in P for it in P[p]]
n = len(all_items)
ans_err = [(p, it) for p, it in all_items if it['정답오류']]
era_fix, fmt_fix, era_split, fmt_split = [], [], [], []
unanimous_ok = confirmed_ok = 0
for p, it in all_items:
    e, f = it['시대'], it['문제형식']
    if e['count'] >= 4 and not e['csv_match']:
        era_fix.append((p, it))
    if e['count'] <= 3:
        era_split.append((p, it))
    if f['count'] >= 4 and not f['csv_match']:
        fmt_fix.append((p, it))
    if f['count'] <= 3:
        fmt_split.append((p, it))
    if e['count'] == 5 and f['count'] == 5 and e['csv_match'] and f['csv_match']:
        unanimous_ok += 1
    if e['count'] >= 4 and f['count'] >= 4 and e['csv_match'] and f['csv_match']:
        confirmed_ok += 1
key_fix = [(p, it) for p, it in all_items if it['정답핵심_csv유사'] < 0.34]
kw = [(p, it) for p, it in all_items if it['자료_missing']]
review_wrong = [(p, it) for p, it in all_items if it['리뷰정답'].get(it['공식정답'], 0) < 4]
g2_diff = [g for g in G2 if g['csv'] != g['proposal']]

L = []
w = L.append
w('# 기초학력 진단·향상도 검사 교차검증 보고서\n')
w(f'대상: `exam_basic.csv` 전체 {n}문항. 2024·2025 고1 역사 가/나형 120, 2024·2025 고2 한국사 가/나형 120, 2026 고1 한국사 향상도 A/B형 50.  ')
w('방법: 리뷰어 5명(A~E)이 CSV를 보지 않고 크롭 이미지와 스킬 규칙 문서(`SKILL.md`·`problem-formats.md`·`schema.md`)만으로 시대·문제형식·세부형식·자료/정답 핵심요소·정답을 판독했습니다. '
  '시험지 10개 단위로 나눠 돌렸고, 원자료는 `output/review/basic_raw/<시험지>/A~E.json`, 문항별 비교는 같은 폴더의 `compare.json`에 있습니다. '
  '시대·형식은 5명 중 4명 이상 일치하면 확정으로 봤습니다. 정답과 성취기준은 리뷰어 합의와 별도로 내용분류표 PDF 원문과 대조했습니다. **CSV는 아직 수정하지 않았습니다.**\n')

w('## 1. 요약\n')
w('| 항목 | 결과 |\n|---|---|')
w(f'| 정답: 내용분류표 PDF와 다름 | **{len(ans_err)}문항** (2025 고1 역사 가형 28 + 시험지 마지막 문항 6) |')
w(f'| 리뷰어 풀이 정답 vs 공식 정답 | {n - len(review_wrong)}/{n}문항에서 4명 이상이 공식 정답과 같게 풀었음 |')
w('| 성취기준: 고1 역사(9역)·2026 A/B(10한사1-) | 170문항 모두 분류표 코드와 같음 |')
w(f'| 성취기준: 고2 한국사 | 120문항 모두 분류표의 2015 개정 코드를 글자만 바꿔 2022 형식으로 옮겨 둠. 내용 기준 2022 코드로 바꾸면 **{len(g2_diff)}문항 변경** (판단 필요) |')
w(f'| 시대·형식 모두 5명 만장일치이고 CSV와 같음 | {unanimous_ok}문항 |')
w(f'| 시대·형식 모두 4명 이상 일치하고 CSV와 같음 | {confirmed_ok}문항 |')
w(f'| 시대: 확정 합의가 CSV와 다름 | {len(era_fix)}문항 |')
w(f'| 문제형식: 확정 합의가 CSV와 다름 | {len(fmt_fix)}문항 |')
w(f'| 시대: 리뷰어끼리 갈림 (3:2 이하) | {len(era_split)}문항 |')
w(f'| 문제형식: 리뷰어끼리 갈림 (3:2 이하) | {len(fmt_split)}문항 |')
w(f'| 정답핵심요소 교체 제안 (CSV 값이 공식 정답 선지와 맞지 않음) | {len(key_fix)}문항 |')
w(f'| 자료핵심요소: 4명 이상이 공통으로 쓴 용어가 CSV에 없음 (병합 제안) | {len(kw)}문항 |\n')
w(NOTES['summary_note'] + '\n')

w('## 2. 정답 오류 (내용분류표 PDF 원문 기준, 확정)\n')
w(NOTES['answer_cause'] + '\n')
w('| 시험지 | 문항 | CSV | 공식 | 리뷰어 풀이 | 정답핵심요소: CSV / 리뷰어 대표값 |\n|---|---|---|---|---|---|')
for p, it in ans_err:
    w(f"| {label(p)} | {it['문항번호']} | {it['csv']['정답']} | **{it['공식정답']}** | {esc(it['리뷰정답'])} | {esc(it['csv']['정답핵심요소'])} / {esc(it['정답핵심_합의'])} |")
w('')
if review_wrong:
    w('리뷰어 다수가 공식 정답과 다르게 푼 문항 (참고, 공식 정답 유지):\n')
    for p, it in review_wrong:
        w(f"- {label(p)} {it['문항번호']}번: 공식 {it['공식정답']}, 리뷰어 {esc(it['리뷰정답'])}. {esc(note(p, it, 'answer'))}")
    w('')

w('## 3. 성취기준 코드\n')
w(NOTES['code_intro'] + '\n')
w('| 시험지 | 문항 | 분류표 원문(2015) | 현재 CSV | 제안(2022, 내용 기준) | 평가요소 |\n|---|---|---|---|---|---|')
for g in G2:
    mark = '' if g['csv'] == g['proposal'] else '**'
    w(f"| {label(g['paper'])} | {g['no']} | {g['raw']} | {g['csv']} | {mark}{g['proposal']}{mark} | {esc(g['eval'])} |")
w('')

w('## 4. 시대 수정 제안 (확정 합의 ≠ CSV)\n')
w('| 시험지 | 문항 | 현재 CSV | 제안 | 표 | 근거·메모 |\n|---|---|---|---|---|---|')
for p, it in era_fix:
    w(f"| {label(p)} | {it['문항번호']} | {it['csv']['시대']} | **{it['시대']['top']}** | {it['시대']['count']}/5 | {esc(note(p, it, 'era'))} |")
w('')

w('## 5. 문제형식 수정 제안 (확정 합의 ≠ CSV)\n')
w(NOTES['format_intro'] + '\n')
w('| 시험지 | 문항 | 현재 CSV (세부) | 제안 (세부) | 표 | 메모 |\n|---|---|---|---|---|---|')
for p, it in fmt_fix:
    w(f"| {label(p)} | {it['문항번호']} | {it['csv']['문제형식']} ({esc(it['csv']['세부형식'])}) | **{it['문제형식']['top']}** ({esc(it['세부형식_제안'])}) | {it['문제형식']['count']}/5 | {esc(note(p, it, 'fmt'))} |")
w('')

w('## 6. 정답핵심요소 교체 제안\n')
w('CSV 값이 공식 정답 선지와 맞지 않는 문항입니다(공식 정답을 고른 리뷰어 값과 거의 겹치지 않음). 대부분 문항 속 단서를 정답 키워드로 적은 경우입니다. 제안값은 공식 정답을 고른 리뷰어들의 대표값입니다.\n')
w('| 시험지 | 문항 | 현재 CSV | 제안 | 리뷰어 A / B / C / D / E |\n|---|---|---|---|---|')
for p, it in key_fix:
    rv = ' / '.join(esc(it['reviewers'][k].get('정답핵심요소')) for k in R)
    w(f"| {label(p)} | {it['문항번호']} | {esc(it['csv']['정답핵심요소'])} | **{esc(it['정답핵심_합의'])}** | {rv} |")
w('')

w('## 7. 자료핵심요소 병합 제안\n')
w('4명 이상이 공통으로 쓴 용어 가운데 CSV에 없는 것을 뒤에 덧붙인 값입니다. 기존 용어는 그대로 둡니다. 대부분 단서만 있고 개념명(예: `고조선`, `3·1 운동`)이 빠진 경우입니다.\n')
w('| 시험지 | 문항 | 현재 CSV | 제안 (병합) |\n|---|---|---|---|')
for p, it in kw:
    merged = ', '.join(terms(it['csv']['자료핵심요소']) + it['자료_missing'])
    w(f"| {label(p)} | {it['문항번호']} | {esc(it['csv']['자료핵심요소'])} | {esc(merged)} |")
w('')

w('## 8. 판단 필요: 리뷰어가 갈린 문항 (3:2 이하)\n')
w(NOTES['split_intro'] + '\n')
for fld, lst, kind in [('시대', era_split, 'era_split'), ('문제형식', fmt_split, 'fmt_split')]:
    w(f'### {fld}\n')
    if not lst:
        w('없음 (모든 문항에서 4명 이상 일치)\n')
        continue
    w('| 시험지 | 문항 | 현재 CSV | 리뷰어 | 추천 |\n|---|---|---|---|---|')
    for p, it in lst:
        default = 'CSV 유지' if it[fld]['csv_match'] else f"{it[fld]['top']} (다수)"
        w(f"| {label(p)} | {it['문항번호']} | {it['csv'][fld]} | {views(it, fld)} | {esc(note(p, it, kind, default))} |")
    w('')

w('## 9. 직접 확인한 표본\n')
w(NOTES['spot_checks'] + '\n')
w('## 10. 원인과 후속 조치 제안\n')
w(NOTES['followups'] + '\n')
open('output/review/2026-10_기초학력_교차검증.md', 'w', encoding='utf-8').write('\n'.join(L))
print('n', n, 'ans', len(ans_err), 'era_fix', len(era_fix), 'fmt_fix', len(fmt_fix), 'era_split', len(era_split),
      'fmt_split', len(fmt_split), 'key_fix', len(key_fix), 'kw', len(kw), 'unanimous_ok', unanimous_ok,
      'confirmed_ok', confirmed_ok, 'g2_diff', len(g2_diff), 'review_wrong', len(review_wrong))
