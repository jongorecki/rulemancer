# Slice 4 Task 5 (cookie requirement + event logging only -- per-code cap is
# Task 6, budget breaker is Task 7). Same in-process route-function
# convention as tests/test_api_debug.py; a fake agent stands in for the real
# RulesAgent so no network/API key is needed.

import pytest
from fastapi import Request

from rulesagent.api import main
from rulesagent.contracts import Answer
from rulesagent.demo_db import create_code, events_for_code, get_code_by_value


class _FakeAgent:
    model = "claude-opus-5"

    def __init__(self):
        self.last_cards = []
        self.last_retrieved = []
        self.last_rewritten = None
        self.last_ruling_selection = {}
        self.last_unresolved_refs = []
        self.last_uncited_success = False
        self.last_fuzzy_fallbacks = []
        self.last_usage = {"input_tokens": 500, "output_tokens": 200,
                            "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
        self.call_count = 0  # fix round 1 finding 1: rejection tests assert
        # this stays 0 -- a refactor that moved a guard's `return` below the
        # agent.answer() call would spend money on unauthenticated requests
        # while every status-code-only assertion kept passing.

    def answer(self, question, history=None):
        self.call_count += 1
        return Answer(text="An honest answer.", tldr="tldr", citations=[],
                       answered=True, suggested_followups=[])


def _fake_request(cookie: str | None = None) -> Request:
    headers = [(b"cookie", f"{main.COOKIE_NAME}={cookie}".encode())] if cookie else []
    scope = {"type": "http", "headers": headers, "client": ("203.0.113.9", 12345),
              "method": "POST", "path": "/answer"}
    return Request(scope)


@pytest.fixture(autouse=True)
def _fake_agent(monkeypatch):
    agent = _FakeAgent()
    monkeypatch.setitem(main._state, "agent", agent)
    monkeypatch.setitem(main._state, "chunk_map", {})
    return agent


def test_gate_disabled_answer_works_without_cookie(monkeypatch):
    monkeypatch.delenv("COOKIE_SECRET", raising=False)
    req = main.AnswerRequest(question="Does trample get through deathtouch?")
    resp = main.answer(req, request=_fake_request())
    assert resp.answered is True


def test_gate_enabled_no_cookie_returns_friendly_401(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    monkeypatch.setattr(main, "DEMO_DB", tmp_path / "demo.db")
    req = main.AnswerRequest(question="Does trample get through deathtouch?")

    resp = main.answer(req, request=_fake_request(cookie=None))

    assert resp.status_code == 401
    assert b"<html" in resp.body.lower()


def test_gate_enabled_valid_cookie_answers_and_logs_query_event(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test")
    from rulesagent.demo_auth import sign_session
    token = sign_session(code_id, "test-secret")
    req = main.AnswerRequest(question="Does trample get through deathtouch?")

    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.answered is True
    events = events_for_code(db, code_id)
    assert len(events) == 1
    assert events[0]["question"] == "Does trample get through deathtouch?"
    assert events[0]["input_tokens"] == 500
    assert events[0]["output_tokens"] == 200
    assert events[0]["cost_usd"] > 0


def test_gate_enabled_revoked_code_returns_friendly_403(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test")
    from rulesagent.demo_db import revoke_code
    from rulesagent.demo_auth import sign_session
    revoke_code(db, code_id)
    token = sign_session(code_id, "test-secret")
    req = main.AnswerRequest(question="q")

    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.status_code == 403


# --- Fix round 1, finding 1 -------------------------------------------------
# The real specification of this task: every rejection path must return
# before agent.answer() is ever invoked, expressed as an assertion on a
# call counter rather than just on the HTTP status code.


@pytest.mark.parametrize("case", ["no_cookie", "malformed_cookie", "expired_cookie",
                                   "wrong_key_cookie", "revoked_code"])
def test_rejections_never_call_the_model(monkeypatch, tmp_path, _fake_agent, case):
    import time as time_mod

    from rulesagent.demo_auth import sign_session
    from rulesagent.demo_db import revoke_code

    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test")

    if case == "no_cookie":
        token = None
    elif case == "malformed_cookie":
        token = "not-a-valid-session-token"
    elif case == "expired_cookie":
        stale_issued_at = int(time_mod.time()) - main.COOKIE_MAX_AGE_S - 3600
        token = sign_session(code_id, "test-secret", issued_at=stale_issued_at)
    elif case == "wrong_key_cookie":
        token = sign_session(code_id, "a-different-secret")
    else:  # revoked_code
        revoke_code(db, code_id)
        token = sign_session(code_id, "test-secret")

    req = main.AnswerRequest(question="Does trample get through deathtouch?")
    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.status_code in (401, 403)
    assert _fake_agent.call_count == 0


# --- Fix round 1, finding 2 -------------------------------------------------
# Once the model call has succeeded, real money is already spent -- a
# failure anywhere in the post-call bookkeeping (cost calc, ip hashing,
# enrichment) must still leave a `query` event row behind, and must not
# turn a successful answer into a 500 for the caller.


def test_post_call_cost_calc_failure_still_writes_query_event_and_answers(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test")
    from rulesagent.demo_auth import sign_session
    token = sign_session(code_id, "test-secret")
    req = main.AnswerRequest(question="Does trample get through deathtouch?")

    def _boom(*a, **kw):
        raise RuntimeError("pricing table exploded")

    monkeypatch.setattr(main, "cost_usd", _boom)

    resp = main.answer(req, request=_fake_request(cookie=token))

    # The model already answered -- a bookkeeping failure must not surface
    # as a 500 to the caller.
    assert resp.answered is True

    events = events_for_code(db, code_id)
    assert len(events) == 1
    assert events[0]["question"] == "Does trample get through deathtouch?"
    assert events[0]["input_tokens"] == 500
    assert events[0]["output_tokens"] == 200
    # cost_usd is genuinely unknown here -- recorded as a visible gap
    # (None/NULL), never a fabricated number.
    assert events[0]["cost_usd"] is None


# --- Task 6 -------------------------------------------------------------
# Per-code max_queries cap. Checked BEFORE agent.answer() is called, and
# counted against committed `query` events only -- a request that never
# reached the model must not consume quota.


def test_at_cap_returns_friendly_402_and_does_not_call_agent(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test", max_queries=2)
    from rulesagent.demo_auth import sign_session
    from rulesagent.demo_db import log_event
    token = sign_session(code_id, "test-secret")
    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="q1", cost_usd=0.01)
    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="q2", cost_usd=0.01)

    calls = []
    monkeypatch.setattr(main._state["agent"], "answer",
                         lambda *a, **k: calls.append(1) or pytest.fail("agent must not be called at cap"))
    req = main.AnswerRequest(question="q3")

    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.status_code == 402
    assert calls == []


def test_under_cap_still_works(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test", max_queries=2)
    from rulesagent.demo_auth import sign_session
    from rulesagent.demo_db import log_event
    token = sign_session(code_id, "test-secret")
    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="q1", cost_usd=0.01)
    req = main.AnswerRequest(question="q2")

    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.answered is True


def test_null_max_queries_falls_back_to_default_25(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test", max_queries=None)
    from rulesagent.demo_auth import sign_session
    token = sign_session(code_id, "test-secret")
    req = main.AnswerRequest(question="q1")

    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.answered is True  # 1 query against an unset (None -> 25) cap is fine


def test_boundary_25th_query_succeeds_26th_is_refused(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test", max_queries=25)
    from rulesagent.demo_auth import sign_session
    from rulesagent.demo_db import log_event
    token = sign_session(code_id, "test-secret")
    for i in range(24):
        log_event(db, code_id=code_id, kind="query", ip_hash="h", question=f"q{i}", cost_usd=0.01)

    # 25th query: 24 already logged, this is the cap-th -- must succeed.
    resp25 = main.answer(main.AnswerRequest(question="q25"), request=_fake_request(cookie=token))
    assert resp25.answered is True

    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="q25", cost_usd=0.01)

    calls = []
    monkeypatch.setattr(main._state["agent"], "answer",
                         lambda *a, **k: calls.append(1) or pytest.fail("agent must not be called past cap"))
    resp26 = main.answer(main.AnswerRequest(question="q26"), request=_fake_request(cookie=token))
    assert resp26.status_code == 402
    assert calls == []


# --- Task 6, fix round 1 finding 1 --------------------------------------
# The cap check and the quota-consuming `query` event write must be atomic
# with respect to each other, or concurrent requests on the same code can
# all read the same pre-spend count, all pass, and all call the model.
# This is a genuine race: it needs real threads hitting the sync handler
# at (approximately) the same instant, not two sequential calls -- a
# barrier holds every worker thread at the starting line, and the fake
# agent's answer() sleeps briefly so any requests that got past the check
# concurrently would actually overlap inside the model call, not just
# happen to interleave by accident.


def test_concurrent_requests_at_cap_only_one_gets_through(monkeypatch, tmp_path):
    import threading
    import time as time_mod

    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test", max_queries=1)
    from rulesagent.demo_auth import sign_session
    token = sign_session(code_id, "test-secret")
    # One query of quota already used -- exactly one slot left. If the
    # race is open, every thread below can see "0 used, cap 1" at once.

    n_workers = 8
    start_barrier = threading.Barrier(n_workers)
    call_lock = threading.Lock()
    call_count = {"n": 0}

    def _slow_answer(question, history=None):
        with call_lock:
            call_count["n"] += 1
        time_mod.sleep(0.05)  # widen the window a buggy (unlocked) check would race in
        return Answer(text="An honest answer.", tldr="tldr", citations=[],
                      answered=True, suggested_followups=[])

    monkeypatch.setattr(main._state["agent"], "answer", _slow_answer)

    results = [None] * n_workers

    def _worker(i):
        start_barrier.wait()
        req = main.AnswerRequest(question=f"concurrent-q{i}")
        results[i] = main.answer(req, request=_fake_request(cookie=token))

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(n_workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly one request reached the model; every other request was
    # refused with the friendly 402 before agent.answer() ran.
    assert call_count["n"] == 1
    statuses = [getattr(r, "status_code", 200) for r in results]
    assert statuses.count(402) == n_workers - 1
    assert statuses.count(200) == 1

    # Exactly one `query` event exists for this code -- the quota was
    # reserved atomically with the check, not double-spent.
    query_events = events_for_code(db, code_id)
    assert len(query_events) == 1


# --- Task 7 ---------------------------------------------------------------
# Global daily USD budget breaker. Checked BEFORE agent.answer() is called,
# same as the per-code cap, but summed across every code -- once the day's
# logged spend hits DAILY_BUDGET_USD, every code is refused until UTC
# midnight rolls the day over.


def test_over_daily_budget_returns_friendly_503_and_does_not_call_agent(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    monkeypatch.setenv("DAILY_BUDGET_USD", "1.00")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test", max_queries=100)
    from rulesagent.demo_auth import sign_session
    from rulesagent.demo_db import log_event
    from datetime import datetime, timezone
    token = sign_session(code_id, "test-secret")
    today = datetime.now(timezone.utc).date().isoformat()
    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="q1", cost_usd=1.50)

    calls = []
    monkeypatch.setattr(main._state["agent"], "answer",
                         lambda *a, **k: calls.append(1) or pytest.fail("agent must not be called over budget"))
    req = main.AnswerRequest(question="q2")

    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.status_code == 503
    assert calls == []


def test_under_daily_budget_still_works(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    monkeypatch.setenv("DAILY_BUDGET_USD", "10.00")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test", max_queries=100)
    from rulesagent.demo_auth import sign_session
    from rulesagent.demo_db import log_event
    token = sign_session(code_id, "test-secret")
    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="q1", cost_usd=0.05)
    req = main.AnswerRequest(question="q2")

    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.answered is True


def test_missing_daily_budget_env_uses_conservative_default(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.delenv("DAILY_BUDGET_USD", raising=False)
    assert main.DAILY_BUDGET_USD_DEFAULT == 5.0


# --- Task 7, fix round 1 -------------------------------------------------
# NULL cost_usd rows (a prior cost-calculation failure) must not vanish
# from SUM(cost_usd) -- but tripping the breaker on the mere presence of
# one NULL row was overruled: it halts the whole demo for the rest of the
# UTC day over one bounded, small failure. Each unpriced row is now priced
# at main.UNPRICED_QUERY_ESTIMATE_USD ($0.15, a deliberately-high stand-in
# for one query) and folded into the running total instead.


def test_unpriced_row_is_added_to_total_at_the_conservative_estimate(monkeypatch, tmp_path):
    """Two priced rows + one unpriced row must total
    priced_sum + UNPRICED_QUERY_ESTIMATE_USD, not just the priced sum."""
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test", max_queries=100)
    from rulesagent.demo_db import log_event
    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="q1", cost_usd=0.10)
    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="q2", cost_usd=0.20)
    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="q3", cost_usd=None)

    from datetime import datetime, timezone
    from rulesagent.demo_db import daily_spend
    today = datetime.now(timezone.utc).date().isoformat()
    priced_sum = daily_spend(db, today)
    unpriced_count = main._unpriced_query_count(db, today)
    total = priced_sum + unpriced_count * main.UNPRICED_QUERY_ESTIMATE_USD

    assert priced_sum == pytest.approx(0.30)
    assert unpriced_count == 1
    assert total == pytest.approx(0.30 + main.UNPRICED_QUERY_ESTIMATE_USD)
    assert total == pytest.approx(0.45)


def test_unpriced_rows_alone_do_not_trip_the_breaker_while_estimate_stays_under_budget(
    monkeypatch, tmp_path,
):
    """The demo must not brick itself over a single unpriced row: with a
    $10 budget and one NULL-cost row (estimated at $0.15), the next request
    must still be served."""
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    monkeypatch.setenv("DAILY_BUDGET_USD", "10.00")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test", max_queries=100)
    from rulesagent.demo_auth import sign_session
    from rulesagent.demo_db import log_event
    token = sign_session(code_id, "test-secret")
    log_event(db, code_id=code_id, kind="query", ip_hash="h", question="q1", cost_usd=None)

    req = main.AnswerRequest(question="q2")
    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.answered is True


def test_enough_unpriced_rows_to_exceed_budget_do_trip_it(monkeypatch, tmp_path):
    """Estimated spend from unpriced rows alone can still exceed the
    budget and trip the breaker once there are enough of them."""
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    monkeypatch.setenv("DAILY_BUDGET_USD", "1.00")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test", max_queries=100)
    from rulesagent.demo_auth import sign_session
    from rulesagent.demo_db import log_event
    token = sign_session(code_id, "test-secret")
    # 7 unpriced rows * $0.15 = $1.05 >= $1.00 budget.
    for i in range(7):
        log_event(db, code_id=code_id, kind="query", ip_hash="h", question=f"q{i}", cost_usd=None)

    calls = []
    monkeypatch.setattr(main._state["agent"], "answer",
                         lambda *a, **k: calls.append(1) or pytest.fail(
                             "agent must not be called once estimated unpriced spend exceeds budget"))
    req = main.AnswerRequest(question="q_final")

    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.status_code == 503
    assert calls == []


# --- task-length-guard ---------------------------------------------------
# MAX_QUESTION_CHARS = 2000, derived by doubling the longest real question
# across the full 1,409-question RulesGuru corpus (1,013 chars) -- see the
# constant's comment in main.py. Checked inside the same `with _lock:`
# critical section as the cap/budget checks, before agent.answer() is ever
# called -- same no-model-call contract every other rejection above proves
# with a call-count assertion.


def _fake_request_with_headers(cookie: str | None = None, headers: dict | None = None) -> Request:
    raw_headers = [(b"cookie", f"{main.COOKIE_NAME}={cookie}".encode())] if cookie else []
    if headers:
        raw_headers += [(k.encode(), v.encode()) for k, v in headers.items()]
    scope = {"type": "http", "headers": raw_headers, "client": ("203.0.113.9", 12345),
              "method": "POST", "path": "/answer"}
    return Request(scope)


def test_question_at_exact_limit_succeeds(monkeypatch, tmp_path, _fake_agent):
    monkeypatch.delenv("COOKIE_SECRET", raising=False)
    q = "a" * main.MAX_QUESTION_CHARS
    req = main.AnswerRequest(question=q)

    resp = main.answer(req, request=_fake_request())

    assert resp.answered is True
    assert _fake_agent.call_count == 1


def test_question_one_char_over_limit_is_rejected_no_model_call(monkeypatch, tmp_path, _fake_agent):
    monkeypatch.delenv("COOKIE_SECRET", raising=False)
    q = "a" * (main.MAX_QUESTION_CHARS + 1)
    req = main.AnswerRequest(question=q)

    resp = main.answer(req, request=_fake_request())

    assert resp.status_code == 413
    assert _fake_agent.call_count == 0


def test_leading_trailing_whitespace_does_not_count_toward_limit(monkeypatch, tmp_path, _fake_agent):
    # A paste that carries surrounding whitespace/newlines must be measured
    # AFTER stripping -- otherwise a legitimate at-limit question with a
    # trailing newline from a copy-paste would trip the guard for free.
    monkeypatch.delenv("COOKIE_SECRET", raising=False)
    q = "  \n" + ("a" * main.MAX_QUESTION_CHARS) + "\n\n  "
    req = main.AnswerRequest(question=q)

    resp = main.answer(req, request=_fake_request())

    assert resp.answered is True
    assert _fake_agent.call_count == 1


def test_whitespace_only_question_is_rejected(monkeypatch):
    # Pre-existing check (top of answer(), before gating) -- verified here,
    # not duplicated, so the length guard's test coverage doesn't imply this
    # gap is new.
    from fastapi import HTTPException

    monkeypatch.delenv("COOKIE_SECRET", raising=False)
    req = main.AnswerRequest(question="   \n\t  ")

    with pytest.raises(HTTPException) as exc_info:
        main.answer(req, request=_fake_request())

    assert exc_info.value.status_code == 400


def test_multibyte_character_counts_as_one_char_not_bytes(monkeypatch, tmp_path, _fake_agent):
    # Accented letters, em dashes, CJK -- each is ONE Python str character
    # even though it's several bytes in UTF-8. An at-limit question made of
    # multi-byte characters must still succeed, not get penalised for
    # encoding.
    monkeypatch.delenv("COOKIE_SECRET", raising=False)
    q = ("é—中" * (main.MAX_QUESTION_CHARS // 3 + 1))[: main.MAX_QUESTION_CHARS]
    assert len(q) == main.MAX_QUESTION_CHARS
    req = main.AnswerRequest(question=q)

    resp = main.answer(req, request=_fake_request())

    assert resp.answered is True
    assert _fake_agent.call_count == 1


def test_length_rejection_is_json_for_fetch_request(monkeypatch, tmp_path, _fake_agent):
    import json as json_mod

    monkeypatch.delenv("COOKIE_SECRET", raising=False)
    q = "a" * (main.MAX_QUESTION_CHARS + 1)
    req = main.AnswerRequest(question=q)
    fake_req = _fake_request_with_headers(headers={"accept": "application/json"})

    resp = main.answer(req, request=fake_req)

    assert resp.status_code == 413
    body = json_mod.loads(resp.body)
    assert "too long" in body["detail"].lower()
    assert str(main.MAX_QUESTION_CHARS) in body["detail"]
    assert _fake_agent.call_count == 0


def test_length_rejection_is_html_for_browser_post(monkeypatch, tmp_path, _fake_agent):
    monkeypatch.delenv("COOKIE_SECRET", raising=False)
    q = "a" * (main.MAX_QUESTION_CHARS + 1)
    req = main.AnswerRequest(question=q)
    fake_req = _fake_request_with_headers(headers={"accept": "text/html,application/xhtml+xml"})

    resp = main.answer(req, request=fake_req)

    assert resp.status_code == 413
    assert b"<html" in resp.body.lower()
    assert _fake_agent.call_count == 0


def test_gated_length_rejection_logs_denied_event_with_truncated_question(monkeypatch, tmp_path, _fake_agent):
    import sqlite3

    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test")
    from rulesagent.demo_auth import sign_session
    token = sign_session(code_id, "test-secret")
    q = "a" * (main.MAX_QUESTION_CHARS + 500)
    req = main.AnswerRequest(question=q)

    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.status_code == 413
    assert _fake_agent.call_count == 0

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM events WHERE code_id = ? AND kind = 'denied'", (code_id,)
    ).fetchall()]
    conn.close()
    assert len(rows) == 1
    # The full oversized question is never stored -- only a short, clearly
    # truncated stand-in.
    assert len(rows[0]["question"]) < len(q)
    assert "truncated" in rows[0]["question"]


def test_daily_budget_reads_utc_day_boundary_not_yesterdays_spend(monkeypatch, tmp_path):
    """A row stamped for yesterday (UTC) must not count toward today's
    budget -- otherwise the breaker never resets and the demo stays down
    forever after one busy day."""
    monkeypatch.setenv("COOKIE_SECRET", "test-secret")
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    monkeypatch.setenv("DAILY_BUDGET_USD", "1.00")
    db = tmp_path / "demo.db"
    monkeypatch.setattr(main, "DEMO_DB", db)
    code_id = create_code(db, "raptor-quill-42", "Test", max_queries=100)
    from rulesagent.demo_auth import sign_session
    import sqlite3
    from datetime import datetime, timedelta, timezone
    token = sign_session(code_id, "test-secret")

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO events (code_id, ts, kind, ip_hash, question, answered, "
        "input_tokens, output_tokens, cost_usd, latency_ms) "
        "VALUES (?, ?, 'query', 'h', 'q0', 1, 10, 10, 1.50, 100)",
        (code_id, yesterday),
    )
    conn.commit()
    conn.close()

    req = main.AnswerRequest(question="q1")
    resp = main.answer(req, request=_fake_request(cookie=token))

    assert resp.answered is True
