# Overnight status — 2026-07-23 into 07-24

Live scratch file, updated as work lands. If the chain stalled, the first
unchecked box is where it stopped. Nothing here is a decision; decisions are
Jon's and are listed at the bottom.

## Spend so far

| item | status | cost |
|---|---|---|
| v5 grid, sonnet arm (8 cells x 3 q) | DONE, 0 errors | ~$0.70 est (no usage capture on this path) |
| v5 grid, gpt-5-mini arm (8 cells x 5 q) | running | ~$0.33 measured |
| c020 phase 2 | queued | ~$0.30 est |
| rewriter bakeoff (3 arms x 31 q x 3 passes) | queued | small — rewrites are short, embeddings cached by string |

## Sequence

- [x] `--qids` flag on both runners (`25bc639`, 240 tests)
- [x] **v5 GRID COMPLETE — 16 files, 64 rows, 0 errors.** Sonnet 8x3
      (c012/c014/c015), gpt-5-mini 8x5 (c002/c004/c011/c012/c015). Verified
      four DISTINCT prompt digests across the four cells, each cell's two runs
      agreeing: A `20c1ea7dd63c`, B `e8c3b17dd61a`, C `894b3fc20054`,
      D `474aa0ebcfb0`. The grid is four real variants, not four copies.
- [x] c011 stale-ruling diagnosis merged (`f841582`, plan doc only, no source)
- [x] rewriter slice merged to master — **267 tests pass** with the real corpus
- [x] **A** — c002 marked non-scoring, c020 added. Merged. Verified: 20 rows,
      ids c001-c020 contiguous, c002's question/gold untouched (still Charging
      Rhino), c020's question byte-identical to Jon's wording. Both cards
      re-verified live via Scryfall: Stampeding Rhino `{4}{G}` with trample,
      Vampire Nighthawk `{1}{B}{B}` flying/deathtouch/lifelink. **`gold` left
      empty — gold is Jon's to encode.**
- [x] **B** — heartbeat test pollution fixed and merged. Source was 4 tests in
      `test_resume_prompts_cache_guard.py` calling the runners end-to-end
      without redirecting `PROGRESS_DIR`. Fixed with an autouse fixture; the
      regression guard was proven to fire via a deliberate probe, then removed.
      **268 tests pass on master, and `_progress/` holds 17 files before and
      after the suite.**
- [x] judge-compare COMPLETE and merged (`judge_v5.py`). 64/64 judge calls,
      0 exceptions, 0 judge errors. Frozen judge imported unchanged.
- [ ] **c020 phase 2 — BLOCKED, deliberately. See "injection is live" below.**

## RESULT — the v5 grid, routed (verdicts are still Jon's)

| arm | cell | no flip | stable flip | unstable | c002 (monitored) |
|---|---|---|---|---|---|
| sonnet | A (v3 control) | 2 | **0** | 1 | — |
| sonnet | B (v3+inject) | 3 | **0** | 0 | — |
| sonnet | C (v4nl) | 3 | **0** | 0 | — |
| sonnet | D (**v5**) | 3 | **0** | 0 | — |
| gpt-5-mini | A (v3 control) | 3 | **0** | 1 | unstable x1 |
| gpt-5-mini | B (v3+inject) | 2 | **1** -> c011 | 1 | **stable x1** |
| gpt-5-mini | C (v4nl) | 1 | **2** -> c011, c015 | 1 | unstable x1 |
| gpt-5-mini | D (**v5**) | 3 | **0** | 1 | **stable x1** |

Cell A is the negative control (v3 vs v3) and shows **0 stable flips on both
arms**, so the zeros elsewhere are real rather than a broken comparison.

**Jon's grading queue:** c011 (cell B); c011 and c015 (cell C); plus the two
monitored c002 flips at B and D, which never enter a count.

**The controller is NOT making the v5 call.** The fact in the table is that
cell D produced zero scoring flips on either arm, at +603 tok/card query and
+509 tok/rules query. What that means is Jon's to decide, alongside the answers.

## STOP — symbol injection is ALREADY LIVE in production, ungated

`answer.py:792-795` appends the symbol-reference block to the user message with
**no `PROMPT_VERSION` gate**:

