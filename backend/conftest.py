"""Shared pytest config — keep imports cheap so unit tests don't open DB."""

import os
import sys
from pathlib import Path

# Ensure `backend/` is importable as the project root for tests.
sys.path.insert(0, str(Path(__file__).parent.resolve()))

# Tests should not exercise live external services unless explicitly enabled.
os.environ.setdefault("SUPABASE_URL", "http://supabase.invalid")
os.environ.setdefault("SUPABASE_KEY", "test-key")
