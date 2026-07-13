# 역사 데이터 에이전트

고등학교 역사 기출문제 PDF를 분석하여 메타데이터를 CSV로 저장하고, 문항 이미지를 PNG로 크롭하는 Cursor 프로젝트 에이전트입니다.

## 폴더 구조

```
HisPastExamAnalysist/
├── 성취기준/          # 교육과정 성취기준 원문 (txt, md, pdf, docx)
├── input/
│   ├── pdf/           # 기출 PDF 원본
│   └── classification/  # 내용분류표 PDF (검사지와 짝)
├── output/
│   ├── data/          # exam_basic.csv / exam_mock.csv / exam_hancert.csv
│   ├── images/        # basic/ · mock/ · hancert/ 하위 문항 PNG
│   └── work/          # 전처리 중간 산출물
└── .cursor/
    ├── rules/         # 프로젝트 규칙
    └── skills/history-exam-analyst/  # 에이전트 스킬 + 스크립트
```

## 설치

### 1. Python 패키지

```powershell
cd c:\HisPastExamAnalysist
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Tesseract OCR (스캔본 PDF용)

스캔본 PDF 처리를 위해 [Tesseract Windows 설치](https://github.com/UB-Mannheim/tesseract/wiki)가 필요합니다.

설치 후 한국어 데이터(`kor`)가 포함되어 있는지 확인하세요. PATH에 `tesseract.exe`가 등록되어 있어야 합니다.

### 3. Poppler (pdf2image 의존, 선택)

`pdf2image`를 직접 사용할 경우 Poppler가 필요할 수 있습니다. 본 프로젝트는 PyMuPDF로 페이지 렌더링을 수행하므로 Poppler 없이도 동작합니다.

## 사전 준비

1. `성취기준/` 폴더에 교육과정 성취기준 파일을 복사합니다.
2. 기출 PDF를 `input/pdf/`에 넣습니다.
3. (권장) 내용분류표 PDF를 `input/classification/`에 넣습니다. 파일명은 검사지와 동일 stem에서 `검사지`→`내용분류표`로 치환합니다.

### 성취기준 인덱스 생성 (최초 1회 또는 파일 변경 시)

```powershell
python .cursor/skills/history-exam-analyst/scripts/index_achievement.py
```

결과: `output/work/achievement_index.json`

## Cursor에서 사용하기

Cursor Agent 채팅에서 다음과 같이 요청합니다:

```
@history-exam-analyst 2024 고1 한국사 기출 PDF에서 15번 문항 분석해줘
```

에이전트가 자동으로:
1. PDF 전처리 (`prepare_pdf.py`)
2. 성취기준 매핑
3. 문제 형식·시대 분류 (모호 시 확인 질문)
4. 문항 이미지 크롭 (`crop_question.py`)
5. CSV 저장 (`append_csv.py`)
6. 검증 (`validate_output.py`)

## 기출 조합 시험지 (로컬 웹 UI)

분석된 CSV와 크롭 PNG로 성취기준·시대·키워드·프로파일을 조합해 A4 2단 문제지를 만듭니다.

**탐색기에서 실행:** 프로젝트 폴더의 `run_compose_app.bat`을 더블클릭하면 됩니다.

```powershell
pip install -r requirements-compose.txt
.\.venv\Scripts\streamlit.exe run compose_app.py
# 또는
.\run_compose_app.bat
```

**GitHub + Google Drive 배포:** [DEPLOY.md](DEPLOY.md) 및 https://github.com/helios3291-cmyk/PHQM

1. 사이드바에서 필터를 0개 이상 지정 (모두 선택 사항, AND 결합)
2. 후보에서 바구니에 추가·순서 변경·삭제
3. **PDF 생성** → `output/composed/`에 문제지·정답지 저장 및 다운로드

기본 배치는 페이지당 4문항(2단×2), 문항 높이에 따라 3·2문항으로 자동 조정됩니다.

## 수동 스크립트 사용

### PDF 전처리

```powershell
python .cursor/skills/history-exam-analyst/scripts/prepare_pdf.py input/pdf/2024_고1_한국사.pdf
```

### 문항 추출 및 크롭 (2단 레이아웃)

```powershell
python .cursor/skills/history-exam-analyst/scripts/extract_questions.py
python .cursor/skills/history-exam-analyst/scripts/validate_crops.py --pdf "(2024)고2한국사(가형)검사지.pdf"
python .cursor/skills/history-exam-analyst/scripts/apply_exam_batch.py
```

이미지만 재크롭: `apply_exam_batch.py --crop-only`

### 내용분류표 인덱싱

```powershell
python .cursor/skills/history-exam-analyst/scripts/index_classification.py `
  --pdf input/classification/(2025)고2한국사(나형)내용분류표.pdf `
  --exam-stem "(2025)고2한국사(나형)검사지"
