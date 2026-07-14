# 로컬 ↔ GitHub ↔ Cursor Cloud 역할

| 환경 | 역할 |
|------|------|
| **GitHub `main` (또는 작업 브랜치)** | 코드·CSV·정답지 메타의 기준 |
| **로컬 `C:\HisPastExamAnalysist`** | PDF·이미지·분석 실행. 변경은 커밋 후 push |
| **Cursor Cloud** | PR용 코드 작업. CSV 최종 확인은 로컬에서 |

## 로컬에 원격 최신 반영

```powershell
cd C:\HisPastExamAnalysist
powershell -ExecutionPolicy Bypass -File .\scripts\sync_from_github.ps1
```

스크립트가 아직 없으면 (최초 1회):

```powershell
cd C:\HisPastExamAnalysist
git fetch origin
git stash push -u -m "before-sync"
git merge --no-edit origin/cursor/csv-answer-column-afa5
# 헤더에 ,정답, 있는지 확인
Get-Content .\output\data\exam_mock.csv -TotalCount 1 -Encoding UTF8
```

`input/pdf`, `output/images`, `output/work`는 gitignore라 **원격에 없고 로컬에만** 있습니다.
