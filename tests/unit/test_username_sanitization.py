import pytest
from control_plane.apps.authentication.utils import sanitize_posix_username


def test_sanitize_standard_email():
    assert sanitize_posix_username("john.doe@example.com") == "john_doe"


def test_sanitize_uppercase_and_special():
    assert sanitize_posix_username("Alice.O'Connor+Test@DOMAIN.COM") == "alice_o_connor_test"


def test_sanitize_leading_digit():
    assert sanitize_posix_username("123user@example.com") == "u_123user"


def test_sanitize_long_username():
    long_name = "a" * 50 + "@example.com"
    sanitized = sanitize_posix_username(long_name)
    assert len(sanitized) == 32
    assert sanitized == "a" * 32


def test_sanitize_single_char():
    assert sanitize_posix_username("a@example.com") == "a_u"


def test_sanitize_empty_and_invalid():
    with pytest.raises(ValueError, match="non-empty string"):
        sanitize_posix_username("")

    with pytest.raises(ValueError, match="non-empty string"):
        sanitize_posix_username(None)


def test_sanitize_domain_backslash():
    assert sanitize_posix_username("DOMAIN\\user_name") == "user_name"


def test_sanitize_regex_failure_guard(monkeypatch):
    import re
    original_match = re.match
    call_count = 0

    def mock_match(pattern, string, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count > 1:
            return None
        return original_match(pattern, string, *args, **kwargs)

    monkeypatch.setattr(re, "match", mock_match)
    with pytest.raises(ValueError, match="Failed to produce valid POSIX username"):
        sanitize_posix_username("valid_user")
