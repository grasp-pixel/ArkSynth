@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

title ArkSynth

set "PYTHONIOENCODING=utf-8"
set "UV_LINK_MODE=copy"
set "BACKEND_HOST=127.0.0.1"
set "BACKEND_PORT=8000"
set "START_DIR=%~dp0"

REM === 배포 구조 감지: app/ 폴더가 있으면 그 안에서 실행 ===
set "APP_DIR=%START_DIR%"
if exist "%START_DIR%app\pyproject.toml" (
    set "APP_DIR=%START_DIR%app\"
)
cd /d "%APP_DIR%"

REM === 0. 잔여물 정리 ===
if exist "%APP_DIR%_restart" del "%APP_DIR%_restart" >nul 2>&1

:apply_update
REM === 1. 대기 중인 업데이트 적용 ===
if exist "%APP_DIR%_pending_update\" (
    echo [ArkSynth] 대기 중인 업데이트를 적용합니다...

    REM src/core 교체
    if exist "%APP_DIR%_pending_update\src\core" (
        if exist "%APP_DIR%src\core" rmdir /s /q "%APP_DIR%src\core"
        xcopy "%APP_DIR%_pending_update\src\core" "%APP_DIR%src\core\" /e /i /q /y >nul
    )

    REM src/tools 교체
    if exist "%APP_DIR%_pending_update\src\tools" (
        if exist "%APP_DIR%src\tools" rmdir /s /q "%APP_DIR%src\tools"
        xcopy "%APP_DIR%_pending_update\src\tools" "%APP_DIR%src\tools\" /e /i /q /y >nul
    )

    REM ArkSynth.exe 교체
    if exist "%APP_DIR%_pending_update\ArkSynth.exe" (
        copy /y "%APP_DIR%_pending_update\ArkSynth.exe" "%APP_DIR%ArkSynth.exe" >nul
    )

    REM version.json, pyproject.toml, uv.lock 교체
    for %%f in (version.json pyproject.toml uv.lock) do (
        if exist "%APP_DIR%_pending_update\%%f" copy /y "%APP_DIR%_pending_update\%%f" "%APP_DIR%%%f" >nul
    )

    REM 스테이징 폴더 정리
    rmdir /s /q "%APP_DIR%_pending_update"
    echo [ArkSynth] 업데이트 적용 완료.
)

REM === 2. uv 설치 확인 ===
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo [ArkSynth] uv가 설치되어 있지 않습니다. 자동 설치를 시작합니다...
    powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if !errorlevel! neq 0 (
        echo [ArkSynth] uv 설치에 실패했습니다.
        pause
        exit /b 1
    )
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    echo [ArkSynth] uv 설치 완료.
)

REM === 3. Python + 의존성 설치 ===
echo [ArkSynth] 의존성을 확인합니다...
uv sync
if %errorlevel% neq 0 (
    echo [ArkSynth] 의존성 설치에 실패했습니다.
    pause
    exit /b 1
)

REM === 4. 백엔드 서버 시작 (백그라운드) ===
echo [ArkSynth] 백엔드 서버를 시작합니다...
start /b "" uv run uvicorn core.backend.server:create_app --factory --host %BACKEND_HOST% --port %BACKEND_PORT%
set "BACKEND_PID="

timeout /t 2 /nobreak >nul
for /f "tokens=2" %%a in ('tasklist /fi "imagename eq python.exe" /fo list 2^>nul ^| findstr "PID"') do (
    set "BACKEND_PID=%%a"
)

REM === 5. Health check 대기 ===
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

REM === 6. Electron 앱 실행 ===
:start_app
echo [ArkSynth] 앱을 시작합니다...

if exist "%APP_DIR%ArkSynth.exe" (
    start "" "%APP_DIR%ArkSynth.exe"
) else (
    echo [ArkSynth] ArkSynth.exe를 찾을 수 없습니다.
    echo [ArkSynth] 브라우저에서 http://%BACKEND_HOST%:%BACKEND_PORT%/docs 로 접속하세요.
)

REM === 7. 종료 대기 ===
if exist "%APP_DIR%ArkSynth.exe" (
    echo [ArkSynth] 앱을 종료하면 서버도 자동으로 종료됩니다.
    :wait_app
    timeout /t 3 /nobreak >nul
    tasklist /fi "imagename eq ArkSynth.exe" 2>nul | findstr /i "ArkSynth.exe" >nul
    if !errorlevel! equ 0 goto :wait_app

    REM exe 종료됨 — 재시작 플래그 확인
    if exist "%APP_DIR%_restart" (
        del "%APP_DIR%_restart" >nul 2>&1
        echo [ArkSynth] 재시작 중...
        goto :restart
    )
) else (
    echo.
    echo [ArkSynth] Ctrl+C를 누르면 서버가 종료됩니다.
    :wait_ctrlc
    timeout /t 60 /nobreak >nul
    goto :wait_ctrlc
)

:cleanup
echo [ArkSynth] 서버를 종료합니다...
call :kill_backend
echo [ArkSynth] 종료되었습니다.
endlocal
exit

:restart
REM 백엔드 종료 후 업데이트 적용 → 재시작
echo [ArkSynth] 서버를 종료합니다...
call :kill_backend
timeout /t 1 /nobreak >nul
goto :apply_update

:kill_backend
taskkill /f /t /fi "windowtitle eq ArkSynth" >nul 2>&1
if defined BACKEND_PID (
    taskkill /f /pid !BACKEND_PID! >nul 2>&1
)
for /f "tokens=2" %%a in ('wmic process where "commandline like '%%uvicorn%%core.backend.server%%'" get processid 2^>nul ^| findstr /r "[0-9]"') do (
    taskkill /f /pid %%a >nul 2>&1
)
exit /b
