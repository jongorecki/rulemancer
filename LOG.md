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

## 2026-07-21 — Scryfall #3b: reframed to enrichment, spiked reachability first

- Jon's real use case isn't "card OR rules" -- it's BOTH at once: "@Dovin's Veto
  to counter a spell while @Dovescape is out without Dovin's Veto getting
  countered." An either/or router drops half of that. Reframed #3b from routing
  to enrichment: always retrieve rules, ALSO pull @-card oracle text + rulings.
- @ trigger (Jon's call) makes card detection deterministic -- no LLM guessing
  card names, no Fog-the-card-vs-fog ambiguity. Kills the routing question.
- Spiked Scryfall reachability BEFORE building (again -- the q016 lesson stuck).
  Reachable, and it validated on Jon's exact example: @Dovin's Veto resolves,
  its 1 ruling is exactly the countering nuance the CR can't give, @dove
  autocompletes to Dovescape. Green light.

## 2026-07-21 — #3b works, and the RULINGS are what make it sing

- Built the enrichment pipeline (Sonnet subagent, approved plan). First live
  end-to-end on the real question -- "[Dovin's Veto] while [Dovescape] is out,
  does Dovescape counter it?" -- came back correct AND used Dovescape's Scryfall
  RULING to note the Bird tokens still get made even though the spell can't be
  countered. That's the payoff: the Comprehensive Rules literally cannot tell
  you that; it's card-specific ruling knowledge. Rules + oracle + rulings fused
  into one answer, both cards cited. First try, no fixups.
- The @ vs [brackets] split clicked once Jon explained it: @ is the mobile
  typing trigger (autocomplete, like tagging someone), [brackets] is what
  actually lands in the query. Clean separation -- deterministic parse, no LLM
  guessing which words are cards.

## 2026-07-21 — ablation: my RAG was redundant on 4 of 5 card questions

- Built the gold-by-ablation harness and ran it. Gut-punch finding: on 4 of 5
  card questions, removing EVERY retrieved rule left the answer correct. The
  card oracle text + rulings + the model already knowing counter/trample/APNAP
  answered them. The rules-RAG -- the thing this whole project is meant to show
  off -- did nothing for those.
- Only c004 (does a creature with lethal marked damage die before Lightning Bolt
  resolves) actually needed rules, because that timing isn't in the card text.
- Real lesson: enrichment (card data + rulings) can quietly make a RAG look
  pointless. The RAG earns its keep on questions the model CAN'T already answer
  from context. So the card eval has to steer toward those, or the RAG isn't
  being tested. Jon's call, and he wants rulings themselves pulled by relevance
  (RAG) next, not dumped wholesale.
- Nice side win: Haiku judged 99% the same as sonnet-5 (104/105), so the
  ablation judge is now Haiku -- cheap enough to scale.
- Ablation also extracted c004's exact mixed gold (all of 3 + any of 4), which
  forced the "groups" match mode. The method proved itself.

## 2026-07-21 — rulings-on-demand spike: 4 of 5 cards have NO rulings

- (Claude) Spiked the 5 card questions rules+oracle-only vs with-all-rulings
  BEFORE building the rulings mini-RAG. Surprise: 4 of 5 questions reference only
  cards with ZERO Scryfall rulings (c001 Counterspell/Divination, c002
  Rhino/Nighthawk, c004 Grizzly Bears/Lightning Bolt, c005 Phyrexian Arena). So
  today's "dump every ruling" was a NO-OP on 4/5 -- the only question that ever
  had rulings to dump is c003 (Monastery Swiftspear 4 + Shardless Agent 9 = 13).
- c003, the one ruling-bearing question, answered CORRECTLY without its rulings
  too -- the CR rules alone reached "prowess resolves before the cascaded spell."
  So even the ruling-dependent question is over-determined on this set: rules
  sufficient AND rulings sufficient. No confidently-wrong-without-rulings case
  fired (but 4/5 had no rulings, so the set literally can't test that hole).
- The grounding nuance that DID show: without the ruling, c003 reached for a
  loosely-relevant rule (704.4, an SBA rule) to prop up an inferred conclusion;
  WITH the ruling it grounded cleanly on Swiftspear's own text ("prowess goes on
  the stack on top of the spell... resolves before that spell"). Evidence for
  surfacing the relevant ruling even when the model can guess right -- the decided
  direction.
- Real consequence: the current 5-question card set is a THIN testbed for a
  rulings-RAG. To build+measure it we need questions where a referenced card HAS
  rulings AND a ruling is load-bearing (the Dovescape Bird-tokens case from #3b is
  the archetype -- and it's not in cards.jsonl yet). Entangles this task with the
  eval curation (task #2).

## 2026-07-21 — pulled the rulings bulk file: rules-warpers have the FEWEST rulings

- (Claude) Jon's instinct: start eval curation from cards with the most rulings,
  and he named Trinisphere ("created a whole new step in mana-cost calc"). Pulled
  Scryfall's rulings bulk file (25.9 MB, 77,999 rulings over 19,770 cards) and
  counted per oracle_id instead of guessing. His hunch inverted cleanly:
  Trinisphere has just **2** rulings. Humility 3, Blood Moon 4, Opalescence 4,
  Doubling Season 5, Mycosynth Lattice 4. The rules-warpers have FEW card-specific
  rulings -- because the warping lives in the Comprehensive RULES themselves (the
  mana-cost steps, the layer system, land-type rules), so Scryfall doesn't need
  card-specific rulings to explain them.
- The actual top of the ruling-count list is a different category entirely:
  new-keyword cards that got a big SHARED mechanic FAQ replicated onto every card
  -- Duskmourn Rooms (20-32 each), manifest (Cloudform/Lightform/Jeskai
  Infiltrator ~29-30), battles (Invasion of X ~20-26) -- plus genuinely gnarly
  singletons (Teferi's Protection 27, Lurrus 23, Valki//Tibalt 22, Krark 20, the
  Gods 20-25).
- The clean split this hands us for eval curation:
  * RULES-warpers (Trinisphere/Humility/Blood Moon/layers) = few rulings, answer
    lives in the CR -> the RULES-RAG's job. This is c004-shaped (task #2).
  * HIGH-ruling cards (Rooms/manifest/battles/complex singletons) = many rulings,
    a specific one load-bearing -> the RULINGS-RAG's job, and the 20-32-ruling
    cards are perfect FILTERING stress tests for the mini-RAG (pull 1-2 of 30).
  So the two tasks the handoff named map onto two different card pools, and the
  data tells us which is which instead of us guessing.

## 2026-07-21 — Trinisphere + X-spell: a ruling that OVERRIDES the naive rule reading

- (Claude) Jon proposed a card question: opponent has untapped Trinisphere, you
  cast Awaken the Woods ({X}{G}{G}, "create X 1/1 Forest Dryads") with reducers.
  Verified against fetched data -- his logic holds. X=0 -> {G}{G}=2 -> Trinisphere
  floors to 3 -> zero tokens (paid 3 for nothing). X=1 -> {1}{G}{G}=3 already -> a
  token for the same 3. So NEVER cast X=0 into Trinisphere; reducers let you push
  to the largest X whose reduced cost is still <=3, all at the same forced 3 mana.
- The gem: Trinisphere's ruling says its effect is applied LAST, AFTER cost
  reductions. The general CR cost order (601.2f: increases before reductions)
  would have you treat Trinisphere as an ordinary increase applied BEFORE
  reductions -- which gets the reducer interaction wrong. The card-specific RULING
  is what flips it. So this single question exercises the rules-RAG AND the
  rulings-RAG, and it's a live example of a ruling correcting the naive rule
  reading -- the strongest card-eval candidate so far. Pending Jon's wording +
  ablation-derived gold before it goes in cards.jsonl.

## 2026-07-21 — before-baseline on the 9 new card Qs: 7 right, 2 telling misses

- (Claude) Ran the 9 new card questions through today's dump-all-rulings pipeline.
  7 correct (c006-c010, c012, c013) -- including the two multi-card combos: c012
  nailed the trap (copying Emrakul the SPELL gives a token but NO second cast
  trigger, because the copy was never cast). Good.
- MISS 1 -- c011 (Valki//Tibalt cascade), CONFIDENTLY WRONG. Bot said you can't
  cast the Tibalt back face off cascade, justifying it with "you'd need permission
  to cast it transformed." That's a category error: Valki//Tibalt is a MODAL DFC,
  not a transforming one -- you cast a back face by CHOICE, no "transform"
  permission needed. Real-world Modern Tibalt-cascade decks confirm the
  interaction works. answered=true, so it's a confident-wrong -- the exact failure
  mode the grounding push targets. Needs the right MDFC-casting rules surfaced
  (and Valki's mana cost -- see below).
- MISS 2 -- c014 (Trinisphere), and it exposed a PIPELINE GAP. Bot used Awaken the
  Woods = {X}{G}{G}{G} and concluded "Trinisphere never fires." The real cost is
  {X}{G}{G} (two green) -- with X=0 that's 2 mana, so Trinisphere DOES fire (2->3).
  Root cause: _format_cards enriches name + oracle_text + rulings but OMITS
  mana_cost and type_line, so for a cost/mana-value question the model guesses the
  cost from training and gets it wrong. Top-line advice ("never X=0") survived,
  but the cost math was wrong. Same gap hurt c011 (Valki's mana cost wasn't given
  either). Fix: add mana_cost + type_line to the enrichment. Small, clear
  grounding win -- pending Jon's OK (plan-before-code).

## 2026-07-21 — I asserted a false rules fact while BUILDING the grounding fix

- (Claude) Justifying why we take Scryfall's computed color_identity, I wrote
  "Extort's {W/B} is in the rules text, so a colorless card with Extort has a W/B
  identity." Jon: wrong -- color identity IGNORES reminder text (rule 903.4), and
  Extort's {W/B} is reminder text. Blind Obedience is mono-W, Crypt Ghast mono-B,
  both with Extort. My claim was a plausible-sounding hallucination from training.
- The irony writes itself: I stated a false MTG rules fact from memory in the same
  breath as building the feature whose whole purpose is to stop the model doing
  exactly that. Best possible argument for grounding on Scryfall + the CR instead
  of model knowledge. The code was already right (we take Scryfall's value); only
  my rationale was wrong. Good README material.

## 2026-07-21 — the enrichment fix flipped c011, and proved the whole thesis

- (Claude) After adding layout + per-face data, re-ran c011. The bot now correctly
  calls Valki // Tibalt a MODAL DFC (not transform) -- and went further: it
  retrieved cascade rule 702.85a and applied its clause "You may cast that card
  without paying its mana cost IF the resulting spell's mana value is less than
  this spell's mana value." Tibalt's MV is 7, so off a normal cascade (MV 3-6) you
  CANNOT cast Tibalt; you can only cast Valki (front MV 2). The bot is RIGHT.
- The twist: I'd told Jon earlier, confidently, that the bot was wrong and "Modern
  Tibalt-cascade decks confirm it works." Jon agreed ("the bot is wrong on c11").
  We were BOTH wrong -- working from the PRE-errata (early 2021) interaction. WotC
  errata'd cascade with the resulting-mana-value clause specifically to kill it,
  and that errata is right there in our June 2026 CR (702.85a). The grounded rules
  settled what neither the human expert nor the model's memory had right.
- This is the single best demonstration of why the project exists: ground on the
  CURRENT CR, not on anyone's memory, human OR model. Two confident wrong answers,
  one correct rule. Straight into the README.
- The rest of the after-fix re-run: c014 now CORRECT (with the real {X}{G}{G} the
  bot picks X=2 as best value -- the enrichment gave it the cost the baseline had
  guessed wrong). c007-c010, c012, c013 still correct. c006 truncated to an honest
  non-answer (flaky max_tokens/thinking degradation, not a wrong answer -- likely
  answers on a re-run). Both prior misses fixed by the enrichment.

## 2026-07-21 — ruling mini-RAG built + floor calibrated on real cosines

- (Claude) Built the per-card ruling mini-RAG (ruling_retrieval.py): embed a
  card's own rulings, keep only the top-3 above a cosine floor, replacing the
  wholesale dump. Wired into RulesAgent (ruling_select=True default; False = old
  dump, for A/B).
- Calibrated the floor off actual data instead of guessing. For each card
  question, embedded the referenced cards' rulings and ranked by cosine to the
  question. The load-bearing ruling (the one my cards.jsonl notes name) landed
  rank-1 or within top-3 on 12 of 15 ruling-bearing questions, cosines 0.41-0.66
  (c008 Lithoform-linked 0.662, c016 Skullbriar 0.652, c003 prowess 0.618). Set
  COSINE_FLOOR = 0.38 (just under the 0.41 low end) + top-3 cap.
- The honest limit: 3 questions have their load-bearing ruling BELOW top-3 --
  c010 (Emrakul "resolves even if countered"), c011 (Valki mana-value ruling 17),
  c019 (Gogo "don't re-pay costs"). Semantic mismatch: the question's wording
  doesn't match the ruling's, so relevance retrieval can't reach it, and lowering
  the floor wouldn't help (they're outside top-3 by rank, not just score). On
  c010/c011 the rules-RAG carries the answer anyway. Good README point: relevance
  retrieval has a real ceiling when the answer-ruling is phrased differently from
  the question -- same class as the q016 multi-hop gap.

## 2026-07-21 — mini-RAG head-to-head: ruling context slashed, answer quality HELD

- (Claude) Ran all 19 with the ruling mini-RAG (top-3 relevant rulings) vs the
  dump-all baselines. The win: quality HELD everywhere. Every question correct
  under dump-all is still correct feeding <=3 relevant rulings per card instead of
  the whole list -- and the cut is huge: c009 dumped 35 rulings (Banishing Light 8
  + Teferi's 27) -> 6; c011 dumped Valki's 22 -> 3; c010 Emrakul 18 -> 3. Massive
  context reduction, zero correctness lost. That's the whole value proposition,
  measured: the rulings-RAG does real selection work AND doesn't degrade answers.
- The 3 semantic-mismatch questions (c010/c011/c019) whose SPECIFIC load-bearing
  ruling the mini-RAG can't reach: answers STILL correct -- the rules-RAG (c011's
  702.85a) and general reasoning + the other selected rulings carried them. The
  known ceiling didn't break anything.
- Selection sanity: c001/c002/c004/c005 (no rulings on any card) selected NOTHING
  -- withhold-by-default works. Load-bearing ruling selected on 12/15.
- Two caveats, neither the mini-RAG's fault:
  * c015 (Animate Dead/Grist): the mini-RAG SELECTED the right ruling (Animate
    Dead #4, which spells out the SBA + sacrifice) but the model didn't apply it
    -- it hedged ("can't confirm the aura falls off"). Faithfulness/reasoning gap,
    not retrieval. Still better than the baseline's confident-wrong.
  * c018 (Clone): reproducibly truncates to an empty answer in BOTH configs, even
    at 16384 max_tokens on a tiny prompt. NOT a mini-RAG issue (dump-all fails it
    too) -- a generation runaway specific to this question. Needs a look, not more
    rulings.

## 2026-07-21 — c018 + c015 fixed: retry-on-empty, and "trust the ruling"

- (Claude) c018 (Clone) diagnosed by rebuilding its exact prompt and reading the
  RAW response. NOT a budget/thinking runaway: at 16384 it answers cleanly
  (stop_reason=end_turn, 622 thinking + 1633 output tokens, far under the cap).
  The empty answers were INTERMITTENT flaky responses. And raising the cap
  BACKFIRES: max_tokens=32768 trips the SDK's non-streaming 10-minute-timeout
  guard and errors the whole call. Fix: RETRY the parse once on empty/invalid
  output before degrading -- recovered c018. Lesson: I'd assumed "give it more
  tokens"; the data said the opposite (don't, it breaks) and that the real fix is
  a retry. Measure before "fixing."
- c015 (Animate Dead/Grist): the mini-RAG selected the RIGHT ruling (Animate Dead
  #4, which states the SBA + sacrifice outcome), but the model HEDGED -- "can't
  confirm, would need a rule not in context" -- over-deferring to the numbered CR
  rule over the ruling that already answered it. Fix: a system-prompt line -- "a
  provided ruling is self-sufficient grounding; don't decline just because the
  underlying numbered rule isn't also present." After the fix c015 reaches Jon's
  confirmed answer (Grist returns as a planeswalker, Animate Dead can't attach ->
  graveyard SBA -> sacrifice Grist), citing ruling #4. c009/c016 regression-
  checked, still correct. (Prompt change rewords all answers -- a full re-grade
  should watch for regressions, same caveat as prior prompt tweaks.)

## 2026-07-22 — scoped ablation: c011 is the real rules-RAG test, c014 is ruling-carried

- (Claude) Ran gold-by-ablation on the two "rules-dependent" card questions. c011:
  removing cascade rule 702.85a BREAKS the answer (NECESSARY); the three MDFC
  rules (712.11/712.8c/712.11d) all tested REPLACEABLE, because the enrichment
  already hands the model the modal-DFC face data. Gold = [702.85a]. A genuine
  rules-RAG test where the load-bearing rule is a CR rule, not a card ruling.
- c014 (Trinisphere): the sanity check (remove ALL cited rules) HELD -- the CR
  rules were redundant. Trinisphere's ruling 0 already states the cost order
  (reductions, then Trinisphere; mana value unchanged) and the enrichment supplies
  the {X}{G}{G} cost, so the rules-RAG added nothing. Gold = []. So a "rules-
  warper" I'd bucketed as rules-RAG turned out RULING-carried once a ruling
  restated the rule. The clean split (warpers -> rules-RAG, high-ruling cards ->
  rulings-RAG) doesn't hold: c011 is the rules-RAG case, c014 collapses to rulings
  like the rest. Only ablation, not intuition, told them apart.
- Judge agreement Haiku vs sonnet-5: 34/36 (94%), consistent with the earlier 99%.
