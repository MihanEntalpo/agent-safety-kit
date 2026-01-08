from __future__ import annotations

import json
import locale
import os
from importlib import resources
from typing import Dict, Optional

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = {"en", "ru"}

_current_language: Optional[str] = None
_translations: Dict[str, str] = {}
_fallback_translations: Dict[str, str] = {}


def _normalize_language(raw: Optional[str]) -> str:
    if not raw:
        return DEFAULT_LANGUAGE
    cleaned = raw.split(".", 1)[0].split("@", 1)[0]
    base = cleaned.split("_", 1)[0].split("-", 1)[0].lower()
    if base in SUPPORTED_LANGUAGES:
        return base
    return DEFAULT_LANGUAGE


def _detect_language() -> str:
    env_lang = os.environ.get("AGSEKIT_LANG")
    if env_lang:
        return _normalize_language(env_lang)
    locale_value = locale.getlocale()[0] or locale.getdefaultlocale()[0] or os.environ.get("LANG")
    return _normalize_language(locale_value)


def _load_translations(language: str) -> Dict[str, str]:
    try:
        payload = resources.files("agsekit_cli").joinpath("locales", f"{language}.json").read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    return json.loads(payload)


def set_language(language: Optional[str] = None) -> str:
    global _current_language, _translations, _fallback_translations
    normalized = _normalize_language(language or _detect_language())
    _current_language = normalized
    _translations = _load_translations(normalized)
    if normalized == DEFAULT_LANGUAGE:
        _fallback_translations = _translations
    else:
        _fallback_translations = _load_translations(DEFAULT_LANGUAGE)
    return normalized


def _ensure_language() -> None:
    global _current_language
    desired = _detect_language()
    if _current_language != desired:
        set_language(desired)


def tr(key: str, **kwargs: object) -> str:
    _ensure_language()
    text = _translations.get(key) or _fallback_translations.get(key) or key
    if kwargs:
        return text.format(**kwargs)
    return text
