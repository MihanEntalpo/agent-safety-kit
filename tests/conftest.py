import os

import pytest


os.environ.setdefault("AGSEKIT_LANG", "en")


@pytest.fixture(autouse=True)
def default_language(monkeypatch):
    monkeypatch.setenv("AGSEKIT_LANG", "en")
