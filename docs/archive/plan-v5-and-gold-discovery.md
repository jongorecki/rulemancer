**DRAFT under Rule 0 — DESIGN ONLY. Nothing built. Three independently-approvable
slices; each needs Jon's ruling on its own open questions before it starts.**

# Plan — the miss matrix, v5 selective symbol injection, and automated gold discovery

Written 2026-07-24 after the v4 A/B concluded; revised the same day to Jon's
corrections (full A/B not a retrieval probe; a v4-without-legend arm; scope the
whole thing to the misses). Grounding read: `src/rulesagent/generate/answer.py`
(rewrite/build_prompt ordering, `_format_cards`), `evals/ablate_gold.py`,
`evals/build_prompts_v4.py`, `evals/run_openrouter_arm.py`,
`evals/run_answer_eval.py`, `evals/lib_v3ab.py`, `docs/plan-prompt-v4.md`,
`docs/plan-rewriter-model-bakeoff.md`, `DECISIONS.md` (2026-07-24),
`evals/report-v4e.md`, and CR 702 headings in
`data/raw/MagicCompRules 20260619.txt`.

## 0. Why this plan exists — what the v4 A/B actually proved

Graded (Jon, strict): **sonnet 46 → 46** (zero divergence across all 50
questions, both runs); **gpt-5-mini 45 → 43** (c002, c011 stable-flipped
`correct` → `wrong`). v4 nearly doubled the SYSTEM (5,189 → 10,045 chars,
~+1,215 tokens) and **failed its own go criterion**. It never moved **c014**,
the mana-arithmetic failure the notation legend was built for.

Conclusions that drive the slices:

1. **The legend's content is fine; its delivery is wrong.** Every question pays
   ~1,215 tokens for `{E}`, `{L}`, `{PW}`, hybrid Phyrexian and the rest,
   including 31 rules-only questions with no mana symbol in play. → Slice A.
2. **We don't know which part of v4 caused the regression** — the legend, or the
   other bullets. Nobody has measured v4-without-the-legend. → Slice B.
3. **Most remaining misses aren't prompt-shaped.** Retrieval was byte-identical
   between v3 and v4, and on several misses the answering rule was never in the
   context at all. → Slice B measures this honestly.
4. **We cannot improve what we cannot score.** Card questions carry `gold=[]` by
   design; several rules questions have incomplete gold. Jon will not rebuild
   gold by hand. → Slice C.

**Open and NOT decided here: the v4 go/no-go.** Master ships
`PROMPT_VERSION = 4`, a candidate that failed its go test, costs +1,215
tokens/query, and pushes gpt-5-mini to a 3-answer gap — tripping Jon's
pre-commitment #3 ("gap ≥3 → sonnet stays pinned") and mothballing the ~8x
cheaper generator. Controller recommendation on record: **revert production to
v3**; carry v4's content into the v5 candidate. Jon's call.

---

## Slice A — Selective symbol injection (the v5 candidate)

**Jon's design:** stop shipping a static legend. When cards are attached, scan
them for the symbols actually present and inject only those definitions as a
reference section in the prompt.

### A1. Why scanning CARDS (not the whole context) is correct

Jon's specification, and it beats the obvious alternative. Scanning the assembled
context would be actively harmful: **CR 107.4 is a single chunk enumerating every
symbol in the game** — ten hybrids, ten hybrid Phyrexians, five monocolored
hybrids, five `{C/x}`, snow, the Phyrexian set. Any question retrieving 107.4
would trigger the whole legend: a worst case *worse than today's static block*.
Card oracle text carries only what's in play.

**Also scan the question text** (Jon, 2026-07-24) — a question can name a symbol
with no card attached. Same regex, negligible cost.

**Scoping note (Jon):** a bare "what does `{C}` mean" is a **Scryfall reference
question, not a rules question** — declining it isn't incorrect. That belongs in
`questions.jsonl`'s `kind` taxonomy, not in a prompt bullet. Eval-metadata
follow-up, out of scope here.

### A2. Mechanism — straight code, zero model calls

Confirmed by reading `answer.py`: `rewrite_query()` is called at line 600,
`build_prompt()` at line 685. **Rewriting happens strictly before prompt
assembly**, so a reference section built inside `build_prompt`/`_format_cards` is
structurally invisible to the rewriter. Jon's requirement that "the rewriter
doesn't touch the reference section" is satisfied by the existing call order — no
guard, no flag. Say so in the implementation comments so nobody later "fixes" it.

Shape:
- `SYMBOL_DEFS: dict[str, str]` — v4's legend content decomposed per symbol.
  Definitions already verified against the repo's CR and Scryfall's
  Colors-and-Costs doc (commit `8c7550f`); reuse them, don't re-derive.
- `_symbols_present(text) -> set[str]`: regex `\{[^}]{1,8}\}` over card oracle
  text, mana costs, and the question.
