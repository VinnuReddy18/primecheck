import os
import time

os.environ.setdefault("SIEVE_LIMIT", "100000")
os.environ.setdefault("ADMIN_TOKEN", "pytest-not-a-real-token")
os.environ.setdefault("FEATURE_FACTOR_HINT", "false")
os.environ.setdefault("TRACING_ENABLED", "false")

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app, tester

ADMIN_TOKEN = os.environ["ADMIN_TOKEN"]


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as started:
        deadline = time.time() + 30
        while not tester.ready and time.time() < deadline:
            time.sleep(0.05)
        assert tester.ready, "the sieve did not warm up within thirty seconds"
        yield started


@pytest.fixture(autouse=True)
def reset_feature_flag():
    original = settings.feature_factor_hint
    yield
    settings.feature_factor_hint = original