```python
symbols = _symbols_present(f"{_card_symbol_text(cards)} {question}")
symbol_block = _symbol_reference_block(symbols)
if symbol_block:
    user += f"\n\n{symbol_block}"
```

`PROMPT_VERSION = 3` selects the SYSTEM text only. So **production today is v3
bullets + injection, which is cell B — not cell A.** The plan labels cell A
"v3 — production baseline"; that label stopped being true when Slice 2 shipped.

This does **not** invalidate the grid. The grid ran from `_prompts_C.json`,
frozen BEFORE Slice 2, so all four cells are exactly what they claim. It is
*production* that drifted, and it drifted to the candidate arm before the
experiment meant to decide that arm was graded.

**How it surfaced:** c020's fresh capture failed gate 3 on all 20 card
questions — including c001-c019, which pass 19/19 against the frozen capture.
The card block in a capture taken *today* ends with the injected "Symbol
reference" section, so the derivation's segment count no longer matches the
card count. **The gate refused to write anything and exited 1**; the four
existing variant files were verified byte-identical afterward.

**Consequence: c020 phase 2 cannot run tonight**, and shouldn't. Deriving its
v3 arm from a capture that already contains injection would mean its "v3" arm
is really cell B, and the c020 experiment would compare cell B against cell D
while calling it v3 vs v5. Jon needs to rule on whether injection stays in
production first — that ruling determines what a c020 capture even means.
- [ ] rewriter bakeoff — **ONE pass, not three.** See the cache finding below.
- [ ] judge-compare the v5 grid -> Jon's grading queue *(agent running)*
- [x] gold discovery — **STOPPED, correctly.** `plan-v5-symbol-injection.md`
      says Slice C "stays queued", the source plan is DESIGN ONLY, and Slice C
      Stage 2 needs live paid calls to generate proposals at all. Build spec
      committed instead. *(The controller mis-scoped this when offering it as
      "proposals only" — there was no proposal path that avoided paid calls.)*
      Useful measurement it took rather than assumed: only **2 of 20** card
      questions have hand-curated gold (c004, c011), so Slice C's own
      "required" validation gate has exactly two targets.
- [x] citation-filter Rule-0 plan merged (`a511d37`, cherry-picked)
- [ ] **Scryfall local-bulk — BUILT BUT NOT MERGED. See below. Jon's call.**

## STOP — the Scryfall local-bulk slice found a real regression

The slice is fully built and tested in branch
`worktree-agent-a818653b08eb516a4` (5 commits, 56 new tests, 283 passing).
**It is deliberately NOT merged**, and master is verified clean of it:
`src/rulesagent/tools/scryfall_store.py` does not exist, `data/scryfall.db`
does not exist, `scryfall.py` is untouched.

**The regression:** resolving `Valki, God of Lies` — the exact card `c011`
references, and the codebase's own flagship RAG example — **works today and
misses under local bulk.** Verified both directions by the controller, not
taken on report:

- Today: `get_card("Valki, God of Lies")` -> `Valki, God of Lies // Tibalt,
  Cosmic Impostor`. Resolves.
- Under local bulk: 28/29 eval card names hit; Valki is the one miss.

