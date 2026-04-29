"""Smoke tests for PostgREST filter sanitization."""

from shared.supabase_client import sanitize_filter_term


def test_strips_postgrest_operator_chars():
    assert "(" not in sanitize_filter_term("foo).or.(bar")
    assert ")" not in sanitize_filter_term("foo).or.(bar")
    assert "," not in sanitize_filter_term("a,b")
    assert "*" not in sanitize_filter_term("foo*")


def test_preserves_safe_characters():
    assert sanitize_filter_term("PUMP-001") == "PUMP-001"
    assert sanitize_filter_term("hex / driver") == "hex / driver"


def test_truncates_long_input():
    long = "a" * 500
    assert len(sanitize_filter_term(long)) == 120
