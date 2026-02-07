@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ArkSynth 배포 패키지 빌드 스크립트
:: 사용법: build_release.bat

set "PROJECT_ROOT=%~dp0"
set "FRONTEND_DIR=%PROJECT_ROOT%src\frontend"
set "VERSION=0.1.0"
set "RELEASE_NAME=ArkSynth-v%VERSION%"
set "RELEASE_DIR=%PROJECT_ROOT%release\%RELEASE_NAME%"

echo ============================================
echo  ArkSynth 배포 패키지 빌드
echo  버전: %VERSION%
echo ============================================
echo.

:: ──────────────────────────────────────────────
:: 1. Electron 빌드
:: ──────────────────────────────────────────────
echo [1/4] Electron 앱 빌드 중...

where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo [오류] npm이 설치되어 있지 않습니다.
    exit /b 1
)

pushd "%FRONTEND_DIR%"
call npm run build:dist
if !errorlevel! neq 0 (
    echo [오류] Electron 빌드에 실패했습니다.
    popd
    exit /b 1
)
popd

echo [완료] Electron 빌드 성공.
echo.

:: ──────────────────────────────────────────────
:: 2. 배포 폴더 구성
:: ──────────────────────────────────────────────
echo [2/4] 배포 폴더 구성 중...

:: 기존 폴더 정리
if exist "%RELEASE_DIR%" rmdir /s /q "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%"

:: Python 소스 복사
xcopy "%PROJECT_ROOT%src\core" "%RELEASE_DIR%\src\core\" /e /i /q /y >nul
if exist "%PROJECT_ROOT%src\__init__.py" copy "%PROJECT_ROOT%src\__init__.py" "%RELEASE_DIR%\src\" >nul

:: 프로젝트 설정 파일
copy "%PROJECT_ROOT%pyproject.toml" "%RELEASE_DIR%\" >nul
copy "%PROJECT_ROOT%uv.lock" "%RELEASE_DIR%\" >nul

:: 실행 스크립트
copy "%PROJECT_ROOT%start.bat" "%RELEASE_DIR%\" >nul

:: README
copy "%PROJECT_ROOT%README.txt" "%RELEASE_DIR%\" >nul 2>&1

:: Electron portable exe 복사
set "EXE_FOUND=0"
for %%f in ("%FRONTEND_DIR%\release\ArkSynth.exe") do (
    if exist "%%f" (
        copy "%%f" "%RELEASE_DIR%\" >nul
        set "EXE_FOUND=1"
    )
)
if "!EXE_FOUND!"=="0" (
    echo [경고] ArkSynth.exe를 찾을 수 없습니다. release 폴더를 확인하세요.
    :: 다른 이름으로 빌드되었을 수 있으므로 exe 파일 검색
    for %%f in ("%FRONTEND_DIR%\release\*.exe") do (
        echo   발견: %%~nxf
        copy "%%f" "%RELEASE_DIR%\ArkSynth.exe" >nul
        set "EXE_FOUND=1"
        goto :exe_done
    )
)
:exe_done

:: __pycache__ 정리
for /d /r "%RELEASE_DIR%" %%d in (__pycache__) do (
    if exist "%%d" rmdir /s /q "%%d"
)

echo [완료] 배포 폴더 구성 완료.
echo.

:: ──────────────────────────────────────────────
:: 3. zip 압축
:: ──────────────────────────────────────────────
echo [3/4] zip 압축 중...

set "ZIP_PATH=%PROJECT_ROOT%release\%RELEASE_NAME%.zip"
if exist "%ZIP_PATH%" del "%ZIP_PATH%"

powershell -Command "Compress-Archive -Path '%RELEASE_DIR%' -DestinationPath '%ZIP_PATH%' -Force"
if !errorlevel! neq 0 (
    echo [경고] zip 압축에 실패했습니다. 폴더 배포를 사용하세요.
) else (
    echo [완료] %ZIP_PATH%
)
echo.

:: ──────────────────────────────────────────────
:: 4. 결과 요약
:: ──────────────────────────────────────────────
echo [4/4] 빌드 결과:
echo   폴더: %RELEASE_DIR%
if exist "%ZIP_PATH%" echo   압축: %ZIP_PATH%
echo.

:: 크기 확인
for %%f in ("%ZIP_PATH%") do echo   zip 크기: %%~zf bytes

echo.
echo 빌드 완료.
pause
endlocal
