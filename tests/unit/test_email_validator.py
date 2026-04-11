"""
Unit tests for disposable email validation.
"""
import pytest

from app.utils.email_validator import is_disposable_email, _DISPOSABLE_DOMAINS


class TestDisposableEmailValidator:
    """Test disposable email detection."""

    def test_blocklist_loaded(self):
        """Test that the blocklist file was loaded successfully."""
        assert len(_DISPOSABLE_DOMAINS) > 5000

    def test_disposable_email_detected(self):
        """Test that known disposable domains are blocked."""
        assert is_disposable_email("test@0-mail.com") is True
        assert is_disposable_email("user@0box.eu") is True

    def test_legitimate_email_allowed(self):
        """Test that legitimate email domains are not blocked."""
        assert is_disposable_email("user@gmail.com") is False
        assert is_disposable_email("user@outlook.com") is False
        assert is_disposable_email("user@onedocs.com") is False

    def test_case_insensitive(self):
        """Test that domain check is case-insensitive."""
        assert is_disposable_email("test@0-MAIL.COM") is True
        assert is_disposable_email("test@0-Mail.Com") is True
