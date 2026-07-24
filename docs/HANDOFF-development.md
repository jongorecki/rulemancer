# Handoff — Rulemancer: layers tool half-built, levers ruled, API cap cleared

**Replaces the prior handoff (git has every version). Written at the end of the
2026-07-24 session, which planned and half-built the layer-system tool, got all
three lever decisions ruled, started the pure-rules eval set, and discovered the
API cap was never actually blocking.**

## ⚠️ FIRST, UNLEARN THIS: the API cap is CLEARED

The previous handoff said the account was capped until 2026-08-01 and that every
live sonnet-5 run 400s. **That was stale and it gated real work.** Verified this
session with a live `claude-sonnet-5` call (16 in / 4 out, `stop_reason=end_turn`).

**Credentials load from `.env` via `load_dotenv()`, NOT the ambient shell.** A bare
`python -c` without `load_dotenv()` fails with *"Could not resolve authentication
method"* — that is an **auth** error and reads exactly like a cap. Don't repeat the
mistake: test before believing any claim that the API is blocked.

## THE ONE THING TO DO FIRST

**Calibrate the layers trigger** (`plan-layer-system-tool.md` §3c and §10 item 2).
It gates Slice 4 and is the single likeliest place this plan fails.

Why it's the risk: layers questions contain **no layers vocabulary**. Across all
1,409 corpus questions, `\blayer\b` appears **once** (and that row is bucket-B
order-only), and `timestamp` / `depend` / `continuous effect` appear **zero** times.
62 of the 68 CR-613 rows match no keyword at all. So the intuitive trigger is dead
and §3c proposes a two-conjunct replacement (characteristic-readout phrasing AND
≥2 loaded cards with continuous-effect-shaped oracle text).

**The bar, already written into the plan:** ≥60% recall on the 51 bucket-A questions
with <10% firing on a 100-row non-layers sample. If conjunct 2 can't hit that, the
blocker is the trigger, not the engine — and that's worth knowing before Slice 4,
not after. **Slice 3 is disjoint and can run in parallel** (engine code vs. a corpus
measurement).

## HOW JON WORKS (unchanged, load-bearing)

- **Rule 0: plan before code.** Every `plan-*.md` is design-only until Jon rules.
  A bug-fix on approved code uses systematic-debugging; a NEW tool needs a plan.
- **USE SUBAGENTS.** Sonnet for scoped implementation against a written plan; Haiku
  for bulk fetch/filter/verify with compact returns. Keep the lead for judgment,
  review, and talking to Jon. This session ran 5.
- **Do-not-delegate:** eval questions, gold, grading verdicts, **reading failures**
  (the lead reads the garbled/failed outputs itself).
- **Judge is FROZEN** (`judge_bakeoff` prompt + gpt-5-mini). Never reword.
- **Never assert an MTG/model fact from memory.** Ground in the repo CR
  (`data/raw/MagicCompRules 20260619.txt`), Scryfall via
  `rulesagent.tools.scryfall.get_card`, or a live check. Model facts via the
  claude-api skill — that skill is how this session found the rg3391 root cause.
- **Verify agents' claims yourself.** Both build agents this session reported green
  suites that were contaminated by the *other* agent's uncommitted files. Neither
  was independent evidence. Re-run on a clean tree, and hand-check deliverables
  against the plan's own expected outputs.