- **Family collapsing:** `{W/U}`, `{B/G}` … resolve to ONE hybrid definition, not
  ten. Same for Phyrexian, hybrid Phyrexian, `{C/x}`, `{2/x}`, and generic
  numerals (`{0}`…`{20}` → one generic entry).
- Emit a `Symbol reference:` block only when the set is non-empty. Zero symbols →
  zero tokens.
- **Cost-math and the mana-value counting rule stay in SYSTEM** — they're
  arithmetic instructions, not definitions, and they're what v4 should have led
  with. Only per-symbol *definitions* move.

Estimate: ~1,215 tokens on every question today → ~150–400 on card questions,
**0 on the 31 rules-only questions**.

### A3. Caching trade-off, stated honestly

SYSTEM sits in the cacheable prefix (~0.1x on repeats); a per-question user block
does not cache. A block 5–10x smaller still wins, but **measure it** — record real
input-token counts both ways and report them.

### A4. Testing — byte-identical methodology still holds

v4's ruling #2 rejected conditional rendering for breaking the single-fixed-SYSTEM
assumption. **That objection no longer applies.** Given a frozen user block, a
symbol scan over it is deterministic: same context → same symbols → same section.
The existing `_prompts_*.json` mechanism supports it directly.

### A5. Open questions
1. Reference section beside `Card data:`, or its own section before it?
2. Symbol in the question with no card attached — inject, or treat as the
   Scryfall-reference case (A1) and stay silent?
3. Mana-value counting rule: stays in SYSTEM always, or rides with the injected
   block when symbols are present?

---

## Slice B — THE MISS MATRIX (merges the former Slices B and C)

> Jon, 2026-07-24: *"we just want to a/b/c the misses to see if they improve."*

One focused experiment instead of two: take **only the questions each arm
currently misses**, and run them across three prompt variants. Everything else
about the eval stays frozen.

### B1. The three prompt variants

| Variant | What it is |
|---|---|
| **A = v3** | the 5,189-char interim production prompt |
| **B = v4** | as shipped, 10,045 chars, full static legend |
| **C = v4-minus-legend** | v4's other changes (4b multiplayer, 4c assumption disclosure, 4d intended-question, 4e no-false-starts, 3b) **without** the per-symbol definitions. Cost-math and the mana-value rule STAY. This is the v5 base. |

Variant C exists because of Jon's point: *"we also need to compare against v4
without the reference stuff because we are going to add that programmatically."*
It is load-bearing twice over — it isolates whether v4's −2 regression came from
the legend or from the other bullets, **and** it's the baseline Slice A's
injection must beat.

### B2. The question set — each arm's own misses

| Arm | Misses (v3 cond-C) |
|---|---|
| sonnet 46/50 | c012, c014, c015, q029 |
| gpt-5-mini 45/50 | c004, c012, c015, q014, q016 |
| gpt-5-mini, v4-only regressions | c002, c011 |

11 arm-question pairs total. Run each arm on its own misses only.

### B3. The de-keyworded arm — c002, and only c002

Jon's hypothesis: naming "trample" and "deathtouch" steers retrieval toward the
*keyword-definition* rules (702.19b, 702.2c — exactly what the failing answers
cited) and away from the *damage-assignment* rules that answer the question. The
cards' oracle text still supplies both abilities, so nothing is lost.

Scope was derived, not guessed: keyword names parsed from **CR 702 headings in
the repo's own CR** (190 abilities). 11 of 50 questions name one; intersecting
with the miss lists leaves three, of which only one qualifies:

- **c002** — trample + deathtouch both restate abilities the named cards carry. **The candidate.**
- **c011** — "my cascade spell" has no card supplying cascade; the word is load-bearing. Not removable.
- **c014** — "awaken" matched the CARD NAME `[Awaken the Woods]`. **False positive.**

**Selection rule:** a keyword is removable only when the question restates an
ability an *attached card's oracle text already carries*. Applying it is judgment
on Jon's own eval questions — **the tool proposes the phrasing; Jon confirms or
rewrites it.** Same contract as gold and grading.

### B4. Capture design

- **Original-question arms need NO new capture.** All three prompt variants share
  the same `user` blocks, so derive three prompt files from `_prompts_C.json` by
  swapping only `system` — generalise `evals/build_prompts_v4.py` to take an
  arbitrary SYSTEM string instead of hardcoding v4.
- **The de-keyworded c002 arm needs ONE new capture** (its question text changed,
  so retrieval changes by design). Capture once, then swap the three systems.
- Within a capture, retrieval is byte-identical across variants, so prompt effects
  stay attributable. **Across captures (original vs de-keyworded) retrieval
  deliberately differs — that IS the treatment.** Any comparison spanning the two
  must say so rather than implying a controlled diff.
- **2 runs per cell**, stable-flip rule unchanged.

### B5. Cost and grading load

11 arm-question pairs × 3 variants × 2 runs ≈ 66 generations, plus c002
de-keyworded × 3 × 2 = 6. Roughly 72 generations, a couple of dollars. The frozen
judge routes each result against the known-wrong reference; **only genuine
changes reach Jon**, so his queue should be a handful of rows.

