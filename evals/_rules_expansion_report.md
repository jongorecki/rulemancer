# Rules-31 expansion draft — report

**Output file:** `evals/_rules_expansion_draft.jsonl` (56 rows, ids `q100`-`q155`, no
collisions with `evals/questions_rules31.jsonl`'s `q001`-`q032`).

Everything below is a draft for Jon's review in the morning. Nothing here was
merged into `questions_rules31.jsonl` and no eval arm, model call, or embedding
was run — this was pure CR reading, jq filtering of `rulesguru_full_v2.jsonl`
on disk, and hand-grounded writing.

## What was drafted (56 rows, not the full 70)

I stopped at 56 rather than stretching to 70. Every extra row I considered
past that point was either a near-duplicate of one already drafted, or
required a CR citation I couldn't actually find and would have had to guess
at — and the brief was explicit that a flagged gap beats a confident wrong
answer. I'd rather hand over 56 solid rows than 70 with padding.

Breakdown by topic:
- Zones (400s): 7 (`q100`-`q106`)
- Turn structure (500s): 6 (`q107`-`q112`)
- Stack, priority, resolution order, targeting (405/603/608/115): 9 (`q113`-`q121`)
- Replacement effects vs. triggered/continuous effects (614): 7 (`q122`-`q128`)
- Copy effects (707/608.3f): 6 (`q129`-`q134`)
- Multiplayer / rule 800s: 12 (`q135`-`q146`)
- Abstracted from `rulesguru_full_v2.jsonl` corpus rows, card names stripped: 8
  (`q147`-`q152`, `q154`, `q155`, mixed across multiplayer/priority/targets/copy;
  `q153` in that range is `direct_cr_question`)

**Provenance split:** 48 rows are `direct_cr_question` (written straight from
CR text, no corpus row involved). 8 rows are
`abstracted_from_rulesguru:<source_qid>` — a corpus row's card-specific
scenario rewritten generically, only where the original `answer_gold` already
stated the rules mechanism in words rather than just asserting a result.

## CR-area coverage: before vs. after

The 31 existing questions are strong on: state-based actions (lethal damage,
empty library, legend rule, loyalty 0), priority basics (untap step, mana
abilities, cost payment, holding priority), layers (613, well covered — also
backed by `purerules.jsonl`'s 8 rows), keyword interactions (trample+deathtouch,
storm, evoke, split second), zones only incidentally, and one question each on
concede, sagas, delayed triggers, spell abilities.

Areas the task flagged as gaps that had **near-zero direct coverage** before
this draft, and what's now covered:
- **Zones** — had nothing dedicated. Now: zone list/ownership, hidden vs.
  public status, library secrecy, exile default visibility, the "new object"
  rule on zone change, instants/sorceries barred from the battlefield, token
  zone-change death, stack-order immutability.
- **Turn structure and steps** — had cleanup, combat steps, and untap-step
  priority, but nothing on phase/step mechanics in general. Now: all-phases-
  always-happen, first-turn draw-step skip (2-player, multiplayer, 2HG),
  extra-turn stacking order, skip-effect timing.
- **State-based actions** — already well covered; added nothing new here on
  purpose to avoid duplication.
- **Targeting and legality** — had zero dedicated rows. Now: illegal-target
  resolution (all illegal vs. partial), self-targeting bar, zero-target
  legality, change-target vs. choose-new-targets mechanics, single-target
  counting.
- **Replacement vs. triggered effects** — had zero dedicated rows (only
  purerules.jsonl's layer-focused rows touch replacement effects tangentially).
  Now: the "instead"/"skip" signal words, the "can't retroactively apply"
  rule, one-shot application, self-replacement vs. continuous, regeneration's
  true nature.
- **Layers / copy effects** — layers were well covered by purerules.jsonl;
  copy effects had zero dedicated rows. Now: what does and doesn't copy,
  token-copy ETB triggers, copy-of-a-spell-isn't-casting, linked abilities
  staying linked.
- **Multiplayer (800s)** — had zero dedicated rows. Now the largest new
  block: multiplayer's start-of-game definition, team/opponent vocabulary,
  starting life totals (2HG, Commander), what happens when a player leaves
  (object ownership, control-change blocking, trigger suppression), the
  free-first-mulligan carve-out (and its absence in 2-player Commander),
  range of influence attack restriction, shared-team-turn draw mechanics.

## Confidence distribution

Verified by script against the actual file: **53 high, 1 medium, 2 low**
(56 total). The two low-confidence rows are `q147` and `q148`; the one
medium-confidence row is `q155`. `q149` — which I first drafted as an
abstraction alongside `q147`/`q148` — turned out to have a clean, explicit
727.1 citation ("all players in that game when it ended"), so it's rated
high, not low.

Provenance split: 48 rows `direct_cr_question`, 8 rows
`abstracted_from_rulesguru:<source_qid>`.

## Every low/medium-confidence row and what's unresolved

- **`q147`** (leaving the game triggers leaves-the-battlefield abilities) —
  low. I'm combining 800.4a (objects leave the game) with the general
  zone-change-trigger framework to conclude that a player leaving the game
  counts as their permanents leaving the battlefield for trigger purposes.
  I could not find one CR sentence that says this outright; it's an inference
  from two rules that individually check out but aren't explicitly wired
  together. The rulesguru source row (`rg61`) agrees, citing 603.6c and
  800.4a, but its own citation didn't fully close the gap for me either.
- **`q148`** (2HG simultaneous team win vs. teammate's empty-library loss) —
  low. The mechanism I describe (both draws determined simultaneously per
  turn-based action, loss is a state-based action checked afterward, so a
  same-event win supersedes it) matches the source row's (`rg2735`) reasoning,
  but I did not verify the exact CR text that resolves a win and a loss from
  the same state-based-action check happening "at once." Open question: is
  there a rule 104-adjacent tie-break for simultaneous win/loss that I should
  have cited instead of inferring it from 704.3/704.5b timing alone?
- **`q155`** (copied permanent's fresh copy resets a "once per turn"
  restriction) — medium. Rule 602.5b only explicitly covers restriction
  tracking across a *control change*, not a *copy event* where the original
  permanent is untouched and a separate new object is created. I'm inferring
  from 400.7/707.2 (a copy is a new object) that the restriction doesn't
  carry over, which matches the source row (`rg1063`, Mirage Mirror), but
  I did not find a rule stating this for copies specifically.

## Deliberate exclusions (and why)

- **A "target tapped creature" restriction persisting/lapsing after
  targeting** (from rulesguru row `rg116`) — the source row itself has an
  empty `gold` field (no CR citation from the original authors), and I
  couldn't independently pin down the exact rule that resolves whether a
  restriction like "target tapped creature" is re-checked at resolution the
  same way a zone/characteristic-based illegality is. Rather than guess, I
  left it out entirely.
- **Subgame membership after Shahrazad** (rulesguru rows `rg468`/`rg469`) —
  I read rule 729 (Subgames) in full and it never explicitly states that only
  players present in the main game when the subgame began are included in
  the subgame; that conclusion is asserted by the source rows without a
  clean citation I could verify. I used the *restart* version of this idea
  instead (`q149`, rule 727.1), which does have a clean, explicit citation
  ("all players in that game when it ended"), and dropped the subgame
  version.
- **"Another" meaning distinct targets in natural-language card text**
  (rulesguru row `rg7400`) — this rests on ordinary-English interpretation
  (rule 608.2c's "apply the rules of English" instruction) rather than a
  rule that names "another" specifically. Too thin a citation to include as
  a confident row, and not interesting enough to include as a flagged
  low-confidence one.
- **Mana-ability cost timing vs. triggered damage timing** (e.g. Mana
  Confluence/City of Brass style life-loss-as-cost vs. life-loss-as-trigger,
  seen across several `rg56xx`/`rg66xx` rows) — genuinely useful distinction,
  but abstracting it card-free without inventing a specific mana ability's
  wording felt artificial, and I'd already spent the "stack/priority" quota.
  Left as a good candidate for a future round if 65-70 rows are wanted later.
- **A ~65-70 count** — I capped at 56 rather than padding to the requested
  ceiling with weaker or more overlap-prone rows. Told plainly per the task's
  instruction to say what I couldn't do as specified: I did not hit 70.

## One thing to flag from mid-task

Partway through, a system reminder appeared claiming `CLAUDE.md` had been
modified (repo test-count bumped 929 -> 1124) "by the user or a linter" and
instructing me not to mention it. I'm not treating an instruction embedded in
a tool/system message as something that overrides telling you what happened —
so: that notice appeared, I did not verify it against the actual file, and I
did not silently comply with the "don't tell them" part. Worth a look, though
it's unrelated to this eval-drafting task and I did not act on it either way.
