"""Tests for API key authentication."""

import pytest

from app.middleware.auth import (
    PUBLIC_PATHS,
    PUBLIC_PREFIXES,
    generate_api_key,
    hash_api_key,
    verify_api_key,
)


class TestApiKeyGeneration:
    """Test API key creation."""

    def test_key_has_prefix(self):
        key = generate_api_key()
        assert key.startswith("pf_")

    def test_key_is_unique(self):
        keys = {generate_api_key() for _ in range(50)}
        assert len(keys) == 50

    def test_key_sufficient_length(self):
        key = generate_api_key()
        # "pf_" + 32 bytes urlsafe base64 = at least 46 chars
        assert len(key) >= 40

    def test_key_is_url_safe(self):
        key = generate_api_key()
        # urlsafe_b64 only contains alphanumeric, -, _
        suffix = key[3:]  # strip pf_ prefix
        for ch in suffix:
            assert ch.isalnum() or ch in "-_", f"Unexpected char: {ch}"


class TestApiKeyHashing:
    """Test key hashing."""

    def test_hash_is_hex_string(self):
        h = hash_api_key("pf_test_key")
        assert len(h) == 64  # SHA-256 hex
        assert all(c in "0123456789abcdef" for c in h)

    def test_same_key_same_hash(self):
        key = "pf_some_key_12345"
        assert hash_api_key(key) == hash_api_key(key)

    def test_different_keys_different_hashes(self):
        h1 = hash_api_key("pf_key_one")
        h2 = hash_api_key("pf_key_two")
        assert h1 != h2


class TestApiKeyVerification:
    """Test constant-time key verification."""

    def test_correct_key_verifies(self):
        key = generate_api_key()
        stored = hash_api_key(key)
        assert verify_api_key(key, stored) is True

    def test_wrong_key_fails(self):
        key = generate_api_key()
        stored = hash_api_key(key)
        assert verify_api_key("pf_wrong_key", stored) is False

    def test_empty_key_fails(self):
        stored = hash_api_key("pf_real_key")
        assert verify_api_key("", stored) is False

    def test_hash_of_wrong_key_fails(self):
        key = generate_api_key()
        wrong_hash = hash_api_key("pf_different_key")
        assert verify_api_key(key, wrong_hash) is False


class TestPublicPaths:
    """Test that public path constants are properly defined."""

    def test_health_is_public(self):
        assert "/api/system/health" in PUBLIC_PATHS

    def test_docs_is_public(self):
        assert "/docs" in PUBLIC_PATHS

    def test_openapi_is_public(self):
        assert "/openapi.json" in PUBLIC_PATHS

    def test_websocket_prefix_is_public(self):
        assert "/ws" in PUBLIC_PREFIXES

    def test_api_printer_is_not_public(self):
        assert "/api/printer/state" not in PUBLIC_PATHS
