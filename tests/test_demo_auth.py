# Slice 4 Task 2. Pure stdlib crypto, no I/O -- no tmp_path needed.

import importlib

from rulesagent.demo_auth import COOKIE_MAX_AGE_S, hash_ip, sign_session, verify_session


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
# SESSION_SECRET and IP_HASH_SALT are module-level, read ONCE at import from
# env vars -- same pattern as demo_db.DEFAULT_DEMO_DB (DEMO_DB_PATH) and
# api/main.py's ADMIN_TOKEN. Fail-CLOSED like ADMIN_TOKEN, not a silent
# random fallback: absent env var -> None, and it is the caller's job (the
# /unlock and /answer endpoints, Task 4/5) to refuse to serve rather than
# invent a value. A random-per-process fallback would look convenient
# locally but breaks multi-worker deployments (each worker gets a different
# secret, so cookies signed by one worker fail verification on another) and
# would silently mask a missing production env var as "it still works."


def test_session_secret_defaults_to_none_when_env_var_unset(monkeypatch):
    monkeypatch.delenv("DEMO_SESSION_SECRET", raising=False)
    import rulesagent.demo_auth as demo_auth_module
    reloaded = importlib.reload(demo_auth_module)
    try:
        assert reloaded.SESSION_SECRET is None
    finally:
        importlib.reload(demo_auth_module)


def test_ip_hash_salt_defaults_to_none_when_env_var_unset(monkeypatch):
    monkeypatch.delenv("IP_HASH_SALT", raising=False)
    import rulesagent.demo_auth as demo_auth_module
    reloaded = importlib.reload(demo_auth_module)
    try:
        assert reloaded.IP_HASH_SALT is None
    finally:
        importlib.reload(demo_auth_module)


def test_session_secret_and_ip_hash_salt_read_from_env_once(monkeypatch):
    monkeypatch.setenv("DEMO_SESSION_SECRET", "env-secret")
    monkeypatch.setenv("IP_HASH_SALT", "env-salt")
    import rulesagent.demo_auth as demo_auth_module
    reloaded = importlib.reload(demo_auth_module)
    try:
        assert reloaded.SESSION_SECRET == "env-secret"
        assert reloaded.IP_HASH_SALT == "env-salt"
    finally:
        importlib.reload(demo_auth_module)
