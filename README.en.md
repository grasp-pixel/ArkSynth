# ArkSynth

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10-3.12](https://img.shields.io/badge/Python-3.10--3.12-3776AB.svg)](https://www.python.org/)
[![Node.js 18+](https://img.shields.io/badge/Node.js-18+-339933.svg)](https://nodejs.org/)
![Platform: Windows](https://img.shields.io/badge/Platform-Windows-0078D6.svg)

[한국어](README.md)

A real-time voice dubbing app for Arknights story playback.
Train per-character GPT-SoVITS voice models, detect dialogue via screen capture + OCR, and synthesize speech in each character's voice.

## Features

- **Story Browser** - Browse dialogues by episode, view characters, multilingual text support
- **Voice Cloning** - GPT-SoVITS zero-shot / fine-tuned voice training
- **Real-time Dubbing** - Screen capture → OCR dialogue detection → automatic TTS playback
- **Pre-rendering** - Episode-level voice cache for improved quality and response time
- **Game Data Management** - Automatic story data download from GitHub/PRTS sources
- **Multilingual UI** - Korean, Japanese, English interface

## Tech Stack

| Area | Technology |
|------|-----------|
| TTS / Voice Cloning | GPT-SoVITS (zero-shot + fine-tuning) |
| OCR | EasyOCR (ko, ja, en, zh) |
| Backend | Python + FastAPI + asyncio |
| Frontend | Electron 28 + React 18 + Vite 5 + Tailwind CSS |
| State Management | Zustand |
| i18n | i18next |

## System Requirements

- **OS**: Windows 10/11 (64-bit)
- **Python**: 3.10 ~ 3.12
- **Node.js**: 18+
- **GPU**: NVIDIA GPU with CUDA support (recommended)
- **RAM**: 8GB or more
- **Disk**: 10GB+ free space

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourname/ArkSynth.git
cd ArkSynth
```

### 2. Python Dependencies

```bash
# Install uv if not available
pip install uv

# Install dependencies
uv sync
```

### 3. Frontend Dependencies

```bash
cd src/frontend
npm install
```

### 4. GPT-SoVITS

After launching the app, use **Settings → Install GPT-SoVITS** (approximately 2GB download)

### 5. Game Data

This project does not include any game assets.

- **Story data**: Use "Download Game Data" in app settings
- **Voice files**: Place game client asset bundles (.ab) in the `Assets/` folder, then use the in-app extraction feature

## Running

### VSCode (Recommended)

1. Open the project in VSCode
2. Press `F5` → Select "Start ArkSynth"
3. Backend + Vite + Electron will start automatically

### Manual

```bash
cd src/frontend
npm run start
```

## Project Structure

```text
ArkSynth/
├── src/
│   ├── core/                   # Python backend
│   │   ├── backend/            #   FastAPI server + API routers
│   │   ├── cache/              #   Render cache management
│   │   ├── character/          #   Character data (ID normalization)
│   │   ├── data/               #   Game data sources (GitHub/PRTS)
│   │   ├── interfaces/         #   Abstract interfaces (OCR)
│   │   ├── models/             #   Data models (Story, Match)
│   │   ├── ocr/                #   OCR module (EasyOCR + matching)
│   │   ├── story/              #   Story parser/loader
│   │   └── voice/              #   Voice processing + GPT-SoVITS
│   ├── tools/extractor/        # Voice/image extraction CLI
│   └── frontend/               # Electron + React app
│       ├── electron/           #   Electron main/preload
│       └── src/                #   React components + state management
├── data/gamedata/              # Game data (user-downloaded)
├── extracted/                  # Extracted voice/image files
├── models/                     # Trained voice models
└── rendered/                   # Pre-rendered voice cache
```

## Architecture

For system design, pipeline diagrams, and interface structure, see [DESIGN.md](docs/DESIGN.md).

## Disclaimer

This project is an **unofficial fan project** with no official affiliation with Hypergryph/Yostar or Arknights.
"Arknights" is a trademark of its respective rights holders.

This project does not include any game assets such as story text, images, or voice files.
The acquisition and use of game data is entirely the user's responsibility, and users must comply with applicable local laws and the game's terms of service.

## License

MIT License - See [LICENSE](LICENSE)

For third-party license information, see [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

## Acknowledgments

- [ArknightsGameData](https://github.com/Kengxxiao/ArknightsGameData) - Story text data
- [ArknightsStoryTextReader](https://github.com/050644zf/ArknightsStoryTextReader) - Story parser reference
- [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) - Voice cloning/synthesis engine
- [Ark-Unpacker](https://github.com/isHarryh/Ark-Unpacker) - Asset extraction (lz4ak.py)
