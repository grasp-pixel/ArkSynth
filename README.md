# ArkSynth

명일방주(Arknights) 스토리 실시간 음성 더빙 앱

## 기능
- 스토리 에피소드 탐색 및 대사 확인
- 캐릭터별 음성 모델 학습 (RVC 기반)
- 실시간 TTS 더빙
- 화면 캡처로 대사 자동 인식 (OCR)

## 기술 스택
- **백엔드**: Python, FastAPI, Edge-TTS, RVC
- **프론트엔드**: Electron, React, Vite, Tailwind CSS
- **데이터**: ArknightsGameData, PaddleOCR

## 설치

### 요구사항
- Python 3.10-3.12
- Node.js 18+
- uv (Python 패키지 관리자)

### 설치
```bash
# 저장소 클론
git clone --recursive https://github.com/yourname/ArkSynth.git
cd ArkSynth

# 백엔드 의존성
uv sync

# 프론트엔드 의존성
cd src/frontend
npm install
```

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
│   ├── tools/          # CLI 도구
│   └── frontend/       # Electron 앱
├── data/gamedata/      # 게임 데이터 (submodule)
├── extracted/          # 추출된 음성 파일
└── models/             # 학습된 음성 모델
```

## 개발 현황
- [x] 음성 추출
- [x] 스토리 파싱
- [x] 기본 TTS (Edge-TTS)
- [x] Electron 프론트엔드
- [ ] OCR 통합
- [ ] RVC 학습/추론
- [ ] 실시간 더빙

## 라이선스
MIT
