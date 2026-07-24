# Handoff — Rulemancer: layers tool fully built, never yet run against a live model

**Replaces the prior handoff (git has every version). Written at the end of the
2026-07-24 session, which landed the held Scryfall merge, calibrated the layers
trigger (it FAILED as specified), finished Slices 3 and 4, and found two
production bugs caused by the same defect.**

Suite is **519 passed, exit 0** on a clean tree. Nine commits: `c481292`,
`8b90395`, `24f2bb9`, `061da94`, `17f4d16`, `7a316bd`, `4343848`, `6aae61f`,
`4f028dd`.

---

## ⚠️ FIRST, UNLEARN THIS

**1. The trigger calibration is DONE, and the plan's own regex was broken.** The
previous handoff made calibration "the one thing to do first" and named it the
likeliest place the plan fails. It was right to. §3c's trigger scored **20.4%**
bucket-A recall against its own ≥60% bar. Two of the three causes were *defects*,
not design limits — a `get\s*` that never matched singular `"gets +N/+N"`, and a
type-alternation blind to land subtypes (so **Blood Moon** and **Magus of the
Moon**, the corpus's most common layer cards, were invisible). Fixing both still
failed at 53.7%. Jon ruled the `>= 2` threshold down to `>= 1`. **Final: 77.8%
recall (42/54) at 5.1% firing over the full 1,341-row non-layers pool.** Verified
against the *shipped* function, not just the calibration script.

**2. The API is live.** Re-verified this session with a real `claude-sonnet-5`
call (15 in / 3 out, `stop_reason=end_turn`). Credentials load from `.env` via
`load_dotenv()`. **New gotcha:** bare `load_dotenv()` raises `AssertionError` when
run from a `python -` heredoc, because `find_dotenv()` walks `frame.f_back` and
there is no caller frame. Pass the path: `load_dotenv("D:/Job_hunt/mtg-rules-bot/.env")`.
That failure looks nothing like auth and nothing like a cap — don't misread it as either.

**3. "Pre-existing failure" is a claim to check, not accept.** A build agent
reported a red test as "unrelated, pre-existing." It was unrelated to *its* change
— and it was not pre-existing; the same suite had been green an hour earlier.
Chasing it found a live production bug. Both times this session that an agent's
green-suite or red-suite claim got checked, the check paid.

---

## THE ONE THING TO DO FIRST

**Run Slice 0, then Slice 5. The layers tool is fully built and has never met a
live model.** Slices 1-4 are done, engine hand-verified against the plan's own
traces, trigger verified against the corpus — but every bit of that is offline.

- **Slice 0 — the control arm.** One prompt variant with CR 613.6 + 611.3a quoted,
  run on the four seeds *and* a non-layers regression sample, several reps,
  aggregated. **Per Jon's §8.2 ruling the tool must TIE OR BEAT this**, on both
  win-rate and regression. Do it first: it is nearly free and it is the bar.
- **Slice 5 — live validation.** Tool-on vs tool-off over the COMPUTE bucket, plus
  the regression arm, against Slice 0 on **both** win-rate and regression. Frozen
  judge. Free with the same run: the **round-usage histogram** — how many layers
  attempts consume both tool-capable rounds. Near zero means `TOOL_ROUND_CAP` is
  right; a meaningful share hitting the forced round with an unfinished tool
  sequence means raise it, with data instead of assumption.

Both are unblocked. The cap never blocked them and the API is confirmed live.

**Bucket-count note:** the plan says the COMPUTE bucket is 51 rows. The buckets
were re-derived and *persisted* this session to `evals/_layers_buckets.json` and
came out **A=54, B=1, C=13**. The re-derived A is slightly more inclusive. Use the
file — it is the only durable record; the 51/1/16 hand-count was never saved.

---

## THE TWO BUGS — one defect, two costumes

Both found this session, both caused by **an index into an externally-owned list,
persisted as if it were an identifier.** The Scryfall local-bulk merge changed the
order in which each card's rulings come back, and everything keyed on position
silently pointed at the wrong text.

**Bug 1 — the ruling embedding cache.** `ruling_id()` was `oracle_id#index` and
`ruling_emb` was keyed by it and "frozen once written." After the merge, **175 of
190 cached embeddings across the card-eval pool (92%) no longer matched the text
at their index.** Selection scored stale vectors while the prompt printed whatever
sat at the chosen index; `COSINE_FLOOR`'s calibration was invalidated for affected
cards. It did **not** self-heal — `_card_ruling_embeddings()` only embeds *missing*
keys and never checks a cached vector against its text. Nothing crashed.
**FIXED** (`17f4d16` purge, `7a316bd` durable): `ruling_id()` is now
`f"{oracle_id}#{sha256(text.strip())[:12]}"`.

**Bug 2 — the eval gold.** `LOAD_BEARING_RULINGS` in `evals/run_openrouter_arm.py`
stores ruling *indices*. **All 14 questions pointed at the wrong ruling.** Only
c014 (Trinisphere #0) survived. This is the worse one: the cache degraded silently
at runtime, this degraded a **measurement**, which reports plausible wrong numbers
with no error anywhere. **RE-DERIVED** (`6aae61f`) by matching each entry back to
the prose description in its own `cards.jsonl` `note` — Jon's prose survived the
reorder even though the numbers didn't.

**Ten of those re-derivations Jon has not individually reviewed** (he approved five
plus two additions; the other nine turned out stale too and were fixed in the same
pass). They are listed with their before→after in the commit message and inline
comments. Worth a confirmation pass.

**Still open:** re-key `LOAD_BEARING_RULINGS` to `ruling_id()` instead of indices so
it cannot rot again. Small, unblocked.

**The lesson to carry:** what caught Bug 1 was a **byte-identity fixture** — the
class of test usually deleted as brittle. Its brittleness was the entire point. Do
not "fix" a red identity fixture by recapturing it until you have proved the delta
is explained; recapturing first is exactly what would have buried this.

---

## HOW JON WORKS (unchanged, load-bearing)

- **Rule 0: plan before code.** Every `plan-*.md` is design-only until Jon rules. A
  bug-fix on approved code uses systematic-debugging; a NEW tool needs a plan.
- **USE SUBAGENTS.** Sonnet for scoped implementation against a written plan, Haiku
  for bulk fetch/filter/verify with compact returns. Lead keeps judgment, review,
  and talking to Jon. This session ran 4.
- **Do-not-delegate:** eval questions, gold, grading verdicts, **reading failures**
  (the lead reads the garbled/failed output itself). Tools route and rank; they
  never assign a verdict.
- **Verify agents' claims yourself.** Re-run on a clean tree and hand-check
  deliverables against the plan's own expected outputs, not the agent's tests.
- **Parallelise only across disjoint file sets.** Forbid `git add -A` / `git add .`
  in every agent prompt — staging collisions are the real hazard. Concurrent agents
  on master work fine if each stages named paths only.
- **Judge is FROZEN** (`judge_bakeoff` prompt + gpt-5-mini). Never reword.
- **Never assert an MTG or model fact from memory.** Ground in the repo CR
  (`data/raw/MagicCompRules 20260619.txt`), Scryfall via
  `rulesagent.tools.scryfall.get_card`, or a live check. Model facts via the
  claude-api skill.
- Commit per slice on master, heredoc messages, `Co-Authored-By: Claude Opus 4.8`.
  `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`. Suite is `uv run pytest`.
  Never pipe a long run through `| tail` — it masks the exit code.
  **Jon runs the app on port 8000 — never bind or kill it.**
- Don't read subagent transcript files; wait for the completion notification.

---

## THE STRATEGY (unchanged through-line)

A **card-interaction reasoning product.** Held-out (RulesGuru-150): sonnet **72%**
raw / **75.3%** after Jon's regrade. Retrieval overfit badly (recall@50 100% tuned
vs **63%** held-out) AND barely predicts correctness — the model answers card
questions from **oracle text**, not retrieved CR rules. **So the levers are
REASONING (tools) and CARD-DATA quality.**

## THE TOOL ROADMAP

The model orchestrates and reasons; deterministic tools own the exact
sub-computations it narrates right and then botches.

1. **Cost calculator — SHIPPED + HARDENED** (`da0449e`, `e763e91`, `1dfe6d4`).
2. **Combat-damage — SHELVED** (only 7 assignment-shaped questions in 1,409).
3. **Layer-system resolver (CR 613) — BUILT, Slices 1-4. Needs Slices 0 and 5.**
4. **State-based-action checker** — idea, not planned.
5. **Question-classification pipeline step** — Jon 2026-07-24: *"classification is
   more durable and something we should do when it makes sense."* Still the
   intended long-term answer for routing; the calibrated regex is the ship-now
   mechanism, not a claim that regexes are right.
6. Other ideas from regrade notes: trigger-type identifier (rg608), ability-type
   definer (rg549, rg517), replacement-effect ordering (rg1095, rg1953).
7. **DO NOT build the keyword-reminder-text tool** — already ruled out.

---

## WHAT SHIPPED THIS SESSION

- **Scryfall merge landed** (`c481292`, `8b90395`) — the held
  `agent-a818653b08eb516a4` branch: local bulk store, per-face lookup tier (fixes
  the c011/Valki miss), fuzzy-fallback debug surface, admin refresh endpoints,
  local-first/live-fallback/self-heal. The feared "four-way `answer.py` conflict"
  was **one hunk and additive on both sides** — `last_tool_calls` and
  `last_fuzzy_fallbacks` registered at the same point in `__init__`. Kept both; all
  four seams asserted by name after resolving.
- **Trigger calibrated + ruled** (`24f2bb9`) — see above. Buckets persisted.
- **Slice 3** (`061da94`) — CR 613.8b dependency ordering incl. the
  loop-falls-back-to-timestamp case, the three missing refusals, and
  `source_on_this_object` replacing fragile ability-text matching. Seed traces
  hand-checked against §3b.5: rg3868 → black 6/6 no abilities, rg807 → 4/4 blue
  Frog, rg811 → 4/4 black Frog with trample + upkeep trigger.
- **Slice 4** (`4343848`) — `RESOLVE_LAYERS_TOOL`, `_needs_layers_tool`,
  `_oracle_all_faces`, `_run_resolve_layers`, `_TOOL_DISPATCH` registration. All
  four of §3d's must-fixes were **already present** from the earlier seam
  generalisation; nothing re-applied.
- **`TOP_N` 3 → 5** (`17f4d16`) per Jon. Honest result: **c011 gains its
  load-bearing modal-DFC ruling at rank 4; c010 and c019 are NOT fixed.** One of
  the three flagged questions was a cap problem; the other two are the
  semantic-mismatch limit the existing calibration note already named. Cost ~63
  tokens/question.
- **Both bugs above, fixed** (`7a316bd`, `6aae61f`), and the fixture recaptured
  once, after both, with the delta proved explained (`4f028dd`).

---

## RESIDUALS / OPEN ITEMS

- **rg3391 — root-caused, fix not built.** Its degrade text says
  `stop_reason=max_tokens`, so it IS truncation. But raising the number alone
  doesn't work — `answer.py` records that `max_tokens=32768` trips the SDK's
  non-streaming 10-minute-timeout guard. The fix is to **stream**
  (`client.messages.stream()` + `.get_final_message()`). Aggravators: sonnet-5 runs
  adaptive thinking by default when `thinking` is omitted and `max_tokens` caps
  thinking + text together; sonnet-5's tokenizer emits ~30% more tokens than 4.6.
  ⚠️ Do NOT "fix" this with `thinking: {"type": "disabled"}` — that makes sonnet-5
  measurably *less* likely to reach for tools, which is exactly wrong here.
- **Sentinel de-conflation** — `answer.py` collapses cap-exhaustion and
  validation-empty into one `"error"` sentinel. Small, unblocked.
- **rg6916 rep1** — leaked scratchpad text in an `answered=False` decline. Small.
- **Re-key `LOAD_BEARING_RULINGS` to `ruling_id()`.** Small, unblocked.
- **Confirm the ten unreviewed gold re-derivations** (see above).
- **rg6636 rep3 word-salad** — deliberately left uncaught; monitored via
  `last_uncited_success`. Not an open item.
- **`evals/_phase1_costtool_repro.py`** has two stale `TOOL_ROUND_CAP (3)` comments.
  Comments only, not exercised by the suite.

## HELD / BLOCKED ON JON

- Nothing is blocked. The Scryfall merge that was held is landed.

## STILL QUEUED

`plan-sso.md` (tied to Jon's job-hunt auth-evidence goal), `plan-deploy.md`,
Slice C gold discovery, `plan-c011-stale-rulings.md` (diagnosed, frozen), the
miss-partition diagnostic (largely mooted), and the pure-rules eval set — batch 1
is 8 approved pairs and **Jon's standing grant lets you draft 15-20+ at a time**,
pulling from any tagged slice. The one binding rule: only generalize where the
original gold ALREADY states the rules mechanism explicitly, so derived gold is a
paraphrase rather than a new ruling.

---

## ENVIRONMENT & GOTCHAS

- **`data/scryfall.db` exists locally** (76 MB, 38,336 cards, gitignored). The
  merged local-first path resolves cards offline — no 180 MB self-heal download is
  waiting. Do not run `scripts/refresh_scryfall_bulk.py` casually.
- **The `agent-a818653b08eb516a4` worktree is now merged** and safe to remove.
- **Oracle text and P/T are per-face** — `Card.faces[i].oracle_text`.
  `getattr(card, "power")` returns `None` even for a plain creature.
- Answer object field for the answer text is **`.text`**, not `.answer`.
- `data/parsed/` is **gitignored**; generated UIs regenerate from their builders.
- Chrome extension blocks `file://`; serve local HTML over `http.server`, **never
  port 8000**. Don't click a button that fires `confirm()` while driving the page.
- The RulesGuru API re-randomizes card/name text per refetch;
  `rulesguru_full.jsonl` is a frozen snapshot (stable on gold/level/tags).
- Worktree agents MUST set `PYTHONPATH=<worktree>\src` or they silently test the
  ORIGINAL repo's code. `data/raw/` and `evals/answers/` are gitignored (absent in
  worktrees) — run on master when the CR corpus or eval data are needed.
- Doc-metadata / token-economy rules live in `D:\Job_hunt\CLAUDE.md` and
  `Token-Economy-Policy.md`.
