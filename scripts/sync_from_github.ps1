# 로컬 C:\HisPastExamAnalysist ← GitHub 최신 통합
# 사용:  PowerShell에서
#   cd C:\HisPastExamAnalysist
#   powershell -ExecutionPolicy Bypass -File .\scripts\sync_from_github.ps1

$ErrorActionPreference = "Stop"
$Repo = "C:\HisPastExamAnalysist"
$Branch = "cursor/csv-answer-column-afa5"  # 정답 컬럼·백필 포함. main 머지 후면 main 으로 바꿔도 됨.

if (-not (Test-Path $Repo)) {
    Write-Error "폴더 없음: $Repo"
}

Set-Location $Repo
Write-Host "== git status (통합 전) ==" -ForegroundColor Cyan
git status -sb

$dirty = git status --porcelain
if ($dirty) {
    Write-Host ""
    Write-Host "로컬에 커밋되지 않은 변경이 있습니다. 백업 stash 후 진행합니다." -ForegroundColor Yellow
    git stash push -u -m "sync-backup $(Get-Date -Format 'yyyy-MM-ddTHH:mm:ss')"
    Write-Host "stash 완료. 나중에: git stash list / git stash pop" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "== fetch ==" -ForegroundColor Cyan
git fetch origin

# 현재 브랜치에 feature를 merge (로컬 전용 커밋·gitignore 데이터 유지)
$current = (git rev-parse --abbrev-ref HEAD).Trim()
Write-Host "현재 브랜치: $current" -ForegroundColor Cyan

if ($current -eq $Branch) {
    git pull origin $Branch
} else {
    # main 등에서 feature 변경을 가져옴
    git merge --no-edit "origin/$Branch"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "merge 충돌. 해결 후 git merge --continue" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "== CSV 헤더 확인 (정답 컬럼 있어야 함) ==" -ForegroundColor Cyan
Get-ChildItem .\output\data\exam_*.csv | ForEach-Object {
    $h = Get-Content $_.FullName -TotalCount 1 -Encoding UTF8
    $has = $h -match ',정답,'
    "{0}: 정답컬럼={1}" -f $_.Name, $has
    $h
}

Write-Host ""
Write-Host "완료. Gitignore 경로(input/pdf, output/images, output/work)는 원격에 없으므로 로컬 파일이 그대로 유지됩니다." -ForegroundColor Green
