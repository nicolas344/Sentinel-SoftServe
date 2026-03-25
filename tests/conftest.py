import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "Backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Safe env defaults for backend imports.
os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret")

from auth import get_current_user  # noqa: E402
from main import app  # noqa: E402


@dataclass
class FakeResponse:
    data: Any


class FakeQueryBuilder:
    def __init__(self, response_data):
        self.response_data = response_data

    def select(self, _value):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def eq(self, _key, _value):
        return self

    def single(self):
        return self

    def execute(self):
        return FakeResponse(self.response_data)


class FakeSupabaseClient:
    def __init__(self, table_data):
        self.table_data = table_data

    def table(self, _table_name):
        return FakeQueryBuilder(self.table_data)


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: {"sub": "test-user"}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
