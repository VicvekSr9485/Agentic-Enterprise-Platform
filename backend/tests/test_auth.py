"""Smoke tests for bearer-token auth helpers."""

import os

import pytest

from shared.auth import _allowed_keys, _matches_any, _path_is_public, derive_user_id


def test_derive_user_id_anonymous_when_no_token():
    assert derive_user_id(None) == "anonymous"


def test_derive_user_id_is_stable_per_token():
    a = derive_user_id("token-1")
    b = derive_user_id("token-1")
    c = derive_user_id("token-2")
    assert a == b
    assert a != c
    assert a.startswith("u_")


def test_path_is_public():
    assert _path_is_public("/health")
    assert _path_is_public("/")
    assert _path_is_public("/inventory/.well-known/agent-card.json")
    assert not _path_is_public("/orchestrator/chat")


def test_matches_any_uses_constant_time():
    assert _matches_any("abc", ["abc", "xyz"])
    assert not _matches_any("abc", ["xyz"])


def test_allowed_keys_parses_csv(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PLATFORM_API_KEY", " key-1 , key-2 ,, ")
    keys = _allowed_keys()
    assert keys == ["key-1", "key-2"]
