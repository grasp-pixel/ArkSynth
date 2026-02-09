# ArkSynth 아키텍처

## 시스템 아키텍처

```mermaid
graph TB
    subgraph Frontend["Frontend (Electron + React)"]
        UI[UI Components<br/>11+ React 컴포넌트]
        Store[Zustand Store]
        APIClient[API Client]
    end

    subgraph Backend["Backend (FastAPI)"]
        Router[API Routers]
        Shared[Shared Loaders<br/>싱글톤]

        subgraph Core["Core Modules"]
            Story[Story<br/>Parser / Loader]
            Voice[Voice<br/>GPT-SoVITS]
            OCR[OCR<br/>EasyOCR]
            Cache[Cache<br/>Render Manager]
        end
    end

    subgraph External["External"]
        GPTSOVITS[GPT-SoVITS<br/>API Server]
        GameData[(Game Data<br/>ArknightsGameData)]
    end

    subgraph Storage["Storage"]
        Models[(models/<br/>음성 모델)]
        Rendered[(rendered/<br/>렌더링 캐시)]
        Extracted[(extracted/<br/>추출 음성)]
    end

    UI --> Store --> APIClient
    APIClient -->|HTTP / SSE| Router
    Router --> Shared
    Shared --> Story & Voice & OCR & Cache

    Voice -->|HTTP API| GPTSOVITS
    Story -->|JSON 파싱| GameData
    Voice -->|로드| Models
    Voice -->|참조 오디오| Extracted
    Cache -->|읽기/쓰기| Rendered
```

## API 라우터 구조

| 라우터 | 접두사 | 주요 기능 |
|--------|--------|-----------|
| health | `/` | 서버 상태, 버전, 언어 |
| episodes | `/api/episodes` | 에피소드 목록/상세/대사/캐릭터 |
| stories | `/api/stories` | 카테고리/그룹별 스토리 탐색 |
| tts | `/api/tts` | 음성 합성, 엔진 상태, 파라미터 |
| voice | `/api/voice` | 캐릭터 음성/이미지/매핑/성별/통계 |
| ocr | `/api/ocr` | 캡처/감지/매칭/영역설정/SSE 스트림 |
| render | `/api/render` | 사전 렌더링 시작/캐시/SSE 스트림 |
| training | `/api/training` | 학습 시작/모델관리/SSE 스트림 |
| settings | `/api/settings` | 언어/의존성/설치/추출/GPU |
| aliases | `/api/aliases` | 캐릭터 별칭 관리/제안 |
| data | `/api/data` | 게임 데이터 업데이트 (GitHub/PRTS) |
| update | `/api/update` | 앱 업데이트 확인 |

## 핵심 파이프라인

### 실시간 더빙

```mermaid
sequenceDiagram
    participant Game as 게임 화면
    participant Capture as ScreenCapture
    participant Detector as DialogueDetector
    participant OCR as EasyOCR
    participant Matcher as DialogueMatcher
    participant Cache as RenderCache
    participant TTS as GPT-SoVITS
    participant Player as Audio Player

    loop 0.1초 간격
        Capture->>Detector: 화면 캡처
        Detector->>Detector: 이미지 해시 비교
    end

    Note over Detector: 안정화 감지 (3회 동일)

    Detector->>OCR: 대사 영역 이미지
    Note over OCR: GPU 세마포어 획득
    OCR->>OCR: 텍스트 인식
    OCR->>Detector: 화자 + 대사 텍스트

    Detector->>Matcher: OCR 결과
    Matcher->>Matcher: 퍼지 매칭<br/>(SequenceMatcher)
    Matcher-->>Detector: MatchResult

    alt 캐시 존재
        Detector->>Cache: 캐시 조회
        Cache->>Player: 캐시된 WAV
    else 캐시 없음
        Detector->>TTS: 합성 요청
        Note over TTS: GPU 세마포어 획득
        TTS->>TTS: 참조 오디오 로드 + 합성
        TTS->>Player: 생성된 WAV
    end

    Player->>Game: 음성 재생
```

### 학습 파이프라인

```mermaid
flowchart TD
    Start([학습 요청]) --> Queue[TrainingManager<br/>큐에 추가]
    Queue --> Mode{학습 모드}

    Mode -->|prepare| Whisper[Whisper 전처리<br/>음성 → 텍스트 레이블]
    Mode -->|finetune| Whisper

    Whisper --> RefSelect[참조 오디오 선택<br/>3~10초, 최대 3개]
    RefSelect --> PrepareRef[ref_audio/ 저장<br/>info.json 생성]

    PrepareRef --> IsFT{finetune?}

    IsFT -->|No| Done([완료<br/>model_type: prepared])

    IsFT -->|Yes| TrainSoVITS[SoVITS 학습<br/>기본 8 epoch]
    TrainSoVITS --> TrainGPT[GPT 학습<br/>기본 10 epoch]
    TrainGPT --> Cleanup{cleanup?}

    Cleanup -->|Yes| Clean[중간 파일 삭제]
    Cleanup -->|No| Save
    Clean --> Save[모델 저장<br/>info.json 업데이트]
    Save --> DoneFT([완료<br/>model_type: finetuned])

    style Start fill:#d4edda
    style Done fill:#d4edda
    style DoneFT fill:#d4edda
    style TrainSoVITS fill:#fff3cd
    style TrainGPT fill:#fff3cd
```

### 렌더링 파이프라인

