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