- Commit per slice on master, heredoc messages, `Co-Authored-By: Claude Opus 4.8`.
  `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. Jon runs the app on port
  8000 — never bind/kill it.

## THE STRATEGY (unchanged through-line)

A **card-interaction reasoning product.** Held-out (RulesGuru-150): sonnet **72%**
raw / **75.3%** after Jon's regrade. Retrieval overfit badly (recall@50 100% tuned
vs **63%** held-out) AND barely predicts correctness — the model answers card
questions from **oracle text**, not retrieved CR rules. **So the levers are
REASONING (tools) and CARD-DATA quality.**

## THE TOOL ROADMAP

Pattern: the model orchestrates and reasons; deterministic tools own the exact
sub-computations it narrates right and then botches.

1. **Cost calculator — SHIPPED + HARDENED** (`da0449e`, `e763e91`, `1dfe6d4`).
2. **Combat-damage — SHELVED** (only 7 assignment-shaped questions in 1,409).
3. **Layer-system resolver (CR 613) — HALF BUILT.** Slices 1-2 done, 3-4 to go.
4. **State-based-action checker** — idea, not planned.
5. **Question-classification pipeline step** (Jon's idea) — route to the right tool.
   Additive, deterministic-first. Not planned. *Note: if the layers trigger fails
   its calibration bar, this is the natural fallback — a classifier could route
   where a regex can't.*
6. Other ideas from regrade notes: trigger-type identifier (rg608), ability-type
   definer (rg549, rg517), replacement-effect ordering (rg1095, rg1953).
7. **DO NOT build the keyword-reminder-text tool** — already ruled out.

## WHAT SHIPPED THIS SESSION (all on master, 419 tests green)

- **`plan-layer-system-tool.md`** (`c8bcd1e`, `6712313`, `aed0292`) — full design,
  Jon's three rulings folded in. **Verdict: tool-shaped, but the deterministic core
  is CR 613.6 ordering bookkeeping, not arithmetic.** sonnet made the *same* 613.6
  error on three of four regrade seeds after narrating the layers correctly. ROI:
  **51** genuinely resolver-shaped questions (68 cite CR 613, hand-bucketed) vs
  combat's 7.
- **answer.py seam generalised** (`a36db25`, `c79cd03`) — the three `use_cost_tool`
  gates broadened to `use_any_tool`, **plus a fourth must-fix the combat plan
  missed**: dispatch had no `block.name` branch and called `_run_calculate_cost`
  unconditionally. Now name-routed with an unknown-tool error.
  `TOOL_ROUND_CAP` 3 → 4 per Jon's ruling.
- **Layer resolver Slices 1-2** (`c85de03`, `ec8cee4`) — layers 2/4/5/6/7a-7d, the
  CR 613.6 `is_active` gate, `applies_if` option B (six predicates + `expect`) and
  all four anti-silent-gating mechanisms. Lead-verified against hand-traces:
  rg3868 → **6/6** (sonnet said 3/3), rg807 → 4/4 blue Frog, rg811 → 4/4 black Frog,
  CR 613.4d switch examples → 4/6 and 1/4, CR 613.5 Gray Ogre → 5/8, Honor of the
  Pure → 3/3, and an `expect` mismatch emits a warning with `skipped_count: 1`.
- **Pure-rules eval batch 1** (`47b3090`, `976c08e`, `f4396c5`) — 8 candidates,
  **8/8 approved by Jon with zero edits**, plus an approval UI with full oracle
  text, P/T, and both faces of double-faced cards.
- **Lever rulings + API correction** (`8d1be26`).

## THE THREE LEVER RULINGS (2026-07-24, in DECISIONS.md)

- **v5 — NO-GO, stay on cell B.** Cell D fixed 0 of 3 sonnet misses and produced 0
  stable flips at **+510 tok/query over current production**, with no prompt caching
  anywhere to offset it. Jon: "stick with B for now, plan to A/B things later."
- **Rewriter — HOLD** for the pure-rules eval. Haiku and sonnet are identical at the
  real operational depth (`TOP_K=15`; @10 87/87, @20 94/94); the holdout coverage
  gain is on a corpus that's 98% card questions, so the gain's *value* is unmeasured.
- **L2 generator — DEFERRED to post-tools** (Jon's reasoning, which overrode a
  recommendation to pin sonnet). Tools move sub-computations out of the model, so
  the 22-question held-out gap was measured on a pipeline being actively replaced.
  **Re-test after layers ships:** compare on the tool-triggering subset measuring
  accuracy AND tool-call well-formedness AND citation stability — the last because
  tools trade reasoning burden for structured-output precision, and gpt-5-mini's
  measured weak spot is exactly there (six-arm bakeoff: **stable citations 2/50**,
  on a since-superseded prompt, so re-measure rather than treat as verdict).
  Cost context: ~$0.0059/query (mini) vs ~$0.048 (sonnet); tool round trips
  multiply both, so the absolute gap **widens** with tools.

## THE PURE-RULES EVAL PROGRAM

Fills the measurement gap: no held-out *pure-rules* set exists, so RulesGuru's
98%-card corpus lets oracle text confound every attempt to test whether the CR-rule
RAG earns its keep.

**Jon's standing grant (2026-07-24):** *"you can rewrite questions when you already
have the answers like that for any that you want... draft as many as you need...
pull from whichever questions you need."* So the earlier "throughput bounded by
Jon's review" constraint is **relaxed** — draft freely in large batches, he approves
in bulk. Batch 2 can be 15-20+ and can pull from any tagged slice, not just CR 613.

**The one rule that still binds:** only generalize where the original gold **already
states the rules mechanism explicitly**, so derived gold is a paraphrase rather than
a new ruling. Derived gold does **not** inherit RulesGuru gold's authority (that
carve-out exists because certified judges wrote it). One candidate was cut for
exactly this (rg1989 — gold's arithmetic doesn't follow without the cards' printed
P/T).

**Second, under-appreciated payoff (Jon's observation):** generalizing a card
question into a rules question is *structurally the same operation the query
rewriter performs*. Every approved pair is a supervised example of good rewriting.
So this set is both the measuring instrument for the rewriter lever **and**
potential training signal for it. That changes the target size — a set built only to
measure would stop earlier than one meant to also teach. Don't build on this until
the set is much larger than 8 pairs.

**Workflow:** draft into `evals/purerules_candidates.json` → run
`evals/enrich_purerules_cards.py` (attaches oracle text, P/T, all faces) →
`evals/build_purerules_approval_ui.py` → open `data/parsed/purerules_approval.html`
(Chrome blocks `file://`, so serve it: `python -m http.server 8765` from
`data/parsed`, **never port 8000**) → Jon exports `purerules_decisions.json`.

