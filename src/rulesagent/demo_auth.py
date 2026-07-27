"""Slice 4 (docs/superpowers/plans/2026-07-27-gated-demo.md Task 2): signed
session cookie and salted IP hashing for the gated demo.

Cookie: HMAC over "code_id:issued_at" (spec: "signed cookie (code id + issue
time), 7-day expiry"). Deliberately stdlib hmac/hashlib rather than a signing
library -- one signed string, nothing that warrants a dependency.

IP hash: events.ip_hash must never be the raw IP (spec). hmac-sha256 keyed by
a server-side salt (IP_HASH_SALT env var) rather than a plain sha256 --
salting stops rainbow-table recovery of common IPs from the stored hash.

Config (review finding from Task 1: the reviewer couldn't judge the ip_hash
salt because no salting code existed yet -- this is where that gets decided):

session_secret() and ip_hash_salt() read COOKIE_SECRET / IP_HASH_SALT from
the environment AT CALL TIME, not import time (Task 4 fix-round-1 correction:
the original design snapshotted these into module-level constants read once
at import -- SESSION_SECRET from a DIFFERENT env var, DEMO_SESSION_SECRET,
that no other module or the plan doc ever used. main.py and the whole plan
(30+ references) standardized on COOKIE_SECRET; the DEMO_SESSION_SECRET name
was a naming slip introduced dispatching Task 2, never caught until Task 4's
implementer noticed main.py couldn't see this module's constant. An
import-time snapshot under a name nothing else reads is a silent split-brain:
set COOKIE_SECRET on the server and this module still returns None while
main.py's own os.environ reads saw it -- two sources of truth with different
lifetimes. Reading at call time removes both problems at once: one env var
name, and no snapshot to go stale relative to a monkeypatched/updated
environment.). Neither is a hardcoded constant in source -- this repo is
public (github.com/jongorecki/rulemancer), so a literal default would ship a
known secret/salt to every reader. A fixed salt also makes ip_hash
correlatable across deployments and reversible: IPv4 space is only ~4 billion
addresses, cheap to hash in bulk and match against a stored hash once the
salt is known. This is also why callers must never fall back to
`os.environ.get("IP_HASH_SALT", "")` -- an empty-string salt is not "no
salt," it silently produces PLAIN unsalted sha256-HMAC hashes over that same
~4B-address space, which is exactly the reversible-rainbow-table case this
module exists to prevent. A future reader may be tempted to "simplify" the
empty-string default back in; don't -- it defeats the whole point of salting.

When the env var is absent, these accessors return None -- fail CLOSED, not a
random-per-process fallback, matching the existing ADMIN_TOKEN pattern in
api/main.py (_require_admin_token: unset token -> 503, never silently open).
A random fallback would look convenient in local dev but is actively wrong in
production: multiple worker processes would each mint their own secret, so a
cookie signed by one worker fails verification on another, and a missing
env var would silently "work" instead of surfacing as a config error. It is
the caller's job (api/main.py's _require_demo_config(), used on every path
that touches this module's crypto -- /unlock and the gated "/" route, and
Task 5's /answer) to check these for None and refuse to serve rather than
invent a value -- same shape as _require_admin_token's 503. Local dev sets
COOKIE_SECRET/IP_HASH_SALT in .env like every other secret in this repo (see
.env.example); until then, the gated-demo endpoints simply refuse to serve,
which is the correct failure mode for a public-facing gate.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time

COOKIE_MAX_AGE_S = 7 * 24 * 3600


def session_secret() -> str | None:
    """COOKIE_SECRET, read fresh on every call -- never cached at import, so
    a config change (or a test's monkeypatch.setenv) takes effect
    immediately. Returns None if unset; callers must fail closed (503), never
    pass None into sign_session/verify_session."""
    return os.environ.get("COOKIE_SECRET")


def ip_hash_salt() -> str | None:
    """IP_HASH_SALT, read fresh on every call -- same call-time contract as
    session_secret(). Returns None if unset; callers must fail closed (503),
    never fall back to "" (see module docstring: an empty salt is not 'no
    salt', it's unsalted and reversible)."""
    return os.environ.get("IP_HASH_SALT")


def sign_session(code_id: int, secret: str, issued_at: int | None = None) -> str:
    issued_at = issued_at if issued_at is not None else int(time.time())
    msg = f"{code_id}:{issued_at}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return f"{code_id}:{issued_at}:{sig}"


def verify_session(token: str | None, secret: str, now: int | None = None,
                    max_age_s: int = COOKIE_MAX_AGE_S) -> int | None:
    if not token:
        return None
    parts = token.split(":")
    if len(parts) != 3:
        return None
    code_id_str, issued_at_str, sig = parts
    if not code_id_str.isdigit() or not issued_at_str.lstrip("-").isdigit():
        return None
    code_id, issued_at = int(code_id_str), int(issued_at_str)
    expected = hmac.new(secret.encode("utf-8"), f"{code_id}:{issued_at}".encode("utf-8"),
                         hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    now = now if now is not None else int(time.time())
    if now - issued_at > max_age_s:
        return None
    return code_id


def hash_ip(ip: str, salt: str) -> str:
    return hmac.new(salt.encode("utf-8"), ip.encode("utf-8"), hashlib.sha256).hexdigest()