### B6. What this cannot do — state it in the report

For **c012** (card text missing), **c015** (missing rules/rulings), **q016**
(117.3c/601.2h rank 189/109, never retrieved) and **q014** (802.2/507.1 never
surface), the answering rule **is not in the frozen context at all**. No prompt
wording fixes those. For them this measures *draw variance* — stable failure vs
unlucky draw — which is still worth knowing, but it is not fixability. The
genuinely prompt-shaped misses are **c014**, **c004**, and the two v4 regressions.

### B7. If de-keywording works, the fix is NOT to reword the eval

A real player would say "trample and deathtouch." If the hypothesis holds, the
production fix belongs in the **rewriter** — teach it to de-emphasise keyword
nouns in favour of the mechanic being asked about. The de-keyworded question lives
beside the real one as a diagnostic instrument; it never replaces it.

### B8. Open questions
1. Confirm c002 is the only de-keyworded candidate, or add c003/c009/c010 even
   though they aren't current misses?
2. Does Jon write the de-keyworded phrasing himself, or approve a proposed one?
3. Is 2 runs per cell enough for the variance question, or does the
   draw-variance angle want 3?

---

## Slice C — Automated gold-rule discovery

> Jon: *"we also need a way to analyze everything and find the gold rules for the
> questions missing them to improve ratings. I don't want to do it by hand if I
> don't absolutely have to."*

**The problem:** card questions carry `gold=[]` by design and several rules
questions have incomplete gold, so retrieval metrics understate quality and some
misses can't be scored at all.

**The precedent and its ceiling.** `evals/ablate_gold.py` already does
gold-by-ablation: hold card data fixed, remove retrieved rules one at a time, see
which the model needs. Its docstring states the limit — it **"ablate[s] only the
CITED rules"**, sound because the prompt forces every relied-upon rule into
citations, so the cited set is the used set. That works when the answer is right.
**It cannot find gold that was never retrieved or never cited** — precisely the
q016 case this slice must solve.

**Two-stage design:**

- **Stage 1 — candidate generation (no LLM, cheap).** Sweep the full corpus at
  depth ~100–200 using several query formulations (raw question, each rewrite,
  and the answer's cited rules as seed terms), union them, and apply the existing
  L1 cross-reference expansion so "see rule 704.5" pointers pull their targets in.
  Output: a ranked candidate pool per question, far wider than production top-k.
- **Stage 2 — necessity testing (LLM, bounded).** Ablation over the candidate
  pool, reusing `ablate_gold.py`'s majority-of-N-trials machinery and the
  **frozen** judge for same/different routing. A rule whose removal changes the
  answer is load-bearing.
- **Output: a ranked PROPOSAL per question, never a write.** Same contract
  `ablate_gold.py` already honours — *"does NOT auto-write gold... encoding it is
  Jon's call"* — and the same principle as the transitive-grading pipeline.
  Surface it in a confirm-in-one-click UI like the grading UI, so Jon's hand-work
  is confirmation, not archaeology.

**The honesty limit, stated in the output.** Ablation finds rules load-bearing
*for this model's answer*, which is not the same as the rules that objectively
answer the question. A rule the model ignores but that genuinely governs the
interaction will not surface. This proposes candidates with evidence; it does not
certify gold.

**Cost control:** Stage 2 is O(candidates) generations per question. Cap the pool
(top ~20 after Stage 1), run Stage 2 on **gpt-5-mini** (~8x cheaper, adequate for
necessity testing), report measured spend, and do not run all 50 before Jon has
seen output on 2–3.

**Validation gate (controller recommendation: required).** The tool must
reproduce existing hand-curated gold on questions that already have it before it's
trusted on questions that don't. Cheap, and the only way to know it works.

**Open questions:** scope — all `gold=[]` card questions, or only those implicated
in current misses?

---

## Sequencing (recommendation; Jon's call)

1. **The v4 go/no-go ruling** — a prerequisite, not a slice.
2. **Slice B (the miss matrix)** — no new prompt content needed beyond building
   variant C, reuses frozen captures, ~$2–3, and it answers the two live
   questions at once: what caused v4's regression, and are the misses fixable.
3. **Slice A (selective injection → v5)** — variant C from Slice B is its
   baseline, so B should land first.
4. **Slice C (gold discovery)** — biggest build; its validation gate runs before
   it's trusted anywhere near the eval.

## Non-goals

- No change to the frozen judge, ever.
- No auto-writing of gold (Slice C proposes; Jon encodes).
- No permanent rewording of eval questions (B3/B7 — the de-keyworded question is a
  diagnostic instrument beside the real one).
- No new generation model, no retrieval/TOP_K change, no `Answer` schema change.
- Not reopening condition E — reasoning effort is closed on latency
  (`DECISIONS.md` 2026-07-24), not on accuracy.
