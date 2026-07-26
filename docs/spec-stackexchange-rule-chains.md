# Spec — Stack Exchange as a source of rule-chain STRUCTURE, not gold

**Status: unruled.** Rule 0 applies — this is design only, nothing below is
built, no data was imported, no scraper was written.

**This doc supersedes a first draft that framed Stack Exchange (SE) as a gold
source.** Jon corrected that mid-task: SE will never supply an answer, a
verdict, or a reference answer for this project. Its value is narrower and
different — a disciplined SE answer walks an **ordered chain of Comprehensive
Rules (CR) citations** to reach its ruling, and that chain tells us **which CR
rules a question actually requires, and how they compose** (all required
together, or genuine independent alternatives). That composition question —
not "what's the right answer" — is exactly what this project's **gold**
already is: a set of rule ids plus a group structure (`gold`, `gold_groups`,
`match: any/all/groups` in `evals/questions.jsonl` and
`evals/questions_rulesguru150_v3.jsonl`), not prose. So SE is read here as a
source of **structure candidates**, never of truth, and never merged with
RulesGuru's answer gold, which stays certified-judge-authored and outranks
anything mined here (`docs/spec-cr-gold-mining.md` line 59).

## The hard filter, stated once, applied everywhere below

Two tests, both required. Fail either, the question is discarded — no lower
tier, no partial credit, no upvote-count substitute:

1. **The top-scored answer and the accepted (asker-marked-correct) answer must
   be the same answer.** If they differ, or if *no* answer is accepted at all,
   the question is out. Divergence or non-acceptance is a signal the community
   itself didn't settle the question, and unsettled material is worthless for
   this purpose.
2. **That one surviving answer must cite specific numbered CR rules** (e.g.
   `702.95c`, `605.1a`). Describing the rules in prose, linking the CR PDF, or
   gesturing at "the stack" doesn't count. A bare number does.

## 1. Where, and how much — carried over from the fitness investigation

MTG rules questions live under the **`magic-the-gathering`** tag (synonym
`mtg`) on **Board & Card Games Stack Exchange** (`boardgames.stackexchange.com`)
— there's no dedicated MTG site. Confirmed 2026-07-26 by rendering the tag
page directly (`web_fetch` refuses `stackexchange.com` domains in this
sandbox; every fact below came from a live browser render or a live API call,
not a guess):

- **5,232 questions, all-time**, printed on the tag page itself.
- **~5 new questions in the last 30 days** (`/tags/magic-the-gathering/
  topusers` tag-info panel) — a slow, low-volume tag, not a firehose.
- **0.1% unanswered, all-time** — almost everything gets *an* answer, which
  says nothing about whether it clears the two filters above.

## 2. Sample, and what survives the hard filter

**10 questions read in full**, sampled across the highest-voted-of-all-time
list, the newest (July 2026) list, and two more for contrast — plus ~20
titles skimmed for context. For each, `is_accepted` and `score` per answer
were pulled straight from the **Stack Exchange API** (`api.stackexchange.com/
2.3/questions/{ids}/answers`, `filter=!9YdnSMKKT`, fetched 2026-07-26) rather
than eyeballed off the rendered page, so acceptance status is exact, not
inferred from which answer sorts to the top visually.

