@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\streamlit.exe" (
    echo [오류] .venv\Scripts\streamlit.exe 가 없습니다.
    echo 먼저 가상환경을 만들고 requirements를 설치하세요.
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

echo 기출 조합 시험지 Streamlit을 시작합니다...
echo 브라우저가 열리면 이 창은 닫지 마세요. 종료하려면 Ctrl+C
echo.
".venv\Scripts\streamlit.exe" run compose_app.py
if errorlevel 1 pause
