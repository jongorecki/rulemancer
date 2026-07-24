**DRAFT under Rule 0. Jon approved building from this on 2026-07-25 ("since all
questions are answered, go ahead and start building").**

# Plan — v5 selective symbol injection, the bullets × injection grid, and the v3 revert

Written 2026-07-25, after the v4 A/B failed its go criterion. Supersedes Slices
A and B of `docs/plan-v5-and-gold-discovery.md` (Slice C, gold discovery, is
untouched and stays queued). Grounding read: `src/rulesagent/generate/answer.py`
(`SYSTEM`, `build_prompt` :287, `_format_cards` :370), `evals/build_prompts_v4.py`,
`evals/answers/_prompts_C.json`, `evals/cards.jsonl`, `src/rulesagent/retrieve/rewrite.py`
(the version-selection precedent), `evals/report-v4e.md`, `DECISIONS.md`.

## 0. Jon's rulings on record (do not relitigate)

1. **v4 is no-go as production. v3 is production** until v5 supersedes it.
   Urgency is low — nothing is publicly deployed and Jon is the only caller.
2. **v5 = v4's content with the per-symbol definitions injected selectively
   instead of the full dictionary attached.** Everything else v4 added stays.
3. **Add a `v3 + injection` arm.** Jon's call, and it completes the design —
   see §3.
4. **Scope: the misses that involve mana symbols**, which derives to the six
   card misses (§2).
5. **c002 is excluded from results** but keeps running as a monitored row, "to
   see if it ever flips in the future." Documented (§6).
6. **c020 replaces c002's role as a well-formed question** — new id, not a
   rewrite of c002. Phase 2 (§7).
7. **Inject when a symbol appears in the question with no card attached.**
8. **No paired keyword variant** of c020 ("we don't really need to consider
   that").
9. **Fix-it-first**: "see if it fixes itself first before we try breaking it
   again." Phase 1 is the existing misses; perturbation work is phase 2.

## 1. What the v4 A/B actually established

Graded, strict: **sonnet 46 → 46** with zero judge-detectable divergence across
all 50 questions and both runs; **gpt-5-mini 45 → 43** (c002, c011 stable-flipped
correct → wrong). SYSTEM grew 5,189 → 10,045 chars (~+1,215 tokens/query), and
**no prompt caching exists on either the eval path or the production path**
(`grep -rn "cache_control\|ephemeral" src/` returns nothing; `answer.py:700`
sends a bare `system=system`), so that cost is paid in full on every query.

Two conclusions drive this plan:

- **The legend's content is fine; its delivery is wrong.** Every question pays
  for `{E}`, `{L}`, `{PW}`, hybrid Phyrexian and the rest, including 31
  rules-only questions with no symbol in play.
- **c014 never moved** — v4 got the model to *state* the cost breakdown
  correctly and still conclude wrong. The bottleneck is multi-step reasoning
  about cost modification, not notation. If v5 also misses c014, that is
  confirmatory and the symbol work is finished either way.

## 2. Scope — derived, not guessed

Scanned each miss's attached cards (mana costs + oracle text, all faces) from
the repo's own Scryfall cache with the `\{[^}]{1,8}\}` regex:

| Miss | Arm(s) | Symbols found | Defs after collapsing |
|---|---|---|---|
| c002 | gpt-5-mini (v4 regression) | `{1} {3} {B} {G}` | 3 |
| c004 | gpt-5-mini | `{1} {G} {R}` | 3 |
| c011 | gpt-5-mini (v4 regression) | `{R} {X}` | 2 |
| c012 | both | `{1} {2} {3} {4} {13} {T}` | 2 |
| c014 | sonnet | `{1} {2} {3} {B} {G} {X}` | 4 |
| c015 | both | `{1} {B} {G}` | 3 |

The three rules misses — **q014, q016, q029** — have no attached cards and no
braces in their question text. The scan finds nothing, injection emits zero
tokens, and they fall out of the comparison automatically. "Misses involving
mana symbols" resolves cleanly to "the card misses."

## 3. The grid — a 2×2 factorial (bullets × injection)

| | no injection | injection |
|---|---|---|
| **v3 bullets** | **A: v3** — production baseline | **B: v3 + injection** |
| **v4 bullets** | **C: v4-minus-legend** | **D: v5** — the candidate |

Without cell B, a v5 win is unattributable — you cannot tell whether the gain
came from the injected definitions or from v4's other bullets riding along.
With all four, every effect lands on bullets, injection, or their interaction.
Cell C subsumes the "insurance arm" Jon took earlier, and generalises it from
c002/c011 to the whole set for the same reason.

**Cell C definition:** v4's `4b` (multiplayer), `4c` (assumption disclosure),
`4d` (intended question), `4e` (no false starts) and the `3b` clause, **without**
the per-symbol definitions. The **cost-math and mana-value counting rules stay
in SYSTEM in cells C and D** — they are arithmetic instructions, not
definitions, and only definitions move (Jon's ruling #2).

**Phase 1 question set** (arm runs its own misses):

- sonnet: c012, c014, c015
- gpt-5-mini: c004, c012, c015, c011
- monitored, non-scoring: c002 (gpt-5-mini)

8 arm-question pairs × 4 variants × 2 runs = **64 generations**, **zero new
captures**, **zero fresh-grade rows** — every cell derives from the frozen
condition-C capture and routes against verdicts Jon has already given. 2 runs
per cell and the stable-flip rule are unchanged; altering the stability rule
mid-programme would make these results non-comparable to every prior A/B.

## 4. Slice 1 — SYSTEM version registry (this *is* the v3 revert)

`rewrite.py:35-54` already solved this problem: both SYSTEM texts retained,
selectable via a `version` param, cache-keyed, with v1 kept "a fully runnable,
unchanged prompt, not just a historical comment" precisely because an A/B
needed it. Mirror it on the generation side.

- `SYSTEM_VERSIONS: dict[str|int, str]` holding **v3** (restored verbatim from
  before `8c7550f`), **v4** (as shipped), and **v4nl** (cell C).
- `PROMPT_VERSION = 3` — the revert, achieved as a side effect rather than as
  its own slice.
- `SYSTEM` stays as a module-level name bound to `SYSTEM_VERSIONS[PROMPT_VERSION]`
  so nothing downstream breaks.

**Mechanics that are easy to get wrong:** commit `8c7550f` deleted
`tests/test_answer_prompt_v3.py`, added `test_answer_prompt_v4.py`, and
regenerated `tests/fixtures/prompt_identity.json`. This slice restores the v3
assertions **alongside** the v4 ones and regenerates the fixture **last**, per
the v4e plan's own risk table.

Also generalise `evals/build_prompts_v4.py` → `evals/build_prompts_variant.py`,
taking an explicit SYSTEM version instead of importing whatever `answer.py`
happens to export. That decoupling matters: today the eval instrument is tied
to whatever production currently ships, which is exactly how a future A/B
silently measures against the wrong baseline.

## 5. Slice 2 — selective symbol injection

### 5a. Production path (`answer.py`)

- `SYMBOL_DEFS: dict[str, str]` — v4's legend decomposed per symbol.
  **Reuse the definitions from `8c7550f` verbatim; do not re-derive them.**
  They were verified at build time against the repo's own CR
  (`data/raw/MagicCompRules 20260619.txt`) and Scryfall's Colors-and-Costs doc.
- `_symbols_present(text) -> set[str]` — regex `\{[^}]{1,8}\}`.
- `_collapse_families(symbols) -> list[str]` — the ten hybrids resolve to ONE
  hybrid definition, not ten. Same for Phyrexian, hybrid Phyrexian, `{C/x}`,
  `{2/x}`, and generic numerals (`{0}`…`{20}` → one generic entry).
- `_symbol_reference_block(symbols) -> str` — emits nothing when the set is
  empty. Zero symbols → zero tokens.
- Called inside `build_prompt` (:287) scanning **the cards** (mana_cost +
  oracle_text, all faces) **and the question text** — never the retrieved rules
  context. Placement: immediately after the `Card data:` block, before
  `\n\nQuestion:`.

**Why scanning cards and not the assembled context is load-bearing, now
measured rather than argued.** CR 107.4 is a single chunk enumerating every
symbol in the game, so a context-wide scan would be *worse* than the static
block. Confirmed empirically on c014's frozen user block: the whole block
contains 8 distinct symbols, the card block 6, and the rules context
contributes symbols the cards do not. Say this in the implementation comments
so nobody later "fixes" it.

**The rewriter structurally cannot see the injected block** — `rewrite_query()`
runs at `answer.py:600`, `build_prompt()` at :685. Jon's requirement is
satisfied by the existing call order, with no guard and no flag. Note that in
the comments too.

### 5b. Eval derivation path

`_prompts_C.json` stores only `{system, user}` **strings** — not the structured
inputs — so the injected variants cannot simply re-run `build_prompt`. They
slice the frozen user block by its markers (`Card data:` … `\n\nQuestion:`),
scan **only that slice plus the question line**, and splice the reference block
in at the position `build_prompt` would have placed it.

This preserves the guarantee that made the v4 A/B work: retrieved chunks and
card data stay byte-identical to condition C, and the only delta is the added
section.

### 5c. Gates (all hard failures, all reported PASS/FAIL)

1. **v3 digest gate** — unchanged. Hash the captured system against the
   recorded v3 digest `25aa69e1…`. This is the check that catches a drifted
   capture producing a clean user-block match against the wrong baseline.
2. **User-block equality** — non-injected variants byte-identical to source;
   injected variants byte-identical *after removing the spliced block*.
3. **Card-block extraction gate** — the sliced card block must equal
   `_format_cards(cards)` for that question's cards. Proves the slice is
   correct rather than plausible.
4. **Over-trigger gate** — the injected symbol set must be a subset of the
   symbols present in cards + question, and must **not** contain any symbol
   found only in the rules context. This is §5a's warning, enforced.
5. **Production parity gate** — for each question, `build_prompt` run on the
   real structured inputs must produce a reference block **identical** to the
   eval derivation's. Without this the experiment measures something production
   would not do.

## 6. Scoring and the c002 exclusion

Restated under the exclusion:

| | v3 (cond-C) | v4 | delta |
|---|---|---|---|
| sonnet, all 50 | 46 | 46 | 0 |
| gpt-5-mini, all 50 | 45 | 43 | −2 |
| sonnet, c002 excluded | 45/49 | 45/49 | 0 |
| gpt-5-mini, c002 excluded | 44/49 | 43/49 | **−1** |

**Consequence that must be recorded:** v4's gap goes from 3 to **2**, which is
*out* of the band where 2026-07-23 pre-commitment #3 auto-pins sonnet, and back
into the band where Jon reviews the flipped answers and decides whether the gap
is livable at ~8x cheaper. The v4 no-go still stands — on sonnet's zero
divergence at +1,215 tokens/query, which is untouched — but it no longer stands
on the pre-commitment argument. Under v3 with c002 excluded, gpt-5-mini sits at
a **1-answer gap**, the most favourable that comparison has ever looked.

**Bookkeeping rules:**

- **Historical figures stay as written.** 46/50 and 45/50 and 43/50 are what
  the verdict files record and what DECISIONS.md, `report-v4e.md` and the
  handoff already say. Recomputing history is worse than a footnote — the
  verdicts are evidence.
- Forward counts are quoted **/49** with the exclusion stated inline.
- c002 runs, is judged, and any flip surfaces under a **"monitored,
  non-scoring"** heading. It never enters a correct-count or a go/no-go delta.

Documentation targets: a DECISIONS.md entry (the exclusion, why, the −2 → −1
restatement, and the pre-commitment consequence); a field on c002's row in
`cards.jsonl`; the c020 row linking back to it; this plan; and
`HANDOFF-development.md`, so a fresh session does not recompute 43/50 and
re-trip a rule that no longer fires.

## 7. Phase 2 — c020 (deferred, defined here so it is ready)

Jon's wording, verbatim:

> I'm attacking with [Stampeding Rhino] and my opponent blocks with [Vampire
> Nighthawk]. How much combat damage do I have to assign to the blocker before
> I can trample the rest over to my opponent?

Verified via `rulesagent.tools.scryfall.get_card`: **Stampeding Rhino** `{4}{G}`
carries *"Trample (This creature can deal excess combat damage to the player or
planeswalker it's attacking.)"* — so unlike c002's **Charging Rhino** (`{3}{G}{G}`,
"can't be blocked by more than one creature", **no trample**), nothing is
granted by the question. Both abilities come from card oracle text.

New id **c020** (`cards.jsonl` runs c001-c019; a suffixed id risks tooling that
assumes `c\d\d\d`), with the relationship to c002 recorded in the row. Old c002
stays frozen exactly as it is, flaw included, because it is evidence.

**Deferred because it is the expensive half in Jon's scarcest resource.** It
needs a fresh capture (new question text → new retrieval by design), and having
no prior verdict the frozen judge cannot route it — every row lands on Jon as
fresh grading. Scope it to **v3 and v5 only, 8 rows**; the middle cells exist
for attribution against a baseline, and c020 has none.

Honest caveat to carry into its report: c020 is arguably a *weaker* RAG test
than c002. Both abilities now ship with full reminder text in the card data, so
the model can assemble the answer from oracle text alone — which is what
c002's own `ablation` field already recorded (*"sanity FAILED — trample/deathtouch
are common enough that the model answers from the keyword oracle text alone;
retrieved rules redundant. Weak RULES-RAG test."*). Better-formed as a rules
question; softer as a retrieval question.

## 8. Verification

Every gate in §5c reports PASS/FAIL. Beyond those:

- Existing suite green (176 tests as of `8c7550f`).
- Tests asserting half-mana and infinite symbols remain **absent** (Jon's
  Un-set ruling) survive the decomposition into `SYMBOL_DEFS`.
- Measured input-token counts recorded both ways, per question, so the token
  claim in §1 is settled with data rather than the ~4 chars/token rule of thumb
  `report-v4e.md` §11 had to fall back on.
- The frozen judge (`judge_bakeoff` prompt + gpt-5-mini) is untouched. Grading
  verdicts are Jon's alone; the judge routes, it never grades.

## 9. Non-goals

- No change to the frozen judge, ever.
- No rewriting or retiring of existing eval questions (c002 stays; c020 is
  additive).
- No new generation model, no retrieval/TOP_K change, no `Answer` schema change.
- Not reopening condition E — closed on latency, not accuracy.
- No auto-writing of gold. Slice C of the superseded plan stays queued.
