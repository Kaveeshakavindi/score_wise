from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest

# Settings are validated at import time (fail-fast, §10), so test env vars
# must be in place before anything under app/ is imported.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from app.core.config import Settings  # noqa: E402
from app.db.models import User  # noqa: E402


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def test_user() -> User:
    """A fully-formed User, for router tests that override get_current_user
    directly rather than exercising the full register/login flow."""
    user = User(id=uuid.uuid4(), name="Test User", nickname="testuser", password_hash="hashed", age=30)
    user.created_at = datetime.now(timezone.utc)
    return user
