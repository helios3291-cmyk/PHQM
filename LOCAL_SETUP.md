# 로컬 작업 환경 설정 (E:\HisPastExamAnalysist)

운영 데이터(PNG·CSV)는 **로컬 PC**에서 만들고, **GitHub(CSV·코드)** + **Google Drive(PNG)** 로 올려 Streamlit Cloud에서 사용합니다.

이 문서는 Windows에서 `E:\HisPastExamAnalysist`를 정본 작업 폴더로 쓸 때의 초기 설정·이전·검증 절차입니다.  
다른 드라이브(`D:\...`)도 동일하며, 경로만 바꾸면 됩니다.

---

## 1. 역할 구분

| 위치 | 하는 일 | Git에 올림? |
|------|---------|-------------|
| **E:\HisPastExamAnalysist** | PDF 분석, 크롭, CSV 편집, 로컬 Streamlit 테스트 | CSV·코드만 |
| **GitHub PHQM** | 코드·CSV 동기화 | — |
| **Google Drive PHQM_images** | 문항 PNG 보관 | 아니오 |
| **Streamlit Cloud** | 조합 시험지 UI (분석 없음) | — |

---

## 2. 사전 준비 체크리스트

- [ ] Python 3.10+ 설치 (`python --version`)
- [ ] Git 설치 (`git --version`)
- [ ] [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) + **kor** 언어팩 (스캔 PDF용)
- [ ] Cursor 설치 후 **폴더를 `E:\HisPastExamAnalysist`로 열기**
- [ ] (선택) Google Drive 데스크톱 앱 — PNG 대량 업로드용

---

## 3. 저장소 연결

### A. 새로 클론

```powershell
git clone https://github.com/helios3291-cmyk/PHQM.git E:\HisPastExamAnalysist
cd E:\HisPastExamAnalysist
```

### B. 이미 폴더가 있는 경우

```powershell
cd E:\HisPastExamAnalysist
git remote -v
# origin 이 https://github.com/helios3291-cmyk/PHQM.git 인지 확인

git fetch origin
git checkout main
git pull origin main
```

### C. 예전 `C:\HisPastExamAnalysist`에서 이전

Git에 없는 데이터만 복사합니다 (`.gitignore` 항목).

| 복사할 것 | 대상 |
|-----------|------|
| `input\pdf\` | `E:\...\input\pdf\` |
| `input\classification\` | `E:\...\input\classification\` |
| `output\images\` | `E:\...\output\images\` |
| `output\work\` | (선택) `E:\...\output\work\` |
| `성취기준\` | `E:\...\성취기준\` |
| `.streamlit\secrets.toml` | (있으면) 동일 경로 — **git에 올리지 마세요** |

이후 **E:만** Cursor 작업 폴더로 사용하는 것을 권장합니다 (C:와 이중 작업 시 CSV·PNG 버전이 어긋날 수 있음).

---

## 4. Python 가상환경

```powershell
cd E:\HisPastExamAnalysist
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-compose.txt
```

분석 파이프라인: `requirements.txt`  
조합 Streamlit UI: `requirements-compose.txt` (위에서 둘 다 설치 권장)

---

## 5. 폴더 구조 확인

```
E:\HisPastExamAnalysist\
├── compose_app.py
├── lib\drive_images.py
├── input\
│   ├── pdf\                 ← 기출 PDF
│   └── classification\      ← 내용분류표
├── output\
│   ├── data\                ← exam_basic.csv, exam_mock.csv, exam_hancert.csv
│   ├── images\              ← basic\, mock\, hancert\ (로컬 전용)
│   └── work\                ← text.json, 중간 산출물 (로컬 전용)
├── 성취기준\
├── assets\fonts\            ← PDF 한글 폰트 (Cloud와 동일)
└── .cursor\skills\history-exam-analyst\
```

최초 1회 — 성취기준 인덱스:

```powershell
python .cursor/skills/history-exam-analyst/scripts/index_achievement.py
```

---

## 6. 로컬에서 동작 확인

### 6-1. 스모크 테스트 (전체 파이프라인 샘플)

```powershell
cd E:\HisPastExamAnalysist
.\.venv\Scripts\activate
python .cursor/skills/history-exam-analyst/scripts/run_smoke_test.py
```

### 6-2. CSV 검증

```powershell
python .cursor/skills/history-exam-analyst/scripts/validate_output.py --all
```

### 6-3. 조합 UI (로컬, Drive 없이)

`output\images`가 있으면 Drive secrets 없이도 미리보기·PDF 생성이 됩니다.

```powershell
.\run_compose_app.bat
# 또는
.\.venv\Scripts\streamlit.exe run compose_app.py
```

브라우저에서 후보 목록·바구니·PDF 생성이 되는지 확인합니다.

### 6-4. (선택) Drive 연동 로컬 테스트

```powershell
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
# secrets.toml 편집 후 Streamlit 실행 → 사이드바 「연결 테스트」
```

자세한 Drive·Cloud 설정: [DEPLOY.md](DEPLOY.md)

---

## 7. 일상 작업 흐름 (신규 기출 추가)

1. **입력**: `input\pdf\` + (권장) `input\classification\`
2. **분석** (Cursor 에이전트 또는 스크립트):
   - `prepare_pdf.py` → `extract_questions.py` → `apply_exam_batch.py`
   - 한능검: `compute_hancert_crop_bbox.py` 경로
3. **검증**: `validate_output.py --profile basic|mock|hancert`
4. **GitHub**: `output\data\exam_*.csv` 변경분 commit & push
5. **Drive**: `output\images\{basic|mock|hancert}\` 새 PNG를 `PHQM_images\` 동일 구조로 업로드
6. **Cloud**: 자동 재배포 후 앱에서 문항·이미지·PDF 확인

CSV `이미지경로` 예: `output/images/basic/2024_고1_역사_가형_1.png`  
→ Drive에서는 `PHQM_images/basic/2024_고1_역사_가형_1.png`

---

## 8. 자주 쓰는 Git 명령

```powershell
cd E:\HisPastExamAnalysist
git status
git add output/data/exam_basic.csv   # 예: 변경한 CSV만
git commit -m "Add 2025 mock exam rows"
git pull origin main
git push origin main
```

PNG는 `.gitignore`에 있으므로 `git add output/images`로 올라가지 않습니다 (의도된 동작).

---

## 9. 문제 해결

| 증상 | 확인 |
|------|------|
| `tesseract` 오류 | PATH, `kor` 언어팩 |
| 크롭 bbox 어긋남 | `validate_crops.py`, `output/work/.../crop_warnings.json` |
| Streamlit `drive_images` import 실패 | `lib/drive_images.py` 존재, `pip install -r requirements-compose.txt` |
| 로컬에 이미지 있는데 Cloud에서만 안 보임 | Drive 업로드·폴더 ID·서비스 계정 공유 ([DEPLOY.md](DEPLOY.md)) |
| C:와 E: 데이터 불일치 | 한쪽만 정본으로 정하고 `git pull` + 폴더 복사로 맞춤 |

---

## 10. 관련 문서

- [README.md](README.md) — 스크립트·스키마 개요
- [DEPLOY.md](DEPLOY.md) — Streamlit Cloud + Google Drive 배포
- `.cursor/skills/history-exam-analyst/SKILL.md` — 에이전트 분석 절차
