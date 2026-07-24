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
- [ ] **A** — mark c002 non-scoring in `cards.jsonl`, add c020 row *(agent running)*
- [ ] **B** — stop tests leaking heartbeats into the real `_progress/` *(agent running)*
- [ ] c020 phase 2 capture + 8 generations at v3 and v5 *(depends on A)*
- [ ] rewriter bakeoff — **ONE pass, not three.** See the cache finding below.
- [ ] judge-compare the v5 grid -> Jon's grading queue
- [ ] gold discovery — proposals only, nothing written
- [ ] merge Scryfall local-bulk slice (agent running)
- [ ] merge citation-filter Rule-0 plan + evidence table (agent running)

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
