ArkSynth - 명일방주 스토리 실시간 음성 더빙
=============================================

[ 시스템 요구사항 ]

- Windows 10/11 (64bit)
- NVIDIA GPU (GTX 1060 이상 권장)
- NVIDIA 드라이버 530 이상 (https://www.nvidia.com/drivers)
- 인터넷 연결 (첫 실행 시 필요)
- 저장 공간 약 10GB (Python 환경 + 의존성)

※ CUDA Toolkit 별도 설치는 필요하지 않습니다 (PyTorch에 포함).
※ Python 별도 설치는 필요하지 않습니다 (uv가 자동 관리).


[ 실행 방법 ]

1. start.bat 을 더블클릭합니다.
2. 첫 실행 시 자동으로 설치가 진행됩니다:
   - uv (Python 패키지 관리자)
   - Python 3.12
   - 필요한 라이브러리 (PyTorch, EasyOCR 등)
   ※ 첫 실행은 인터넷 속도에 따라 5~15분 소요될 수 있습니다.
3. 설치 완료 후 ArkSynth 앱이 자동으로 실행됩니다.
4. 이후 실행부터는 빠르게 시작됩니다.


[ 앱 내 추가 설치 ]

다음 항목은 앱 실행 후 앱 내에서 다운로드/설치합니다:
- 게임 데이터 (스토리 텍스트)
- GPT-SoVITS (음성 합성 엔진)
- Whisper 모델 (음성 전처리)


[ 종료 ]

- 앱 창을 닫고, 콘솔 창에서 아무 키나 누르면 백엔드 서버도 종료됩니다.


[ 문제 해결 ]

- "uv 설치 실패": PowerShell 실행 정책 문제일 수 있습니다.
  관리자 권한 PowerShell에서 다음을 실행하세요:
  Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

- "서버 시작 시간 초과": NVIDIA 드라이버가 최신인지 확인하세요.
  https://www.nvidia.com/drivers

- "ArkSynth.exe를 찾을 수 없습니다":
  앱 없이도 브라우저에서 http://127.0.0.1:8000/docs 로 API에 접근 가능합니다.
