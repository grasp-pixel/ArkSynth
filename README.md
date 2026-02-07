# ArkSynth

명일방주(Arknights) 스토리 플레이 중 실시간 음성 더빙을 제공하는 앱.
캐릭터별 음성 모델을 학습하고, 화면 캡처로 대사를 인식하여 해당 캐릭터 음성으로 TTS 출력합니다.

## 기능

- 스토리 에피소드 탐색 및 대사 확인
- 캐릭터별 음성 클로닝 (GPT-SoVITS)
- 실시간 TTS 더빙
- 화면 캡처로 대사 자동 인식 (EasyOCR)

## 기술 스택

- **백엔드**: Python, FastAPI
- **프론트엔드**: Electron, React, Vite, Tailwind CSS
- **TTS**: GPT-SoVITS (음성 클로닝)
- **OCR**: EasyOCR (한국어 최적화)

## 설치

### 요구사항

- Python 3.10-3.12
- Node.js 18+
- uv (Python 패키지 관리자)
- GPT-SoVITS (별도 설치)

### 설치

```bash
# 저장소 클론
git clone https://github.com/yourname/ArkSynth.git
cd ArkSynth

# 백엔드 의존성
uv sync

# 프론트엔드 의존성
cd src/frontend
npm install
```

### 게임 데이터 준비

이 프로젝트는 게임 에셋을 포함하지 않습니다. 앱 실행 후:

1. **스토리 데이터**: 앱 내 설정에서 "게임 데이터 다운로드" 실행 (커뮤니티 오픈소스 레포에서 다운로드)
2. **음성 파일**: 게임 클라이언트의 에셋번들(.ab)을 `Assets/` 폴더에 배치 후, 앱 내 추출 기능 사용

## 실행

### VSCode (권장)

1. VSCode에서 프로젝트 열기
2. `F5` → "Start ArkSynth" 선택

### 수동 실행

```bash
cd src/frontend
npm run start
```

## 프로젝트 구조

```
ArkSynth/
├── src/
│   ├── core/           # Python 백엔드
│   ├── tools/          # CLI 도구 (음성 추출 등)
│   └── frontend/       # Electron 앱
├── data/               # 게임 데이터 (사용자가 직접 다운로드)
├── extracted/          # 추출된 음성 파일
└── models/             # 학습된 음성 모델
```

## 면책 조항

이 프로젝트는 Hypergryph/Yostar 및 명일방주(Arknights)와 공식적인 연관이 없는 **비공식 팬 프로젝트**입니다.
"Arknights" 및 "명일방주"는 각각 해당 권리자의 상표입니다.

이 프로젝트는 게임의 스토리 텍스트, 이미지, 음성 등 어떠한 게임 에셋도 포함하지 않습니다.
게임 데이터의 취득 및 사용은 전적으로 사용자의 책임이며, 사용자는 해당 지역의 관련 법률 및 게임 이용약관을 준수해야 합니다.

## 라이선스

MIT License - [LICENSE](LICENSE) 참조

이 프로젝트의 일부 코드는 제3자 라이선스의 적용을 받습니다:

- `src/tools/extractor/lz4ak.py`: [Ark-Unpacker](https://github.com/isHarryh/Ark-Unpacker) (BSD-3-Clause)