## RESIDUALS / OPEN ITEMS

- **rg3391 — ROOT-CAUSED this session, fix not built.** Its recorded degrade text
  says `stop_reason=max_tokens`, so it **is** truncation. Jon's original "raise
  max_tokens" note was right; the prior handoff talked him out of it by
  over-generalising a c018 finding. **But raising the number alone doesn't work** —
  `answer.py:1421` records that `max_tokens=32768` trips the SDK's non-streaming
  10-minute-timeout guard. The real fix is to **stream** (`client.messages.stream()`
  + `.get_final_message()`), which lifts the ceiling toward sonnet-5's real 128K.
  Two aggravating factors: sonnet-5 runs **adaptive thinking by default** when
  `thinking` is omitted (answer.py doesn't set it) and `max_tokens` caps thinking +
  text *together*; and sonnet-5's tokenizer produces **~30% more tokens** than 4.6.
  ⚠️ Do NOT "fix" this with `thinking: {"type": "disabled"}` — that makes sonnet-5
  measurably *less* likely to reach for tools, which is exactly wrong for this
  pipeline.
- **Sentinel de-conflation** — `answer.py:1556` collapses cap-exhaustion and
  validation-empty into one `"error"` sentinel. Small, unblocked.
- **rg6916 rep1** — leaked scratchpad text in an `answered=False` decline. Small.
- **rg6636 rep3 word-salad** — deliberately left uncaught; monitored via
  `last_uncited_success`. Not an open item.
- **`evals/_phase1_costtool_repro.py`** has two stale `TOOL_ROUND_CAP (3)` comments.
  Comments only, not exercised by the suite.

## HELD / BLOCKED ON JON

- **Scryfall local-bulk + per-face + self-heal** (worktree
  `agent-a818653b08eb516a4`, ~8 commits, complete + verified, NOT merged).
  ⚠️ **The `answer.py` conflict is now FOUR-way** — the branch's fuzzy-fallback
  wiring, master's cost-tool loop, the `1dfe6d4` reliability fix, and this session's
  seam generalisation. **Keep all four.** Jon's ruling: *"needs to get resolved as
  soon as it doesn't require stopping something that's already in progress"* — so
  land it when no agent owns `answer.py`. Master has no `scryfall.db` (first
  `get_card` self-heals → 180MB download; pre-build or accept it).

## STILL QUEUED

`plan-sso.md` (tied to Jon's job-hunt auth-evidence goal), `plan-deploy.md`,
Slice C gold discovery, `plan-c011-stale-rulings.md` (diagnosed, frozen), the
miss-partition diagnostic (largely mooted).

## LAYERS TOOL — REMAINING SLICES

- **Slice 3** — CR 613.8b dependency ordering (including the loop-falls-back-to-
  timestamp case the CR never illustrates) + the full refusal list.
  **Also fold in a fix flagged during Slice 2 review:** the 613.6 `removed_at`
  bookkeeping currently matches ability **text strings** to decide which source got
  removed. That was a genuine correction to the plan's own spec (a literal reading
  would have marked Muraganda Petroglyphs removed and returned 4/4 instead of 6/6 on
  rg3868), but string matching is fragile — `"Trample"` vs `"trample"` silently
  misjudges. Replace with an explicit `source_on_this_object` flag in the schema.
- **Slice 4** — wiring: `RESOLVE_LAYERS_TOOL` schema, `_needs_layers_tool`,
  `_run_resolve_layers`, and registration in `_TOOL_DISPATCH`. **Gated on the
  trigger calibration above.**
- **Slice 0** (prompt-bullet control arm) and **Slice 5** (live validation) are both
  **now runnable** — the cap never blocked them. Per Jon's ruling the tool must
  **tie or beat** the control arm, and both arms carry a regression measurement,
  because a system-prompt bullet is a global change while the tool only fires when
  triggered.

## ENVIRONMENT & GOTCHAS

- Worktrees are pruned to 2. **KEEP `agent-a818653b08eb516a4`** (Scryfall, unmerged).
- Answer object field for the answer text is **`.text`**, not `.answer`.
- `data/parsed/` is **gitignored** — generated UIs live there and regenerate from
  their builder scripts.
- Power/toughness are **not** top-level `Card` fields — they live on `Card.faces[]`.
  `getattr(card, "power")` returns `None` even for a plain creature.
- Chrome extension blocks `file://` URLs; serve local HTML over `http.server`.
  Also: don't click a button that fires `confirm()` while driving the page — a modal
  freezes the extension connection.
- The RulesGuru API re-randomizes card/name text per refetch; `rulesguru_full.jsonl`
  is a frozen snapshot (stable on gold/level/tags, not byte-reproducible).
- Doc-metadata / token-economy rules live in `D:\Job_hunt\CLAUDE.md` and
  `Token-Economy-Policy.md`.
