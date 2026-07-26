# Plan — multi-turn generation stability (follow-up answers flake ~50%)

## The measured problem (2026-07-22)

With `history` present, the sonnet-5 structured-output call collapses to a
degenerate response — `answered=false`, empty citations, empty or fragment
text — at a drastically elevated rate:

- Multi-turn (Grist/Animate Dead follow-up thread): 3 good / 3 bad across
  today's 4 draws + the LOG session's 2. ~50% failure.
- Single-turn, same question, same retrieval, same selected rulings:
  clean 2,188-char correct answer; historical single-turn base rate is
  ~one flake ever (c018) across 50+ graded draws.

Retrieval, card carryover, and the mini-RAG are healthy on the failing
draws (15 rules retrieved, Animate Dead ruling #4 selected rank-1). The
failure is entirely in the final generation call. The existing retry
doesn't fire because the degenerate output PARSES fine.

## Candidate mechanisms (fix addresses both; not distinguishable cheaply)

1. **Format contradiction:** prior assistant turns are injected as plain
   prose messages, but the reply must be `Answer` JSON. The transcript
   pattern (assistant speaks prose) fights the required output format.
2. **Grounding confusion:** history's assistant turns cite rules (e.g.
   903.3) that are NOT in the current context; the "ground ONLY in provided
   rules" guard may tip the model into a degenerate decline.

## What (two changes in `generate/answer.py`)

### A. History moves into the final user message (no more prose assistant turns)

Replace the real-message injection (`msgs = history + [user]`) with a
condensed-transcript block inside the single user message, above the rules
context — the same shape the rewriter already consumes:

```
Conversation so far (for context only):
User: ...
Assistant: ...

Rules context:
[...]
```

- Same clipping as the rewriter path (last N turns, per-turn char clip;
  reuse the existing `convo_ctx` construction — build once, use for both).
- The history-gated system-prompt line stays, reworded to point at the
  transcript block ("read the final question in the context of the
  conversation transcript provided").
- The message list is now ALWAYS a single user message → the structured-
  output pattern is identical to the single-turn path that graded 31/31.
- Single-turn path stays byte-identical (all of this is gated on
  `history`), so no eval number moves.

### B. Targeted retry on degenerate output (to-do #6, both paths)

Current retry only catches parse failures. Add: after a successful parse,
treat as degenerate-and-retryable iff ALL of:

- `answered == false`
- `citations == []`
- `len(text.strip()) < 80` (an honest decline explains what's missing —
  today's specimens were 0 and ~70 chars; real declines in the eval history
  run well past 200)

One extra attempt (shared with the existing retry budget: max 2 calls
total, not 2+2). If the retry is also degenerate, return the better of the
two (longer text) — never loop. The honest-decline guard survives: a
genuine decline with substantive text is untouched, and even a short
genuine decline just costs one extra call before being returned as-is.

## Risks / what this deliberately does NOT do

- Does not touch the rewriter, retrieval, card carryover, or the API
  contract. `history` still arrives the same way.
- The transcript block adds tokens to the user message — bounded by the
  existing clipping (6 turns × 500 chars ≈ 3k chars max).
- The retry can double latency on degenerate draws (~50s → ~100s worst
  case). Acceptable for a private demo; streaming is the real fix later.
- Follow-up rewrite mis-anchor (to-do #5) is adjacent but SEPARATE — not
  in this slice.

## Verification (before calling it fixed)

1. 5 fresh draws of the Grist/Animate Dead follow-up thread through the
   live API: expect ≥4/5 `answered=true` with citations (vs 3/6 baseline).
2. 1 single-turn control (same question, no history): still correct.
3. Grep-level check that the single-turn prompt string is untouched
   (history=None path identical), preserving every eval number.
4. LOG.md entry with the before/after rates.
