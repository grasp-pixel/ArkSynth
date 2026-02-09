# ArkSynth

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10-3.12](https://img.shields.io/badge/Python-3.10--3.12-3776AB.svg)](https://www.python.org/)
[![Node.js 18+](https://img.shields.io/badge/Node.js-18+-339933.svg)](https://nodejs.org/)
![Platform: Windows](https://img.shields.io/badge/Platform-Windows-0078D6.svg)

[English](README.en.md)

명일방주(Arknights) 스토리 플레이 중 실시간 음성 더빙을 제공하는 앱입니다.
캐릭터별 GPT-SoVITS 음성 모델을 학습하고, 화면 캡처 + OCR로 대사를 인식하여 해당 캐릭터의 음성으로 TTS를 출력합니다.

## 주요 기능

- **스토리 탐색** - 에피소드별 대사 조회, 캐릭터 확인, 다국어 텍스트 지원
- **음성 클로닝** - GPT-SoVITS 기반 제로샷 / 파인튜닝 음성 학습
- **실시간 더빙** - 화면 캡처 → OCR 대사 감지 → 자동 TTS 재생
- **사전 렌더링** - 에피소드 단위 음성 캐시로 품질과 응답속도 향상
- **게임 데이터 관리** - GitHub/PRTS 소스에서 스토리 데이터 자동 다운로드
- **다국어 UI** - 한국어, 일본어, 영어 인터페이스

## 기술 스택

| 영역 | 기술 |
|------|------|
| TTS / 음성 클로닝 | GPT-SoVITS (제로샷 + 파인튜닝) |
| OCR | EasyOCR (ko, ja, en, zh) |
| 백엔드 | Python + FastAPI + asyncio |
| 프론트엔드 | Electron 28 + React 18 + Vite 5 + Tailwind CSS |
| 상태 관리 | Zustand |
| 다국어 | i18next |

## 시스템 요구사항

- **OS**: Windows 10/11 (64-bit)
- **Python**: 3.10 ~ 3.12
- **Node.js**: 18 이상
- **GPU**: NVIDIA GPU (CUDA 지원) 권장
- **RAM**: 8GB 이상
- **디스크**: 10GB 이상 여유 공간

## 설치

### 1. 저장소 클론

```bash
git clone https://github.com/yourname/ArkSynth.git
cd ArkSynth
```

### 2. Python 의존성

```bash
# uv가 없는 경우
pip install uv

# 의존성 설치
uv sync
```

### 3. 프론트엔드 의존성

```bash
cd src/frontend
npm install
```

### 4. GPT-SoVITS

앱 실행 후 설정에서 **GPT-SoVITS 자동 설치** 실행 (약 2GB 다운로드)

### 5. 게임 데이터

이 프로젝트는 게임 에셋을 포함하지 않습니다.

- **스토리 데이터**: 앱 내 설정에서 "게임 데이터 다운로드" 실행
- **음성 파일**: 게임 클라이언트의 에셋번들(.ab)을 `Assets/` 폴더에 배치 후 앱 내 추출 기능 사용

## 실행

### VSCode (권장)

1. VSCode에서 프로젝트 열기
2. `F5` → "Start ArkSynth" 선택
3. 백엔드 + Vite + Electron이 자동 시작됨

### 수동 실행

```bash
cd src/frontend
npm run start
```

## 프로젝트 구조

```text
ArkSynth/
├── src/
│   ├── core/                   # Python 백엔드
│   │   ├── backend/            #   FastAPI 서버 + API 라우터
│   │   ├── cache/              #   렌더링 캐시 관리
│   │   ├── character/          #   캐릭터 데이터 (ID 정규화)
│   │   ├── data/               #   게임 데이터 소스 (GitHub/PRTS)
│   │   ├── interfaces/         #   추상 인터페이스 (OCR)
│   │   ├── models/             #   데이터 모델 (Story, Match)
│   │   ├── ocr/                #   OCR 모듈 (EasyOCR + 매칭)
│   │   ├── story/              #   스토리 파서/로더
│   │   └── voice/              #   음성 처리 + GPT-SoVITS 통합
│   ├── tools/extractor/        # 음성/이미지 추출 CLI
│   └── frontend/               # Electron + React 앱
│       ├── electron/           #   Electron 메인/프리로드
│       └── src/                #   React 컴포넌트 + 상태 관리
├── data/gamedata/              # 게임 데이터 (사용자 다운로드)
├── extracted/                  # 추출된 음성/이미지
├── models/                     # 학습된 음성 모델
└── rendered/                   # 사전 렌더링 캐시
```

## 아키텍처

시스템 설계, 파이프라인 다이어그램, 인터페이스 구조 등은 [DESIGN.md](docs/DESIGN.md)를 참조하세요.

## 면책 조항

이 프로젝트는 Hypergryph/Yostar 및 명일방주(Arknights)와 공식적인 연관이 없는 **비공식 팬 프로젝트**입니다.
"Arknights" 및 "명일방주"는 각각 해당 권리자의 상표입니다.

이 프로젝트는 게임의 스토리 텍스트, 이미지, 음성 등 어떠한 게임 에셋도 포함하지 않습니다.
게임 데이터의 취득 및 사용은 전적으로 사용자의 책임이며, 사용자는 해당 지역의 관련 법률 및 게임 이용약관을 준수해야 합니다.

## 라이선스

MIT License - [LICENSE](LICENSE) 참조

제3자 라이선스 정보는 [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)를 참조하세요.

## 참고 오픈소스

- [ArknightsGameData](https://github.com/Kengxxiao/ArknightsGameData) - 스토리 텍스트 데이터
- [ArknightsStoryTextReader](https://github.com/050644zf/ArknightsStoryTextReader) - 스토리 파서 참고
- [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) - 음성 클로닝/합성 엔진
- [Ark-Unpacker](https://github.com/isHarryh/Ark-Unpacker) - 에셋 추출 (lz4ak.py)
