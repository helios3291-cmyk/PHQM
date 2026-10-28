"""Apply confirmed 5-reviewer fixes to exam_hancert.csv and write applied_changes.csv."""
import csv, json, os
from collections import Counter

S = os.path.dirname(os.path.abspath(__file__))
REPO = '/home/claude/PHQM'
CSV = f'{REPO}/output/data/exam_hancert.csv'
LOG = f'{REPO}/output/review/hancert_raw/applied_changes.csv'

cmp = {i['id'].split('_', 3)[-1]: i for i in json.load(open(f'{S}/compare.json'))}
with open(CSV, encoding='utf-8-sig') as f:
    rd = csv.DictReader(f)
    fields = rd.fieldnames
    rows = list(rd)

# 시대: 4표+ 중 제외(규칙상 CSV 유지)
ERA_KEEP = {'63회심화_26'}
# 문제형식: 4표+ 중 제외
FMT_KEEP = {
    '64회심화_1',  # 이전 스레드 사용자 결정(대화형 유지)
    '62회심화_19', '66회심화_9', '69회심화_29', '77회심화_37',  # 기기 화면 속 동영상 플레이어 → 영상자료형 유지(결정 항목 1)
    '74회심화_37', '79회기본_45',  # 교복 학생 발표 장면 → 수업형 유지(65회 13번과 일관)
}
# 문제형식: 3표 이하지만 이미지 확인 후 직접 정한 값
FMT_PICK = {
    '61회심화_46': '자료 제시형', '76회심화_7': '자료 제시형',  # 스마트폰 슬라이드
    '64회심화_6': '수업형', '78회심화_34': '수업형',  # 교복 학생 도서관 대화
    '67회심화_25': '실내전시형', '76회심화_48': '실내전시형',  # 홀로그램 무대 / 전시장 도슨트
    '77회기본_7': '대화형',  # 장수·관리 대화(왕 없음)
    '70회심화_24': '자료 제시형',  # 텍스트 대본 속 왕-신하 대화(결정 항목 2)
}
# 문장형 정답핵심요소 → 짧은 핵심어
ANS_SHORT = {
    '76회심화_3': '(나)-(가)-(다)', '76회심화_14': '(나)-(다)-(가)', '76회심화_47': '(가)-(나)-(다)',
    '78회심화_2': '(가)-(다)-(나)', '77회기본_14': '(라) 1170~1388', '77회심화_18': '(마) 1351~1392',
    '76회심화_26': '주자소 계미자 주조(태종)', '76회심화_34': 'ㄴ, ㄷ (알렌 건의 병원·전차)',
    '76회심화_38': '조선 혁명 선언', '76회심화_41': '경학사 조직(임시 정부 아님)',
    '76회심화_43': '새마을 운동(시기 부적절)', '76회심화_46': '이황·기대승 사단칠정 논쟁(추사 고택과 무관)',
    '76회심화_50': '대한국 국제 반포(고종)', '77회기본_38': '새마을 운동 초가지붕 개량(시기 부적절)',
    '77회심화_13': '호우명 그릇(고려 유산 아님)', '77회심화_23': '계해약조(세종, 시기 부적절)',
    '78회심화_25': '활구(은병) 주조(고려)', '78회심화_43': '텔레비전 방송(광복 이후, 부적절)',
    '78회심화_47': '국민 기초 생활 보장법(김대중 정부)',
}


def pick_detail(item, fmt):
    c = Counter(item['세부'][x] for x in 'ABCDE' if rv[x].get(item['id'], {}).get('문제형식') == fmt)
    return c.most_common(1)[0][0] if c else None


NORM = {'자료제시형': '자료 제시형', '역사장면형': '역사 장면형', '실내 전시형': '실내전시형'}
rv = {}
for x in 'ABCDE':
    rv[x] = {}
    for fn in os.listdir(f'{S}/out/{x}'):
        if fn.endswith('.json'):
            for it in json.load(open(f'{S}/out/{x}/{fn}')):
                it['문제형식'] = NORM.get(it['문제형식'], it['문제형식'])
                rv[x][it['id']] = it

log = []
for r in rows:
    key = f"{r['문형']}_{int(r['문항번호'])}"
    it = cmp.get(key)
    if not it:
        continue

    def change(field, new, why):
        if r[field] != new:
            log.append(['한능검', r['연도'], r['문형'], r['문항번호'], field, r[field], new, why])
            r[field] = new

    e = it['시대']
    if e['cnt'] >= 4 and e['top'] != r['시대'] and key not in ERA_KEEP:
        change('시대', e['top'], f"리뷰어 {e['cnt']}/5")

    f = it['문제형식']
    new = None
    if key in FMT_PICK:
        new, why = FMT_PICK[key], f"리뷰어 {f['votes'].get(FMT_PICK[key], 0)}/5 + 이미지 확인"
    elif f['cnt'] >= 4 and f['top'] != r['문제형식'] and key not in FMT_KEEP:
        new, why = f['top'], f"리뷰어 {f['cnt']}/5"
    if new and new != r['문제형식']:
        change('문제형식', new, why)
        d = pick_detail(it, new)
        if d:
            change('세부형식', d, '문제형식 변경에 따름')

    if key in ANS_SHORT:
        change('정답핵심요소', ANS_SHORT[key], '문장형 → 핵심어')

with open(CSV, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
    w.writeheader()
    w.writerows(rows)
with open(LOG, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f, lineterminator='\n')
    w.writerow(['프로파일', '연도', '문형', '문항번호', '필드', '이전', '이후', '근거'])
    w.writerows(log)
print('changes', len(log), Counter(l[4] for l in log))
