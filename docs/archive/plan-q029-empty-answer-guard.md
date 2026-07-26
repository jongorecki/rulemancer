# Plan — q029 empty-answer guard + c012 silent-drop observability (two independent Rule 0 mini-plans)

Status: **APPROVED by Jon 2026-07-23, with amendments.** His rulings on the open questions:

1. **Plan A scope (amended):** catch blank-text as degenerate (as planned), AND additionally **flag** any `answered: true` answer with zero citations — "then it's not grounding in the rules." Interpretation applied (flag ≠ retry): blank text triggers the retry/degenerate machinery; success-with-no-citations is **surfaced** (log warning + a `Debug` field + visible in telemetry), NOT auto-retried — this respects the false-positive concern for legitimately ruling-grounded answers while making every ungrounded "success" auditable. If Jon meant no-citations to also retry, say so and it's a two-line change.
2. **PROMPT_VERSION bump: skipped** (confirmed — nothing about the prompt changes).
3. **Plan B crash→graceful: approved, catch broadly** — Jon: "catch all error types broadly, which should help us audit this." The broad `except Exception` ships with the warning log as the audit trail.
4. **Does the transient-fetch worry (Plan B shape 2) go away once docs/plan-scryfall-local-bulk.md ships?** Mostly at the network level, yes — local lookups can't network-fail. But the observability stays valuable: (a) the local-bulk slice ships later, so there's an interim window; (b) local lookups still have non-network failure modes (disk, db, code bugs); (c) post-migration, a silent "card ref failed" log line is exactly the proof the migration worked — the line should simply stop appearing. So Plan B ships as designed, and its logging becomes the local-bulk migration's verification signal.

**Sequencing:** implementation must wait until the in-flight prompt-v3 A/B generation runs fully complete — these changes touch the production answer path (`answer.py`), and editing it mid-sweep would make late re-runs inconsistent with early ones.

Two small, independent production-path fixes bundled in one doc — both surfaced from the L1 diagnostic pass (LOG.md 2026-07-21). Either can ship without the other.

---

## Plan A — q029 empty-answer guard (`_degenerate()` blind spot)

### Problem

`_degenerate()` (`src/rulesagent/generate/answer.py:201-207`) is the retry-then-degrade guard applied to every parsed draw (call site `answer.py:533`, `if parsed is not None and _degenerate(parsed):`). Today it only inspects the `answered=False` branch:

```python
def _degenerate(a: Answer) -> bool:
    return (not a.answered) and not a.citations and len(a.text.strip()) < 80
```

L1's gate 4 caught q029 drawing `answered:true` with **completely blank `text`** (LOG.md, "2026-07-21 — L1 cross-refs shipped": *"NEW BUG found by L1's gate 4: q029 answered:true with EMPTY text slips past `_degenerate()` (fires only on answered:false)"*). `not a.answered` short-circuits before that draw is ever inspected, so it's treated as a normal good answer: no retry, no low-confidence UI state, `ATTRIBUTION` still appended if cards were in play. The frontend renders a blank "answer" as if the bot had spoken.

Note for scoping: the system prompt (`answer.py:63-69`) also says "whenever answered is true the citations field MUST be non-empty" — so `answered:true` + empty citations is *also* a contract violation. But the only **observed** specimen is blank `text`, not empty-citations-with-real-text. Scoping to the observed shape matches this repo's own habit here (`_degenerate`'s docstring: "Deliberately narrow... clears the observed degenerate specimens... with margin").

### Exact proposed change (`src/rulesagent/generate/answer.py`, no SYSTEM/schema change → **no PROMPT_VERSION bump**, per its own bump rule)

1. **Extend `_degenerate()`** with a narrow `answered=True` branch:
```python
def _degenerate(a: Answer) -> bool:
    if not a.answered:
        return not a.citations and len(a.text.strip()) < 80
    # answered=True but no actual content: q029 (2026-07-21, L1 gate 4) drew
    # answered:true with fully blank text. Deliberately blank-only (not a
    # length threshold) so a legitimately short answered=True answer never
    # matches — that's the only shape observed.
    return not a.text.strip()
```
Since `_degenerate()` is already called unconditionally on every draw, this one edit routes q029-shaped draws into the existing retry/weak-fallback machinery for free.

2. **Fix the weak-draw fallback** (`answer.py:547-548`) so a persistently-blank `answered:true` draw can't leak through even after both retries. Today `if parsed is None and weak is not None: parsed = weak` returns `weak` as-is — fine for an honest short `answered=False` decline, but wrong for a still-blank `answered=True` draw (reproduces the bug). Tighten to:
```python
if parsed is None and weak is not None and not weak.answered:
    parsed = weak
```
so a blank `answered=True` `weak` falls through to the existing honest "(no structured answer...)" `Answer` (lines 549-560) instead.