**Root cause, diagnosed not guessed.** Scryfall carries two cards with that
name — the real `modal_dfc` and a non-playable `art_series` decoy — and
neither's full combined name exact-matches a bare `"Valki, God of Lies"`.
On fuzzy fallback the unrelated real card **"Loki, God of Lies" scores 91.4,
above the true target at 90.0**, inside the 3-point ambiguity margin, so the
guard refuses rather than picking wrong. **The guard is working correctly; the
missing piece is a per-face-name lookup tier**, which the approved plan never
discusses. The agent confirmed live that Scryfall's production fuzzy endpoint
(today's mechanism) resolves this string correctly, so this is a demonstrated
regression, not a hypothetical.

**Jon's options:** (a) add a per-face-name lookup tier — the natural fix, but
new surface beyond what he ruled on; (b) require full combined names for
split-card bracket tokens — breaks today's single-face reference pattern and
would mean editing c011; (c) ship as-is relying on the honest-miss debug
surface. Note (b) touches an eval input that carries three verdict files.

**Second finding from the same slice:** the plan's `UNIQUE INDEX ON name_norm`
does not survive real data — **497 colliding rows across 219 distinct names**
(tokens, art series, joke cards). Handled defensively as first-seen-wins so
import doesn't crash, but the plan's schema was wrong. Excluding non-spell
layouts would reduce the collisions and, measured, would **not** fix Valki:
Loki still outscores the real target with the decoy removed.

## Why c020 needed a code slice first

`--assemble-only` deliberately ignores `--limit`/`--questions`/`--cards` and
always captures the FULL combined question set, overwriting its target rather
than merging — the comment says this is so a condition's cache can never become
"a stitched-together mix of two capture sessions." With c020 added that set is
now 51 questions. Separately, `build_prompts_variant.py` hardcoded both its
source (`_prompts_C.json`) and its output names (`_prompts_variant_{A..D}.json`).
Deriving c020's variants with the script as-written would have **overwritten the
four variant files the completed v5 grid was built from** — which are now
evidence. Hence a parameterisation slice with a refuse-to-clobber guard before
any c020 work.

## Operational findings paid for tonight

- **Worktrees do not have gitignored data.** `.gitignore:7` excludes
  `data/raw/`, so a fresh worktree has no CR corpus and 46 tests fail
  environmentally. Seeded `data/raw` into the live worktrees by hand.
- **The venv's editable install resolves `rulesagent` from the ORIGINAL repo's
  `src/`, not the worktree's**, unless `PYTHONPATH` points at the worktree's
  `src`. A worktree agent can otherwise silently test unmodified code while
  believing it tested its own. Found by the rewriter agent.
- **Test suite leaks heartbeat files into the real `evals/answers/_progress/`.**
  The `fake/model` file that kept reappearing was test pollution, not a stale
  manual run. Slice B fixes it.
- `run_eval.py` has **no per-arm selector** — every invocation runs the whole
  `REWRITE_MODELS` grid. Adding `gpt5mini` means haiku and sonnet arms run too.
  That is fine here (haiku is the control) but it is not free.
- **THE 3-PASS STABILITY REQUIREMENT CANNOT BE MET AS WRITTEN.** Rewrites are
  cached in persistent SQLite (`KVCache`, key `[model, version, n, question]` —
  no pass index), and query embeddings are cached by string. Invoking
  `run_eval.py` three times replays the cache; passes 2 and 3 would be
  byte-identical to pass 1. The plan's "recall@5 mean with the observed range"
  would report **range = 0**, which reads as "perfectly stable" but actually
  means "deterministic cache" — a fake result wearing the costume of a strong
  one. The caching is deliberate, not a bug: `query_vectors()`'s docstring says
  Voyage returns slightly different vectors on repeated calls and they cache
  precisely so the eval is reproducible. **One pass was run instead, and the
  bakeoff report is labelled single-pass with stability NOT measured.**

## Waiting on Jon

1. **Citation filter** — where the filter lives (product path vs eval-only),
   what counts as ungrounded, and whether the signed-off baseline gets
   re-scored. See `docs/plan-citation-filter.md` when it lands.
2. **c011** — accept the diagnosis and freeze c011 as evidence, and/or approve
   a future prompt-version instruction preferring current CR text over a
   conflicting older ruling. See `docs/plan-c011-stale-rulings.md`.
3. **The v5 call itself** — grading verdicts are Jon's alone. The judge routes;
   it never grades.
4. **Rewriter stability methodology.** To get a real 3-pass spread, something
   has to defeat the rewrite/embedding caches — a bakeoff-only cache bypass, or
   a pass index in the cache key. Both trade away the reproducibility the caches
   were built to give. Options, cheapest first: (a) accept single-pass and treat
   a large recall gap as signal and a small one as unresolved; (b) add a
   pass-index to the rewrite cache key for bakeoff runs only, leaving the
   embedding cache alone (rewrite variation is the thing being measured);
   (c) bypass both, which also re-pays every Voyage call. Recommend (b) if the
   single-pass gap turns out small enough to matter.
5. **Citation-filter granularity** — new evidence found tonight. q016's context
   contains `601.2f` but NOT `601.2g`/`601.2h`, and deepseek cited the range
   `601.2f-h`. So a strict STRING-level filter would strip a citation that is
   partly correct. Whether the filter operates on citation strings or on
   citation members is now a real design question with evidence behind it.
