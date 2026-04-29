"""Smoke tests for email allowlist + HTML escaping."""

import pytest

from agents.notification.email_draft_tool import _build_html, recipient_allowed


def test_recipient_allowed_open_when_unset(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("EMAIL_ALLOWED_DOMAINS", raising=False)
    monkeypatch.delenv("EMAIL_ALLOWED_RECIPIENTS", raising=False)
    assert recipient_allowed("anyone@example.com")
    assert not recipient_allowed("not-an-email")


def test_recipient_allowed_by_domain(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("EMAIL_ALLOWED_DOMAINS", "example.com")
    monkeypatch.delenv("EMAIL_ALLOWED_RECIPIENTS", raising=False)
    assert recipient_allowed("ops@example.com")
    assert not recipient_allowed("attacker@evil.com")


def test_recipient_allowed_by_specific_address(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("EMAIL_ALLOWED_DOMAINS", raising=False)
    monkeypatch.setenv("EMAIL_ALLOWED_RECIPIENTS", "ops@example.com")
    assert recipient_allowed("ops@example.com")
    assert not recipient_allowed("ceo@example.com")


def test_html_is_escaped():
    bad_section = "<script>alert(1)</script>"
    html = _build_html(subject="x", sections=[bad_section], intro="intro")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
