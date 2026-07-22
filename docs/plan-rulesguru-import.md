# Plan — RulesGuru question import: 150-question eval set with human-written gold (DRAFT, pending Jon's review)

Working Rule 0 artifact. No code until reviewed.

## The idea (Jon, 2026-07-22)

RulesGuru (rulesguru.org) hosts judge-curated MTG rules questions with a public
API (`/api/questions/`, documented at rulesguru.org/api/documentation/). Each
question ships with exactly the things our eval set has been missing:

- `questionSimple` — a realistic scenario question (named players, real cards)
- `answerSimple` — a **human-written gold answer**
- `citedRules` — CR rule numbers the answer cites (`"608.2c"` etc.), same id
  format as our `gold` fields
- `includedCards` — the cards involved, by name, with full oracle data
- `level` (0–3, "Corner Case"), `complexity`, `tags`, `url`, `submitterName`

This directly attacks the weakness the card-gold ablation exposed: most
`cards.jsonl` entries have empty rules-gold and test the model's priors more
than the RAG. RulesGuru's harder tiers come with verified citations attached.

Verified live 2026-07-22: one GET with a percent-encoded `json` settings object
returns an array of question objects in exactly this shape. Rate limit is one
request per 2 seconds.

## Jon's calls (made in-session, 2026-07-22)

1. **Set size: ~150, full spread** — all levels including Corner Case, not
   hard-only. (Options offered: 30 hard-only / 60 hard-weighted / 150 spread.)
2. **Grading: auto-judge** — the adopted gpt-5-mini outside judge grades
   generated answers against RulesGuru's `answerSimple`; Jon spot-checks
   disagreements rather than hand-grading every row.

## What gets built

### 1. `evals/fetch_rulesguru.py` — fetch + convert, one script

- **Stratified fetch:** 5 requests, one per level (`"0"`, `"1"`, `"2"`, `"3"`,
  `"Corner Case"`), `count: 30` each, all three complexities,
  `legality: "all"`, `from: "rulemancer-evals"`. Sleep ≥2s between requests
  (their rate limit). Stratifying guarantees the full spread Jon picked —
  a single count=150 request would give us whatever mix the API favors.
- **Raw responses saved** to `evals/rulesguru_raw.json` (one file, list of all
  fetched objects, deduped by RulesGuru id). Re-runs are additive: load
  existing raw file, fetch, merge by id, write back. Never re-fetch what we
  have; the converter reads only the raw file, so conversion is re-runnable
  offline.
- **Convert** to `evals/rulesguru.jsonl`, one line per question:

  ```json
  {"id": "rg1812", "question": "<questionSimple, card names bracketed>",
   "cards": ["Tempt with Discovery"], "gold": ["608.2c"], "match": "any",
   "kind": "rulesguru", "answer_gold": "<answerSimple>",
   "level": "1", "complexity": "Simple", "tags": [...],
   "url": "https://rulesguru.org/?1812...", "submitter": "<submitterName>"}
  ```