```mermaid
flowchart TD
    Start([렌더링 시작]) --> Load[에피소드 로드<br/>대사 + 음성 배정]

    Load --> Loop{대사 순회}

    Loop -->|다음 대사| Cached{캐시<br/>존재?}

    Cached -->|있음| Skip[스킵]
    Cached -->|없음| ModelReady{모델<br/>준비됨?}

    ModelReady -->|No| AutoPrepare[자동 prepare<br/>참조 오디오 준비]
    AutoPrepare --> Synth
    ModelReady -->|Yes| Synth[GPU 세마포어 획득<br/>TTS 합성]

    Synth --> SaveWAV[WAV 저장<br/>meta.json 업데이트]

    Skip --> Progress[진행률 SSE 전송]
    SaveWAV --> Progress

    Progress --> Loop

    Loop -->|완료| End([렌더링 완료])

    style Start fill:#d4edda
    style End fill:#d4edda
    style Synth fill:#fff3cd
```

## 인터페이스 설계

```mermaid
classDiagram
    class OCRProvider {
        <<abstract>>
        +recognize(image) list~OCRResult~
        +recognize_region(image, region) OCRResult
        +get_supported_languages() list~str~
        +set_language(language)
    }

    class SynthesisAdapter {
        <<abstract>>
        +engine_name: str
        +supports_training: bool
        +is_available() bool
        +synthesize(request) SynthesisResult
        +get_available_voices() list~str~
        +is_voice_available(voice_id) bool
    }

    class TrainingAdapter {
        <<abstract>>
        +engine_name: str
        +supported_modes: list~TrainingMode~
        +train(config, callback) bool
        +cancel()
        +get_default_config(mode) dict
    }

    class ModelAdapter {
        <<abstract>>
        +engine_name: str
        +get_model_type(char_id) ModelType
        +is_ready(char_id) bool
        +list_models() list~ModelInfo~
        +delete_model(char_id) bool
    }

    class EasyOCRProvider {
        -reader: EasyOCR
    }

    class GPTSoVITSSynthesizer {
        -api_client: GPTSoVITSAPIClient
        -model_manager: GPTSoVITSModelManager
    }

    class GPTSoVITSTrainer {
        -config: GPTSoVITSConfig
        -process: Process
    }

    class GPTSoVITSModelManager {
        -models_path: Path
    }

    OCRProvider <|.. EasyOCRProvider
    SynthesisAdapter <|.. GPTSoVITSSynthesizer
    TrainingAdapter <|.. GPTSoVITSTrainer
    ModelAdapter <|.. GPTSoVITSModelManager
    GPTSoVITSSynthesizer --> GPTSoVITSModelManager
```

### 인터페이스 파일 위치

| 인터페이스 | 파일 | 구현체 |
|-----------|------|--------|
| `OCRProvider` | `src/core/interfaces/ocr.py` | `EasyOCRProvider` |
| `SynthesisAdapter` | `src/core/voice/interfaces/synthesis_adapter.py` | `GPTSoVITSSynthesizer` |
| `TrainingAdapter` | `src/core/voice/interfaces/training_adapter.py` | `GPTSoVITSTrainer` |
| `ModelAdapter` | `src/core/voice/interfaces/model_adapter.py` | `GPTSoVITSModelManager` |

### 주요 데이터 모델

| 모델 | 파일 | 용도 |
|------|------|------|
| `Episode`, `Dialogue`, `Character` | `src/core/models/story.py` | 스토리 데이터 |
| `StoryGroup`, `StoryCategory` | `src/core/models/story.py` | 스토리 분류 |
| `MatchResult`, `MatchConfidence` | `src/core/models/match.py` | OCR 매칭 결과 |
| `SynthesisRequest/Result` | `src/core/voice/interfaces/synthesis_adapter.py` | TTS 요청/응답 |
| `TrainingConfig/Progress` | `src/core/voice/interfaces/training_adapter.py` | 학습 설정/진행 |
| `ModelInfo`, `ModelType` | `src/core/voice/interfaces/model_adapter.py` | 모델 상태 |

## GPU 리소스 관리

OCR(EasyOCR)과 TTS(GPT-SoVITS)가 동시에 GPU를 사용하면 VRAM 부족으로 크래시가 발생한다.
이를 방지하기 위해 전역 `asyncio.Semaphore(1)`로 GPU 접근을 직렬화한다.

```text
backend/__init__.py
  └── _gpu_semaphore = asyncio.Semaphore(1)
      ├── OCR 인식 시 획득 (easyocr_provider.py)
      ├── TTS 합성 시 획득 (synthesizer.py)
      └── gpu_semaphore_context() 컨텍스트 매니저
```

예상 VRAM 사용량:

- EasyOCR: ~1-2GB
- GPT-SoVITS: ~2-4GB
- 권장: NVIDIA GPU 6GB VRAM 이상

## SSE 스트리밍

장시간 작업은 Server-Sent Events로 실시간 진행률을 전송한다.

| 스트림 | 엔드포인트 | 이벤트 |
|--------|-----------|--------|
| OCR 실시간 감지 | `GET /api/ocr/stream` | 대사 감지, 매칭 결과 |
| 렌더링 진행률 | `GET /api/render/stream` | 진행률, 완료/에러 |
| 학습 진행률 | `GET /api/training/stream` | 단계, epoch, 완료/에러 |
| 설치 진행률 | `GET /api/settings/install/stream` | 다운로드/압축해제 진행률 |

## 명명 규칙

| 영역 | 규칙 | 예시 |
|------|------|------|
| Python 함수/변수 | snake_case | `load_episode`, `char_id` |
| Python 클래스 | PascalCase | `StoryLoader`, `GPTSoVITSSynthesizer` |
| TypeScript 함수/변수 | camelCase | `fetchEpisode`, `charId` |
| React 컴포넌트 | PascalCase | `DialogueViewer`, `VoiceSetupPanel` |
| API URL | kebab-case | `/api/voice/characters` |
| JSON 필드 | snake_case | `episode_id`, `speaker_name` |
