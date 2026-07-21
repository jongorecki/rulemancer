# Decisions

Every non-obvious choice, logged as it's made. 5-10 lines each: what,
alternatives rejected, why, what would change your mind. This is interview
prep — write it in the moment, not reconstructed later.

Template:

```
## YYYY-MM-DD — <short title>

**What:** <the choice>
**Alternatives considered:** <what else was on the table>
**Why:** <the reasoning>
**What would change my mind:** <the condition that would flip this later>
```

---

## 2026-07-21 — Project scaffold, no OpenCode yet

**What:** Starting the build with Claude Code only. Repo skeleton matches the
build plan's target layout, in this existing `mtg-rules-bot` folder rather
than a newly-created `mtg-rules-agent` one.
**Alternatives considered:** Setting up OpenCode + OpenRouter first, per the
original plan's "install OpenCode, configure both keys" step.
**Why:** Jon wants to defer OpenRouter/model-rotation setup until later and
start writing code now. Model rotation for review is a stretch goal, not a
day-1 blocker.
**What would change my mind:** Once OpenCode/OpenRouter is set up, revisit the
"whoever writes doesn't review" rule — Claude Code has been both author and
only reviewer so far, which the plan explicitly warns against.

---

## 2026-07-21 — contracts.py field decisions

**What:** Six decisions locking down `contracts.py`:
1. Glossary gets its own `GlossaryEntry` class (`term`, `definitions`), not
   folded into `Rule`.
2. `Rule.text` excludes trailing `Example:` blocks — those live in
   `Rule.examples` instead.
3. `Rule.parent_chain` is a full audit trail for every rule, not just
   lettered subrules (e.g. plain rule "104.3" still records `["104"]`).
4. `Rule.section` is just the section name string (e.g. "Game Concepts"),
   no separate number field or lookup table.
5. `Rule.kind` is `Literal["rule", "subrule"]` only — "glossary" was cut
   since those rows are `GlossaryEntry` now, never `Rule`.
6. Cross-references ("see rule 201.3") stay as plain text wherever they
   appear — not resolved into links, not pulled into their own field.

**Alternatives considered:** Squashing glossary into `Rule` with `number`
repurposed to hold the term name; a fourth `kind` value for section
headers; a separate section-number field.

**Why:** Splitting glossary out lets it be labeled and displayed as a
different kind of result from a rule, even though a definition's "See rule
113" line still ties it back to one (that tie stays as plain text — nothing
structural needed to preserve it). The rest are all "don't build machinery
before something needs it" calls — no fields, tables, or extra `kind`
values for features that don't exist yet.

**What would change my mind:** If a real feature needs to query "everything
in section 7" or "jump straight to the rule a glossary term cites," that's
the point to add a section-number field or a structured cross-reference
field — not before.

---

## 2026-07-21 — Parser: finding the real body past the Contents page

**What:** The Contents page near the top of the CR file repeats the exact
same heading text ("1. Game Concepts," "Glossary," "Credits") that the real
sections use later. Searching for those headings from the top of the file
would stop at the Contents page's copy, not the real one. Fix: find the
first line that matches a full rule pattern (e.g. "100.1.") — that pattern
never appears on the Contents page, only in the real body — then walk
*backward* from there to the nearest section heading. That's guaranteed to
be the real "1. Game Concepts," since it's the one immediately before
actual rule text starts. "Glossary" and "Credits" are then searched for
starting from that point onward, past the Contents page entirely.

**Alternatives considered:** Hardcoding a line number or byte offset where
the real body starts. Counting a fixed number of "Contents"-like lines to
skip.

**Why:** Hardcoding a line number breaks the moment Wizards ships a new
revision with different pagination. Searching forward for a heading text
match breaks on the very first run, because the Contents page hits first.
Anchoring on "first thing that looks like an actual rule, then look
backward" survives revisions because rule numbering (100.1, 100.2, ...)
is structurally stable in a way page layout isn't.

**What would change my mind:** If a future CR revision ever puts a full
rule-shaped line inside the Contents page itself, this breaks — no
evidence that's ever happened, but it's the one assumption this approach
rests on.

**Measured (2026-07-21):** 3,151 rules parsed, 735 glossary entries, 44% of
rules under 30 words, 213 rules with at least one example. The 44% number
is what the chunking decision (Day 2) gets made from.

---

## 2026-07-21 — Chunking: label-like rules don't get their own chunk

**What:** The 44% "under 30 words" bucket isn't one kind of thing. Some are
short, complete, standalone sentences (e.g. `104.3f: "If a player would
both win and lose the game simultaneously, that player loses the game."`).
Others are bare labels with no independent meaning at all (e.g. `205.3:
"Subtypes"`, `701.49: "Venture into the Dungeon"`) that only make sense
together with the lettered subrules underneath them. Decision: a rule is
"label-like" if (a) it has subrules under it, (b) it's 6 words or fewer,
and (c) after stripping a trailing closing curly-quote or paren, it
doesn't end in `.`, `:`, or `?`. Label-like rules don't get their own
chunk — their (short) text becomes prepended parent-context on each of
their children's chunks instead. Every other rule gets its own chunk: its
own text, its immediate parent's text prepended, and any attached
`Example:` text appended.

