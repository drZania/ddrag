"""Test-only environment defaults."""

import os


os.environ.setdefault("JWT_SECRET", "test-only-secret-not-for-production-32")