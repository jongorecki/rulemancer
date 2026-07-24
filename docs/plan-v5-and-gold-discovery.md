**DRAFT under Rule 0 — DESIGN ONLY. Nothing built. Four independently-approvable
slices; each needs Jon's ruling on its own open questions before it starts.**

# Plan — v5 selective symbol injection, miss-variance probe, keyword ablation, and automated gold discovery

Written 2026-07-24, after the v4 A/B concluded. Source of intent: Jon's
direction in-session. Grounding read for this plan: `src/rulesagent/generate/
answer.py` (rewrite/build_prompt ordering, `_format_cards`), `evals/
ablate_gold.py`, `evals/run_openrouter_arm.py`, `evals/run_answer_eval.py`,
`evals/lib_v3ab.py`, `docs/plan-prompt-v4.md`, `docs/plan-rewriter-model-
bakeoff.md`, `DECISIONS.md` (2026-07-24 entries), `evals/report-v4e.md`.

## 0. Why this plan exists — what the v4 A/B actually proved

Graded result (Jon, strict): **sonnet 46 → 46 (zero divergence across all 50
questions, both runs); gpt-5-mini 45 → 43** (c002 and c011 stable-flipped
`correct` → `wrong`). v4 nearly doubled the SYSTEM (5,189 → 10,045 chars,
~+1,215 tokens) and **failed its own go criterion** ("sonnet flat-or-up AND
gpt-5-mini up"). It also did not move **c014**, the mana-arithmetic failure the
notation legend was built for.

Three conclusions drive the slices below:

1. **The legend's content is fine; its delivery is wrong.** Every question pays
   ~1,215 tokens for definitions of `{E}`, `{L}`, `{PW}`, hybrid Phyrexian and
   the rest, including the 31 rules-only questions with no mana symbol in play.
   → Slice A.
2. **Most remaining misses are not prompt-shaped.** Because the SYSTEM-swap held
   retrieval byte-identical, v3 and v4 saw the *same* context on every miss — and
   on several, the answering rule was never in it. → Slices B and C.
3. **We cannot improve what we cannot score.** Card questions carry `gold=[]` by
   design and several rules questions have incomplete gold, so retrieval metrics
   understate or misreport quality. Jon does not want to rebuild gold by hand.
   → Slice D.

**Also still open and NOT decided by this plan: the v4 go/no-go.** Master
currently ships `PROMPT_VERSION = 4`, a candidate that failed its go test, costs
+1,215 tokens/query, and pushes gpt-5-mini to a 3-answer gap — which trips Jon's
own pre-commitment #3 ("gap ≥3 → sonnet stays pinned") and mothballs the ~8x
cost saving. Controller recommendation on record: **revert production to v3**
and treat Slice A's output as the v5 candidate. Jon's call.

---

## Slice A — Selective symbol injection (the v5 candidate)

**The idea (Jon's, 2026-07-24):** stop shipping a static legend. When cards are
attached, scan them for symbols actually present, and inject only those
definitions as a reference section in the prompt.

### A1. Why scanning CARDS (not the whole context) is the correct scope

Jon's specification, and it is better than the obvious alternative. Scanning the
assembled context would be actively harmful: **CR 107.4 is a single chunk that
enumerates every symbol in the game** — all ten hybrids, all ten hybrid
Phyrexians, the five monocolored hybrids, the five `{C/x}` symbols, snow, and
the Phyrexian set. Any question that retrieves 107.4 would trigger the entire
legend, i.e. a worst case *worse than today's static block*. Card oracle text
carries only the symbols actually in play.

**Fallback (Jon, 2026-07-24): also scan the question text.** A question can name
a symbol with no card attached. Cheap, same regex.

**Scoping note Jon raised, worth encoding in the eval rather than the prompt:** a
bare "what does `{C}` mean" is a **Scryfall reference question, not a rules
question** — declining it is not incorrect. That belongs in `questions.jsonl`'s
`kind` taxonomy, not in a prompt bullet. Flagged as a possible eval-metadata
follow-up, out of scope here.

### A2. Mechanism — straight code, zero model calls

Confirmed by reading `answer.py`: `rewrite_query()` is called at line 600,
`build_prompt()` at line 685. **Rewriting happens strictly before prompt
assembly**, so a reference section built inside `build_prompt`/`_format_cards`
is structurally invisible to the rewriter. Jon's requirement that "the rewriter
doesn't touch the reference section" is satisfied by the existing call order —
no guard, no flag, nothing to enforce. State this in the implementation's
comments so nobody later "fixes" it.

Shape:
- A `SYMBOL_DEFS: dict[str, str]` table (the v4 legend content, decomposed into
  per-symbol entries; definitions already verified against the June 2026 CR and
  Scryfall's Colors-and-Costs doc — see commit `8c7550f`).
- `_symbols_present(text) -> set[str]`: regex `\{[^}]{1,8}\}` over card oracle
  text + mana costs + the question. Normalise case.
- Family collapsing: `{W/U}`, `{B/G}` etc. all resolve to the ONE hybrid
  definition, not ten copies. Same for Phyrexian, hybrid Phyrexian, `{C/x}`,
  `{2/x}`, and generic numerals (`{0}`…`{20}` → one generic entry).
- Emit a `Symbol reference:` block only when the set is non-empty. Zero symbols
  → zero tokens.
- The **cost-math rules and the mana-value counting rule stay in SYSTEM** — they
  are arithmetic instructions, not symbol definitions, and they are what v4
  should have led with. Only the per-symbol *definitions* move.

Estimated cost: ~1,215 tokens on every question today → roughly 150–400 on card
questions and **0 on the 31 rules-only questions**.

### A3. The caching trade-off, stated honestly

SYSTEM sits in the cacheable prefix (~0.1x on repeat calls); a per-question user
block does not cache. A block 5–10x smaller still wins, but this should be
**measured, not assumed** — record real input-token counts per question, both
ways, and report them.

### A4. Testing — the byte-identical methodology still holds

v4's ruling #2 rejected conditional rendering because it broke the
single-fixed-SYSTEM assumption. **That objection no longer applies.** Given a
frozen user block, a symbol scan over that block is deterministic: same context
→ same symbols → same reference section, every time. The existing
`_prompts_*.json` capture mechanism supports this directly.

Test grid: sonnet + gpt-5-mini, v5 vs the **v3 baseline** (46 / 45), 2 runs each,
same stable-flip rule, same frozen retrieval. Go criterion, unchanged and
non-negotiable: no net sonnet regression on stable flips.

### A5. Open questions
1. Does the reference section sit next to `Card data:` in the user block, or as
   its own section before it?
2. If a symbol appears in the question but no card is attached, inject it —
   or treat that as the Scryfall-reference case (A1) and stay silent?
3. Does the mana-value counting rule stay in SYSTEM unconditionally, or does it
   ride along with the injected block when symbols are present?

---

## Slice B — Miss-variance probe (cheap, no new code paths)

**Question it answers:** are the remaining misses *stable* failures the model
can never get right, or unlucky draws it sometimes lands?

Both frozen prompt files already exist (`_prompts_C.json` = v3,
`_prompts_v4.json` = v4), so this is pure re-generation at fixed retrieval.

**Miss lists, derived from the graded references:**

| Arm | Misses (v3 cond-C) |
|---|---|
| sonnet 46/50 | c012, c014, c015, q029 |
| gpt-5-mini 45/50 | c004, c012, c015, q014, q016 |
| gpt-5-mini under v4 | + c002, c011 (the two regressions) |

**Method:** for each arm, each of its missed questions, under BOTH v3 and v4
prompts, generate **3 draws**. Report per (arm, prompt, question): how many
draws the frozen judge routes as `different` from the known-wrong reference, and
send only those to Jon. Everything else inherits the existing verdict. Roughly
66 generations, ~$1.40 total.

**Honest scoping — what this cannot do.** For c012 (card text missing), c015
(missing rules/rulings), q016 (117.3c/601.2h rank 189/109, never retrieved) and
q014 (802.2/507.1 never surface), the answering rule **is not in the frozen
context at all**. No prompt wording can fix those, and this probe will not
pretend otherwise — it measures variance, not fixability. The genuinely
prompt-shaped misses in the set are **c014** and **c004**.

---

## Slice C — Keyword-ablation retrieval probe (c002)

**Jon's hypothesis:** naming "trample" and "deathtouch" in c002 steers retrieval
toward the *keyword-definition* rules (702.19b, 702.2c — exactly what the failing
answers cited) and away from the *damage-assignment* rules that answer "how much
do I assign." The cards' own oracle text still supplies both abilities, so the
model loses no information when the words are dropped.

**Method — retrieval-only, cents, no generation, no grading.** Build a c002
variant with the keyword nouns removed, run both phrasings through
rewrite → retrieve, and diff retrieved rule ids and ranks. Reuse the rewriter
bakeoff's phase-1 method (`docs/plan-rewriter-model-bakeoff.md`), including its
**3-run mean±spread** requirement — embedding draw noise (~30-34%) would
otherwise masquerade as a real difference.

**This is a diagnostic probe, not an eval edit.** A real player *would* say
"trample and deathtouch." If the hypothesis holds, the fix belongs in the
**rewriter** (de-emphasise keyword nouns in favour of the mechanic being asked
about) — never in rewording Jon's gold questions. Say so in the writeup.

---

## Slice D — Automated gold-rule discovery (Jon: "I don't want to do it by hand")

**The problem:** card questions carry `gold=[]` by design and several rules
questions have incomplete gold, so retrieval metrics understate quality and some
misses can't be scored at all. Rebuilding gold by hand across 50 questions is
exactly the labour Jon wants to avoid.

**The precedent, and its ceiling.** `evals/ablate_gold.py` already does
gold-by-ablation: hold card data fixed, remove retrieved rules one at a time,
see which the model actually needs. Its own docstring states the limit: it
**"ablate[s] only the CITED rules"**, on the sound logic that the prompt forces
every relied-upon rule into citations, so the cited set is the used set. That
works when the answer is *right*. **It cannot find gold that was never retrieved
or never cited** — which is precisely the q016 case this slice must solve.

**Proposed two-stage design:**

- **Stage 1 — candidate generation (no LLM, cheap).** For each question needing
  gold, sweep the full corpus at depth ~100–200 using several query
  formulations (raw question, each rewrite, and the answer's own cited rules as
  seed terms), union the results, and apply the existing L1 cross-reference
  expansion so "see rule 704.5" pointers pull their targets in. Output: a ranked
  candidate pool per question, far wider than production top-k.
- **Stage 2 — necessity testing (LLM, bounded).** Ablation over the candidate
  pool, reusing `ablate_gold.py`'s existing majority-of-N-trials machinery and
  the **frozen** judge for same/different routing. A rule whose removal changes
  the answer is load-bearing.
- **Output: a ranked PROPOSAL per question, never a write.** Same contract
  `ablate_gold.py` already honours — *"does NOT auto-write gold... encoding it is
  Jon's call"* — and the same principle as the transitive-grading pipeline: the
  tool routes and ranks, Jon rules. Surface it in a confirm-in-one-click UI like
  the grading UI, so Jon's hand-work is confirmation, not archaeology.

**The honesty limit that must be stated in the output.** Ablation finds rules
that are load-bearing *for this model's answer*, which is not the same as the
rules that objectively answer the question. A rule the model ignores but that
genuinely governs the interaction will not surface. So this proposes candidates
and shows evidence; it does not certify gold.

**Cost control:** Stage 2 is O(candidates) generations per question. Cap the
candidate pool (top ~20 after Stage 1), run Stage 2 on **gpt-5-mini** rather
than sonnet (~8x cheaper and adequate for necessity testing), and report the
measured spend. Do not run Stage 2 across all 50 questions before Jon has seen
the tool's output on 2–3.

**Open questions:** which questions are in scope (all `gold=[]` card questions,
or only ones implicated in current misses)? Does a proposal need to reproduce
existing hand-curated gold on questions that already have it, as a validation
gate, before Jon trusts it on questions that don't? (Controller recommendation:
**yes** — that gate is cheap and it is the only way to know the tool works.)

---

## Sequencing (recommendation; Jon's call)

1. **The v4 go/no-go ruling** — this is a prerequisite, not a slice. Everything
   below is measured against whichever prompt is production.
2. **Slice B** (miss-variance) — no new code, uses existing frozen prompts,
   ~$1.40, and tells us which misses are even addressable.
3. **Slice A** (selective injection → v5) — the real prompt work; Slice B's
   result informs whether c014/c004 are worth targeting in it.
4. **Slice C** (keyword ablation) — independent, cents, can run alongside A.
5. **Slice D** (gold discovery) — biggest build, and its validation gate should
   run before it's trusted anywhere near the eval.

## Non-goals

- No change to the frozen judge, ever.
- No auto-writing of gold (Slice D proposes; Jon encodes).
- No rewording of eval questions (Slice C is a probe; the fix lands in the
  rewriter).
- No new generation model, no retrieval/TOP_K change, no `Answer` schema change.
- Not reopening condition E — reasoning effort is closed on latency
  (`DECISIONS.md` 2026-07-24), not on accuracy.
