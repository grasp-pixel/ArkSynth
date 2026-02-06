"""charword_table.json 로드 공통 모듈

캐릭터 대사 텍스트 로드 (스킨/이격 포함).
training_worker.py와 finetuning_worker.py에서 공통으로 사용합니다.
"""

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def _extract_voice_id_from_asset(voice_asset: str, char_id: str) -> str | None:
    """voiceAsset에서 스킨 접미사 포함 voice_id 추출

    Args:
        voice_asset: voiceAsset 경로 (예: "char_003_kalts_boc#6/CN_001")
        char_id: 기본 캐릭터 ID (예: "char_003_kalts")

    Returns:
        voice_id (예: "CN_001_boc6") 또는 None
    """
    # 기본 캐릭터: char_003_kalts/CN_001
    if voice_asset.startswith(f"{char_id}/"):
        return voice_asset[len(char_id) + 1:]  # CN_001

    # 스킨 캐릭터: char_003_kalts_boc#6/CN_001
    skin_pattern = re.compile(rf'^{re.escape(char_id)}_([a-z]+)#(\d+)/(.+)$')
    match = skin_pattern.match(voice_asset)
    if match:
        skin_type = match.group(1)  # boc, epoque, iteration
        skin_num = match.group(2)   # 6, 34, 2
        voice_id = match.group(3)   # CN_001
        return f"{voice_id}_{skin_type}{skin_num}"  # CN_001_boc6

    return None


def load_charword_transcripts(
    char_id: str,
    gamedata_path: Path,
    language: str = "ko",
) -> dict[str, dict]:
    """charword_table.json에서 대사 텍스트 로드 (스킨/이격 포함)

    voiceAsset 기반으로 필터링하여 정확한 음성-텍스트 매칭을 보장합니다.

    Args:
        char_id: 캐릭터 ID (char_002_amiya)
        gamedata_path: gamedata 경로
        language: 언어 코드 (ko, ja, zh, en)

    Returns:
        {voice_id: {"text": str, "title": str}} 딕셔너리
        예: {"CN_001": {"text": "기본 대사...", "title": "어시스턴트 임명"},
             "CN_001_boc6": {"text": "스킨 대사...", "title": "어시스턴트 임명"}}
    """
    # 언어 코드 매핑
    lang_map = {
        "ko": ("ko_KR", "kr"),
        "ja": ("ja_JP", "jp"),
        "zh": ("zh_CN", "zh"),
        "en": ("en_US", "en"),
    }
    game_lang, server_code = lang_map.get(language, ("ko_KR", "kr"))

    # 후보 경로들 (우선순위 순)
    candidates = [
        # arkprts 경로 (data/gamedata/kr/gamedata/excel/)
        gamedata_path.parent / "gamedata" / server_code / "gamedata" / "excel" / "charword_table.json",
        # gamedata 경로
        gamedata_path / server_code / "gamedata" / "excel" / "charword_table.json",
        # 기존 경로 (data/gamedata_yostar/ko_KR/gamedata/excel/)
        gamedata_path / game_lang / "gamedata" / "excel" / "charword_table.json",
        # 직접 gamedata 경로
        gamedata_path / "gamedata" / "excel" / "charword_table.json",
    ]

    charword_path = None
    for candidate in candidates:
        if candidate.exists():
            charword_path = candidate
            break

    if charword_path is None:
        logger.warning(f"charword_table.json not found for {char_id}")
        return {}

    try:
        with open(charword_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        result = {}
        skin_count = 0

        for key, item in data.get("charWords", {}).items():
            # voiceAsset에서 스킨 접미사 포함 voice_id 추출
            voice_asset = item.get("voiceAsset", "")
            voice_id = _extract_voice_id_from_asset(voice_asset, char_id)

            if voice_id is None:
                continue

            voice_text = item.get("voiceText", "")
            voice_title = item.get("voiceTitle", "")

            if voice_text and voice_id not in result:
                result[voice_id] = {"text": voice_text, "title": voice_title}
                # 스킨 카운트 (CN_001_boc6 형태)
                if "_" in voice_id and voice_id.count("_") > 1:
                    skin_count += 1

        base_count = len(result) - skin_count
        logger.info(
            f"Loaded {len(result)} transcripts for {char_id} "
            f"(base: {base_count}, skin: {skin_count}) from {charword_path}"
        )
        return result

    except Exception as e:
        logger.error(f"Failed to load charword_table.json: {e}")
        return {}


def load_charword_texts(
    gamedata_path: Path,
    char_id: str,
    language: str = "ko",
) -> dict[str, str]:
    """charword_table.json에서 대사 텍스트만 로드 (스킨/이격 포함)

    load_charword_transcripts의 간소화 버전으로, text만 반환합니다.

    Returns:
        {voice_id: text} 형태의 딕셔너리
    """
    transcripts = load_charword_transcripts(char_id, gamedata_path, language)
    return {k: v["text"] for k, v in transcripts.items()}
