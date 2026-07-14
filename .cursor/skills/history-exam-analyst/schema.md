# 데이터 스키마

## 시험 프로파일 (저장 경로)

| 프로파일 | 시험 | CSV | 이미지 |
|----------|------|-----|--------|
| `basic` | 기초학력 진단·향상도 | `output/data/exam_basic.csv` | `output/images/basic/` |
| `mock` | 학평·모평·수능 | `output/data/exam_mock.csv` | `output/images/mock/` |
| `hancert` | 한국사능력검정시험 | `output/data/exam_hancert.csv` | `output/images/hancert/` |

`exam_questions.csv`는 deprecated(기초학력 호환 복사본). 신규 저장은 `exam_basic.csv` 등을 사용합니다.

## CSV 컬럼 (프로파일 공통)

| 컬럼 | 필수 | 설명 | 예시 |
|------|------|------|------|
| `연도` | Y | 시험 연도. 학평·기초학력은 표기연도만. 모평·수능은 `시행연도(학년도)` | `2024`, `2026(2027)` |
| `학년` | Y | 학년 | `고1` |
| `과목` | Y | 과목명 (검사지·파일명 그대로) | `한국사` (고2), `역사` (고1) |
| `문형` | Y | 시험 문형 | `가형`, `나형`, `A형` |
| `문항번호` | Y | 문항 번호 | `15` |
| `성취기준_코드` | Y | 교육과정 코드 (대괄호 없음) | `10한사1-01-01` (고등), `9역01-01` (중학) |
| `시대` | Y | 시대 분류 | `조선` |
| `문제형식` | Y | 1차 분류 | `자료 제시형` |
| `세부형식` | Y | 2차 분류 | `단일 자료` |
| `자료핵심요소` | Y | 자료의 핵심 역사 요소 | `임진왜란, 이순신` |
| `정답` | N* | 객관식 선지 번호 (`1`~`5`). 없으면 빈칸 허용 | `3` |
| `정답핵심요소` | Y | 정답의 핵심 역사 요소 | `해전 승리` |
| `이미지경로` | Y | 크롭 PNG 경로 | `output/images/basic/2024_고1_역사_가형_15.png` |
| `원본PDF` | Y | 원본 PDF 경로 | `input/pdf/2024_고1_한국사.pdf` |
| `처리일시` | Y | ISO 8601 | `2026-07-08T10:00:00` |

## 연도 표기

| 시험 | 형식 | 예시 | 설명 |
|------|------|------|------|
| 학평·기초학력 등 | `YYYY` | `2026` | 시행 연도 = 시험 표기 연도 |
| 모평·수능 | `YYYY(YYYY)` | `2026(2027)` | 시행 연도(학년도). 예: 2027학년도 대수능은 2026년 11월 시행 |

모평·수능 PDF 파일명의 `(YYYY)` / `YYYY학년도`는 **학년도(표기 연도)** 로 해석하고, CSV·이미지의 `연도`는 `시행연도(학년도)`로 기록합니다. 시행 연도 = 학년도 − 1.

## 문형

시험지 유형 분류. 예: `가형`, `나형`, `A형`, `B형`, `6월모평`

PDF 표지·머리말·파일명에서 확인합니다. 불명확하면 사용자에게 확인합니다.

## 교육과정·성취기준 매핑 규칙

| 학교급 | 적용 교육과정 | 참조 파일 | 인덱스 필터 |
|--------|--------------|-----------|-------------|
| 중학교 (중1~3) | 2015 개정 | `평가기준+역사과+5차+1205.pdf` | `school_level=중학`, `curriculum=2015` |
| 고등학교 (고2·고3) | 2022 개정 | `성취기준/2. 고등학교 한국사 교육과정 성취기준(2022개정교육과정).pdf` | `school_level=고등`, `curriculum=2022` |
| 고1 역사 기초학력 검사 | 2015 개정 (중3 범위) | `성취기준/평가기준+역사과+5차+1205.pdf` | `school_level=중학`, 코드 `9역XX-YY` |

**고등학교 문항에 2015 개정 성취기준을 적용하면 안 됩니다.**

## 시대 (enum)

다음 8개 중 정확히 하나:

- 삼국시대 이전
- 삼국시대
- 남북국시대
- 고려
- 조선
- 개항기
- 일제강점기
- 현대

## 문제 형식 (1차 분류, enum)

상호배타. 충돌 시 [problem-formats.md](problem-formats.md) **우선순위**를 따릅니다.

| 우선순위 | 형식 |
|----------|------|
| 1 | 역사 신문형 |
| 2 | 영상자료형 |
| 3 | 퀴즈형 |
| 4 | 마인드맵형 |
| 5 | 카드형 |
| 6 | 인터뷰형 |
| 7 | 답사형 |
| 8 | 실내전시형 |
| 9 | 메신저형 |
| 10 | 챗봇형 |
| 11 | 수업형 |
| 12 | 대화형 |
| 13 | 계획서형 |
| 14 | 역사 장면형 |
| 15 | 역사 토론형 |
| 16 | 자료 제시형 (잔여) |