- **Card names get bracketed** in the question text (`Tempt with Discovery` →
  `[Tempt with Discovery]`), because the pipeline's card enrichment triggers
  on `[Card Name]` tokens (answer.py's token parser). Longest-name-first
  replacement, first occurrence only, so `Llanowar Elves` inside a longer card
  name can't double-bracket. This matches the existing `cards.jsonl`
  convention and guarantees the bot sees the same card data RulesGuru's answer
  assumed.
- **Gold validation at convert time:** every cited rule id is checked against
  the parsed CR chunk ids (same check run_eval.py does). Ids that don't
  resolve — CR version drift between RulesGuru's snapshot and ours — are kept
  in the record but logged to the console and counted in the summary line, so
  we know how much drift we're carrying before anyone chases a "retrieval
  miss" that's actually a version skew.

### 2. Eval wiring — extend, don't fork

- **`run_eval.py` (rules recall):** gains a `--questions PATH` flag
  (default: existing `questions.jsonl`, unchanged). Pointing it at
  `rulesguru.jsonl` runs the same recall@k machinery — the loader ignores the
  extra fields it doesn't know. Questions with empty `citedRules` are skipped
  for recall (nothing to score) but still counted in the summary.
- **`run_answer_eval.py` (answer generation):** same `--questions` flag.
  Output rows carry `answer_gold` through so the judge step has the reference
  inline.
- **New: `evals/judge_rulesguru.py`** — auto-judging. For each generated
  answer: gpt-5-mini (the bake-off winner, via OpenRouter) judges
  agreement with `answer_gold`, reusing `JUDGE_SYS` + the OpenRouter call
  pattern from judge_bakeoff.py. The judge prompt gets one added context
  line: *"Player names starting with 'A' are the active player; other
  letters are nonactive players in turn order. Questions refer to objects by
  their original names even after copy effects."* The **bot does not** get
  that preamble — production users don't announce conventions, and parsing
  scenario phrasing is part of what's being tested. Output:
  `evals/rulesguru_verdicts.json` — per-question verdict + judge reason +
  level/complexity, plus a summary block (accuracy overall and by level).
  Disagreements are what Jon spot-checks.

### 3. What does NOT change

- `questions.jsonl` and `cards.jsonl` stay untouched — the hand-curated sets
  remain the primary regression suite. The RulesGuru set is a separate,
  clearly-provenanced expansion pack.
- No production (src/) code changes at all. This is evals-only.

## Attribution / usage

Questions are community-submitted to RulesGuru and served by their public API.
Every record keeps `url` + `submitter`. Local eval use only; nothing gets
republished. `from: "rulemancer-evals"` identifies us to their logs, as their
docs request. Raw file and jsonl are committed (they're small and the evals
already commit fixture data) — if RulesGuru ever objects, the fetch script
regenerates everything and the files can be dropped from the repo.

## Edge cases

- **API returns fewer than 30 for a level** (Corner Case is likely thin at
  some complexities): take what's there, report actual counts. 150 is a
  target, not a contract.
- **Duplicate questions across level requests:** dedupe by RulesGuru id.
- **Empty `citedRules`:** keep the question (answer-judging still works),
  `gold: []`, excluded from recall scoring.
- **Card name appears in the answer but not the question:** only the question
  gets bracketed; `cards` still lists every `includedCards` name so we can
  audit enrichment coverage later.
- **Multi-face / split cards:** bracket the name exactly as `includedCards`
  gives it; the existing card resolver handles lookup quirks (that's its job,
  and if it can't, that's a real finding).
- **HTML entities / mana symbols in questionSimple:** the API's "Simple"
  variants are plain text (that's their documented purpose); converter
  asserts no `<` survives, fails loudly if one does.

## Verification (the pass/fail for accepting the build)

1. `fetch_rulesguru.py` run produces `rulesguru_raw.json` + `rulesguru.jsonl`;
   line count reported per level; gold-id drift count reported.
2. `pytest` green (a small `tests/test_rulesguru_convert.py` covers:
   bracketing incl. the substring-name case, dedupe, empty-citedRules
   handling, id mapping `1812` → `rg1812`).
3. `run_eval.py --questions evals/rulesguru.jsonl` completes and prints
   recall@5 without crashing on the new fields.
4. One smoke slice: `run_answer_eval.py --questions ... ` on ~5 questions +
   `judge_rulesguru.py` on the output produces verdicts. Full 150-question
   run is Jon-triggered (it's ~150 generation calls — real money and >10 min),
   not part of build acceptance.

## Decisions for Jon (beyond the two already made) — RESOLVED 2026-07-22

1. **Score BOTH `any` and `all` semantics (Jon's call).** Jon wants to see the
   difference, not pick one blind. Implementation: the recall runner scores
   each question's retrieved top-k under both match modes **in one pass** (no
   second retrieval run needed — the top-k is identical; only the hit rule
   differs) and prints two summary columns, recall@k-any and recall@k-all.
   The jsonl stores `match: "any"` as the nominal default; a `--match-both`
   flag (explicit, default off, documented in the runner help) adds the
   `all` column without disturbing the existing question sets' behavior. The gap between
   the two columns is itself the finding: it measures how many
   context-extra citations the retriever drops.
2. **Commit the fetched data (Jon: yes).** Raw + jsonl are committed;
   reproducible evals beat a live dependency, and the files are small.

## Scope / limits (stated honestly)

- RulesGuru's citations are *the rules their answer cites*, not a measured
  minimal set — treat imported gold as strong-but-unverified. The ablation
  machinery exists if a specific question's gold looks off.
- CR version skew is real: RulesGuru tracks current CR; our snapshot is
  whatever `data/` holds. The drift counter makes it visible instead of
  silent.
- 150 questions × 1 generation + 1 judge call per full run — cheap-ish but
  not free; that's why the full run is manual, not CI.
