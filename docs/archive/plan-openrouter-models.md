# Plan — OpenRouter model lab: generation A/B arms + outside judge

## Goal (Jon, 2026-07-22)

Use the OpenRouter key (already in .env) for two measured experiments:

1. **Generation A/B:** hold retrieval constant, run the full eval question
   set through other generator models, Jon grades. The DESIGN.md stretch
   goal, now activated. Special interest: models that ACCEPT temperature=0,
   because claude-sonnet-5 rejects sampling params and its draw variance is
   a documented, recurring pain (c018 empties, the 77% lucky roll, the 3/6
   multi-turn flakes).
2. **Outside judge (to-do #4):** validate a non-Claude judge for the
   ablation/eval harness. Adopt at >=95% agreement with sonnet-5 verdicts
   (Haiku's bar was 94-99%). Removes Claude-judging-Claude family bias.

## Non-goals (explicit)

- NOT switching the shipped app model. claude-sonnet-5 stays the default
  until an A/B result plus Jon's call says otherwise. Every existing eval
  number stays attached to the pinned model.
- NOT touching retrieval, rewriting, enrichment, or ruling selection —
  those are frozen context for the A/B; only the final generation call
  varies.

## Candidates (Jon trims/extends at review)

| Model (OpenRouter id, verify at build) | Role | Why |
|---|---|---|
| deepseek/deepseek-chat-v3.2 | generator + judge | ~$0.14/$0.28 per 1M; temp=0 accepted |
| moonshotai/kimi-k3 | generator | DESIGN.md's original pick; 1M context |
| google/gemini-2.5-flash-lite | judge | ~$0.10/$0.40; handoff candidate |
| openai/gpt-5-mini | judge | ~$0.40 in; handoff candidate |

## Design

### A. Prompt assembly extracted, byte-identity preserved

`RulesAgent.answer()` currently builds the prompt inline and calls
`client.messages.parse`. Extract the prompt assembly (system string + user
string construction) into a pure helper both backends share, so the
OpenRouter arm generates from the EXACT prompt sonnet-5 sees — otherwise
the A/B measures prompt drift, not models.

Identity gate: a fixture test captures the assembled (system, user) pair
for 3 representative questions before the refactor and asserts byte-equal
after. The anthropic call path itself is untouched.

### B. OpenRouter generation backend (eval-only)

New module `src/rulesagent/generate/openrouter_backend.py`:

- POST /chat/completions with the shared prompt; `model` pinned per arm;
  `provider: {allow_fallbacks: false}` per DESIGN.md's standing rule (a
  silent failover corrupts the numbers); record the served model/provider
  from the response for attribution.
- `temperature: 0` on models that accept it (record what was sent).
  Honest note for the README: temp=0 reduces draw variance, it does not
  guarantee determinism — same caveat the rewriter carries.
- Structured output via OpenRouter's `response_format: json_schema`
  (strict) mapped from the same `Answer` schema. Models that don't support
  structured outputs on OpenRouter get dropped from the candidate list
  rather than hand-parsed — comparability beats coverage.
- Used ONLY by the eval harness (single-turn path). The app never routes
  through it in this slice.

### C. Eval integration

- `evals/run_answer_eval.py` gains `--backend openrouter --model <id>`.
  Frozen context: cached query embeddings, committed rewrite cache,
  `card_no_refresh` — identical retrieval inputs across arms.
- All 31 rules questions + 19 card questions per arm, answers into the
  grading UI, Jon grades (do-not-delegate).
- Variance spot-check per temp=0 arm: 3 questions x 3 draws; report
  whether outputs are actually stable draw-to-draw vs sonnet-5's.
- Serialization: eval runs write caches; never run while the app server
  is answering (existing standing rule) and arms run sequentially.

### D. Outside judge validation (to-do #4 method, unchanged)

- Re-run the ablation agreement tally with each judge candidate scored
  beside sonnet-5's existing verdicts (the 34-36 verdict set).
- Adopt as harness judge at >=95% agreement; below that, report and keep
  Haiku.

## Cost estimate

~50 questions x (~12K in + ~3K out) ≈ 0.75M in / 0.15M out per arm.
DeepSeek ≈ $0.15/arm; K3 and the judges similar order. The whole lab is
under a few dollars.

## Verification

- Prompt byte-identity fixture passes; full test suite passes.
- Shipped defaults untouched (`GEN_MODEL` unchanged; app behavior
  unchanged — confirmed by a live /answer spot-check after merge).
- Deliverables: per-arm answer files + Jon's grades -> the README's
  "generation models compared, retrieval held constant" table; judge
  agreement percentages -> adopt/reject decision in DECISIONS.md.

## Sequencing (Jon's call)

Packaging (#1) is one Jon-read and one clean-clone test from done. Options:
finish packaging first (recommended — this lab's results then extend the
README rather than delaying it), or run the lab now and fold both into the
README at the end.
