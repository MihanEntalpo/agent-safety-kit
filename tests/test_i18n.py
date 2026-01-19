import json
from pathlib import Path

import pytest

from agsekit_cli import i18n


def test_normalize_language_variants():
    assert i18n._normalize_language(None) == "en"
    assert i18n._normalize_language("ru_RU.UTF-8") == "ru"
    assert i18n._normalize_language("en-US") == "en"
    assert i18n._normalize_language("de_DE") == "en"


def test_tr_uses_environment_language(monkeypatch):
    monkeypatch.setenv("AGSEKIT_LANG", "ru")
    i18n.set_language("en")

    message = i18n.tr("backup.waiting_minutes", minutes=5)

    assert message == "Готово, ждём 5 минут"


def test_tr_falls_back_to_english_when_missing(monkeypatch):
    en_payload = json.loads(Path("agsekit_cli/locales/en.json").read_text(encoding="utf-8"))
    ru_payload = json.loads(Path("agsekit_cli/locales/ru.json").read_text(encoding="utf-8"))
    missing_keys = sorted(set(en_payload) - set(ru_payload))
    if not missing_keys:
        pytest.skip("No missing translations in ru locale to validate fallback behavior.")
    missing_key = missing_keys[0]

    monkeypatch.setenv("AGSEKIT_LANG", "ru")
    i18n.set_language("ru")

    assert i18n.tr(missing_key) == en_payload[missing_key]


def test_tr_returns_key_for_unknown_entry(monkeypatch):
    monkeypatch.setenv("AGSEKIT_LANG", "en")
    i18n.set_language("en")

    assert i18n.tr("unknown.key") == "unknown.key"
