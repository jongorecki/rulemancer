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

SESSION_SECRET and IP_HASH_SALT are read ONCE at import time from env vars
(DEMO_SESSION_SECRET, IP_HASH_SALT), the same module-level-constant pattern
as demo_db.DEFAULT_DEMO_DB reading DEMO_DB_PATH. Neither is a hardcoded
constant in source -- this repo is public (github.com/jongorecki/rulemancer),
so a literal default would ship a known secret/salt to every reader. A fixed
salt also makes ip_hash correlatable across deployments and reversible: IPv4
space is only ~4 billion addresses, cheap to hash in bulk and match against a
stored hash once the salt is known.

When the env var is absent, these constants are None -- fail CLOSED, not a
random-per-process fallback, matching the existing ADMIN_TOKEN pattern in
api/main.py (_require_admin_token: unset token -> 503, never silently open).
A random fallback would look convenient in local dev but is actively wrong in
production: multiple worker processes would each mint their own secret, so a
cookie signed by one worker fails verification on another, and a missing
env var would silently "work" instead of surfacing as a config error. It is
the caller's job (the /unlock and /answer endpoints, Task 4/5) to check these
for None and refuse to serve rather than invent a value -- same shape as
_require_admin_token's 503. Local dev sets DEMO_SESSION_SECRET/IP_HASH_SALT
in .env like every other secret in this repo (see .env.example); until then,
the gated-demo endpoints simply refuse to serve, which is the correct
failure mode for a public-facing gate.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time

COOKIE_MAX_AGE_S = 7 * 24 * 3600

# Read once at import -- verify_session/hash_ip take secret/salt as explicit
# parameters (Tasks 4/5/11 pass these constants in), so the crypto functions
# below stay pure and independently testable with no env dependency.
SESSION_SECRET = os.environ.get("DEMO_SESSION_SECRET")
IP_HASH_SALT = os.environ.get("IP_HASH_SALT")


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
