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
