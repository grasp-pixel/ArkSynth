"""언어 코드 매핑 상수 (프로젝트 전체 공유)

이 파일은 프로젝트 전체에서 사용하는 언어 코드 변환 로직을 집중합니다.
서버 코드, 표준 로케일 코드, 단축 코드 간 변환을 제공합니다.
"""

# 표준 로케일 코드 → 서버 코드
LOCALE_TO_SERVER: dict[str, str] = {
    "ko_KR": "kr",
    "en_US": "en",
    "ja_JP": "jp",
    "zh_CN": "cn",
}

# 단축 코드 → (표준 로케일, 서버 코드)
SHORT_LANG_MAP: dict[str, tuple[str, str]] = {
    "ko": ("ko_KR", "kr"),
    "ja": ("ja_JP", "jp"),
    "zh": ("zh_CN", "cn"),
    "en": ("en_US", "en"),
}

# 단축 코드 → 음성 폴더명
SHORT_TO_VOICE_FOLDER: dict[str, str] = {
    "ko": "voice_kr",
    "ja": "voice",
    "zh": "voice_cn",
    "en": "voice_en",
}

# 음성 폴더명 → 단축 코드 (별칭 포함: voice_jp, voice_ja → ja)
VOICE_FOLDER_TO_SHORT: dict[str, str] = {
    "voice_kr": "ko",
    "voice": "ja",
    "voice_jp": "ja",
    "voice_ja": "ja",
    "voice_cn": "zh",
    "voice_en": "en",
}

# 지원 언어 목록 (UI 표시용)
SUPPORTED_LANGUAGES: list[dict[str, str]] = [
    {"short": "ko", "locale": "ko_KR", "label": "한국어", "native": "한국어"},
    {"short": "ja", "locale": "ja_JP", "label": "日本語", "native": "日本語"},
    {"short": "en", "locale": "en_US", "label": "English", "native": "English"},
]


def normalize_voice_folder(folder_name: str) -> str:
    """음성 폴더명을 정규화 (voice_jp/voice_ja → voice)

    Examples:
        >>> normalize_voice_folder("voice_jp")
        'voice'
        >>> normalize_voice_folder("voice_kr")
        'voice_kr'
    """
    short = VOICE_FOLDER_TO_SHORT.get(folder_name)
    if short:
        return SHORT_TO_VOICE_FOLDER[short]
    return folder_name


def short_to_voice_folder(short: str) -> str:
    """단축 코드를 음성 폴더명으로 변환

    Examples:
        >>> short_to_voice_folder("ko")
        'voice_kr'
        >>> short_to_voice_folder("ja")
        'voice'
    """
    return SHORT_TO_VOICE_FOLDER.get(short, f"voice_{short}")


def short_to_locale(short: str) -> str:
    """단축 코드를 로케일로 변환

    Examples:
        >>> short_to_locale("ko")
        'ko_KR'
    """
    entry = SHORT_LANG_MAP.get(short)
    return entry[0] if entry else f"{short}_{short.upper()}"


def locale_to_short(locale: str) -> str:
    """로케일 코드를 단축 코드로 변환

    Examples:
        >>> locale_to_short("ko_KR")
        'ko'
    """
    for short, (loc, _) in SHORT_LANG_MAP.items():
        if loc == locale:
            return short
    return locale.split("_")[0] if "_" in locale else locale


def locale_to_server(locale: str) -> str:
    """표준 로케일 코드를 서버 코드로 변환

    Args:
        locale: 표준 로케일 코드 (ko_KR, en_US, ja_JP, zh_CN)

    Returns:
        서버 코드 (kr, en, jp, cn)

    Examples:
        >>> locale_to_server("ko_KR")
        'kr'
        >>> locale_to_server("unknown")
        'unknown'
    """
    return LOCALE_TO_SERVER.get(locale, locale.split("_")[0] if "_" in locale else locale)


def short_to_locale_and_server(short: str) -> tuple[str, str]:
    """단축 코드를 (로케일, 서버) 튜플로 변환

    Args:
        short: 단축 언어 코드 (ko, ja, zh, en)

    Returns:
        (표준 로케일 코드, 서버 코드) 튜플

    Examples:
        >>> short_to_locale_and_server("ko")
        ('ko_KR', 'kr')
        >>> short_to_locale_and_server("unknown")
        ('unknown_UNKNOWN', 'unknown')
    """
    return SHORT_LANG_MAP.get(short, (f"{short}_{short.upper()}", short))