새 형식 추가 시 사용자 확인 후 `problem-formats.md`에 우선순위와 함께 기록합니다.

## 세부 형식 (2차 분류)

문제 형식에 종속. 완전 표준화 불필요. 예: `학생 2인 대화`, `단일 자료`, `복합 자료`.

## 이미지 파일명 규칙

```
output/images/{basic|mock|hancert}/{연도}_{학년}_{과목}_{문형}_{문항번호}.png
```

예: `output/images/basic/2024_고2_한국사_가형_15.png`, `output/images/mock/2026(2027)_고3_한국사_6월모평_1.png`

공백·특수문자는 `_`로 치환합니다.

## crop_warnings.json (`output/work/<pdf_stem>/`)

```json
{
  "warnings": [
    "Q12: ⑤ 미검출, 페이지 하단까지 사용"
  ]
}
```

## classification.json (`output/work/<pdf_stem>/`)

내용분류표 PDF 파싱 결과. `index_classification.py`가 생성합니다.

```json
{
  "source_file": "input/classification/(2025)고2한국사(나형)내용분류표.pdf",
  "exam_format": "diagnostic_g2",
  "entries": [
    {
      "number": 1,
      "achievement_code_raw": "10한사01-01",
      "achievement_code": "10한사1-01-01",
      "achievement_text_index": "고대국가의형성과 성장과정을파악한 다.",
      "evaluation_element": "신석기 시대의 생활 모습 이해하기",
      "content_area": "역사이해",
      "answer": "3",
      "answer_label": "③"
    }
  ],
  "warnings": []
}
```

- `exam_format`: `diagnostic_g2` (고2 진단), `diagnostic_g1_middle` (고1 중학 역사), `enhancement_c01` (고1 C01형) 등 코드·인덱서가 쓰는 값
- C01형 항목에는 `minimum_achievement` 필드 추가
- CSV 매핑: `성취기준_코드`·`정답`(있을 때)을 분류표에서 사용 (원문은 CSV에 넣지 않음). `evaluation_element`는 참고용
- `문제형식`, `세부형식`, `시대`, `자료핵심요소`, `정답핵심요소`는 **`exam_analysis.json`만** (AI, 크롭 PNG 기반). 모평 등 분류표 없을 때 `answer`(1~5)도 exam_analysis에 기록. 정답지는 `input/answers/`에서도 백필 가능. 샤드는 `merge_exam_analysis_shards.py`로 병합

## CSV 필드 데이터 출처

| 필드 | 출처 |
|------|------|
| `성취기준_코드` | classification.json (있을 때). 대괄호 없이 코드만 |
| `정답` | classification.json `answer` 우선. 없으면 exam_analysis.json `answer` 또는 `input/answers/` 정답지 (`1`~`5`) |
| `과목` | PDF/파일명 (`역사` / `한국사`) |
| `시대`, `문제형식`, `세부형식`, `자료핵심요소`, `정답핵심요소` | exam_analysis.json (AI) |

## 내용분류표 파일 매칭

| 방식 | 규칙 |
|------|------|
| 자동 | `검사지.pdf` stem에서 `검사지` → `내용분류표` 치환 후 `input/classification/` 탐색 |
| 수동 | `input/classification/manifest.json`의 `pairs` 배열 |

## text.json 구조 (`output/work/<pdf_stem>/text.json`)

```json
{
  "source_pdf": "input/pdf/example.pdf",
  "pdf_stem": "example",
  "pages": [
    {
      "page": 1,
      "source": "text",
      "page_image": "output/work/example/pages/page_001.png",
      "blocks": [
        {
          "text": "15. 다음 자료를 읽고...",
          "bbox": [50.0, 100.0, 550.0, 800.0]
        }
      ]
    }
  ]
}
```

- `bbox`: `[x0, y0, x1, y1]` — 페이지 PNG와 동일 좌표계 (픽셀)
- `source`: `text` | `ocr` | `image_only` (`--skip-ocr`) | `ocr_failed`
- 권장: `dpi` 필드 (렌더/OCR 스케일 일치)

## achievement_index.json 구조

```json
{
  "entries": [
    {
      "code": "9역01-01",
      "text": "성취기준 원문...",
      "source_file": "성취기준/평가기준+역사과+5차+1205.pdf",
      "curriculum": "2015",
      "school_level": "중학"
    },
    {
      "code": "10한사1-01-01",
      "text": "성취기준 원문...",
      "source_file": "성취기준/2. 고등학교 한국사 교육과정 성취기준(2022개정교육과정).pdf",
      "curriculum": "2022",
      "school_level": "고등"
    }
  ]
}
```
