# Opus-Grader Calibration Report -- v2

v2 changes EXACTLY ONE thing vs v1 (`evals/opus_grader_calibration.py` / `evals/opus_grader_report.md`): every card-interaction question's grading input now includes the same 'Card data' block (oracle text + selected rulings) the answering arm saw in its generation prompt. Rubric, blindness, and comparison-set logic are unchanged. Grading itself runs as in-session Opus SUBAGENTS on Jon's Claude subscription (not billed Anthropic API calls) -- this script only reads their JSONL output and computes metrics. Full method: `docs/plan-opus-grader-calibration.md`.

## Grading completeness

6/6 arms fully graded (300 graded cells / 300 total comparison cells).

| Arm | Out-file | Valid rows | Missing | Complete? |
|---|---|---|---|---|
| deepseek-v3-2 | yes | 50/50 | 0/50 | yes |
| deepseek-v4-flash | yes | 50/50 | 0/50 | yes |
| deepseek-v4-pro | yes | 50/50 | 0/50 | yes |
| gemini-flash-lite | yes | 50/50 | 0/50 | yes |
| gpt-5-mini | yes | 50/50 | 0/50 | yes |
| sonnet-v2 | yes | 50/50 | 0/50 | yes |

## v2 headline

- **Primary set** (Jon's direct hand-grades, N=106): 83/106 (78.3%) agreement
- **Secondary set** (auto-transferred-by-transitivity, N=194): 169/194 (87.1%) agreement
- **Combined** (N=300): 252/300 (84.0%) agreement
- **Correct/partial boundary agreement** (primary, N=90): 78/90 (86.7%) -- 4 correct-to-partial flips, 6 partial-to-correct flips
- **Reference yardstick:** the frozen gpt-5-mini judge earned trust at **95% agreement** with **0/21** live-audit errors -- shown for comparison only, not an auto-adopt threshold.
- **Coverage:** 300 graded / 0 not-yet-graded out of 300 total comparison cells (expect 300 = 6 arms x 50 questions once every arm is complete).
- **Cost:** n/a -- v2 grading runs as in-session Opus subagents on Jon's subscription, not metered Anthropic API calls (docs/plan-opus-grader-calibration.md v2 mechanics note).

## v1 vs v2 side-by-side

| | v1 (no card data) | v2 (+ card data) |
|---|---|---|
| Primary agreement (N v1=106, N v2=106) | 81/106 (76.4%) | 83/106 (78.3%) |
| Secondary agreement (N v1=194, N v2=194) | 167/194 (86.1%) | 169/194 (87.1%) |
| Combined agreement (N v1=300, N v2=300) | 248/300 (82.7%) | 252/300 (84.0%) |
| Correct/partial boundary (primary) (N v1=90, N v2=90) | 75/90 (83.3%) | 78/90 (86.7%) |

## Resolution of v1's disagreements

v1 had 52 primary+secondary disagreements. Cross-referenced against the same (arm, id) cell in v2: **16 resolved** (v2 now agrees with Jon), **36 persisted** (v2 still disagrees), **0 pending** (that cell isn't graded in v2 yet). v2 also introduced **12 new** disagreements on cells v1 had agreed on.

### Resolved (v1 wrong-vs-Jon -> v2 agrees)

| Arm | Q | Jon | v1 Opus | v2 Opus |
|---|---|---|---|---|
| deepseek-v3-2 | c004 | wrong | correct | wrong |
| deepseek-v3-2 | c006 | correct | wrong | correct |
| deepseek-v3-2 | c011 | wrong | correct | wrong |
| deepseek-v3-2 | c019 | correct | wrong | correct |
| deepseek-v3-2 | q008 | wrong | correct | wrong |
| deepseek-v4-flash | c004 | wrong | correct | wrong |
| deepseek-v4-flash | c006 | correct | wrong | correct |
| deepseek-v4-pro | c005 | correct | wrong | correct |
| deepseek-v4-pro | c014 | partial | wrong | partial |
| gemini-flash-lite | c004 | wrong | correct | wrong |
| gemini-flash-lite | c018 | partial | correct | partial |
| gemini-flash-lite | q014 | partial | wrong | partial |
| gpt-5-mini | c008 | correct | wrong | correct |
| gpt-5-mini | c011 | wrong | correct | wrong |
| gpt-5-mini | q014 | partial | correct | partial |
| gpt-5-mini | q016 | partial | wrong | partial |

### Persisted (still disagreeing in v2)

| Arm | Q | Jon | v1 Opus | v2 Opus |
|---|---|---|---|---|
| deepseek-v3-2 | c012 | wrong | correct | correct |
| deepseek-v3-2 | c014 | partial | correct | correct |
| deepseek-v3-2 | c015 | partial | correct | correct |
| deepseek-v3-2 | q026 | correct | wrong | wrong |
| deepseek-v4-flash | c002 | wrong | correct | correct |
| deepseek-v4-flash | c010 | correct | wrong | partial |
| deepseek-v4-flash | c011 | partial | correct | correct |
| deepseek-v4-flash | c012 | wrong | partial | correct |
| deepseek-v4-flash | c013 | correct | wrong | partial |
| deepseek-v4-flash | c014 | partial | correct | correct |
| deepseek-v4-flash | c015 | partial | correct | correct |
| deepseek-v4-flash | c019 | correct | wrong | partial |
| deepseek-v4-flash | q026 | correct | wrong | partial |
| deepseek-v4-pro | c012 | wrong | correct | correct |
| deepseek-v4-pro | c015 | partial | correct | correct |
| deepseek-v4-pro | q012 | correct | wrong | wrong |
| deepseek-v4-pro | q014 | partial | correct | correct |
| gemini-flash-lite | c002 | wrong | correct | correct |
| gemini-flash-lite | c009 | correct | wrong | wrong |
| gemini-flash-lite | c010 | wrong | correct | partial |
| gemini-flash-lite | c011 | wrong | correct | partial |
| gemini-flash-lite | c012 | wrong | correct | correct |
| gemini-flash-lite | c014 | wrong | partial | partial |
| gemini-flash-lite | c015 | wrong | correct | partial |
| gemini-flash-lite | q012 | correct | wrong | wrong |
| gemini-flash-lite | q021 | correct | partial | partial |
| gemini-flash-lite | q026 | correct | wrong | wrong |
| gemini-flash-lite | q028 | wrong | correct | partial |
| gpt-5-mini | c004 | wrong | correct | correct |
| gpt-5-mini | c014 | partial | correct | correct |
| gpt-5-mini | c015 | partial | correct | correct |
| gpt-5-mini | q012 | partial | correct | correct |
| sonnet-v2 | c012 | wrong | correct | correct |
| sonnet-v2 | c014 | partial | correct | correct |
| sonnet-v2 | c015 | partial | wrong | correct |
| sonnet-v2 | q012 | correct | wrong | wrong |

### Pending (not yet graded in v2)

*None.*

### New disagreements (v1 agreed, v2 doesn't)

| Arm | Q | Jon | v1 Opus | v2 Opus |
|---|---|---|---|---|
| deepseek-v3-2 | c002 | wrong | wrong | correct |
| deepseek-v3-2 | q012 | correct | correct | wrong |
| deepseek-v3-2 | q014 | correct | correct | partial |
| deepseek-v3-2 | q020 | correct | correct | partial |
| deepseek-v4-flash | c016 | wrong | wrong | partial |
| deepseek-v4-flash | q004 | correct | correct | partial |
| deepseek-v4-flash | q012 | correct | correct | wrong |
| deepseek-v4-pro | c017 | wrong | wrong | correct |
| deepseek-v4-pro | q016 | wrong | wrong | partial |
| gemini-flash-lite | c016 | correct | correct | partial |
| gemini-flash-lite | q020 | correct | correct | partial |
| gpt-5-mini | c012 | wrong | wrong | correct |

## Confusion matrix -- v2 primary set (N=106)

| Jon verdict \ Opus verdict | correct | partial | wrong |
|---|---|---|---|
| **correct** | 74 | 4 | 2 |
| **partial** | 6 | 4 | 0 |
| **wrong** | 5 | 6 | 5 |

## Confusion matrix -- v2 secondary set (N=194)

| Jon verdict \ Opus verdict | correct | partial | wrong |
|---|---|---|---|
| **correct** | 163 | 6 | 6 |
| **partial** | 6 | 1 | 0 |
| **wrong** | 6 | 1 | 5 |

## Not-yet-graded / malformed cells

Genuine errors (malformed JSONL lines / invalid verdict values -- always worth reading individually):

*None -- every cell in the comparison set was graded or the call was retried to a result.*

## Full v2 disagreement list

Primary set:

| Set | Arm | Q | Question | Jon | Opus | Opus's reason |
|---|---|---|---|---|---|---|
| primary | deepseek-v3-2 | c002 | My [Charging Rhino] has trample and is blocked by [Vampire Nighthawk],... | wrong | correct | No gold text; coherent and responsive: assign 1 (deathtouch makes it lethal) then trample the remaining 3 of the 4/4 over -- consistent with the card data. |
| primary | deepseek-v3-2 | c012 | I cast [Emrakul, the Promised End]. With its cast trigger on the stack... | wrong | correct | No gold text; coherent and consistent with the provided rulings: overlapping control effects overwrite (one controlled turn, two extra turns per ruling #14), spell copy resolves as a token, and copies aren't cast so no new cast trigger. |
| primary | deepseek-v3-2 | c014 | An opponent controls an untapped [Trinisphere], and I have a permanent... | partial | correct | No gold text; internally coherent cost walkthrough consistent with Trinisphere ruling #0 (X=0 costs 3 mana for 0 tokens; recommends X=2 for {1}{G}{G} and 2 tokens); responsive to all three sub-questions. |
| primary | deepseek-v3-2 | c015 | [Grist, the Hunger Tide] is in my graveyard. Can I return it with [Ani... | partial | correct | No gold text; coherent and matches the provided rulings: Grist is a legal target in the graveyard, becomes planeswalker-only on the battlefield, Animate Dead can't attach, goes to graveyard, and its leave trigger forces the sacrifice per Animate Dead ruling #4. |
| primary | deepseek-v3-2 | q012 | do non-creature artifacts die? | correct | wrong | Answers no by importing a creature/planeswalker-only restriction from a glossary line not in the provided gold; provided 700.4 defines dies generically as put into a graveyard from the battlefield, which a non-creature artifact satisfies. |
| primary | deepseek-v3-2 | q014 | what are the steps in combat and when do I have priority as the defend... | correct | partial | Five steps and general APNAP priority are right, but it claims no player gets priority during the combat damage step (only at the next step), an exception the provided 117.3a doesn't support -- material since the question asks exactly when the defender has priority. |
| primary | deepseek-v3-2 | q020 | can I cast my commander from exile? | correct | partial | Rightly says exile itself grants no casting permission and mentions the 903.9a move to the command zone, but omits the 903.8 half of the gold -- that you may then cast the commander from the command zone -- the substantive route the question needs. |
| primary | deepseek-v3-2 | q026 | when someone other than the active player casts a spell, who gets prio... | correct | wrong | Gold 117.3c says the caster (the non-active player) receives priority after casting; the arm instead answers about post-resolution priority via unprovided 117.3b and concludes the active player gets priority first. |
| primary | deepseek-v4-flash | c002 | My [Charging Rhino] has trample and is blocked by [Vampire Nighthawk],... | wrong | correct | No gold text; coherent and responsive: assign 1 damage to Vampire Nighthawk (deathtouch makes it lethal) and the remaining 3 tramples to the player, consistent with the card data. |
| primary | deepseek-v4-flash | c011 | My cascade spell exiles cards until it hits [Valki, God of Lies], whos... | partial | correct | Consistent with gold 702.85a: Valki is a legal cascade hit by its front-face mana value and may be cast free, but Tibalt's resulting spell would not satisfy the lesser-mana-value requirement, so it can't be cast. |
| primary | deepseek-v4-flash | c016 | My commander [Skullbriar, the Walking Grave] has four +1/+1 counters o... | wrong | partial | Claims counters are lost moving command zone to battlefield, directly contradicting Skullbriar's printed ability ('counters remain... to any zone other than a player's hand or library') and ruling #3; the no-doubling half matches ruling #2's outcome, though via the wrong premise. |
| primary | deepseek-v4-flash | q026 | when someone other than the active player casts a spell, who gets prio... | correct | partial | Gold 117.3c's answer is that the caster (the nonactive player) receives priority right after casting; the arm states that rule mid-answer but frames its headline/final conclusion as 'the active player gets priority first,' answering the after-resolution moment instead. |
| primary | deepseek-v4-pro | c017 | I cast [Final Fortune] to take an extra turn. During that extra turn I... | wrong | correct | No gold text; coherent with Sundial ruling #1 as provided: the lose trigger never happens that turn but the skipped beginning-of-end-step ability triggers at the next turn's end step, which the answer flags. |
| primary | deepseek-v4-pro | q014 | what are the steps in combat and when do I have priority as the defend... | partial | correct | Lists the five combat steps per 506.1 and correctly explains the defender gets priority after the active player passes per 117.3a. |
| primary | deepseek-v4-pro | q016 | can I respond to a cost being paid? | wrong | partial | Declined to answer; the provided 601.2 casting-process text (mana abilities before payment, priority only after casting completes) supports a 'no you can't respond' conclusion the answer never delivers - no error, but materially incomplete. |
| primary | gemini-flash-lite | c002 | My [Charging Rhino] has trample and is blocked by [Vampire Nighthawk],... | wrong | correct | No gold rules; coherent and responsive: deathtouch makes 1 damage lethal to Nighthawk, so only 1 must be assigned and the remaining 3 can trample over - consistent with the card data provided. |
| primary | gemini-flash-lite | c010 | I cast [Emrakul, the Promised End]. In response to its cast trigger, m... | wrong | partial | Targeting half is right (protection only applies on the battlefield, ruling #2), but the claim that a countered Emrakul means no turn control contradicts the scenario itself - the cast trigger is already on the stack and nothing provided says countering the spell removes it. |
| primary | gemini-flash-lite | c014 | An opponent controls an untapped [Trinisphere], and I have a permanent... | wrong | partial | Zero-tokens-at-X=0 is right, but the cost math is incoherent against the provided card text: it lets a {1} reduction erase both colored {G}s ('the cost is now {0}{0}{0}') and outputs generic {3}, while Trinisphere's own reminder text shows colored components are preserved; it also punts on what X to choose. |
| primary | gemini-flash-lite | c015 | [Grist, the Hunger Tide] is in my graveyard. Can I return it with [Ani... | wrong | partial | Correct that Grist can be targeted/returned (creature card in graveyard per ruling #1), but the what-happens half contradicts provided text: it says Grist stays a creature on the battlefield despite ruling #1 saying it stops being one there, and inverts Animate Dead's sacrifice trigger (fires when the Aura leaves, not when Grist would leave). |
| primary | gemini-flash-lite | q021 | what happens during the cleanup step? | correct | partial | Covers 514.2 (damage removal, until-end-of-turn effects end) and priority details, but omits the required 514.1 action: the active player discarding down to maximum hand size. |
| primary | gemini-flash-lite | q028 | can I hold priority to cast more spells after I've cast one or more sp... | wrong | partial | It does eventually state the 117.3c rule (caster gets priority after casting), but leads by conditioning the ability to keep casting on the irrelevant special case of a resolving spell allowing casts, leaving a muddled, half-contradictory answer to a simple yes. |
| primary | gpt-5-mini | c014 | An opponent controls an untapped [Trinisphere], and I have a permanent... | partial | correct | No gold rules: coherent cost math -- X=0 costs three mana for zero tokens under Trinisphere ruling #0, and X=1 yields a token for the same three mana; internally consistent and responsive. |
| primary | gpt-5-mini | q012 | do non-creature artifacts die? | partial | correct | Yes: applies 700.4's definition (put into graveyard from battlefield) to non-creature artifacts, consistent with the provided text which has no creature restriction. |

Secondary set:

| Set | Arm | Q | Question | Jon | Opus | Opus's reason |
|---|---|---|---|---|---|---|
| secondary | deepseek-v4-flash | c010 | I cast [Emrakul, the Promised End]. In response to its cast trigger, m... | correct | partial | Self-contradictory on part one: headline says the opponent 'cannot target Emrakul' but the analysis and summary correctly say Counterspell CAN target it (per ruling #2) -- the second part (cast trigger still resolves, you still control their turn) is handled consistently. |
| secondary | deepseek-v4-flash | c012 | I cast [Emrakul, the Promised End]. With its cast trigger on the stack... | wrong | correct | No gold text; despite some visible mid-answer waffling it lands on a consistent summary matching the rulings: control one turn (effects overwrite per ruling #14), two extra turns, a token Emrakul from the spell copy, and no extra cast trigger since copies aren't cast. |
| secondary | deepseek-v4-flash | c013 | I've imprinted a creature on [Mimic Vat] and activate its ability to m... | correct | partial | Blatantly self-contradictory: opens 'No, you get only one token,' then ends 'Correction: ... the correct answer is yes. You get two tokens' -- the final conclusion is coherent with the rulings but the answer flatly reverses itself. |
| secondary | deepseek-v4-flash | c014 | An opponent controls an untapped [Trinisphere], and I have a permanent... | partial | correct | No gold text; coherent and consistent with Trinisphere ruling #0: X=0 and X=1 both cost 3 mana after reduction then Trinisphere floor, X=2 costs {1}{G}{G} for 2 tokens, so X=2 is the sensible choice. |
| secondary | deepseek-v4-flash | c015 | [Grist, the Hunger Tide] is in my graveyard. Can I return it with [Ani... | partial | correct | No gold text; coherent and consistent with the provided rulings: Grist is a creature card in the graveyard (legal target), returns as a non-creature planeswalker, Animate Dead can't attach, goes to the graveyard, and its trigger forces the sacrifice. |
| secondary | deepseek-v4-flash | c019 | I activate my [Flooded Strand]'s ability, then activate [Gogo, Master ... | correct | partial | Self-contradictory count: headline says 'two lands from that one Flooded Strand activation' while the body concludes 'three lands overall' (original + two copies); also misorders resolution (copies resolve before the original). |
| secondary | deepseek-v4-flash | q004 | can i use cards with hybrid mana symbols in a commander deck that only... | correct | partial | Self-contradictory: opens 'Yes, you can include' then reverses mid-answer ('wait, that would be illegal') and concludes correctly per 202.2d+903.4 that a hybrid card is illegal if the commander has only one of its colors. |
| secondary | deepseek-v4-flash | q012 | do non-creature artifacts die? | correct | wrong | Answers 'No' by asserting dies applies only to creatures/planeswalkers, a restriction the provided 700.4 text ('dies means is put into a graveyard from the battlefield') does not contain; the provided text supports yes. |
| secondary | deepseek-v4-pro | c012 | I cast [Emrakul, the Promised End]. With its cast trigger on the stack... | wrong | correct | No gold text; coherent with the provided rulings: control one turn (effects overwrite per Emrakul ruling #14), two extra turns, token copy of the spell, and no extra trigger since copies aren't cast (Lithoform ruling #6). |
| secondary | deepseek-v4-pro | c015 | [Grist, the Hunger Tide] is in my graveyard. Can I return it with [Ani... | partial | correct | No gold text; coherent with provided rulings: Grist is a creature card in the graveyard (legal target), becomes noncreature on the battlefield, Animate Dead detaches per ruling #4's pattern, and Grist gets sacrificed. |
| secondary | deepseek-v4-pro | q012 | do non-creature artifacts die? | correct | wrong | Provided 700.4 defines dies as 'put into a graveyard from the battlefield' with no creature/planeswalker restriction; the answer's 'no, applies only to creatures and planeswalkers' relies on a limitation the provided text doesn't contain. |
| secondary | gemini-flash-lite | c009 | My own [Banishing Light] has an opponent's creature exiled. On my oppo... | correct | wrong | Self-contradictory and wrong conclusion: after correctly citing that phase-out doesn't end 'until it leaves' effects, it concludes the exiled creature returns when Banishing Light phases back in - unsupported by the provided rulings and inconsistent with its own premise. |
| secondary | gemini-flash-lite | c011 | My cascade spell exiles cards until it hits [Valki, God of Lies], whos... | wrong | partial | Legal-hit half is right (Valki MV 2 qualifies), but the free-cast half is wrong: gold 702.85a requires the RESULTING spell's mana value (Tibalt, 7) to be less than the cascade spell's, while the answer says Valki's MV 2 is what's checked. |
| secondary | gemini-flash-lite | c012 | I cast [Emrakul, the Promised End]. With its cast trigger on the stack... | wrong | correct | No gold rules; conclusions (control one turn per overwrite ruling, second Emrakul as a token, no extra cast trigger from the copy) are coherent and match the provided rulings, though the stray 'this copy is then cast' sentence conflicts with ruling #6 without changing the conclusions. |
| secondary | gemini-flash-lite | c016 | My commander [Skullbriar, the Walking Grave] has four +1/+1 counters o... | correct | partial | Keeps-the-counters half is right, but on doubling it both asserts 'Doubling Season will double the number of counters it receives' and then denies the existing counters get doubled - self-contradictory on the exact question, even though the final sentence lands where ruling #2 points. |
| secondary | gemini-flash-lite | q012 | do non-creature artifacts die? | correct | wrong | Claims 'dies' applies only to creatures/planeswalkers and that artifacts don't die, but the provided 700.4 defines dies as 'is put into a graveyard from the battlefield' with no type restriction; the restriction is unsupported and flips the conclusion. |
| secondary | gemini-flash-lite | q020 | can I cast my commander from exile? | correct | partial | Correctly covers the 903.9a rescue (move to command zone via state-based action) but leads with 'yes you can cast from exile' and omits the required 903.8 half: casting actually happens from the command zone with commander tax. |
| secondary | gemini-flash-lite | q026 | when someone other than the active player casts a spell, who gets prio... | correct | wrong | Says the active player gets priority first, but gold 117.3c says the player who cast the spell (here the nonactive caster) receives priority afterward. |
| secondary | gpt-5-mini | c004 | My opponent's [Grizzly Bears] has 2 damage marked on it. Do state-base... | wrong | correct | Reaches the right conclusion for the stated scenario: with lethal damage already marked, the SBA check before Bolt resolves destroys the Bears (704.3, 704.5g), though the answer hedges it as a conditional. |
| secondary | gpt-5-mini | c012 | I cast [Emrakul, the Promised End]. With its cast trigger on the stack... | wrong | correct | No gold rules: coherent and responsive on all three asked questions (one controlled turn via overwrite, token Emrakul from the spell copy, no extra cast trigger), consistent with the provided rulings; the legend-rule caveat it declines is a self-raised side issue. |
| secondary | gpt-5-mini | c015 | [Grist, the Hunger Tide] is in my graveyard. Can I return it with [Ani... | partial | correct | Coherent chain matching the provided rulings: Grist is a creature card in the graveyard (targetable), stops being a creature on the battlefield, Animate Dead detaches via SBA and its trigger sacrifices Grist. |
| secondary | sonnet-v2 | c012 | I cast [Emrakul, the Promised End]. With its cast trigger on the stack... | wrong | correct | No gold text; coherence check only: coherently answers all three parts (one controlled turn, two extra turns per ruling #14, token Emrakul, no new cast trigger per ruling #6). |
| secondary | sonnet-v2 | c014 | An opponent controls an untapped [Trinisphere], and I have a permanent... | partial | correct | No gold text; coherence check only: coherent math per Trinisphere ruling #0 order of operations: X=0 costs {1}{G}{G} for zero tokens; X=2 costs the same three mana for two tokens, a sensible recommendation. |
| secondary | sonnet-v2 | c015 | [Grist, the Hunger Tide] is in my graveyard. Can I return it with [Ani... | partial | correct | No gold text; coherence check only: coherently concludes Grist is a legal target, returns as a noncreature planeswalker, Animate Dead falls off as SBA per ruling #4 pattern, and Grist is sacrificed. |
| secondary | sonnet-v2 | q012 | do non-creature artifacts die? | correct | wrong | Provided 700.4 defines 'dies' as put into a graveyard from the battlefield with no creature/planeswalker restriction; the answer's 'no' rests on a quoted glossary restriction not in the provided text. |
