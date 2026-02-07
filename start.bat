@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

title ArkSynth

set "PYTHONIOENCODING=utf-8"
set "BACKEND_HOST=127.0.0.1"
set "BACKEND_PORT=8000"

:: ──────────────────────────────────────────────
:: 1. uv 설치 확인
:: ──────────────────────────────────────────────
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo [ArkSynth] uv가 설치되어 있지 않습니다. 자동 설치를 시작합니다...
    powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if !errorlevel! neq 0 (
        echo [ArkSynth] uv 설치에 실패했습니다.
        pause
        exit /b 1
    )
    :: PATH 갱신
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    echo [ArkSynth] uv 설치 완료.
)

:: ──────────────────────────────────────────────
:: 2. Python + 의존성 설치
:: ──────────────────────────────────────────────
echo [ArkSynth] 의존성을 확인합니다...
uv sync
if %errorlevel% neq 0 (
    echo [ArkSynth] 의존성 설치에 실패했습니다.
    pause
    exit /b 1
)

:: ──────────────────────────────────────────────
:: 3. 백엔드 서버 시작 (백그라운드)
:: ──────────────────────────────────────────────
echo [ArkSynth] 백엔드 서버를 시작합니다...
start /b "" uv run uvicorn core.backend.server:create_app --factory --host %BACKEND_HOST% --port %BACKEND_PORT%
set "BACKEND_PID="

:: 서버 PID 확보 (가장 최근 uvicorn 프로세스)
timeout /t 2 /nobreak >nul
for /f "tokens=2" %%a in ('tasklist /fi "imagename eq python.exe" /fo list 2^>nul ^| findstr "PID"') do (
    set "BACKEND_PID=%%a"
)

:: ──────────────────────────────────────────────
:: 4. Health check 대기
:: ──────────────────────────────────────────────
echo [ArkSynth] 서버 준비를 기다리는 중...
set "RETRY=0"
set "MAX_RETRY=30"

:health_loop
if !RETRY! geq !MAX_RETRY! (
    echo [ArkSynth] 서버 시작 시간이 초과되었습니다.
    goto :cleanup
)

powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://%BACKEND_HOST%:%BACKEND_PORT%/health' -TimeoutSec 2 -UseBasicParsing; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if !errorlevel! equ 0 (
    echo [ArkSynth] 서버 준비 완료.
    goto :start_app
)

set /a RETRY+=1
timeout /t 1 /nobreak >nul
goto :health_loop

:: ──────────────────────────────────────────────
:: 5. Electron 앱 실행
:: ──────────────────────────────────────────────
:start_app
echo [ArkSynth] 앱을 시작합니다...

if exist "%~dp0ArkSynth.exe" (
    start "" "%~dp0ArkSynth.exe"
) else (
    echo [ArkSynth] ArkSynth.exe를 찾을 수 없습니다.
    echo [ArkSynth] 브라우저에서 http://%BACKEND_HOST%:%BACKEND_PORT%/docs 로 접속하세요.
)

:: ──────────────────────────────────────────────
:: 6. 종료 대기
:: ──────────────────────────────────────────────
echo.
echo [ArkSynth] 종료하려면 아무 키나 누르세요...
pause >nul

:cleanup
echo [ArkSynth] 서버를 종료합니다...
:: uvicorn 프로세스 종료
taskkill /f /t /fi "windowtitle eq ArkSynth" >nul 2>&1
if defined BACKEND_PID (
    taskkill /f /pid !BACKEND_PID! >nul 2>&1
)
:: 남은 uvicorn 프로세스 정리
for /f "tokens=2" %%a in ('wmic process where "commandline like '%%uvicorn%%core.backend.server%%'" get processid 2^>nul ^| findstr /r "[0-9]"') do (
    taskkill /f /pid %%a >nul 2>&1
)

echo [ArkSynth] 종료되었습니다.
endlocal
