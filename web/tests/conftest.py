"""Fixtures for the web app suite.

Puts ``web/`` on ``sys.path`` so ``import app`` works from the repo root, and
points upload/output/gallery paths at a temporary directory per test.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).resolve().parent
WEB_ROOT = TESTS_ROOT.parent
for _path in (WEB_ROOT, TESTS_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


@pytest.fixture
def app_module(tmp_path, monkeypatch):
    import app as application

    uploads = tmp_path / "uploads"
    outputs = tmp_path / "outputs"
    uploads.mkdir()
    outputs.mkdir()
    monkeypatch.setattr(application, "UPLOADS", uploads)
    monkeypatch.setattr(application, "OUTPUTS", outputs)
    monkeypatch.setattr(application, "GALLERY_INDEX", outputs / "gallery.json")
    monkeypatch.setattr(application, "_SESSIONS", {})
    return application


@pytest.fixture
def client(app_module):
    from fastapi.testclient import TestClient

    with TestClient(app_module.app) as test_client:
        yield test_client