| question | top score | accepted? | top == accepted? | cites numbered CR rule? | **survives both filters** |
|---|---:|---|---|---|---|
| [Player loses in multiplayer](https://boardgames.stackexchange.com/questions/4749) (2011) | 72 | yes | **yes** | yes — 800.4a, 800.4c, 110.5a, 303.4c | **YES** |
| [Sleight of Mind / "colorless"](https://boardgames.stackexchange.com/questions/64569) (2026) | 6 | yes | **yes** (only answer) | yes — 105.4 | **YES** |
| [Living Metal + Coin of Mastery + Sunburst](https://boardgames.stackexchange.com/questions/64560) (2026) | 3 | yes | **yes** (only answer) | yes — 614.1c, 614.12, 702.161a, 702.44a | **YES** |
| [Optimus Prime + Phyrexian Metamorph cloning](https://boardgames.stackexchange.com/questions/64547) (2026) | 4 | yes | **yes** (only answer) | yes — 712.14a | **YES** |
| [Choice that doesn't matter until it does](https://boardgames.stackexchange.com/questions/64544) (2026) | 4 | yes | **yes** (only answer) | yes — 613.1f, 613.3 | **YES** |
| [Which player specifies physical card attributes](https://boardgames.stackexchange.com/questions/64566) (2026) | 3 | **no** | no — nobody accepted the only answer | no | no |
| [Unlimited pump loop, 2 Nantuko Shades](https://boardgames.stackexchange.com/questions/14437) (2014) | 20 (of 7 answers) | **no answer accepted, at all** | no | yes, heavily — but disputed and one number (716.3) since renumbered to 719.3 *within the thread itself* | no |
| [Tap opponent's creatures before attack](https://boardgames.stackexchange.com/questions/473) (2010) | 57 | yes | yes | **no** — describes turn structure in prose, no rule number anywhere | no |
| [Names for color combinations](https://boardgames.stackexchange.com/questions/11550) (2013) | 233 | yes | yes | no — not a rules question | no |
| [What beats Photon, Living Light](https://boardgames.stackexchange.com/questions/64542) (2026) | 2 | yes | yes | no — deckbuilding/card-pool question | no |

**Result: 5 of 10 survive both filters (50%).** Citation rate alone (any
numbered CR rule in any answer, regardless of acceptance) was **6/10 (60%)**
— the one question that drops out between those two numbers is exactly the
case the filter is designed to catch: **Q14437 has the tag's heaviest CR
citation of the whole sample and still fails**, because its 7 competing
answers were never reconciled to one accepted answer. That's the clearest
possible demonstration that citation volume and citation *authority* are
different things, and that the hard filter is doing real work, not just
paperwork.

One more concentration worth naming: of the 5 survivors, **3 are the only
answer their question ever received**, all authored by `murgatroid99` — a
site moderator whose public bio says *"I primarily work on gRPC"*, no stated
judge credential. That's not disqualifying under Jon's filter (which tests the
answer's structure, not the answerer's credentials), but it means a pilot's
usable yield leans heavily on a small number of disciplined contributors
answering solo, not a broad community consensus.

## 3. Do the surviving chains look conjunctive enough to matter?

This is the actual point of the exercise, so it's worth walking each survivor
by hand rather than just counting citations:

| question | chain | shape |
|---|---|---|
| Q64560 (Living Metal) | 614.1c (what counts as a replacement effect) → 614.12 (how to determine which apply, and in what state) → 702.161a (Living Metal's actual definition) → 702.44a (Sunburst's actual definition, which explicitly says to ignore type-changing effects) | **genuinely conjunctive, 4 rules.** Drop any one and the conclusion doesn't follow — e.g. without 702.44a's "ignoring type-changing effects" clause, the answer would wrongly give +1/+1 counters instead of charge counters. |
| Q64544 (choice doesn't matter) | 613.1f (layer 6 covers ability-adding/removing) + 613.3 (apply in timestamp order within a layer, referencing 613.7/613.8 for dependency) | **conjunctive, 2 rules working together** — 613.1f alone doesn't establish the *order*; 613.3 alone doesn't establish *what's in* layer 6. |
| Q4749 (player leaves multiplayer) | 800.4a / 800.4c / 110.5a / 303.4c | **not one chain** — four *independent* single-rule citations, one per sub-question. Useful as a worked example of "one rule fully answers one narrow question" but not an OR-group analog. |
| Q64569 (Sleight of Mind) | 105.4 alone | degenerate, single rule. |
| Q64547 (Optimus Prime cloning) | 712.14a alone | degenerate, single rule. |

So of 5 survivors, **2 are clean multi-rule conjunctive chains** (2/10 of the
full sample), 1 is a bundle of independent single-rule answers, and 2 are
single-rule degenerate cases. That's a thin yield per 10 questions pulled —
consistent with the tag's low overall volume (§1) — and says a pilot aimed at
accumulating conjunctive-chain examples would need to pull considerably more
than 10–50 questions to get a useful count of them, not just of "passes the
filter" questions generally.

## 4. Why this is worth doing anyway — the two problems it's aimed at

**(a) The OR-group defect.** `docs/results-orgroup-repass.md` (written this
session) re-graded all 105 multi-member `gold_groups` in `evals/
questions_rulesguru150_v3.jsonl` against the actual CR text and found:

| category | groups |
|---|---:|
| (a) legitimate OR — every member independently sufficient | 26 |
| (b) mis-encoded conjunction — a required step wrongly merged as an alternative | **54** |
| (c) mixed/unclear — needs Jon's judgment | **25** |

Category (b) is precisely the failure mode Q64560 and Q64544 above are clean
positive examples of avoiding: an SE answer that explicitly says "*first*
614.1c and 614.12 establish X, *then* 702.161a establishes Y, *then* 702.44a's
exception overrides it" is stating the conjunctive structure in plain
language, which is exactly the information the miner got wrong 54 times.
**Whether SE chains can help adjudicate the 25 category-(c) groups
specifically is not established by this sample** — that would require
checking, per flagged `rg` id, whether a qualifying SE answer exists covering
the *same rule pairing*, which is a per-item cross-reference this task didn't
do (it would mean opening `questions_rulesguru150_v3.jsonl`'s actual rows,
out of scope for a design doc, and not guaranteed to find a match for any
given pairing given the tag's low volume). What this sample *does* establish
is that the pattern exists in the wild and is detectable by the same
top==accepted plus numbered-citation filter — so cross-referencing the 25 is
a plausible, checkable next step, not a promise of resolution.

**(b) Second-hop retrieval (`rg241`).** Per `docs/HANDOFF-development.md`'s
live queue: a correct derivation can require CR rules that are already
indexed but whose wording bears no surface resemblance to the question, so
no amount of question-side rewriting reaches them. Q64560's chain is a
worked example of exactly this: nothing in "would Optimus Prime enter with
+1/+1 counters" surface-resembles rule **702.44a** (Sunburst's definition,
two hops away from the question's own vocabulary of "Living Metal" and "Coin
of Mastery"). A corpus of validated SE chains is, structurally, a corpus of
worked examples of which rules sit 2–3 hops from a question's surface
wording — useful as qualitative evidence for where second-hop retrieval needs
to reach, though turning that into a *retrieval* fix is a separate, later
step this spec doesn't design.

## 5. Validation before anything touches the project

A chain surviving §2's hard filter is a **candidate**, never auto-accepted:

1. **Cross-check every cited rule number against the repo's own CR**,
   `data/raw/MagicCompRules 20260619.txt`. A number that doesn't resolve, or
   resolves to materially different text than the SE answer quotes, is
   flagged — never silently "corrected" by rewriting the SE answer's words as
   if the answerer had said something they didn't.
2. **Cross-check against existing RulesGuru gold where the question
   overlaps** — if a mined chain's rule set conflicts with an existing
   `gold`/`gold_groups` entry for a question covering the same interaction,
   RulesGuru's entry wins outright, per the standing ruling; the SE chain is
   discarded or logged as a disagreement for Jon to see, never used to
   override it.
3. **Lands in front of Jon as a proposal, not a merge.** Same posture this
   repo already uses for `docs/spec-cr-gold-mining.md`'s mined `gold` field —
   proposed, reviewed, never auto-applied at the "accepted without individual
   review" tier that spec grants *only* to rows already anchored to a
   judge-authored answer. SE chains have no such anchor, so they don't
   inherit that shortcut.

## 6. Rules drift — a bigger risk here than for RulesGuru, and content has to be checked even when the number resolves

RulesGuru's answers are dated to when RulesGuru wrote them, generally close to
current rules. SE questions span **2010 to 2026** in this sample alone, and a
number that still exists in the current CR is **not evidence the rule is
unchanged** — the id can survive while the text underneath it is rewritten, or
gets reused for an entirely unrelated mechanic later. That's a real,
`check_cr_update.py`-recognized class (`edited`), distinct from `renumbered`
and `deleted`, and it's the most dangerous one because it *looks* clean: the
citation resolves, so a naive resolver would accept it silently.

### 6.1 The four-way resolution outcome

Every harvested citation gets one of four outcomes — never a silent pass on
"the number resolved":

1. **RESOLVED-BY-NUMBER** — the cited number exists in the current CR *and*
   its current text agrees (after `normalize()`-style cleanup) with what the
   SE answer quotes or paraphrases. Highest confidence; used as-is.
2. **RESOLVED-BY-NUMBER, CONTENT DISAGREES** — the number exists, but its
   current text is materially different from what the SE answer attributes to
   it. **This is a flag, not a pass.** The rule was edited (or, as found
   below, the number was recycled for an unrelated later mechanic) since the
   SE answer was written. A chain containing one of these is not auto-dropped
   wholesale — the *other* citations in the same chain may still be fine — but
   the disagreeing step is pulled and either re-resolved by content (outcome
   3) or the whole chain is held for Jon if re-resolution fails, exactly like
   an unresolved citation. It is never left in place as if the number were
   sufficient on its own.
3. **RESOLVED-BY-CONTENT** — the number failed to resolve (or resolved to
   disagreeing content per #2), but the SE answer's quoted text matches a
   *different* current rule closely enough to identify it. Recorded with the
   old number, the new number, and the matched text as evidence — auditable,
   never silent.
4. **UNRESOLVED** — no confident match by number or content. Dropped, and
   counted, so the loss rate is known rather than invisible.

### 6.2 Verified on this session's own sample — not hypothetical

Every rule number cited by the 5 filter-surviving questions (§2) was checked
directly against `data/raw/MagicCompRules 20260619.txt` this session (`Grep`,
not eyeballed):

| citation | outcome | evidence |
|---|---|---|
| 105.4, 614.1c, 702.44a, 702.161a, 712.14a, 613.1f, 613.3, 303.4c | **RESOLVED-BY-NUMBER** | text at that number in the current CR matches what the SE answer quoted, verbatim modulo curly-quote/whitespace differences |
| 800.4a | resolves by number; full text not diffed character-by-character in this pass (output truncation) — treated as unconfirmed rather than asserted clean |
| **800.4c** | **RESOLVED-BY-NUMBER, CONTENT DISAGREES** | the number still exists, but today it reads *"If an effect that gives a player still in the game control of an object ends… the object is exiled…"* — a completely different rule (control-effect-ending) than what Q4749's 2011 answer quoted (*"If an object that would be owned by a player who has left the game would be created in any zone, it isn't created…"*). The quoted content is still in the current CR, verbatim — just at **800.4d** now (confirmed by direct grep). This is a live, real example of exactly the dangerous case: naive number-only resolution would have silently attached the wrong current rule. |
| **110.5a** | **RESOLVED-BY-NUMBER, CONTENT DISAGREES** | today reads *"Status is not a characteristic…"* — unrelated to what Q4749 quoted (*"a token is both owned and controlled by the player under whose control it entered the battlefield"*). This session did not locate the token-ownership rule's new home; it's a genuine open UNRESOLVED case pending a content search, not something to guess at. |
| **614.12** (the general rule, no letter) | effectively **UNRESOLVED-NOT-FOUND at that identity** | the current CR only has `614.12a`/`614.12b` as sub-lettered rules, with different content (choice-timing and cost-payability, not "check characteristics as it would exist on the battlefield" — the concept Q64560 quoted). A direct phrase search for the quoted sentence found no match anywhere in the current CR. |

**So of the 12 individual citations across the 5 survivors: 8 confirmed
RESOLVED-BY-NUMBER cleanly, 1 resolves but is unconfirmed on content (800.4a),
2 are the dangerous RESOLVED-BY-NUMBER-DISAGREES case (800.4c, 110.5a), and 1
doesn't resolve at its cited identity at all (614.12).** That's roughly a
quarter of citations in a *passing* sample needing content-level attention —
number-only resolution would have been wrong or incomplete on 3 of 12 (25%)
citations in material that already cleared the top-answer-equals-accepted and
has-a-citation bar. This is a real rate, not a worst case invented for effect.

**Two worked RESOLVED-BY-CONTENT successes, from the sample that failed the
hard filter (Q14437) but is instructive on method:**

- The "fragmented loop" rule Q14437 cites as **716.3**, with a later answer in
  the same thread claiming it moved to **719.3** — **neither is its current
  home.** Direct grep against the current CR shows `716.3` is now about
  *Class* cards and `719.3` is now about *Case* cards — both unrelated later
  mechanics that reused the freed-up numbers. A phrase search for the actual
  fragmented-loop text found it, **byte-identical**, at **732.3** today. Even
  the SE thread's own "corrected" citation has since drifted again — a number
  can be renumbered more than once, and a stale correction is still stale.
- **800.4c → 800.4d** (§6.2 above): a clean single-letter shift, byte-identical
  text, found the same way.
- By contrast, **421.5** — a rule Q14437 mentions as a historical curiosity
  from a 2002 Mark Rosewater article, already known by the answerer to be
  long superseded — has no trace anywhere in the current CR by number or by
  phrase search: a genuine **UNRESOLVED**, not a renumber.

### 6.3 What the resolver needs beyond `rule_fingerprint`, and how it reports ambiguity

`scripts/check_cr_update.py`'s `normalize()` and `rule_fingerprint()`
(`sha256(normalize(text))[:16]`) are directly reusable as **pure, one-sided
text functions** — hash the SE-quoted snippet the same way, hash every rule
in the current CR the same way, and look for an exact match. That's cheap and
exactly what recovered 732.3 and 800.4d above by hand.

Its `classify_rules(old_rules, new_rules)`, however, **assumes a full
old-release-vs-new-release diff** — it needs a *complete* old rule set to know
what fingerprint disappeared from its old slot and reappeared elsewhere. A
single quoted snippet is not a release; it's one query string, so
`classify_rules` itself isn't the right entry point for resolving an isolated
citation (§6.4 changes this once a real old release is available).

**Exact fingerprint match will routinely fail** even when a human would
recognize the rule instantly — a paraphrase instead of a verbatim quote, an
ellipsized partial quote (Q64566's answer quotes rule 403.1 with a "…" mid-
quote), or the rule's wording changed by even one word. So a snippet resolver
needs a fallback ladder, applied in order, each tier only reached if the
previous one fails:

1. **Exact fingerprint match** (as above) — highest confidence.
2. **Normalized substring containment** — does the normalized snippet appear
   as a contiguous run inside some current rule's normalized text, or vice
   versa (handles partial/truncated quotes). Only counted above a minimum
   length (e.g. ~40 normalized characters) to avoid trivial short-string
   collisions.
3. **Token-overlap threshold** (e.g. Jaccard or overlap coefficient over
   normalized word tokens, restricted to candidate rules in the *same*
   top-level CR section as the originally-cited number where possible — a
   rule about loops isn't going to have moved from section 7xx to section
   100) — catches a real wording edit that a human would still call "the same
   rule, reworded."

**Ambiguity is reported, never guessed through.** If tier 2 or 3 produces more
than one candidate clearing the bar, the resolver does **not** pick the
highest-scoring one — that is exactly the outcome worse than harvesting
nothing. It emits the same shape `check_cr_update.py` already uses for its own
`ambiguous` class (`cls="ambiguous", candidates=[...]`) — every plausible
candidate number and its match score, for a human to resolve by hand if it's
ever worth the effort. Anything ambiguous counts as **UNRESOLVED** in the
pipeline's automatic accounting; it is never auto-resolved to the top
candidate.

### 6.4 A dated CR archive exists — and it changes the economics

Jon asked whether Wizards publishes a changelog or whether a version archive
exists that would let this be "look up what the rule meant then" instead of
"fuzzy-match a 2013 quote against 2026 text." Checked this session, with
sources:

- **The repo's own CR file carries no internal change history.** Line 9 of
  `data/raw/MagicCompRules 20260619.txt` is a generic disclaimer ("Changes may
  have been made to this document since its publication…") pointing at
  Wizards' current-rules page — no changelog, no diff-from-previous-release
  summary, confirmed by direct grep of the file.
- **Wizards itself does not appear to publish a formal per-release
  changelog/redline document** as a distinct product — searches turned up no
  such official artifact; what exists instead are community-maintained
  indexes of Wizards' informal "update bulletin" announcements.
- **Yawgatog** (`yawgatog.com/resources/rules-changes/`) — the same site
  `murgatroid99`'s answers already link to for individual rule numbers (seen
  organically in this session's sample, e.g. Q64547/Q64560's citations link
  `yawgatog.com/resources/magic-rules/#R71214a` etc.) — maintains an index of
  per-set rules changes from **Ravnica: City of Guilds (2005) through Ixalan
  (2017)**, then stops; single-person-maintained (contact listed as
  `yawgatog@yawgatog.com`). Useful for that 12-year window, not current.
- **Academy Ruins** (`academyruins.com`; frontend source
  `github.com/lunakv/academyruins`, data API `lunakv/academyruins-api`) is the
  real find: an **archive of dated, full-text historical Comprehensive Rules
  releases by Magic set code**, plus the Magic Tournament Rules and Infraction
  Procedure Guide, **with a built-in incremental-diff feature between
  versions**. Confirmed working endpoints at `api.academyruins.com/file/cr/
  {SET_CODE}` for set codes spanning at least **Odyssey (ODY, 2001) and
  Onslaught (ONS, 2002) through Eldraine (ELD, 2019)** and, per the live site,
  continuing to present — safely covering this project's entire 2010–2026
  sample window. The frontend is **AGPL-3.0 licensed** (open source, GitHub);
  the underlying CR *text* itself is still Wizards of the Coast's own rules
  document, the same status as this repo's own local CR file — Academy Ruins
  is mirroring official releases Wizards itself no longer hosts once
  superseded, not asserting new rights over the content.

**What this unlocks, stated precisely:** with a specific historical release
pulled from Academy Ruins for the CR that was in effect around when a given
SE answer was written, `check_cr_update.py`'s existing `classify_rules()` runs
**unmodified** — `--old <academyruins release>.txt --new "MagicCompRules
20260619.txt"` — and classifies *every* rule id in that old release as
unchanged/renumbered/edited/deleted/ambiguous in one pass, not just the one
citation a resolver happens to be checking. That turns SE-citation resolution
from "fuzzy-match one snippet" into "look up a precomputed classification,"
which is cheaper and more reliable than the fallback ladder in §6.3 — the
fallback ladder becomes the tool for the (probably small) residue Academy
Ruins doesn't cover cleanly, not the primary method. The one remaining step
this doesn't remove: **mapping an SE answer's date to the specific CR release
in effect then** is a small lookup (Academy Ruins' own set/date index, or a
manually built table of CR-effective-dates), not automatic — an answer dated
"2014-01-28" needs the release current on that date, not a guess from the set
name mentioned in the question.

**This reaches beyond SE mining.** The same archive-plus-`classify_rules`
pipeline is exactly what this repo's own gold maintenance needs every time a
*future* CR release lands — `check_cr_update.py` was already built this
session for that purpose (`docs/spec-cr-update-check.md`); Academy Ruins is
the missing "get the old release" half of that pipeline for *any* two dates,
not just SE's. Worth flagging to whoever owns that spec as a shared
dependency rather than building two separate old-release-sourcing paths.

## 7. Licensing and attribution — still applies, the repo is public

Underlying Q&A text is Creative Commons Attribution-ShareAlike, but the
**version depends on when the specific post revision was made** — confirmed
from Stack Overflow's own help page (`stackoverflow.com/help/licensing`,
2026-07-26): CC BY-SA 2.5 before 2011-04-08, 3.0 through 2018-05-01, 4.0 from
2018-05-02 on. Several sampled threads (asked 2010–2014, edited as late as
2025) span more than one version across their own edit history — any
harvested chain needs to record which revision it used and that revision's
license, not assume 4.0 blanket-wide.

**Route:** the Stack Exchange API (`api.stackexchange.com`), not the 2024-
gated data dump. Read endpoints need no auth; a free, instant self-serve
`key` (registered at `stackapps.com`) raises the daily quota from an
anonymous **300/day** (confirmed directly this session — a live API response
carried `"quota_max":300,"quota_remaining":298"` after two calls) to
**10,000/day**. Stack Overflow's Public Network Terms of Service (`stackoverflow.com/legal/terms-of-service/public`, § 6) explicitly excludes
"content made available via the Stack Overflow API" from the general
personal-noncommercial-use restriction that governs other site content — the
2024 data dump's added "no LLM training" click-through is a condition on the
dump product specifically, not on the API or the underlying CC license. A
scoped API pull sits on cleaner ground than the dump; that's a plain reading
of the posted terms, not legal advice, and doesn't fully dissolve Stack
Exchange's stated discomfort with content feeding LLM pipelines at scale —
one more reason to keep any pilot small, attributed, and structure-only
(never republishing full answer prose as gold text).

**Attribution, per Stack Exchange's own stated practice**: a direct
(non-`nofollow`) hyperlink to the original question, the answerer's display
name, and a hyperlink from that name to their profile. For this project:
every retained chain needs the question URL, the answer permalink, the
answerer's display name + profile URL, and the CC version of the revision
used. **Whether RulesGuru's own gold already carries equivalent bookkeeping
in this repo wasn't checked as part of this task** — worth confirming before
treating this as SE-specific overhead (see Open Decisions).

## 8. The smallest useful pilot, and its cost

1. **Pull** ~50–100 candidate questions via the API in one scoped run (well
   under the 10,000/day keyed quota; even the un-keyed 300/day covers it),
   restricted to the `magic-the-gathering` tag, using the `answers` endpoint
   with `filter=!9YdnSMKKT` (or an equivalent custom filter) to get
   `is_accepted` and `score` in the same call — no separate page-scrape
   needed, as demonstrated in §2.
2. **Apply the hard filter mechanically**: keep only questions where the
   top-scored answer's `answer_id` equals the accepted answer's `answer_id`
   (both fields are directly in the API response — no page-rendering
   required for this step, only for the human read of what survives).
3. **Apply the citation test**: regex for CR-shaped numbers (e.g.
   `\b\d{3}\.\d+[a-z]?\b`) in the surviving answer body, then a human/agent
   confirms it's a real CR citation and not a card collector number or a
   forum-post reference.
4. **Expect roughly this sample's ratio**: ~50% survive both filters, and
   within that, only a minority (this sample: 2 of 5) are genuinely
   multi-rule conjunctive chains rather than single-rule or independent-
   citation cases — so a 50–100 question pull should yield on the order of
   **10–15 usable chains**, of which perhaps **4–6** are clean multi-step
   conjunctive examples. Re-measure on the real pull; this is an expectation
   set by a 10-question sample, not a promise.
5. **Validate per §5–6**, propose to Jon per §5.3, never merge into
   `evals/questions.jsonl` or `questions_rulesguru150_v3.jsonl` directly.

**Cost: $0 in Anthropic/Voyage spend for the pull itself** — the API is free,
self-serve, and one scoped run sits far under quota. The real cost is
labor: per-candidate CR cross-checking (§5.1) and license/attribution
bookkeeping (§7), which is exactly the batched fetch/filter/verify shape this
repo's token-economy policy has a lane for — Haiku workers doing the bulk
pull-and-check with a compact pass/fail per candidate, the lead reviewing
only what survives, never raw SE threads entering the lead's context.

## Open decisions for Jon

1. **Whether to run the pilot at all**, and at what size (§8's 50–100, or
   larger given the thin per-10 yield of genuinely conjunctive chains).
2. **Whether to cross-reference the specific 25 category-(c) `rg` ids from
   `docs/results-orgroup-repass.md` against any SE chains found** — this spec
   establishes the pattern is real and detectable, not that it resolves any
   particular one of the 25.
3. **Whether RulesGuru's own gold carries license/attribution bookkeeping
   today** — if not, SE chains would be the first thing in this repo to carry
   that overhead, worth knowing before pricing it as SE-specific friction.
4. **Whether to pull historical CR releases from Academy Ruins (§6.4) now**,
   making `check_cr_update.py`'s existing `classify_rules()` directly usable
   for every SE citation at once, versus running the cheaper fallback ladder
   (§6.3) on the current CR alone at pilot scale and only reaching for Academy
   Ruins if the pilot's UNRESOLVED rate turns out too high to live with.
5. **Who builds the SE-answer-date → CR-release-in-effect lookup** (§6.4's
   one remaining manual step) if Academy Ruins is used — a small one-time
   table, not automated by anything this spec found.
6. **Where the citation-quote check happens** — a human reading each
   candidate's cited rule against the CR file, or a scripted string-match
   between the SE answer's quoted rule text and the CR file's own text
   (catches paraphrase drift a skim might miss, but needs care around CR
   wording that legitimately changed since the SE answer was written).