**Alternatives considered:**
- Word count alone (<=4 words): zero false positives, but missed two real
  5-word labels ("Roll to Visit Your Attractions," "More Than Meets the
  Eye").
- Punctuation-ending alone (no word-count bound): fixed those two, but
  wrongly flagged two long, legitimate rules (602.1, 603.1) that happen to
  end with bracketed template notation instead of plain prose.
- Punctuation check counting "!" as a sentence-ender: wrongly excluded two
  more real labels ("For Mirrodin!", "Start Your Engines!") — flavor-named
  keywords that end in "!" without being sentences.
- Merging a whole rule family (base + all lettered subrules) into one
  chunk, always: rejected — families like 104.3 have 11 subrules, and
  cramming all of them into one chunk risks the embedding blurring across
  11 different situations, plus it loses per-subrule citation precision
  everywhere, not just for the ~270 pathological cases.

**Why:** Each single-signal version looked "robust" until checked against
the full 3,151-rule corpus, where it turned out to have a different blind
spot. The combined check — word count as a scope limiter, sentence-ending
punctuation as the actual decision within that scope, "!" excluded because
it's decorative here, not grammatical — was checked against every rule in
the file with zero known exceptions in either direction. Simpler versions
each had exactly 2 known misses; this one currently has none.

**What would change my mind:** If a future CR revision introduces a label
longer than 6 words, or a short legitimate rule that happens to end
without terminal punctuation, this heuristic will misclassify it. That's
an acceptable, documented gap for now — the fix is to read it off an
actual eval failure once the eval harness exists (days 3-5), not to keep
hardening this check against hypothetical future formatting no evidence
supports yet.

---

## 2026-07-21 — Child detection: parent_chain membership, not string prefix

**What:** Deciding whether rule A is a child of rule B (used for label
detection's "has children" test). Implemented as: B is a child of A if A
is in B's `parent_chain`. NOT as: B's number starts with A's number.

**Alternatives considered:** Naive string-prefix match
(`b.number.startswith(a.number)`), which is what the orchestrator's spec
originally called for.

**Why:** String-prefix has a false positive: `"118.10".startswith("118.1")`
is True, which would wrongly classify sibling rule 118.10 as a child of
118.1. `parent_chain` encodes the actual dotted hierarchy the parser
derived, so it's immune. This collision is NOT hypothetical — it fires on
52 rules in the current ruleset (every X.1 that has an X.10-or-higher
sibling: 106.1, 107.1, 111.1, 113.1, 118.1, etc.; rule 118 alone runs to
118.14). It happens not to change the final label count (269 either way)
only because none of those 52 affected rules are label-shaped — they're
all full sentences, so a phantom "has children" flag can't flip them into
labels. That's luck of this ruleset's content, not a property to rely on;
parent_chain is correct regardless. (Correction: an earlier draft of this
entry claimed no such collision existed in the current data — Jon caught
that by noticing rule 118 runs to 118.14, and the 52-rule count was then
measured.) Caught in two stages by human+model review, not by the
orchestrator's original spec — a live example of "whoever writes doesn't
review."

**What would change my mind:** Nothing foreseeable — parent_chain is
strictly more correct here at no extra cost, since the parser already
computes it.

**Measured (2026-07-21):** 3,151 rules + 735 glossary in -> 3,617 chunks
out (2,882 rule + 735 glossary); 269 rules dropped as label-like.

---

## 2026-07-21 — Golden test coverage expanded to all 9 sections + 700s verified

**What:** Added test_golden_sections.py: one structural test per section
2-9 (section name, kind, parent_chain, example count), a test that all
nine section names are present, and two exact-behavior tests for the
section-7 label mechanic (keyword "Cast" 701.5 produces no chunk; its
child 701.5a leads with "Cast" prepended). Suite: 25 -> 36 tests.

**Alternatives considered:** Exact full-text assertions on all breadth
cases (heavier, and the value there is "section is handled," which
structure proves); leaving coverage clustered in section 1 (the original
state — no evidence sections 2-9 were exercised at all).

**Why:** Breadth via structural assertions is robust and cheap; exact-text
is spent where subtle breakage actually bites (the label mechanic).
Parse golden tests assert "matches what's literally in the file" —
transcription, verifiable by re-reading the file — which is distinct from
"what counts as a correct ANSWER" (the eval question set, still
do-not-delegate, comes later).

**Verified (section 7, the label detector's stress test):** 1,518 rules in
section 7, 261 classified as labels (261 of the 269 total) — all clean
keyword names, e.g. Activate/Attach/Behold/Cast. Checked both failure
directions across the whole corpus: zero childless short keyword names
leaking through as false non-labels, and zero missed labels in the 7-9
word range (our <=6-word bound cuts off nothing real — longest actual
labels are 5 words). The label detector is sound on the section that
exercises it hardest.

**What would change my mind:** A future CR revision adding a keyword name
longer than 6 words would slip past the bound; caught then off an eval
failure, not hardened for speculatively now.
