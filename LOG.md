# Log

Raw, ugly, unedited. Under 60 seconds per entry. Capture failures, surprises,
and numbers — never clean it up during the build. See DESIGN.md's "Content
capture" section for the trigger rules.

---

## 2026-07-21 — start

- Failed the AI-103 exam on the first attempt (2026-07-20). Building this to
  prove the RAG/agent material to myself and to employers, not just to pass
  a retake.
- Scaffolded the repo. Starting with Claude Code only — OpenCode/OpenRouter
  model rotation comes later.

## 2026-07-21 — parser first pass

- expected: that's more than I expected. 30 words felt really short for how complex this game is, so I'm surprised to see that 44% of the rules are under that number.

## 2026-07-21 — chunking, label detection

- Word-count-only heuristic (<=4 words) had zero false positives but missed
  two real labels ("Roll to Visit Your Attractions," "More Than Meets the
  Eye") at 5 words.
- Adding a punctuation check fixed those two but broke two DIFFERENT ones
  ("For Mirrodin!", "Start Your Engines!") because I counted "!" as sentence
  punctuation, and these are flavor-named keywords that end in "!" without
  being sentences.
- Took longer than expected -- every fix traded one small set of edge cases
  for a different small set. Final version (word count <=6 as a bound,
  "!" excluded from sentence enders) checked out clean against the whole
  corpus, but it took three iterations to get there, not one.

## 2026-07-21 — string-prefix bug, take two

- I hadn't thought about the string-prefix vs parent-chain thing to be
  honest. although it probably should be already showing up differently,
  as I can see that rule 118 has children that go all the way to 118.14.
- (Claude) My earlier "no collision exists in this ruleset" was wrong.
  Jon's 118.14 hunch was right: measured 52 rules where prefix-matching
  wrongly adopts X.10+ as children of X.1. Doesn't change the label count
  (269) because none of the 52 are short labels, but the claim was false
  and got corrected in DECISIONS.md.

## 2026-07-21 — eval harness works, first BM25 numbers

- Harness runs end-to-end. BM25 over 3,617 chunks, 5 SEED questions only
  (not a real eval yet): recall@1=40%, recall@5=80%, recall@10=100%.
- Real miss already: "What does trample do?" -> gold 702.19a (the actual
  one-line definition) lands rank 6-10, NOT top 5. BM25 ranks longer
  sibling chunks (702.19b-g, "Trample Over Planeswalkers") higher because
  "trample" saturates across ~10 sibling chunks and the short primary
  definition gets no credit for being primary. Classic BM25 weakness on
  short definitional queries -- the thing vector/hybrid is meant to fix.
  Good to have it on record as a real example, not a hypothetical.

## 2026-07-21 — first REAL eval: 32 questions, BM25 baseline

- Jon wrote 32 real questions (rules-only). BM25 baseline:
  recall@1=31%, recall@5=44%, recall@10=53%. This is THE number we move from.
- 18 misses, and they cluster into named patterns:
  1. Lexical gap: "Do you cast lands?" -> answer 305.1 says lands are
     "played," not "cast," so the query word never matches. Textbook
     embeddings-fix.
  2. Glossary distractor: short keyword-dense glossary chunks ("Untap Step,"
     "Respond," "Cleanup Step") outrank the actual rule.
  3. Short primary def beaten by its own children: "delayed triggered
     ability" retrieves 603.7d-h (the longer children) but not 603.7 or the
     glossary term. Same failure as the trample seed.
  4. Term saturation: all 3 priority questions target 117.3c and miss --
     "priority" appears everywhere, BM25 can't pin the one rule.
- Some "misses" are arguably gold-answer calibration, not retrieval bugs
  (e.g. is retrieving 603.7d an acceptable answer for "what is a delayed
  triggered ability?"). Flagged for Jon's ruling.

## 2026-07-21 — final curated baseline

- After the gold audit (dropped non-answering ids, tagged true interactions
  match=all), the honest BM25 baseline settled at recall@1=22%, recall@5=38%,
  recall@10=50%. Lower than the first pass (44%) on purpose -- the drop is
  cleaner gold, not worse retrieval. This 38% is the real "move from" number.

## 2026-07-21 — Jon overrode q029 tagging

- I kept q029 ("when are lore counters put on sagas?") as match=any,
  reasoning each of the two times was independently a valid "when." Jon:
  "q029 does NOT get fully answered by either of those rules individually,
  and needs both, as both of those are times that counters get put on it."
  Right -- it's an enumeration ("give me all the times"), not "name a time."
  Retagged all. My "each is a valid when" frame was the wrong lens.

## 2026-07-21 — rigorous any-audit, curated baseline

- Audited all 24 any-questions against "one rule must completely answer."
  Revised 6 (q008 reword+all, q010 drop weak id, q012 rule-over-glossary,
  q015 ->all, q023 cut, q019 keep). Baseline now recall@5=32% over 31 Qs.
- q012 was a real surprise: the glossary ("a creature or planeswalker dies")
  contradicts rule 700.4 ("dies means put into graveyard from battlefield,"
  no type restriction). Trusting the rule -> non-creature artifacts DO die.

## 2026-07-21 — Phase B: embeddings nearly double recall@5

- recall@5: BM25 32% -> voyage-4 55% -> voyage-4-large 65%. voyage-4-large
  wins clean. q007 "do you cast lands?" flipped miss->hit exactly as I
  predicted (rule says "played" not "cast").
- Surprise: q001 "phasing back in trigger ETB?" -- BM25 HITS, both vector
  models MISS. Keyword still wins sometimes. That's the argument for hybrid,
  handed to me by the data instead of theory.
- The 152ms/query is the Voyage query-embed API call, NOT the search. Brute-
  force cosine over 3,617 vectors is sub-ms. "No vector DB" holds.

## 2026-07-21 — Phase C: hybrid didn't help (the useful surprise)

- Expected hybrid to beat vector. It didn't: recall@5 BM25 32%, vector 65%,
  hybrid-RRF 48%, hybrid-wt0.5 55%. Fusion DILUTED the strong vector signal
  because BM25 is too weak here. Alpha sweep: more vector weight = better,
  converging to pure vector.
- Pool nuance: at k=20 hybrid-wt (87%) > vector (81%), but at k=50 vector
  (90%) wins. So pure vector, pool 50, is the best first stage for reranking.
- Good story: measurement rejecting complexity I added. Knowing when NOT to
  ship a component.

## 2026-07-21 — Phase D rerank + a reproducibility catch

- Caught a real bug: voyage-4-large recall@5 read 65% then 61% on identical
  runs. Voyage query embeddings aren't perfectly deterministic. Froze query
  embeddings to disk -> two runs now byte-identical (rerank included). This is
  exactly the eval-reproducibility thing AI-103 harps on, hit for real.
- Rerank: rerank-2.5 best recall@5 (68%) but HURTS @1 (26) and @10 (71 vs 81).
  Not a free win. If we feed the generator ~10 chunks, pure vector (81% @10)
  beats reranked. Embeddings were the real lever (32 -> 65); rerank is polish.

## 2026-07-21 — answer accuracy 93.5%, zero hallucinations

- Jon graded 31 answers vs cited rules: 29 correct, 1 partial, 1 wrong = 93.5%.
- Best part: NO hallucinations. The one "wrong" (q016) was an honest DECLINE,
  not a fabrication. Checked why: its top-10 was all cost-mechanics rules;
  neither answering rule (117.3c/601.2h) was retrieved, so it declined for
  lack of the answer. Same q016 that missed in the RETRIEVAL eval -- the two
  evals caught the same failure from both ends. Retrieval fix -> answer fix.
- q014 partial: had 506.1 + multiplayer 802.5 but answered two-player only.

## 2026-07-21 — #2 re-grade: fixes held, no regressions

- After the prompt+k fixes, re-graded: still 29 correct / 1 partial (q014) /
  1 wrong (q016) = 93.5%. The reworded 27 all stayed correct -- NO regressions
  from the general prompt change. q001/q020 clearer; q014 now covers
  multiplayer (Jon keeps it partial for remaining nuance: defending player(s),
  no-attacker case, declare-blockers priority). q016 still declines -> #3.
- Captured Jon's Scryfall reqs in docs/scryfall-notes.md: @-triggered
  autocomplete, nicknames (Gary/Steve/Tim), per-card rulings via rulings_uri,
  and reference-by-oracle_id / display-by-name for the friend's app.

## 2026-07-21 — #3a spike: half my plan died in two API calls

- Spiked q016 before building the rewriting layer. 601.2h went 108 -> 2. But
  117.3c went 198 -> 69 at best, and most rewrites made it WORSE (300, 291).
  Read the chunk: 117.3c is about who RETAINS priority, never mentions costs
  or responding. It answers q016 only by deduction (pair it with "casting is
  atomic"). Embeddings match meaning, not inference -- no rewrite reaches it.
- Second thing I got wrong: I'd argued fusing the raw question in alongside
  its rewrites was a free safety net. It LOST in every arm -- RRF was worse
  than the best single rewrite every time (601.2h: 2 alone -> 10 fused). The
  original is a weak query; fusing it dilutes. That is the Phase C hybrid
  finding restated, and I walked into it AFTER writing that entry myself.
- Jon's call: build the layer on the 601.2h result, re-audit q016's gold
  separately, don't let one questionable label veto a working layer.

- (Jon) why re-audit the gold instead of leaving it frozen:
  i want to see what different rules are pulled now that we are rewriting the
  query. changing the wording could change the rules called significantly.
- (Jon) on spiking before building:
  i bet this saved me a lot of time and money. we love to see it. test your
  ideas before you implement them to see if they'll actually help or not.

## 2026-07-21 — my reproducibility fix wasn't reproducible

- Same prompt, same model, same 31 questions: rw1-haiku recall@5 came back
  68%, then 71%, then 77% across clean re-runs. The FAILING questions changed
  too (q025 one run, q003+q030 another). I'd been quoting 77% as a fact and
  building a story on it. It was one lucky draw.
- Cause: I "froze query embeddings for reproducibility" back in Phase B and
  thought retrieval was deterministic. But rewriting makes the query STRING
  itself LLM output -- a random draw. Freezing the embedding of a string that
  changes every run does nothing. I froze the wrong layer and didn't notice
  because the cache made each single run look stable.
- Confirmed by just calling Haiku 3x on one question: three totally different
  rewrites. Obvious in hindsight.
- temperature=0 (Haiku allows it; Sonnet-5 would 400) cut the swing from ~9pts
  to ~1 question. 5-draw noise floor: mean 69.7%, stdev 1.6%, range 67.7-71.0.
  21 questions always hit, 9 always miss, 1 flaky.
- Real lesson: every "improvement" I chased under 2 questions this session --
  v1-vs-v2 prompt, the regressions I kept fixing -- was inside the noise. I was
  tuning against dice and reading the flips as signal. Parking the prompt
  micro-tuning; the honest #3a number is ~70%, not 77%.

## 2026-07-21 — split the 601.2 family to help q016, split HURT q016

- The embed_text/text split was aimed at the 601.2 family blurring together
  (0.90 cosine, near-duplicate vectors). It worked: 0.90 -> 0.63. And the whole
  base recall went up (pure vector @20 81 -> 87, rw1-haiku @10 81 -> 87).
- Then I checked q016 -- the exact question I did this FOR. 601.2i went 16 -> 84.
  WORSE. Isolated it clean (same rewrite, old index vs new index): 16 vs 84, so
  it's the chunking, not rewrite noise.
- The preamble I stripped was HELPING q016. The query is about the casting
  process in general, and the preamble is full of casting-process words.
  Stripping it separated the siblings but killed the topical match. I removed
  the thing that was making it work.
- Saving grace: rank 16 was already a miss (k=15 window), so I didn't break a
  pass, just moved a miss farther out. And 84 is honestly clearer -- q016 is a
  multi-hop problem, not a chunking one. Kept the split; the base gains are real
  and q016 was never passing.

## 2026-07-21 — answer eval: I predicted q016 would decline. it answered, correctly.

- I was SURE q016 would decline now (its gold 601.2i sits at rank 84, way
  outside the top 15 the generator sees). Ran the answer eval. It answered "No"
  -- correctly -- citing 601.2g and 601.2h instead. Not the gold rule.
- Jon's point: 601.2a-h are ALL the steps of casting one spell. You don't need
  the exact rule I picked; several of the casting steps let you infer "you're
  mid-cast, nobody can respond." My [601.2i]-only gold was too narrow. Broadened
  it to the casting-process rules.
- The real lesson: retrieval said MISS, the answer was RIGHT. recall@k against
  one gold rule can't see a question that's answerable multiple ways. Textbook
  RAG-eval gap and I walked right into it by trusting my own too-narrow gold.
- Also caught: 3 answers (q005 q020 q031) were confident but had EMPTY citations
  -- refs were in the prose, not the field, or missing entirely. That's the
  groundedness signal leaking. Fixed the prompt (every ref must hit the field;
  answered=true means citations can't be empty). 3 -> 0, no new declines.
- Built Jon a grading UI (build_grading_ui.py -> grading.html) so he can grade
  the 31 the way he did before.
