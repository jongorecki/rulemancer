# Plan — c011 stale-ruling data bug: diagnosis + fix options

**DRAFT under Rule 0 — DESIGN ONLY. Nothing built. Awaiting Jon's review.**

## 0. Scope note (why this is diagnosis-only)

Investigated per Jon's approval to work "the stale-ruling data bug from c011"
(`docs/HANDOFF-development.md` STILL QUEUED list, line 195). Per explicit
mid-task instruction, this plan does **not** touch any ruling data, Scryfall
cache entry, or retrieval input for c011, even though the root cause below is
fairly well pinned down — c011 is a **scored** question in a paid eval grid
running right now, and it carries verdicts in three tracked files
(`evals/verdicts_v3ab.json`, `evals/verdicts_v4e.json`,
`evals/verdicts_gpt-5-mini_final.json`). Nothing in this session read, wrote,
or queried live Scryfall or any paid model API; every finding below comes from
files already in the repo.

## 1. What the bug actually is (evidence)

**The failure, in Jon's own words.** `evals/verdicts_v4e.json`:

```
{ "id": "gpt-5-mini_v4_r1:c011", "verdict": "wrong", "note": "old ruling, not updated one." }
{ "id": "gpt-5-mini_v4_r2:c011", "verdict": "wrong", "note": "old ruling, not updated one." }
```

**Where the bug got its name.** `docs/HANDOFF-development.md` git history
(`git log -p -- docs/HANDOFF-development.md`, an earlier revision of the file
than HEAD, superseded but not deleted from history) records the diagnosis at
the time it was written:

> Jon's c011 note — *"old ruling, not updated one"* — is a **stale-ruling data
> bug** in the corpus, now the backlog's first `data-bug` entry. Retrieval was
> byte-identical between v3 and v4, so both saw the same stale ruling; v3
> answered around it, v4 leaned on it.

That sentence is the single most important piece of evidence in this
investigation: **the retrieved rulings content was identical between the v3
and v4 generation prompts.** The regression is not a retrieval change, not a
cache-freshness change between the two runs, and not a rewiring of which
rulings got selected — it is the **generation prompt version** (v3 vs v4
system prompt / instructions) changing how the model *weighted* a piece of
data that was present in both prompts unchanged. `docs/HANDOFF-development.md`
still lists the bug as unresolved (STILL QUEUED, line 195) and it is currently
tagged in the auto-harvested backlog as a `data-bug`
(`evals/harvest_grading_notes.py` lines 39-41, pattern includes literal
`stale`).

**What question and what's actually load-bearing.** `evals/cards.jsonl` id
`c011`:

```
"question": "My cascade spell exiles cards until it hits [Valki, God of Lies],
  whose back face is the seven-mana planeswalker Tibalt, Cosmic Impostor. Is
  that a legal cascade hit, and can I cast the Tibalt side for free?"
"gold": ["702.85a"]
"note": "... Load-bearing: cascade rule 702.85a (the 'you may cast it if the
  resulting spell's mana value is less than this spell's' clause -- the
  errata that killed Tibalt-cascade; Tibalt's MV is 7) + Valki ruling 17 (in
  exile, MV = front face) + modal-DFC-not-transform (layout). ... Rules-gold
  BY ABLATION: 702.85a is NECESSARY ..."
```

The **correct** answer requires two facts working together: (a) CR rule
702.85a — cascade's post-errata "resulting spell's mana value must be less"
clause, which is why Tibalt (MV 7) can't be cast off a normal cascade even
though Valki (front face, MV 2) is a legal hit — and (b) Valki's own ruling
#17, which establishes that in a non-battlefield/non-stack zone (exile, mid-
cascade) a modal DFC's mana value is read from the front face only. Both are
CR-current, non-controversial facts; 702.85a is confirmed necessary by
ablation (`LOG.md` 2026-07-22 entry, "scoped ablation: c011 is the real
rules-RAG test").

**The retrieval ceiling that's already documented (a different, known,
already-accepted limitation).** `src/rulesagent/tools/ruling_retrieval.py`
lines 26-34:

```python
COSINE_FLOOR = 0.38
# CALIBRATED on the 19-question card eval (2026-07-21). ... 3 questions have a
# load-bearing ruling BELOW this / outside top-3 (c010, c011, c019) -- a
# genuine semantic-mismatch limit of relevance retrieval, not a floor to
# chase down (lowering it wouldn't lift those into the top 3 anyway).
```