```

### 문항 이미지 크롭 (수동)

```powershell
python .cursor/skills/history-exam-analyst/scripts/crop_question.py `
  --page-image output/work/2024_고1_한국사/pages/page_003.png `
  --bbox 50,100,550,800 `
  --year 2024 --grade 고1 --subject 한국사 --number 15
```

### CSV 행 추가

```powershell
python .cursor/skills/history-exam-analyst/scripts/append_csv.py `
  --profile basic `
  --year 2024 --grade 고1 --subject 한국사 --exam-type 가형 --number 15 `
  --achievement-code "10한사1-01-01" `
  --era "조선" --format "자료 제시형" --sub-format "단일 자료" `
  --source-key "임진왜란, 이순신" --answer-key "해전 승리" `
  --image output/images/basic/2024_고1_한국사_가형_15.png `
  --source-pdf input/pdf/2024_고1_한국사.pdf
```

### 출력 검증

```powershell
python .cursor/skills/history-exam-analyst/scripts/validate_output.py --profile basic
# 또는 --all
```

## 출력 형식

### CSV (`output/data/`)

프로파일별 파일:

| 파일 | 시험 |
|------|------|
| `exam_basic.csv` | 기초학력 진단·향상도 |
| `exam_mock.csv` | 학평·모평·수능 |
| `exam_hancert.csv` | 한국사능력검정시험 |

컬럼: 연도, 학년, 과목, 문형, 문항번호, 성취기준_코드, 시대, 문제형식, 세부형식, 자료핵심요소, 정답핵심요소, 이미지경로, 원본PDF, 처리일시

연도: 학평·기초학력은 `2026`처럼 표기연도만. 모평·수능은 `2026(2027)`처럼 `시행연도(학년도)`.

(`exam_questions.csv`는 deprecated 호환 복사본)

### 교육과정·성취기준 참조

| 학교급 | 교육과정 | 참조 파일 |
|--------|---------|-----------|
| 중학교 | 2015 개정 | `성취기준/평가기준+역사과+5차+1205.pdf` |
| 고등학교 | 2022 개정 | `성취기준/2. 고등학교 한국사 교육과정 성취기준(2022개정교육과정).pdf` |

고등학교 문항에는 2015 개정 성취기준을 적용하지 않습니다.

### 이미지 (`output/images/{basic|mock|hancert}/`)

파일명: `{연도}_{학년}_{과목}_{문형}_{문항번호}.png`

## 트러블슈팅

| 문제 | 해결 |
|------|------|
| OCR 결과가 비어 있음 | Tesseract 설치 및 `kor` 언어팩 확인 |
| bbox가 맞지 않음 | `validate_crops.py`로 미리보기 확인, `crop_warnings.json` 검토 |
| 성취기준 매핑 실패 | `성취기준/` 파일 형식·코드 패턴 확인 후 인덱스 재생성 |
| CSV 중복 경고 | `--force`로 덮어쓰기 또는 기존 행 삭제 |

## 스모크 테스트

```powershell
python .cursor/skills/history-exam-analyst/scripts/run_smoke_test.py
```

샘플 PDF·성취기준으로 전체 파이프라인을 검증합니다.
