# Handoff — the session that found out which channel was doing the work

**Replaces the prior handoff (git has every version). Written at the end of the
2026-07-26 late session. The previous handoff's headline was "every instrument
used to measure retrieval was broken." That held up. This session went further and
asked what the pipeline is actually made of — and found that one channel carries
it, and it is not the one the roadmap was about.**

Suite: **1124 passed** (was 929). API spend this session: **~$50** of an $88
balance. Everything below is committed.

---

## ⚠️ FIRST, UNLEARN THIS

**1. The CR-rules retrieval layer is nearly inert on card questions.** Replace the
retrieved rules with the rules retrieved for a *completely different question* and
accuracy moves **3.3 points** — 12-8 across 20 discordant pairs, p=0.50. A coin
flip. That is the entire subject of the retrieval pipeline, the gold mining, the
rewrite/RRF work, and several sessions of eval effort.

**2. The card oracle text is what carries the system.** Scramble the card data and
accuracy collapses **30.8 points**, 46-9 across 55 discordant pairs, **p=4.3e-07**.

**3. Rulings are minor; the layers tool does nothing.** Full single-variable
scoreboard, each arm tested against a matched baseline:

| component | cost when scrambled/removed | verdict |
|---|---|---|
| **card oracle text** | **-31 pts, p=4.3e-07** | **carries the system** |
| card rulings | -6 pts, p=0.19 | minor |
| CR rules retrieval | -3 pts, p=0.50 | ~inert |
| layers tool | 0, p=0.73 | ~inert |
| reasoning effort low->high | 0 (n=15) | no effect |

**4. Wrong information is catastrophic; missing information is cheap.** Wrong
cards cost 31 points. Missing rules cost 3. **This is the single most actionable
asymmetry in the project** — it means card *mis*-resolution is the expensive
failure mode, and it retroactively justifies the @-mention design as an accuracy
safeguard rather than a UX convenience.

**5. "Placebo" is not "absence", and one of my own arms got this wrong.** Arm Z
was specced as a parametric-knowledge floor and is not one — it hands the model
the WRONG cards, not no cards, and scored 3.3%. The real floor is the earlier
no-rules control (empty context) at ~59.5%.

**6. Retrieval is GOOD at the question type the corpus barely contains.** On 31
card-free rules questions it scores **87.5% mean gold coverage / 93.5% hit@15**,
versus **29.4%** on the card corpus. Not a gold-size artifact (mean gold 1.9 vs
1.82). Direct rules questions are lexically close to the rules that answer them;
card interactions are not.

**7. The corpus is 99.4% card-interaction questions.** Only 9 of 1,409 rows have
no cards. So "rules don't matter" may really be **"rules are redundant GIVEN card
text"** — and we could not tell, because no card-free set with reference answers
existed. There is one now.

---

## WHAT SHIPPED

**Channel ablation** — `docs/results-channel-ablation.md`. Five arms, 120 rows
each, one channel scrambled per arm, byte-identical elsewhere. The scoreboard
above. `evals/analyze_channels.py` reads it and **excludes rows that were not
actually swapped** (rg1006 has no cards; rg46/rg625/rg1006 have no rulings) rather
than diluting the effect toward zero.

**Retrieval A/B** — `docs/results-ab-pilot.md`. The pilot's power analysis (20%
discordance, ~68 discordant pairs needed for a 2:1 effect) is what shaped every
run after it.

**Layers tool, isolated for the first time** — 68 rows whose gold requires a CR
613 rule, live path, one variable. Fired on 42/68 (62%) and changed nothing
(5-3 on fired rows, p=0.73). Previously untestable: every layers-off arm on disk
was sonnet, every layers-on arm was opus. **Removing it saves 8.6%/query and 41%
of round trips** (in 8,469 -> 5,982 tokens; 116 -> 68 API rounds).

**Groundedness guard** — `docs/results-groundedness-guard.md`. The existing check
was advisory (logged a warning nothing consumed) and tested the wrong condition
(emptiness of a field mixing rule numbers, glossary terms, card names and ruling
labels). `cr_rule_citations()` / `needs_regrounding()` / `reground_once()` added,
shared by both generation paths, **`--reground` default OFF**. On placebo context
it converted 6 of 13 challenged rows into honest declines with **zero fabricated
citations**. Jon's ruling: use as telemetry, not a gate.