So Valki's load-bearing ruling #17 is **already known** not to clear the
mini-RAG's top-3 cosine selection for c011's question wording — this is a
pre-existing, measured, accepted ceiling (`LOG.md` 2026-07-21, "mini-RAG
head-to-head"), and answers were previously correct anyway because the CR
rule (702.85a) carried the answer on its own. **This is not the stale-ruling
bug** — it's a separate, already-documented retrieval-recall gap that
happens to share a question id. The stale-ruling bug is about *content*
being wrong/outdated, not about the *right* content failing to be retrieved.

**What "old ruling, not updated one" most likely refers to.** Scryfall's
`rulings_uri` (`src/rulesagent/tools/scryfall.py` line 136-140) returns the
**full historical list** of rulings WotC has ever published for a card,
in publication order, with no supersession markers — when WotC/Scryfall
issues a newer, clarifying ruling, the older one is **not** retracted or
flagged; both remain in the list forever. Valki, God of Lies previewed with
Kaldheim in early 2021, and cascade's mana-value-of-the-cast-card errata
(the clause now codified as CR 702.85a) was issued later that same year
specifically to close the "free Tibalt" line that both Jon and Claude
independently (and wrongly) remembered as legal (`LOG.md` 2026-07-21, "the
enrichment fix flipped c011, and proved the whole thesis" — "We were BOTH
wrong -- working from the PRE-errata (early 2021) interaction"). Valki
carries 22 rulings total (`LOG.md` 2026-07-21, "c011 dumped Valki's 22 -> 3").
It is highly plausible — though **not directly confirmed in this session**,
see "What I could not verify" below — that one or more of those 22 rulings
predates the cascade errata and reads consistent with the old, incorrect
"cast Tibalt for free" interaction, and that the v4 generation prompt (unlike
v3) leaned on that older ruling's phrasing over the CR text's current,
correct clause.

**What I could not verify directly.** This worktree does not have live or
cached access to Valki's actual 22 ruling strings: `data/cache.db` is
gitignored (`.gitignore` lines "data/cache.db*") and not present in this
worktree, `evals/answers/` (the captured prompts/answers for the v3/v4 runs)
is untracked per `docs/HANDOFF-development.md`'s ENVIRONMENT section and also
absent here, and calling live Scryfall or any paid model is out of scope /
forbidden for this task. So the specific ruling text that reads as "old" is
identified by inference from the dated LOG.md/cards.jsonl trail and Jon's
grading note, not by directly reading the ruling string. **Confirming the
exact ruling text is the first action item below**, and it is read-only
(Scryfall's public rulings endpoint, not the frozen eval cache) — it does not
touch any eval input.

## 2. Root cause classification

**Data**, not cache, not code, with a compounding retrieval-design gap:

- **Not a cache-freshness bug.** `get_card(ref, no_refresh=True)` is used
  everywhere in the eval path (`evals/run_answer_eval.py` line 276,
  `evals/run_openrouter_arm.py` line 132/373, `evals/opus_grader_v2_prep.py`
  line 140, `evals/build_prompts_variant.py` line 281) *by design*, so that
  eval runs are reproducible regardless of TTL age
  (`src/rulesagent/tools/scryfall.py` lines 178-179, `DECISIONS.md` lines
  915-916). The cache is frozen on purpose. Refreshing it would not fix
  anything — Scryfall's rulings feed does not retract old rulings when a
  newer one is added, so a fresh fetch would still contain the same old
  ruling text alongside the newer material. Freshness is not the axis the
  bug lives on.
- **Not a code bug in the narrow sense.** `ruling_retrieval.py`'s cosine
  selection and `scryfall.py`'s fetch/cache logic both do exactly what
  they're specified to do, and are independently well-tested
  (`tests/test_scryfall.py`, `test_no_refresh_uses_stale_entry_without_fetching`).
  Nothing here is a defect against its own spec.
- **It is a data problem with a design gap sitting on top of it.** The
  underlying corpus (Scryfall's own rulings history for Valki) contains an
  entry that is temporally superseded by a later CR errata, and nothing in
  the pipeline — neither the mini-RAG's cosine selection nor the generation
  prompt — has any notion of "this ruling predates a rules change and should
  be weighted below the current CR text when they conflict." The `v3` system
  prompt happened not to lean on it; the `v4` system prompt did. That's a
  **prompt-sensitivity symptom** riding on top of a **corpus-currency data
  gap** — fixing the symptom (prompt wording) without addressing the gap
  (an unflagged stale ruling sitting in the retrieval pool) would just move
  where the next prompt version trips over the same rock.

## 3. Blast radius — exactly what a content fix would invalidate

Any fix that changes *what ruling content c011 retrieves or is shown* — e.g.
editing/removing the stale ruling from the frozen Scryfall cache, changing
`COSINE_FLOOR`/`TOP_N` so a different ruling set is selected, adding a
recency/supersession filter to `ruling_retrieval.py`, or adding a
per-card override/annotation that suppresses a specific ruling — changes the
**retrieval input** for c011, and therefore invalidates:

- **`evals/verdicts_v3ab.json`** — every `*_C_r{1,2}:c011` and `*_B_r{1,2}:c011`
  (and any other condition) verdict was graded against the ruling content c011
  retrieved under the *current* frozen cache. A content change desyncs the
  verdict from the text that earned it.
- **`evals/verdicts_v4e.json`** — the two `gpt-5-mini_v4_r{1,2}:c011` "wrong /
  old ruling, not updated one" verdicts specifically. These are also the
  *evidence* that the bug exists; overwriting the data they were graded
  against would delete the reproducibility of the bug itself, not just the
  grade.
- **`evals/verdicts_gpt-5-mini_final.json`** — named explicitly in the
  coordinator's scope note; not independently re-checked in this session
  (out of scope to open/modify), but it sits in the same blast radius as the
  other two verdict files for the same reason.
- **Any future v5/v-next run of c011** — since `no_refresh=True` freezes the
  cache, a content edit changes what *every future eval run* retrieves too,
  silently, unless the change is versioned the way `PROMPT_VERSION` already
  is for the rewrite prompt (`docs/plan-prompt-tuning.md` line 159) and the
  card cache schema already is (`CARD_CACHE_SCHEMA`, `scryfall.py` lines
  30-39) — i.e. it would need the same discipline this codebase already
  applies to prompt changes, not an ad hoc data edit.
- **The rules-gold-by-ablation record for c011** (`LOG.md` 2026-07-22) —
  which asserts 702.85a is *necessary* and the MDFC rules are *replaceable*
  under the ruling/enrichment content as it exists today. A ruling-content
  change reopens that ablation; it would need to be re-run, not assumed
  still valid.

**Nothing captured/graded is touched by writing this plan doc, or by the
read-only verification step proposed in §5.1 below** (a live, read-only
Scryfall fetch of Valki's public ruling list, outside the frozen eval cache,
purely to confirm which specific ruling is "the old one" — this does not
call `get_card()`, does not write to `data/cache.db`, and does not alter
anything the eval path reads).

## 4. Can any fix be made touching NOTHING already captured or graded?

**Yes — one class of fix is code-only and forward-looking, and is safe to
build later without disturbing any evidence, subject to Jon's sign-off on
scope:**

- **A system-prompt instruction, versioned the normal way** (bump the
  generation prompt version, exactly as `docs/plan-prompt-tuning.md` line 159
  requires for any `SYSTEM` wording change), telling the model: when a card's
  rulings and the provided Comprehensive Rules text disagree, and the CR text
  is more specific/recent (e.g. cites an errata clause), prefer the CR text
  — a generation-time tie-break rule, not a retrieval-time content edit. This
  changes **future prompts only** (a new prompt version is a new, distinct
  captured artifact by this project's own convention — see how `PROMPT_VERSION`
  bumps are already handled for `rewrite.py`, `docs/plan-v3-execution-tasks.md`
  line 14) and would not touch `verdicts_v3ab.json`, `verdicts_v4e.json`, or
  `verdicts_gpt-5-mini_final.json`, all of which are keyed to prompt versions
  that already exist and stay exactly as graded.
- **This is squarely out of this session's scope regardless** — `rewrite.py`
  is explicitly owned by another agent/worktree right now, and any generation
  `SYSTEM` prompt change is a Rule-0 item (plan first, build only after Jon
  reviews) that touches shared, currently-running eval infrastructure. Flagged
  here only to answer the coordinator's question, not proposed for action
  tonight.

**No fix that changes what content c011 retrieves can be made without
touching captured/graded material** — that class of fix is definitionally a
retrieval-input change, covered in full in §3.

## 5. Recommended path (mirrors the c002 → c020 precedent)

When Jon found c002 was malformed, the fix was **not** to rewrite c002 — it
was frozen (excluded from scoring, kept as-is) and a new id, c020, was added
to carry the corrected version, specifically *because* "the verdicts are
evidence" (`docs/HANDOFF-development.md` "STILL QUEUED" section references the
c002 exclusion; `LOG.md`/`DECISIONS.md` record the c020 addition as the
carrier of the fix). The same shape applies here:

### 5.1 Immediate, read-only, safe to do anytime (recommend doing this first)

Fetch Valki, God of Lies's public ruling list from Scryfall live (read-only,
outside the frozen eval cache — do not call `get_card()`, do not touch
`data/cache.db`) and identify by inspection which of the 22 rulings predates
the cascade mana-value errata and reads consistent with the old "cast Tibalt
for free" interpretation. This confirms the diagnosis in §1 with the actual
ruling text instead of inference, at zero risk to any eval artifact. Output:
a one-paragraph addendum to this plan naming the specific ruling (index +
text), not a code or data change.

### 5.2 If Jon wants the corpus-currency gap actually closed

**Do not edit c011 or its retrieved content.** Instead, mirroring c002/c020:

- Add a **new** card-question id (e.g. `c021`) that is either (a) c011's
  exact question again, re-asked, so it gets a fresh independent grading
  history under the current/any-future ruling corpus, or (b) a question
  purpose-built to exercise "old ruling vs. current errata" conflict
  resolution directly (e.g. explicitly asking the model to reconcile a
  ruling that predates a known errata), so the fix has a dedicated, honest
  test rather than retrofitting c011's history to a changed corpus.
- **`c011` itself stays exactly as-is — same cards, same gold, same note —
  frozen, the same way c002 was frozen.** Its existing verdicts
  (`verdicts_v3ab.json`, `verdicts_v4e.json`, `verdicts_gpt-5-mini_final.json`)
  remain valid evidence of what v3/v4 actually did against the corpus as it
  existed at grading time; they are not retroactively "fixed."
- Any corpus-level fix that generalizes beyond c011/c021 (e.g. a
  recency-aware ruling filter in `ruling_retrieval.py`, or a per-card
  "superseded ruling" annotation layer) is its own Rule-0 plan, scoped and
  reviewed separately, and would only ever apply to **future** cache entries
  and **future** question ids — never retroactively to already-frozen,
  already-graded ones.

## 6. Non-goals

- Not proposing to change `COSINE_FLOOR`, `TOP_N`, or any selection parameter
  in `ruling_retrieval.py` tonight.
- Not proposing to edit, refresh, or invalidate any Scryfall cache entry for
  Valki (or any other card) tonight.
- Not proposing any change to `evals/cards.jsonl`, `evals/questions.jsonl`,
  any `verdicts_*.json`, any `_prompts_*.json`, or `evals/answers/`.
- Not proposing any change to `src/rulesagent/retrieve/rewrite.py`,
  `src/rulesagent/generate/openrouter_backend.py`, or `evals/run_eval.py`
  (owned elsewhere).
- Not proposing a `SYSTEM` prompt wording change tonight — flagged in §4 as
  the one code-only fix class that's safe *in principle*, but it's a
  separate Rule-0 decision with its own plan, not bundled into this one.
- Not claiming certainty about which specific one of Valki's 22 rulings is
  "the old one" — that's exactly what §5.1's read-only check is for.

## What would change my mind

If §5.1's live read shows Valki's rulings list does **not** actually contain
anything reading consistent with the pre-errata interpretation — i.e. the
"old ruling" Jon flagged turns out to be something else entirely (a
mis-citation, a different card's ruling bleeding in, a formatting artifact)
— then this is not a corpus-currency problem at all and the classification in
§2 needs to be redone from that evidence, most likely pointing back at a real
code bug (e.g. a citation-id mixup) rather than a data-recency one.
