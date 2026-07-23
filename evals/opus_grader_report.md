# Opus-Grader Calibration Report

Blind-graded every already-graded cell with `claude-opus-4-8` and measured agreement against Jon's verdicts. Auditions Opus as a possible pre-grader -- the frozen gpt-5-mini judge was not touched. Full method: `docs/plan-opus-grader-calibration.md`.

## Headline

- **Primary set** (Jon's direct hand-grades, N=106): **81/106 (76.4%) agreement**
- **Secondary set** (auto-transferred-by-transitivity, N=194): 167/194 (86.1%) agreement
- **Combined** (N=300): 248/300 (82.7%) agreement
- **Correct/partial boundary agreement** (primary, N=90): 75/90 (83.3%) -- 1 correct-to-partial flips, 8 partial-to-correct flips
- **Reference yardstick:** the frozen gpt-5-mini judge earned trust at **95% agreement** with **0/21** live-audit errors -- shown for comparison only, not an auto-adopt threshold.
- **Coverage:** 300 graded / 0 errors out of 300 total comparison cells (300 = 6 arms x 50 questions).
- **Cost:** $3.41 (560,407 input + 24,178 output tokens, claude-opus-4-8 at $5.00/$25.00 per MTok)

## Confusion matrix -- primary set (N=106)

| Jon verdict \ Opus verdict | correct | partial | wrong |
|---|---|---|---|
| **correct** | 75 | 1 | 4 |
| **partial** | 8 | 0 | 2 |
| **wrong** | 9 | 1 | 6 |

## Confusion matrix -- secondary set (N=194)

| Jon verdict \ Opus verdict | correct | partial | wrong |
|---|---|---|---|
| **correct** | 164 | 0 | 11 |
| **partial** | 5 | 0 | 2 |
| **wrong** | 8 | 1 | 3 |

## Errors

*None -- every cell in the comparison set was graded or the call was retried to a result.*

## Patterns in the disagreements (quick read, verify against the table)

- **No-gold-rule blind spot, 8 cells across 4 questions (c002, c010, c012, c015):** these card questions have an empty gold list (`cards.jsonl` rows Jon graded on faithfulness, not rules-recall), so the grader has no rule text to check substance against -- it can only judge internal coherence. Opus upgraded these from Jon's wrong to correct because the answer read as coherent even though it was substantively wrong. This is the single largest disagreement driver and is inherent to the blind-input spec (no card oracle/rulings text was given to the grader, per the plan), not a script bug.
- **Self-contradiction catches (a real win):** on several cells (c006, c009, c010, c013, c019) Opus caught an answer's headline conclusion contradicting its own body text and correctly marked it wrong -- these look like genuine coherence-check value, not noise.
- **Correct/partial boundary skews lenient:** 8 of the 9 boundary flips in the primary set are partial-to-correct -- Opus more forgiving than Jon -- vs. only 1 the other way, across questions c011, c014, c015, c018, q012, q014. Consistent with the rubric's correct-with-note relaxation in spirit, but worth checking whether Opus is over-applying it to real incompleteness rather than reserving it for genuine undisclosed-assumption cases like c004.
- **q026 ("who gets priority after a non-active player casts a spell") recurs as a correct-to-wrong flip on 3 different arms' answers**, and **q012 ("do non-creature artifacts die") recurs as correct-to-wrong on 3 arms plus one partial-to-correct on a 4th** -- worth a first look, since the same gold rule (117.3c / 700.4) is driving repeat disagreement across otherwise-independent answers.

## Full disagreement list

Primary set:

| Set | Arm | Q | Question | Jon | Opus | Opus's reason |
|---|---|---|---|---|---|---|
| primary | deepseek-v3-2 | c004 | My opponent's [Grizzly Bears] has 2 damage marked on it. Do state-base... | wrong | correct | Correctly concludes SBAs don't check during resolution, so Bears isn't destroyed until Lightning Bolt finishes resolving, consistent with 704.3, 120.5, 117.2d, 704.5g. |
| primary | deepseek-v3-2 | c006 | I cast a sorcery with buyback and pay its buyback cost, then copy that... | correct | wrong | Answer concludes zero copies return to hand, but its own reasoning shows the original card returns to hand (one card), making the final tally self-contradictory and substantively incorrect on the count asked. |
| primary | deepseek-v3-2 | c011 | My cascade spell exiles cards until it hits [Valki, God of Lies], whos... | wrong | correct | The core conclusions are right per 702.85a: Valki//Tibalt's mana value is determined by front face (2), so it's a legal hit and the resulting spell's MV is still 2 even when cast as Tibalt, permitting the free cast; the front-face-MV rule for MDFCs is standard and the answer applies it correctly. |
| primary | deepseek-v3-2 | c012 | I cast [Emrakul, the Promised End]. With its cast trigger on the stack... | wrong | correct | Answer is internally coherent and directly responsive: one controlled turn (overlapping effects overwrite), a second Emrakul token from copying the spell, and no extra control trigger since the copy isn't cast; no gold text provided so substance unverified beyond coherence. |
| primary | deepseek-v3-2 | c014 | An opponent controls an untapped [Trinisphere], and I have a permanent... | partial | correct | Answer is internally coherent and directly responsive: X=0 costs 3 mana for 0 tokens due to Trinisphere floor, and X=2 gives 2 tokens for the same 3 mana; the reasoning about cost reduction, Trinisphere, and X being freely choosable is consistent (substance not rule-verifiable here as no gold text provided). |
| primary | deepseek-v3-2 | c015 | [Grist, the Hunger Tide] is in my graveyard. Can I return it with [Ani... | partial | correct | Answer is internally coherent, directly responsive, and walks through a consistent sequence; no gold rule text provided to verify substance, so coherence is the basis. |
| primary | deepseek-v3-2 | c019 | I activate my [Flooded Strand]'s ability, then activate [Gogo, Master ... | correct | wrong | Each Flooded Strand copy is a separate ability that resolves independently, each requiring its own sacrifice-and-search; the answer's claim that all three merge into a single search under 701.23h and yield three lands is an unsupported/incorrect application, and the copies would need the sacrifice cost which was already paid only once. |
| primary | deepseek-v3-2 | q008 | can I sacrifice an evoked creature before that creature's evoke trigge... | wrong | correct | The answer correctly concludes you cannot sacrifice the creature before the evoke trigger resolves, since sacrifice happens during the trigger's resolution and players can't act mid-resolution; consistent with 702.74a and 603.3, though it cites some rules whose text wasn't provided. |
| primary | deepseek-v3-2 | q026 | when someone other than the active player casts a spell, who gets prio... | correct | wrong | Per 117.3c, the player who casts a spell receives priority afterward (the non-active player), but the answer says the active player gets priority first. |
| primary | deepseek-v4-flash | c002 | My [Charging Rhino] has trample and is blocked by [Vampire Nighthawk],... | wrong | correct | Answer is coherent, directly responsive, and self-consistent: only 1 damage need be assigned to the deathtouch blocker before trampling the rest; no gold rule text provided to verify substance beyond coherence. |
| primary | deepseek-v4-flash | c011 | My cascade spell exiles cards until it hits [Valki, God of Lies], whos... | partial | correct | Under 702.85a cascade uses mana value; the answer correctly concludes Valki is a legal hit (front-face MV 2) and you can only cast Valki, not Tibalt, which is consistent with the rule text and the cited DFC rules. |
| primary | deepseek-v4-flash | q026 | when someone other than the active player casts a spell, who gets prio... | correct | wrong | Question asks who gets priority immediately after a nonactive player casts a spell; per 117.3c the caster (nonactive player) retains priority, but the answer's main conclusion is that the active player gets priority, conflating resolution (117.3b) with the post-cast priority the question asks about. |
| primary | deepseek-v4-pro | q014 | what are the steps in combat and when do I have priority as the defend... | partial | correct | Correctly lists the five combat steps per 506.1 and correctly explains defending player gets priority after active player passes per 117.3a; extra multiplayer detail is consistent and not contradictory. |
| primary | gemini-flash-lite | c002 | My [Charging Rhino] has trample and is blocked by [Vampire Nighthawk],... | wrong | correct | Answer is coherent and responsive: correctly reasons that deathtouch makes 1 damage lethal, so only 1 must be assigned before trampling over; no gold rule text provided to verify substance further. |
| primary | gemini-flash-lite | c010 | I cast [Emrakul, the Promised End]. In response to its cast trigger, m... | wrong | correct | Answer is internally coherent and directly responsive: protection only applies on battlefield so it can be targeted on the stack, and countering it means the control effect doesn't happen; no gold rule text provided to verify substance beyond coherence. |
| primary | gemini-flash-lite | c014 | An opponent controls an untapped [Trinisphere], and I have a permanent... | wrong | partial | Cost/token analysis is internally coherent and responsive, but it dodges the explicit 'what X should you actually choose' question by punting entirely, and the reduction only applies once (X=0 gives {G}{G}, reduced to {G}, then Trinisphere bumps to {3}) which means X=2 gets the same {3} cost for 2 tokens — a substantively important value point the answer omits. |
| primary | gemini-flash-lite | c015 | [Grist, the Hunger Tide] is in my graveyard. Can I return it with [Ani... | wrong | correct | Answer is internally coherent and directly responsive: Grist counts as a creature everywhere except the battlefield, so Animate Dead can target it in the graveyard; no gold rule text provided to verify substance beyond coherence. |
| primary | gemini-flash-lite | c018 | I cast [Clone]. When and how do I choose what it copies, and can my op... | partial | correct | Answer is coherent, directly responsive: choice made as replacement effect on ETB (not on cast), not a target, so opponents can't respond to the choice; no gold rule text provided so substance not independently verified. |
| primary | gemini-flash-lite | q014 | what are the steps in combat and when do I have priority as the defend... | partial | wrong | Answer misstates 117.3a: the ACTIVE player receives priority at the beginning of steps, not the defending/nonactive player; the defending player gets priority only after the active player passes. |
| primary | gemini-flash-lite | q021 | what happens during the cleanup step? | correct | partial | Correctly covers 514.2 damage removal and effects ending, but omits the discard-to-hand-size turn-based action from 514.1 which the gold requires. |
| primary | gemini-flash-lite | q028 | can I hold priority to cast more spells after I've cast one or more sp... | wrong | correct | Per 117.3c, after casting a spell the player receives priority again and can cast more spells; answer confirms this correctly despite extra tangent about resolution-cast spells. |
| primary | gpt-5-mini | c014 | An opponent controls an untapped [Trinisphere], and I have a permanent... | partial | correct | Answer is internally coherent and directly responsive: X=0 costs 3 mana (Trinisphere floor after reduction) for zero tokens, and correctly recommends X=1 to get a token for the same 3-mana outlay; no gold text to verify substance, but the reasoning is consistent and non-contradictory. |
| primary | gpt-5-mini | q012 | do non-creature artifacts die? | partial | correct | Per 700.4, 'dies' means put into graveyard from battlefield, which applies to any permanent including non-creature artifacts; answer correctly affirms yes. |
| primary | gpt-5-mini | q014 | what are the steps in combat and when do I have priority as the defend... | partial | correct | Correctly lists the five combat steps with skip/first-strike conditions (506.1) and correctly states the active player receives priority at start of steps after turn-based actions/triggers (117.3a); the 'answered:false' flag and hedging about passing order don't undermine the substantively correct conclusions from the gold rules. |
| primary | gpt-5-mini | q016 | can I respond to a cost being paid? | partial | wrong | The correct answer is no—casting a spell/paying costs happens as a single uninterruptible action with no priority window, which the gold rules support; the bot refused to answer and left it unresolved. |

Secondary set:

| Set | Arm | Q | Question | Jon | Opus | Opus's reason |
|---|---|---|---|---|---|---|
| secondary | deepseek-v4-flash | c004 | My opponent's [Grizzly Bears] has 2 damage marked on it. Do state-base... | wrong | correct | Correctly explains SBAs check only when a player would get priority, not during Lightning Bolt's resolution, so the Bears die after Bolt resolves; consistent with 704.3/704.4/117.2d/704.5g. |
| secondary | deepseek-v4-flash | c006 | I cast a sorcery with buyback and pay its buyback cost, then copy that... | correct | wrong | The question asks how many copies of the card end up in hand; the buyback original card returns to hand, so the answer is one, but the answer's headline conclusion states 'Zero copies of the card end up back in your hand,' which is self-contradictory with its own body text acknowledging the original returns. |
| secondary | deepseek-v4-flash | c010 | I cast [Emrakul, the Promised End]. In response to its cast trigger, m... | correct | wrong | The answer is internally self-contradictory: it opens with 'No, your opponent cannot target Emrakul' but then concludes the opponent CAN target it, directly contradicting the stated bottom-line answer. |
| secondary | deepseek-v4-flash | c012 | I cast [Emrakul, the Promised End]. With its cast trigger on the stack... | wrong | partial | Core conclusions (no cast trigger from copying the spell, get a second Emrakul token) are coherent and responsive, but the answer is muddled and self-contradictory on the turn-control question—it waffles between 'one turn' and two extra turns and openly second-guesses itself ('extra turn? Actually...'), leaving the control-count answer materially unclear. |
| secondary | deepseek-v4-flash | c013 | I've imprinted a creature on [Mimic Vat] and activate its ability to m... | correct | wrong | The answer is fatally self-contradictory: it opens with a bold 'No, you get only one token' then reverses to 'yes, two tokens' mid-reasoning, failing the coherence check the rubric requires when no gold rule text is provided. |
| secondary | deepseek-v4-flash | c014 | An opponent controls an untapped [Trinisphere], and I have a permanent... | partial | correct | Answer is internally coherent, correctly analyzes Trinisphere's floor of 3 mana vs cost reduction at each X, and reaches the sensible conclusion that X=2 gives best value for 3 mana; no gold rule text provided to check substance further, but the reasoning is consistent and directly responsive. |
| secondary | deepseek-v4-flash | c015 | [Grist, the Hunger Tide] is in my graveyard. Can I return it with [Ani... | partial | correct | Answer is internally coherent and directly responsive: yes it can be returned since Grist is a creature card in graveyard, enters as a non-creature planeswalker, Animate Dead can't enchant it and goes to graveyard, triggering sacrifice; no gold rule text provided to verify substance beyond coherence. |
| secondary | deepseek-v4-flash | c019 | I activate my [Flooded Strand]'s ability, then activate [Gogo, Master ... | correct | wrong | The answer is self-contradictory and gives a confused final number: it opens saying 'two lands' but the reasoning arrives at three total (one original + two copies), yet Flooded Strand's ability sacrifices it, so the numeric conclusion is muddled and incoherent. |
| secondary | deepseek-v4-pro | c005 | It's my upkeep. My [Phyrexian Arena]'s beginning-of-upkeep trigger and... | correct | wrong | Answer is internally incoherent: it claims 'you don't get to choose the order' yet as active player you order your own triggers; and the standard APNAP handling (active player's triggers go on stack first, then nonactive player's, resolving in reverse) means the active player's trigger resolves first, contradicting the answer's claim the opponent's resolves first. |
| secondary | deepseek-v4-pro | c012 | I cast [Emrakul, the Promised End]. With its cast trigger on the stack... | wrong | correct | Answer is internally coherent and directly responsive: controls 1 turn (control effects overwrite), 2 extra turns, token second Emrakul, and no new cast trigger since copies aren't cast; no gold rule text provided to verify substance beyond coherence. |
| secondary | deepseek-v4-pro | c014 | An opponent controls an untapped [Trinisphere], and I have a permanent... | partial | wrong | The X=0 case claims cost becomes {3} generic, but Trinisphere sets total to 3 mana while preserving colored requirements—it should be {1}{G}{G}, not three generic; also the Trinisphere payment description is incorrect. |
| secondary | deepseek-v4-pro | c015 | [Grist, the Hunger Tide] is in my graveyard. Can I return it with [Ani... | partial | correct | Answer is internally coherent, directly responsive, and consistent with Grist being a creature only outside the battlefield; no gold rule text provided to verify substance beyond coherence. |
| secondary | deepseek-v4-pro | q012 | do non-creature artifacts die? | correct | wrong | Rule 700.4 defines 'dies' as being put into a graveyard from the battlefield with no restriction to creatures/planeswalkers, so the claim that non-creature artifacts don't die is not supported by the provided text. |
| secondary | gemini-flash-lite | c004 | My opponent's [Grizzly Bears] has 2 damage marked on it. Do state-base... | wrong | correct | Correctly explains 2 damage on a 2/2 is not lethal (toughness 2, needs >=2... but 2>=2), wait—actually the answer's conclusion that the bear won't die from 2 damage is the right substantive point since the question presupposes it hasn't died yet, and SBAs are checked on priority not mid-resolution. |
| secondary | gemini-flash-lite | c009 | My own [Banishing Light] has an opponent's creature exiled. On my oppo... | correct | wrong | Answer is self-contradictory: it states the creature will not return when Banishing Light phases out, then claims it returns when Banishing Light phases back in—but the exile effect from Banishing Light does not persist through phasing, and the answer's internal logic conflicts (the phase-back-in reasoning contradicts its own premise that phasing isn't leaving the battlefield). |
| secondary | gemini-flash-lite | c011 | My cascade spell exiles cards until it hits [Valki, God of Lies], whos... | wrong | correct | Per 702.85a, mana value determines both the hit and castability; using Valki's front-face mana value of 2, the answer correctly concludes it's a legal hit and castable if cascade MV > 2, which lets Tibalt be cast for free. |
| secondary | gemini-flash-lite | c012 | I cast [Emrakul, the Promised End]. With its cast trigger on the stack... | wrong | correct | Answer coherently concludes: one controlled turn (copying trigger not casting doesn't create new control trigger, so both copies give... actually it says two trigger instances but one controlled turn), a second Emrakul token, and copying the spell gives no new cast trigger since copies aren't cast; internally consistent and directly responsive, though I cannot verify rules substance without gold text. |
| secondary | gemini-flash-lite | q012 | do non-creature artifacts die? | correct | wrong | Per 700.4, 'dies' means any permanent put into graveyard from battlefield, so non-creature artifacts do die; the answer wrongly restricts 'dies' to creatures/planeswalkers, contradicting the provided rule text. |
| secondary | gemini-flash-lite | q026 | when someone other than the active player casts a spell, who gets prio... | correct | wrong | Per 117.3c, the player who cast the spell (the non-active player) retains priority afterward, but the answer says the active player gets priority first. |
| secondary | gpt-5-mini | c004 | My opponent's [Grizzly Bears] has 2 damage marked on it. Do state-base... | wrong | correct | Bears is 2/2 with only 2 damage marked, which is not lethal (2<2 is false, but 2>=2 IS lethal); the answer correctly explains SBAs aren't checked mid-resolution so it won't die before Bolt resolves, and that if lethal damage already existed it would have died at the prior check — substantively correct on the timing question. |
| secondary | gpt-5-mini | c008 | My [Fiend Hunter]'s enters-the-battlefield ability is on the stack, ab... | correct | wrong | The copy of Fiend Hunter's ETB ability is not itself a linked ability tied to Fiend Hunter's LTB trigger; the actual rules interaction (widely known but not provided here) is that only the creature exiled by the original ability returns, not the copy's target—the answer's coherent-sounding claim that both return relies on linked-ability reasoning the copy doesn't satisfy, making its conclusion a substantive rules error. |
| secondary | gpt-5-mini | c011 | My cascade spell exiles cards until it hits [Valki, God of Lies], whos... | wrong | correct | MDFC mana value uses front face (Valki=2) per 712.8c, and the Valki//Tibalt ruling permits casting the back face when an effect lets you cast without regard to mana cost; answer correctly concludes legal hit and free Tibalt cast provided cascade MV > 2. |
| secondary | gpt-5-mini | c015 | [Grist, the Hunger Tide] is in my graveyard. Can I return it with [Ani... | partial | correct | The answer is internally coherent and directly responsive: it explains Grist is a creature card in the graveyard (targetable), but becomes only a planeswalker on the battlefield so Animate Dead can't stay attached, gets bin'd, and its LTB trigger sacrifices Grist; no gold rule text provided to verify substance beyond coherence. |
| secondary | sonnet-v2 | c012 | I cast [Emrakul, the Promised End]. With its cast trigger on the stack... | wrong | correct | No gold rules provided, but the answer is internally coherent, directly responsive to all three sub-questions (one controlled turn plus two extra turns, second Emrakul token, no new cast trigger), and not self-contradictory; substance not rule-verifiable here. |
| secondary | sonnet-v2 | c014 | An opponent controls an untapped [Trinisphere], and I have a permanent... | partial | correct | Answer is internally coherent and directly responsive: X=0 costs {1}{G}{G} for zero tokens due to Trinisphere floor, and X=2 optimally offsets the tax for same cost with two tokens; no gold rule text provided to verify substance beyond coherence, which holds. |
| secondary | sonnet-v2 | c015 | [Grist, the Hunger Tide] is in my graveyard. Can I return it with [Ani... | partial | wrong | Answer's final claim is self-contradictory and rules-wrong: Animate Dead falling off leaves Grist a planeswalker on the battlefield with no aura, so its trigger cannot sacrifice it—Grist stays, not sacrificed as claimed. |
| secondary | sonnet-v2 | q012 | do non-creature artifacts die? | correct | wrong | The provided rule 700.4 defines 'dies' as simply 'put into a graveyard from the battlefield' with no restriction to creatures/planeswalkers; the answer's claim that the term is reserved for those types contradicts the given text, so a non-creature artifact put into a graveyard from the battlefield does die under 700.4. |

## Grader blindness -- example prompt

Shown as evidence: the grader prompt never contains a verdict, a grading note, or any other arm's answer -- only the question, the gold rule numbers/match-semantics/full text (or a no-gold-recorded note), and the one arm's own answer JSON.

**System prompt** (fixed, shown once):

```
You are a blind grading auditor for an MTG (Magic: The Gathering) rules-RAG bot's answer evals. You are auditioning as a possible pre-grader for future evals -- your verdicts will be compared against a human grader's hand-grades to measure agreement, so grade as carefully and consistently as you would if this were the real job.

GROUNDING RULE (the same law the bot itself lives under): base your verdict ONLY on the rule text provided below and the question as asked. Never use your own memory or general knowledge of Magic: The Gathering rules to override, supplement, or second-guess the provided rule text -- if the provided text doesn't settle something the answer claims, say so in your reason instead of falling back on what you recall about the actual rule. You are NOT told what any human grader concluded about this cell -- grade fresh, blind.

RUBRIC (verbatim, distilled from the project's grading history, including a 2026-07-22 rubric ruling on undisclosed assumptions):
- CORRECT: the answer reaches the right substantive conclusion under a reasonable reading of the question, consistent with the provided rule text (or, when no gold rule text is provided below, the answer is internally coherent, directly responsive to the question, and not self-contradictory). A correct answer that silently assumes away an ambiguity the asker didn't resolve STILL grades CORRECT -- note the assumption in your reason, but do not mark it partial just because it didn't flag the ambiguity or ask a clarifying question first. The disclosure bar belongs to a future clarify-then-escalate feature, not to this verdict.
- PARTIAL: the answer is materially incomplete or half-right on the substance -- it gets part of a multi-part question right and part wrong or missing, or its core conclusion is right but it omits a substantively important piece the question needed. (Omitting a disclosure/caveat about an assumption is NOT this -- that's still correct, per the rule above.)
- WRONG: the answer makes a substantive rules error -- it reaches the wrong conclusion, or relies on a rule in a way the provided text doesn't support.

For each cell you will get: the question; the gold rule numbers and how they combine (any/all/groups) with their full corpus text (or a note that no gold rules were recorded for this question); and the arm's complete answer (answered flag, text, citations). Output a verdict (correct/partial/wrong) and a ONE-LINE reason a human grader could spot-check in a few seconds.
```

**User prompt for `deepseek-v3-2` / `q003`** (note: no verdict, no note, no other arm's answer anywhere in this):

```
Question: is storm a triggered ability that can be countered?

Gold rules:
Match semantics: all
  ALL of these are required: 702.40a, 113.9

Full text of each gold rule:
[702.40a] Storm Storm is a triggered ability that functions on the stack. “Storm” means “When you cast this spell, copy it for each other spell that was cast before it this turn. If the spell has any targets, you may choose new targets for any of the copies.”
[113.9] Activated and triggered abilities on the stack aren’t spells, and therefore can’t be countered by anything that counters only spells. Activated and triggered abilities on the stack can be countered by effects that specifically counter abilities. Static abilities don’t use the stack and thus can’t be countered at all.

Arm's answer:
answered: True
citations: ['702.40a', '113.9']
text: Yes, Storm is a triggered ability that can be countered. Storm is defined as a triggered ability that functions on the stack [702.40a]. Triggered abilities on the stack are not spells, but they are objects on the stack that can be countered by effects that specifically counter abilities [113.9]. Therefore, while Storm cannot be countered by effects that counter only spells, it can be countered by effects that counter abilities.

Grade this answer per the rubric. Output your verdict and a one-line reason.
```