**Grounding telemetry** — `evals/grounding_sources.py`. Classifies every citation
against what that row's prompt actually provided: `cr_rule` / `ruling` / `card` /
`glossary` / `unresolved`. The rule is general — unresolved means "matches nothing
provided" — so an unanticipated citation shape cannot masquerade as fabrication.
**Fabrication canary is 0 on every arm.** CR-reliance rate (97.5% real vs 22.5%
placebo) is a free production monitor for retrieval failure.

**Batch API** — validated end to end. 2-row smoke test completed in **1m47s**,
re-run **attached instead of resubmitting**, schema identical to synchronous,
cost halves. Refuses loudly on the live path and with `--reground`.
**Prompt caching with batch is NET NEGATIVE and must stay off**: 6% hit rate
against a ~22% break-even, +$0.113 on 120 rows. Parallel requests cannot read a
cache entry the others are still writing.

**A validated card-free eval set** — `evals/questions_rules31.jsonl`. 31 questions
with reference answers, drafted by agents reading the CR directly (quoting
verbatim, blocked from reading `evals/answers/`), then confirmed **31/31** by
three independent adversarial reviewers who derived each answer *before* seeing
the draft. The mined gold was incomplete on **4 of 31 (13%)**.

**Config matrix + gold-size stratification on the dashboard**, and coverage now
counts prompt-supplied rule ids (24.8% -> 29.4%).

---

## THE NEXT FEATURE — RAG over card oracle text

**`docs/spec-cards-rag.md`. Design only, Rule 0, awaiting Jon's ruling. This is
the next thing to build.**

The rules RAG failed because the model already knows the Comprehensive Rules.
**No model has memorised which of 38,336 cards has a similar effect at two mana
less** — that is lookup, not reasoning, so semantic search is genuinely the right
tool and its value can be demonstrated rather than assumed.

Jon's framing: *"same or similar effect but [less mana, less money, different
colors, strictly better]."*

