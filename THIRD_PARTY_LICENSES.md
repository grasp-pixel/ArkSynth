# Third-Party Licenses

이 프로젝트는 아래 제3자 소프트웨어의 코드를 포함하거나 활용합니다.

## 포함된 코드

### Ark-Unpacker (BSD-3-Clause)

- **파일**: `src/tools/extractor/lz4ak.py`
- **원본**: https://github.com/isHarryh/Ark-Unpacker
- **저작권**: Copyright (c) 2022-2024, Harry Huang

```
BSD 3-Clause License

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

## 외부 도구 (별도 설치)

이 프로젝트는 아래 소프트웨어와 연동되지만, 직접 번들하지 않습니다.
사용자가 앱 내에서 별도로 설치합니다.

| 소프트웨어 | 라이선스 | 용도 |
|-----------|---------|------|
| [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) | MIT | 음성 클로닝/합성 엔진 |
| [FFmpeg](https://ffmpeg.org/) | LGPL 2.1+ | 오디오 처리 |

## 데이터 소스

게임 데이터는 프로젝트에 포함되지 않으며, 사용자가 직접 다운로드합니다.

| 소스 | 라이선스 | 용도 |
|------|---------|------|
| [ArknightsGameData](https://github.com/Kengxxiao/ArknightsGameData) | 커뮤니티 오픈소스 | 스토리 텍스트 데이터 |

## 주요 의존성 라이선스

### Python

| 패키지 | 라이선스 |
|--------|---------|
| FastAPI | MIT |
| PyTorch | BSD-style |
| EasyOCR | Apache 2.0 |
| Pillow | HPND |
| librosa | ISC |
| faster-whisper | MIT |
| UnityPy | MIT |

### JavaScript / Node.js

| 패키지 | 라이선스 |
|--------|---------|
| Electron | MIT |
| React | MIT |
| Vite | MIT |
| Tailwind CSS | MIT |
| Zustand | MIT |
| i18next | MIT |

전체 의존성 목록은 [`pyproject.toml`](pyproject.toml) 및 [`src/frontend/package.json`](src/frontend/package.json)을 참조하세요.
