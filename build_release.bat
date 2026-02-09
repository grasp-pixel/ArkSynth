@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ArkSynth 배포 패키지 빌드 스크립트
:: 사용법: build_release.bat

set "PROJECT_ROOT=%~dp0"
set "FRONTEND_DIR=%PROJECT_ROOT%src\frontend"

:: version.json에서 버전 읽기
for /f "delims=" %%a in ('powershell -NoProfile -Command "(Get-Content '%PROJECT_ROOT%version.json' | ConvertFrom-Json).version"') do (
    set "VERSION=%%a"
)
if not defined VERSION set "VERSION=0.0.0"

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
echo [1/6] Electron 앱 빌드 중...

:: package.json 버전 동기화 (포맷 유지, BOM 방지)
powershell -NoProfile -Command "$f='%FRONTEND_DIR%\package.json'; $c=[IO.File]::ReadAllText($f); $c=$c -replace '\"version\":\s*\".*?\"','\"version\": \"%VERSION%\"'; [IO.File]::WriteAllText($f,$c)"

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
echo [2/6] 배포 폴더 구성 중...

:: 기존 폴더 정리
if exist "%RELEASE_DIR%" rmdir /s /q "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%\app"

:: Python 소스 복사 (app/ 하위)
xcopy "%PROJECT_ROOT%src\core" "%RELEASE_DIR%\app\src\core\" /e /i /q /y >nul
xcopy "%PROJECT_ROOT%src\tools" "%RELEASE_DIR%\app\src\tools\" /e /i /q /y >nul
if exist "%PROJECT_ROOT%src\__init__.py" copy "%PROJECT_ROOT%src\__init__.py" "%RELEASE_DIR%\app\src\" >nul

:: 프로젝트 설정 파일 (app/ 하위)
copy "%PROJECT_ROOT%pyproject.toml" "%RELEASE_DIR%\app\" >nul
copy "%PROJECT_ROOT%uv.lock" "%RELEASE_DIR%\app\" >nul
copy "%PROJECT_ROOT%version.json" "%RELEASE_DIR%\app\" >nul

:: 실행 스크립트 (루트에 배치)
copy "%PROJECT_ROOT%start.bat" "%RELEASE_DIR%\" >nul

:: README (루트에 배치)
copy "%PROJECT_ROOT%README.txt" "%RELEASE_DIR%\" >nul 2>&1

:: Electron portable exe 복사 (app/ 하위)
set "EXE_FOUND=0"
for %%f in ("%FRONTEND_DIR%\release\ArkSynth.exe") do (
    if exist "%%f" (
        copy "%%f" "%RELEASE_DIR%\app\" >nul
        set "EXE_FOUND=1"
    )
)
if "!EXE_FOUND!"=="0" (
    echo [경고] ArkSynth.exe를 찾을 수 없습니다. release 폴더를 확인하세요.
    :: 다른 이름으로 빌드되었을 수 있으므로 exe 파일 검색
    for %%f in ("%FRONTEND_DIR%\release\*.exe") do (
        echo   발견: %%~nxf
        copy "%%f" "%RELEASE_DIR%\app\ArkSynth.exe" >nul
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
echo [3/6] zip 압축 중...

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
:: 4. 업데이트 패키지 생성
:: ──────────────────────────────────────────────
echo [4/6] 업데이트 패키지 생성 중...

set "UPDATE_DIR=%PROJECT_ROOT%release\_update_temp"
set "UPDATE_ZIP=%PROJECT_ROOT%release\ArkSynth-%VERSION%-update.zip"

if exist "%UPDATE_DIR%" rmdir /s /q "%UPDATE_DIR%"
mkdir "%UPDATE_DIR%\app"

:: app/ 내용만 복사 (start.bat, README 제외)
xcopy "%RELEASE_DIR%\app" "%UPDATE_DIR%\app\" /e /i /q /y >nul

:: __pycache__ 정리
for /d /r "%UPDATE_DIR%" %%d in (__pycache__) do (
    if exist "%%d" rmdir /s /q "%%d"
)

if exist "%UPDATE_ZIP%" del "%UPDATE_ZIP%"
powershell -Command "Compress-Archive -Path '%UPDATE_DIR%\app' -DestinationPath '%UPDATE_ZIP%' -Force"
if !errorlevel! neq 0 (
    echo [경고] 업데이트 패키지 압축에 실패했습니다.
) else (
    echo [완료] %UPDATE_ZIP%
)

:: 임시 폴더 정리
if exist "%UPDATE_DIR%" rmdir /s /q "%UPDATE_DIR%"
echo.

:: ──────────────────────────────────────────────
:: 5. update-manifest.json 생성
:: ──────────────────────────────────────────────
echo [5/6] update-manifest.json 생성 중...

set "MANIFEST_PATH=%PROJECT_ROOT%release\update-manifest.json"

:: SHA256 계산
for /f "delims=" %%h in ('powershell -Command "(Get-FileHash '%UPDATE_ZIP%' -Algorithm SHA256).Hash.ToLower()"') do (
    set "SHA256=%%h"
)

:: 파일 크기
for %%f in ("%UPDATE_ZIP%") do set "FILESIZE=%%~zf"

:: manifest 생성
powershell -Command ^
    "$m = @{ version='%VERSION%'; minimum_version='0.1.0'; sha256='!SHA256!'; filename='ArkSynth-%VERSION%-update.zip'; size=[int]'!FILESIZE!'; changelog='ArkSynth v%VERSION% 업데이트' }; " ^
    "$json = $m | ConvertTo-Json; " ^
    "[IO.File]::WriteAllText('%MANIFEST_PATH%', $json)"

if exist "%MANIFEST_PATH%" (
    echo [완료] %MANIFEST_PATH%
) else (
    echo [경고] manifest 생성 실패
)
echo.

:: ──────────────────────────────────────────────
:: 6. 결과 요약
:: ──────────────────────────────────────────────
echo [6/6] 빌드 결과:
echo   배포 폴더:    %RELEASE_DIR%
if exist "%ZIP_PATH%" echo   전체 패키지:  %ZIP_PATH%
if exist "%UPDATE_ZIP%" echo   업데이트 패키지: %UPDATE_ZIP%
if exist "%MANIFEST_PATH%" echo   매니페스트:   %MANIFEST_PATH%
echo.

:: 크기 확인
if exist "%ZIP_PATH%" for %%f in ("%ZIP_PATH%") do echo   full.zip 크기: %%~zf bytes
if exist "%UPDATE_ZIP%" for %%f in ("%UPDATE_ZIP%") do echo   update.zip 크기: %%~zf bytes

echo.
echo 빌드 완료. GitHub Release에 아래 파일을 업로드하세요:
if exist "%ZIP_PATH%" echo   - %ZIP_PATH%
if exist "%UPDATE_ZIP%" echo   - %UPDATE_ZIP%
if exist "%MANIFEST_PATH%" echo   - %MANIFEST_PATH%
echo.
pause
endlocal