**Why it is a better engineering target than the rules index: the gold standard is
COMPUTABLE.** Functional reprints (identical oracle text after substituting the
card's self-reference), strictly-better pairs, and colour-shifted variants are all
derivable from Scryfall with **no human labelling and no LLM judge**. That is
precisely the property whose absence caused every defect in
`results-adversarial-review.md`. Evaluation costs **$0** and can be iterated
freely.

Everything needed is already local: `data/scryfall.db` has 38,336 oracle cards
with `oracle_text`, `type_line`, `mana_cost`, `mana_value`, `colors`,
`color_identity`, `faces`, `layout`, plus 77,999 rulings. Embeddings reuse
`voyage-4-large` and `rulesagent.index`.

**Controls the spec mandates, carried over from this session:** a deranged-index
placebo (recall must collapse to chance), a BM25 baseline (if lexical matches
embeddings, embeddings are not earning their cost), and stratification by
oracle-text length and multi-face status.

**Four open decisions need Jon before building** (spec's final section): reminder
text stripped or kept; one vector per face or per card; "strictly better" as
filter or ranking signal; standalone or eventually feeding the answer path.

**Cost gate:** Voyage pricing is **NOT** in `rulesagent.pricing` and must be
looked up and added before any indexing spend.

---

## RUNNING OVERNIGHT

**Card-free question set expansion** (subscription labor, $0 API). An agent is
drafting up to 70 new card-free rules questions with CR-grounded reference
answers, targeting CR areas the current 31 miss. Output lands in
`evals/_rules_expansion_draft.jsonl` + `_rules_expansion_report.md` as a **REVIEW
QUEUE — not the eval set.** Jon approves in the morning. Getting to ~100 makes the
card-free set properly powered, which is the only way to settle whether rules are
inert or merely redundant given cards.

---

## NEXT, IN ORDER

1. **Rule on the cards RAG spec** (four open decisions) and build it. This is the
   next feature.
2. **Review the overnight expansion queue**, then run real-vs-placebo rules on the
   full card-free set (~$2 batched). That settles inert-vs-redundant.
3. **Remove the layers tool.** Zero measured benefit, 8.6%/query and 41% of round
   trips saved. Its schema is also under-specified (quotes 613.6 and 613.8a but
   not 613.1/613.2/613.4, which carry the layer order and sublayer structure) —
   but do NOT "fix" it and remove it in the same change.
3b. **Harden card resolution.** Highest-leverage surface by an order of magnitude.
   Prefer failing to resolve over resolving wrongly. Split cards (`Pain //
   Suffering`), DFCs and apostrophes (`Urza's Saga`) broke two separate parsers
   during this session's own analysis.
4. **Fix the short-chunk retrieval defect.** The two zero-coverage card-free rows
   had CORRECT gold: `700.4` is one line with almost nothing to embed, `601.2` is
   subrule-dense so matches fragment. Short chunks lose to long ones.
5. **Do NOT buy the $73-91 full corpus run yet.** It measures corpus-wide accuracy
   on a corpus that is 99.4% one question type, through a one-directionally harsh
   judge. Batched it is ~$90; the question it answers is not the live one.

Still open from before: cosine floor (spec written), second-hop retrieval,
rerank-after-rewrite, the 153 empty-gold rows, the 54+1 mis-encoded conjunctions.
**Note that gold-quality work is now lower value than it looked** — it improves an
instrument pointed at a channel worth 3 points.

---

## HOW JON WORKS (load-bearing)

- **Explain things properly.** Define jargon at first use, lead with what a thing
  means, show a concrete example. He is a partner, not an observer.
- **Rule 0: plan before code.** Every `plan-*.md` / `spec-*.md` is design-only
  until he rules.
- **Complete $0 work without asking.** Split local compute (genuinely free) from
  "$0 in credits" (free only on a subscription subagent).
- **Anything spending API credits gets an explicit ask** with a hard ceiling and a
  pilot checkpoint. The subscription upgrade does NOT change this — Claude Code
  and its subagents run on the subscription, but any Python here that builds an
  Anthropic client from `.env` bills API credits, a separate pool.
- **Verify agents' claims against the underlying data before relaying them.** This
  session that caught: a SHIPPED_ARMS list containing two sonnet arms, a missing
  verdict-file mapping, a "stale metadata" report that was a misread field, and my
  own two wrong numbers (a 40% ungrounded rate that was 0.8%, and a 12.7% missing-
  gold rate that was 0%).
- **Subagent deliverables must land in the repo, never the scratchpad.**
- **Do not run the full pytest suite while an eval arm is running** — it races
  `evals/answers/_progress/`.
- **Never assert an MTG or model fact from memory.** Ground in
  `data/raw/MagicCompRules 20260619.txt` or Scryfall. For pricing import
  `rulesagent.pricing`; do not load the claude-api skill.
- **Verify by rendering** for UI. **Jon runs the app on port 8000 — never bind or
  kill it.** Use 8947.
- Python `.venv/Scripts/python.exe`, `PYTHONIOENCODING=utf-8`, JSON
  `encoding="utf-8"`. Commit per slice on master with the `Co-Authored-By: Claude
  Opus 5` trailer.
- Do not use `nohup ... &` inside a backgrounded call — the child dies with its
  parent shell. Cost $0.16 to learn.

---

## THE LESSON TO CARRY

Previous sessions: *a value that looks like an identity but is really a position*;
*a claim inherited without being checked*; *anything used as ground truth is an
experiment subject*; *an instrument that has never been tested is not a
measurement*.

This session: **you cannot know which part of a system is doing the work until you
take each part away, one at a time, and watch what happens.**

Four components had been built, tuned, documented and reasoned about for months.
Ablation took a day and showed that one carried the system and three were close to
free. None of the prior reasoning was stupid; it was just unfalsifiable, because
nothing had ever been removed to see if it mattered.

The corollary, learned twice today: **check whether the rows that moved are the
rows the intervention touched.** The first layers experiment showed a 6.7-point
gap that looked like a result. The tool had fired on `rg783`; the single
discordant row was `rg6556`. Different rows. The effect was noise. That one query
is the difference between a finding and an artifact, and it costs nothing.
