# Slice 4 Task 2 (updated Task 4 fix-round-1: SESSION_SECRET/IP_HASH_SALT
# import-time constants replaced with session_secret()/ip_hash_salt()
# call-time accessors, and DEMO_SESSION_SECRET unified onto COOKIE_SECRET --
# see demo_auth.py's module docstring for why). Pure stdlib crypto, no I/O.

from rulesagent.demo_auth import (
    COOKIE_MAX_AGE_S, hash_ip, ip_hash_salt, session_secret, sign_session, verify_session,
)


def test_sign_then_verify_round_trip():
    token = sign_session(42, "test-secret", issued_at=1_000_000)
    assert verify_session(token, "test-secret", now=1_000_100) == 42


def test_wrong_secret_rejected():
    token = sign_session(42, "test-secret", issued_at=1_000_000)
    assert verify_session(token, "wrong-secret", now=1_000_100) is None


def test_tampered_code_id_rejected():
    token = sign_session(42, "test-secret", issued_at=1_000_000)
    code_id_str, issued_at_str, sig = token.split(":")
    tampered = f"999:{issued_at_str}:{sig}"
    assert verify_session(tampered, "test-secret", now=1_000_100) is None


def test_expired_after_seven_days_rejected():
    token = sign_session(42, "test-secret", issued_at=1_000_000)
    just_inside = 1_000_000 + COOKIE_MAX_AGE_S - 1
    just_outside = 1_000_000 + COOKIE_MAX_AGE_S + 1
    assert verify_session(token, "test-secret", now=just_inside) == 42
    assert verify_session(token, "test-secret", now=just_outside) is None


def test_none_token_rejected():
    assert verify_session(None, "test-secret") is None


def test_malformed_token_rejected_not_raised():
    assert verify_session("not-a-valid-token", "test-secret") is None
    assert verify_session("", "test-secret") is None
    assert verify_session("1:2:3:4", "test-secret") is None
    assert verify_session("abc:def:ghi", "test-secret") is None


def test_hash_ip_is_deterministic_and_salted():
    a = hash_ip("203.0.113.5", "salt-one")
    b = hash_ip("203.0.113.5", "salt-one")
    c = hash_ip("203.0.113.5", "salt-two")
    assert a == b
    assert a != c
    assert "203.0.113.5" not in a  # never the raw IP


def test_hash_ip_different_ips_differ():
    assert hash_ip("203.0.113.5", "salt") != hash_ip("203.0.113.6", "salt")


# --- config-loading decision (review finding from Task 1: the IP hash salt
# must not be a hardcoded constant, since a fixed salt makes ip_hash
# correlatable across deployments and reversible over the ~4B IPv4 space).
# session_secret()/ip_hash_salt() read COOKIE_SECRET/IP_HASH_SALT from the
# environment AT CALL TIME (Task 4 fix-round-1: NOT an import-time snapshot
# -- the prior module-level SESSION_SECRET constant read a different env var,
# DEMO_SESSION_SECRET, that nothing else in the codebase used, a naming slip
# that made main.py and this module silently disagree about whether
# COOKIE_SECRET was configured). Fail-CLOSED like ADMIN_TOKEN, not a silent
# random fallback: absent env var -> None, and it is the caller's job
# (api/main.py's _require_demo_config(), covering /unlock, the gated "/"
# route, and Task 5's /answer) to refuse to serve rather than invent a
# value. A random fallback would look convenient locally but breaks
# multi-worker deployments (each worker gets a different secret, so cookies
# signed by one worker fail verification on another) and would silently mask
# a missing production env var as "it still works."


def test_session_secret_defaults_to_none_when_env_var_unset(monkeypatch):
    monkeypatch.delenv("COOKIE_SECRET", raising=False)
    assert session_secret() is None


def test_ip_hash_salt_defaults_to_none_when_env_var_unset(monkeypatch):
    monkeypatch.delenv("IP_HASH_SALT", raising=False)
    assert ip_hash_salt() is None


def test_session_secret_and_ip_hash_salt_read_from_env(monkeypatch):
    monkeypatch.setenv("COOKIE_SECRET", "env-secret")
    monkeypatch.setenv("IP_HASH_SALT", "env-salt")
    assert session_secret() == "env-secret"
    assert ip_hash_salt() == "env-salt"


def test_accessors_read_at_call_time_not_import_time(monkeypatch):
    # The whole point of the fix: no reload, no snapshot -- a monkeypatch
    # made AFTER this module was already imported (which it was, at test
    # collection) must still be visible on the next call.
    monkeypatch.delenv("COOKIE_SECRET", raising=False)
    assert session_secret() is None
    monkeypatch.setenv("COOKIE_SECRET", "just-set")
    assert session_secret() == "just-set"
