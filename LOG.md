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
