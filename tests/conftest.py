import os
import sys

import pytest


os.environ.setdefault("AGSEKIT_LANG", "en")


@pytest.fixture(autouse=True)
def default_language(monkeypatch):
    monkeypatch.setenv("AGSEKIT_LANG", "en")


def _host_integration_ready() -> tuple[bool, str]:
    if os.environ.get("AGSEKIT_RUN_HOST_IT") != "1":
        return False, "Set AGSEKIT_RUN_HOST_IT=1 to run host integration tests."
    if sys.platform != "linux":
        return False, "Host integration tests require Linux."
    return True, ""


def pytest_collection_modifyitems(config, items):
    enabled, reason = _host_integration_ready()
    if enabled:
        return
    skip_marker = pytest.mark.skip(reason=reason)
    for item in items:
        if "host_integration" in item.keywords:
            item.add_marker(skip_marker)