Net diff ≈12-15 lines including comments — well under 50.

### Edge cases
- Whitespace-only text — caught via `.strip()`.
- Blank text + non-empty citations — still caught (blank text is bad regardless of citations).
- Non-blank short text (`"Yes."`) — NOT caught, deliberately, no evidence it's broken.
- Non-blank text + empty citations (contract violation, unobserved) — NOT caught this slice (see Non-goals).
- Both retry attempts blank — now falls through to the honest non-answer message instead of returning either.
- `weak`-selection tie-break: a blank `answered:true` draw (len 0) vs. a real `answered:false` decline (len >0) — `weak` still *stores* by length regardless of `answered`, but only an `answered:false` `weak` is ever *used* at return; needs an explicit test (below) to pin down.

### TDD test list
New `tests/test_degenerate.py` (unit, no client) + agent-level tests via the same fake-`.messages.parse`-client pattern `tests/test_answer_prompt_v3.py`/`test_prompt_identity.py` already use:
1. `answered=True, text=""` → True (exact q029 shape).
2. `answered=True, text="   \n\t"` → True.
3. `answered=True, text="Yes."` → False (regression guard for terse legit answers).
4. `answered=True, text=""`, citations populated → True.
5. `answered=False, text=""`, citations=[] → True (existing case, regression guard).
6. `answered=False`, 200+ char honest decline → False (existing case, regression guard).
7. `answered=True`, real 300-char answer + citations → False (regression guard).
8. Attempt 1 q029-shaped, attempt 2 real answer → `answer()` returns the real answer.
9. Both attempts q029-shaped → `answer()` returns the honest non-answer `Answer` (`answered=False`), not either blank draft — the fallback-guard test.
10. Attempt 1 q029-shaped, attempt 2 raises `ValidationError` → same honest fallback.
11. Existing False-branch degenerate case still retries as before (no regression).
12. No-cards path with a q029-shaped draw (q029's real question had no bracketed cards).

### What could regress / detection
- Misclassifying a legit short answer as degenerate → extra retry latency, or worse, the honest-fallback message. Mitigated by blank-only scoping; test 3 pins it. Prod detection: watch `queries` telemetry (`main.py` `_log_row`) `text` column for a spike in the literal "(no structured answer..." fingerprint on previously-fine questions.
- `weak` length-comparison logic accidentally preferring a blank draw's len(0) in a way that discards a usable decline — explicit test needed before ship.
- Eval numbers: False-branch is byte-identical; True-branch only fires on literal blank text (no passing eval answer should have that shape). Verify via a before/after eval diff, not a re-baseline.
- Not bumping PROMPT_VERSION is itself a judgment call worth flagging, not an oversight.

### Non-goals
- `answered=True` + non-blank text + empty citations (unobserved contract-violation shape).
- SYSTEM prompt text or `Answer` schema changes.
- Retry budget (2 attempts), `max_tokens`, model pinning.
- Re-scoring frozen eval/judge artifacts.

### Open questions for Jon
- Blank-text-only (recommended), or also catch `answered=True` + empty citations regardless of length (broader, unproven, risks false positives on legit card-only answers)?
- OK to skip the PROMPT_VERSION bump?

---

## Plan B — c012 silent-drop observability (unresolved card refs)

### Problem

The historical c012 symptom doesn't reproduce by reading today's code: `docs/plan-prompt-tuning.md` §7 already traced ref-parsing → dedup → `get_card()` → `_format_cards()` and found no cap/drop path. Today's diagnostic adds: Lithoform Engine's cache entry is healthy, and the assembled prompt contains all three cards' oracle text. So current code doesn't explain the historical miss — the real, live gap is that ref resolution has **zero observability**, in `RulesAgent.answer()`:
```python
cards = [c for ref in all_refs if (c := get_card(ref, no_refresh=self.card_no_refresh)) is not None]
```
Two distinct failure shapes land here:
1. **Confirmed miss** (`get_card` → `None` on a genuine 404). Already an *intentional* design choice per the comment right above this line ("Unresolvable tokens... are silently dropped rather than erroring the whole answer... this is the call made here") — silent by design, but nothing records which ref or on which request.
2. **Transient fetch failure**. `scryfall.py`'s `_http_get` (lines 88-92) only special-cases a 404; any other bad status hits `response.raise_for_status()`, which **raises unhandled** — not converted to `None`. That propagates through `get_card()`, the comprehension, and `answer()`, and (no exception handler in `api/main.py`) surfaces as a generic 500 for the whole request. Loud, not silent — but still unattributed: `_log_row`'s `queries` insert (`main.py:318-332`) only fires after `agent.answer()` *returns*, so a crash logs nothing structured.

Converging both into one observable, non-crashing path is a real, deliberate behavior change on the error path (shape 2 goes from crash→graceful) — flagged explicitly, not hidden inside "observability only."

### Exact proposed change

1. **`answer.py`**: add `import logging` / `logger = logging.getLogger(__name__)` (mirrors `main.py`'s existing pattern), replace the comprehension with a loop:
```python
resolved, unresolved = [], []
for ref in all_refs:
    try:
        c = get_card(ref, no_refresh=self.card_no_refresh)
    except Exception as e:
        logger.warning("card ref failed to resolve (fetch error): %r: %r", ref, e)
        unresolved.append({"ref": ref, "reason": "error"}); continue
    if c is None:
        logger.warning("card ref failed to resolve (not found): %r", ref)
        unresolved.append({"ref": ref, "reason": "not_found"}); continue
    resolved.append(c)
cards = resolved
self.last_unresolved_refs = unresolved
```
`self.last_unresolved_refs: list[dict] | None = None` in `__init__`, same lifecycle/pattern as `self.last_crossref` (set every call).

2. **`main.py`**: read `agent.last_unresolved_refs` inside the existing `with _lock:` block, add one field to `Debug` (mirrors how `last_ruling_selection`/`last_retrieved` are already surfaced):
```python
class Debug(BaseModel):
    ...
    unresolved_card_refs: list[dict]   # NEW
```

Net diff ≈20-25 lines across both files.

### Edge cases
No brackets (`all_refs==[]`, no-op); same ref deduped across history+current (recorded once); cache-hit vs. live-fetch irrelevant (loop only sees `get_card`'s three outcomes); every ref fails → rules-only answer proceeds as today.

### TDD test list
Monkeypatch `get_card` at `answer`'s imported name (same seam as `test_answer_prompt_v3.py`'s `spies` fixture):
1. All refs resolve → `last_unresolved_refs == []`.
2. One 404 among two refs → 1 card resolved, `last_unresolved_refs == [{"ref":..., "reason":"not_found"}]`, `caplog` warning names the ref.
3. One raises (simulated `httpx` error) → `answer()` does **not** raise; other ref still resolves; `reason:"error"` recorded; warning logged — the regression test proving crash→graceful-degrade actually lands.
4. Failing ref referenced only in `history` → still recorded.
5. No brackets → `[]`, no warnings.
6. New minimal API test (none exists today) — `Debug.unresolved_card_refs` matches `agent.last_unresolved_refs` in an `/answer` response.

### What could regress / detection
- **The real risk**: a transient failure that used to 500 loudly now returns a plausible-looking but card-incomplete 200. No known caller keys off the 500 today, but it's a product-shape decision, not just a bugfix — see Open questions.
- `except Exception` is broad — will also swallow unrelated future bugs inside `get_card()` (e.g. a schema-mismatch `TypeError`) as a silent omission instead of a crash; the `logger.warning(%r)` is the only safety net.
- Detection: grep server logs for `"card ref failed to resolve"` post-deploy; eyeball `unresolved_card_refs` on known card-referencing questions.

### Non-goals
- No durable SQLite telemetry column for unresolved refs — `main.py`'s `CREATE TABLE IF NOT EXISTS` won't retroactively add a column to an existing `data/cache.db`; that's a real migration concern, out of scope here. Log line + Debug field are this slice's entire observability surface.
- Not wiring the separately-already-unwired `last_crossref` field into `Debug` — same kind of gap, but distinct, not touched here.
- No retry/backoff added to `scryfall.py`.
- No further re-diagnosis of the historical c012 transcript (§7's investigation is closed/non-reproducing).
- Frozen judge artifacts / eval harness / retrieval / prompt: untouched.

### Open questions for Jon
- Is crash→graceful-degrade for transient fetch errors the right call, or should this slice cover *only* the already-silent 404 path and leave the crash loud (drop the `except Exception`)? Recommended default is "catch both," but it's a behavior change worth explicit sign-off.
- OK leaving `except Exception` broad rather than narrowing to `httpx`-specific error types?

---

### Interplay with docs/plan-scryfall-local-bulk.md (drafted in parallel)

Plan B's observability survives the local-bulk migration unchanged: local lookups can still miss (true miss, fuzzy-fallback flag), and the unresolved-refs debug surface is exactly where those get reported. If the local-bulk plan ships, shape-2 (network transient) disappears from the primary path by construction — the logging then documents that it never fires, which is itself the verification.

### Critical files for implementation
- src/rulesagent/generate/answer.py
- src/rulesagent/tools/scryfall.py
- src/rulesagent/api/main.py
- src/rulesagent/contracts.py
- tests/test_answer_prompt_v3.py (fake-client pattern to reuse for new tests)
