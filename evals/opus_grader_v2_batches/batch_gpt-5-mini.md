# Opus-Grader Calibration v2 -- Batch: gpt-5-mini

50 cells, blind. You are auditioning as a possible pre-grader for future evals (docs/plan-opus-grader-calibration.md). For EACH cell below, grade the arm's answer against the rubric using ONLY the question, the gold rule text (or card data) provided in that cell, and the arm's own answer, and output a correct/partial/wrong verdict plus a one-line reason -- exact output format is at the end of this file. You are never shown a human verdict or grading note anywhere in this file; grade fresh, blind, per cell.

## Grading rubric (verbatim from v1, evals/opus_grader_calibration.py)

```
You are a blind grading auditor for an MTG (Magic: The Gathering) rules-RAG bot's answer evals. You are auditioning as a possible pre-grader for future evals -- your verdicts will be compared against a human grader's hand-grades to measure agreement, so grade as carefully and consistently as you would if this were the real job.

GROUNDING RULE (the same law the bot itself lives under): base your verdict ONLY on the rule text provided below and the question as asked. Never use your own memory or general knowledge of Magic: The Gathering rules to override, supplement, or second-guess the provided rule text -- if the provided text doesn't settle something the answer claims, say so in your reason instead of falling back on what you recall about the actual rule. You are NOT told what any human grader concluded about this cell -- grade fresh, blind.

RUBRIC (verbatim, distilled from the project's grading history, including a 2026-07-22 rubric ruling on undisclosed assumptions):
- CORRECT: the answer reaches the right substantive conclusion under a reasonable reading of the question, consistent with the provided rule text (or, when no gold rule text is provided below, the answer is internally coherent, directly responsive to the question, and not self-contradictory). A correct answer that silently assumes away an ambiguity the asker didn't resolve STILL grades CORRECT -- note the assumption in your reason, but do not mark it partial just because it didn't flag the ambiguity or ask a clarifying question first. The disclosure bar belongs to a future clarify-then-escalate feature, not to this verdict.
- PARTIAL: the answer is materially incomplete or half-right on the substance -- it gets part of a multi-part question right and part wrong or missing, or its core conclusion is right but it omits a substantively important piece the question needed. (Omitting a disclosure/caveat about an assumption is NOT this -- that's still correct, per the rule above.)
- WRONG: the answer makes a substantive rules error -- it reaches the wrong conclusion, or relies on a rule in a way the provided text doesn't support.

For each cell you will get: the question; the gold rule numbers and how they combine (any/all/groups) with their full corpus text (or a note that no gold rules were recorded for this question); and the arm's complete answer (answered flag, text, citations). Output a verdict (correct/partial/wrong) and a ONE-LINE reason a human grader could spot-check in a few seconds.
```

## Cells

### Cell 1: id=q001

Question: Do creatures phasing back in trigger enter the battlefield abilities?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: 702.26d

Full text of each gold rule:
[702.26d] Phasing The phasing event doesn’t actually cause a permanent to change zones or control, even though it’s treated as though it’s not on the battlefield and not under its controller’s control while it’s phased out. Zone-change triggers don’t trigger when a permanent phases in or out. Tokens continue to exist on the battlefield while phased out. Counters and stickers remain on a permanent while it’s phased out. Effects that check a phased-in permanent’s history won’t treat the phasing event as having caused the permanent to leave or enter the battlefield or its controller’s control.

Arm's answer:
answered: True
citations: ['[702.26a]', '[702.26b]', '[702.26c]', '[702.26d]', '[603.6a]', '[703.4a]', '[502.1]']
text: Short answer: No. Phasing does not cause a permanent to change zones, so it does not trigger enters-the-battlefield (ETB) or other zone-change triggers when a creature phases in.

Definition of phasing (key points you need to know):
- Phasing is a status and a turn-based action that changes a permanent’s phased in/phased out status during the untap step; phased-in permanents with phasing phase out and phased-out permanents that phased out under that player phase in simultaneously as a turn-based action (untap step) [702.26a][703.4a][502.1].
- A phased-out permanent is treated as though it does not exist for most purposes; it remains on the battlefield (tokens continue to exist there) and keeps counters and stickers, but it isn’t considered to have left the battlefield or changed controllers [702.26b][702.26d][702.26c].

Why ETB abilities don’t trigger when a creature phases in:
- ETB abilities are zone-change triggers that trigger when a permanent enters the battlefield [603.6a].
- The phasing event does not actually change a permanent’s zone or its controller, and zone-change triggers don’t trigger when a permanent phases in or out [702.26d].

Practical ruling you can act on: If a creature was phased out and then phases in (for example during the untap step), do not check for or put any enters-the-battlefield triggers on the stack for that creature. The creature did not “enter the battlefield,” so ETB effects don’t trigger [603.6a][702.26d].

---

### Cell 2: id=q002

Question: how does trample work with deathtouch?

Gold rules:
Match semantics: all
  ALL of these are required: 702.19b, 702.2c

Full text of each gold rule:
[702.19b] Trample The controller of an attacking creature with trample first assigns damage to the creature(s) blocking it. Once all those blocking creatures are assigned lethal damage, any excess damage is assigned as its controller chooses among those blocking creatures and the player, planeswalker, or battle the creature is attacking. When checking for assigned lethal damage, take into account damage already marked on the creature and damage from other creatures that’s being assigned during the same combat damage step, but not any abilities or effects that might change the amount of damage that’s actually dealt. The attacking creature’s controller need not assign lethal damage to all those blocking creatures but in that case can’t assign any damage to the player or planeswalker it’s attacking. A 2/2 creature that can block an additional creature blocks two attackers: a 1/1 with no abilities and a 3/3 with trample. The active player could assign 1 damage from the first attacker and 1 damage from the second to the blocking creature, and 2 damage to the defending player from the creature with trample. A 6/6 green creature with trample is blocked by a 2/2 creature with protection from green. The attacking creature’s controller must assign at least 2 damage to the blocker, even though that damage will be prevented by the blocker’s protection ability. The attacking creature’s controller can divide the rest of the damage as they choose between the blocking creature and the defending player.
[702.2c] Deathtouch Any nonzero amount of combat damage assigned to a creature by a source with deathtouch is considered to be lethal damage for the purposes of determining if excess damage is being dealt.

Arm's answer:
answered: True
citations: ['[702.19a]', '[702.19b]', '[702.2c]', '[120.4a]', '[702.19c]', '[302.7]', '[702.2b]', '[704.5h]', '[702.19d]', '[Lethal Damage]', '[Excess Damage]']
text: Definitions you need:
- Deathtouch: If a creature with toughness greater than 0 has been dealt damage by a source with deathtouch since the last time state-based actions were checked, that creature is destroyed as a state-based action. Damage dealt to creatures is marked on them (and removed by regeneration or cleanup) (see rules cited). [Defines effect of deathtouch and damage marking.]
- Trample: A static ability that changes how an attacking creature assigns its combat damage; when assigning combat damage an attacking creature with trample must assign lethal damage to the creatures blocking it first, then may assign any excess to the defending player or planeswalker (with a special variant for planeswalkers).
- Lethal damage / Excess damage: Lethal damage is an amount greater than or equal to a creature’s toughness; excess damage is damage greater than lethal (for a planeswalker, damage greater than its loyalty).

How they interact (what a player does when assigning combat damage):
1) When you assign combat damage with an attacking creature that has both trample and deathtouch, treat any nonzero amount of combat damage assigned to a blocking creature by that deathtouch source as sufficient to be "lethal" for the purposes of determining excess damage. Therefore you need only assign 1 point of damage to each blocking creature (subject to damage already marked on them or damage being assigned to them at the same time) to meet the “lethal damage” requirement and allow excess to be assigned to the defending player or planeswalker. [702.19a] [702.19b] [702.2c] [120.4a]
2) After you have assigned that lethal amount to all blocking creatures, you may assign any remaining damage as you choose among the blocking creatures and the defending player or planeswalker (or the planeswalker’s controller, for trample over planeswalkers). If the creature is attacking a planeswalker, you must assign damage at least equal to that planeswalker’s loyalty (taking into account other creatures assigning damage at the same time) before assigning further excess to the planeswalker’s controller; deathtouch only affects the lethal amount for creatures, not the planeswalker’s loyalty requirement. [702.19b] [702.19c] [120.4a]
3) Practical effect: an attacking creature with trample and deathtouch that has, for example, power 5 and is blocked by a single creature will normally assign 1 damage to that blocker (counted as lethal because of deathtouch) and can assign the other 4 to the defending player or planeswalker, unless damage already marked or other simultaneous damage changes the lethal calculations. [702.19b] [702.2c] [302.7]

Notes and edge details covered by the rules cited:
- The 1-point lethal threshold from deathtouch is used only for determining how much must be assigned to blockers when computing excess; state-based actions will still destroy a creature dealt damage by deathtouch as described. [702.2b] [704.5h] [120.4a]
- If the attacking creature is blocked but there are no creatures blocking it when damage is assigned, its damage is assigned to the defending player and/or planeswalker as though all blocking creatures had been assigned lethal damage. [702.19d]

You can act on these rules: when assigning trample+deathtouch damage, assign 1 to each blocker (or less if other marked/simultaneous damage covers lethal), then send the rest where you want subject to the planeswalker loyalty rule if applicable.

---

### Cell 3: id=q003

Question: is storm a triggered ability that can be countered?

Gold rules:
Match semantics: all
  ALL of these are required: 702.40a, 113.9

Full text of each gold rule:
[702.40a] Storm Storm is a triggered ability that functions on the stack. “Storm” means “When you cast this spell, copy it for each other spell that was cast before it this turn. If the spell has any targets, you may choose new targets for any of the copies.”
[113.9] Activated and triggered abilities on the stack aren’t spells, and therefore can’t be countered by anything that counters only spells. Activated and triggered abilities on the stack can be countered by effects that specifically counter abilities. Static abilities don’t use the stack and thus can’t be countered at all.

Arm's answer:
answered: True
citations: ['702.40a', '603.1a', '601.2a', '603.3', '603.3d', '113.9']
text: Short answer: Yes — Storm is a triggered ability that goes on the stack, and because it’s an ability on the stack (not a spell) it can’t be countered by effects that only counter spells, but it can be countered by effects that specifically counter abilities.

Why: "Storm" is a triggered ability that functions on the stack (702.40a). A triggered ability is an ability with a trigger condition and an effect that goes on the stack when it triggers (603.1a). When you cast the spell that has storm, the storm ability triggers and that triggered ability is put on the stack as an object that isn’t a card (601.2a; 603.3 / 603.3d). Because activated and triggered abilities on the stack aren’t spells, they aren’t affected by effects that counter only spells; such abilities can, however, be countered by effects that specifically counter abilities (113.9).

---

### Cell 4: id=q004

Question: can i use cards with hybrid mana symbols in a commander deck that only has one of those colors?

Gold rules:
Match semantics: all
  ALL of these are required: 202.2d, 903.4

Full text of each gold rule:
[202.2d] An object is the color or colors of the mana symbols in its mana cost, regardless of the color of its frame. An object with one or more hybrid mana symbols and/or Phyrexian mana symbols in its mana cost is all of the colors of those mana symbols, in addition to any other colors the object might be. (Most cards with hybrid mana symbols in their mana costs are printed in a two-tone frame. See rule 107.4e.)
[903.4] The Commander variant uses color identity to determine what cards can be in a deck with a certain commander. The color identity of a card is the color or colors of any mana symbols in that card’s mana cost or rules text, plus any colors defined by its characteristic-defining abilities (see rule 604.3) or color indicator (see rule 204). Bosh, Iron Golem is a legendary artifact creature with mana cost {8} and the ability “{3}{R}, Sacrifice an artifact: Bosh, Iron Golem deals damage equal to the sacrificed artifact’s mana value to any target.” Bosh’s color identity is red.

Arm's answer:
answered: True
citations: ['[903.5c]', '[903.4]', '[202.2d]', '[107.4e]', '[702.124c]']
text: Short answer: No — if a hybrid mana symbol on a card contains a color your commander doesn’t have, that card’s color identity includes that other color and the card can’t be in your Commander deck. Definitions and reasoning: 

- Color identity: the color(s) of any mana symbols in a card’s mana cost or rules text (plus colors from characteristic-defining abilities or a color indicator). A card’s color identity must be a subset of its commander’s color identity for it to be legal in that commander’s deck [903.4].

- Hybrid mana symbol: a mana symbol that can be paid in one of two ways (for example {W/U} or {R/G}); a hybrid symbol is all of its component colors [107.4e]. An object with one or more hybrid mana symbols in its mana cost is considered to have all of those colors in its color identity [202.2d].

Therefore: because a hybrid symbol like {R/G} makes the card both red and green in color identity, 903.5c forbids putting that card into a deck whose commander is only red (or only green). Example: a mono-red commander cannot have cards whose mana cost includes {R/G}, because those cards’ color identity includes green in addition to red [903.5c][202.2d][107.4e][903.4].

Special note: monocolored hybrid symbols (for example {2/R}) are listed as hybrid symbols but only include the one color (red) as their colored component, so they don’t add an additional color to the card’s color identity beyond that one color; such a card would be legal in a commander that includes that single color (see 107.4e and 202.2d). 

Partner/Two-commanders case: if you have two commanders (Partner), references to your commander’s color identity use the combined color identities of both commanders, so a card whose hybrid symbols’ colors are covered by the combined identity can be included [702.124c][903.4].

---

### Cell 5: id=q005

Question: can I respond to the untap step?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: 502.4

Full text of each gold rule:
[502.4] No player receives priority during the untap step, so no spells can be cast or resolve and no abilities can be activated or resolve. Any ability that triggers during this step will be held until the next time a player would receive priority, which is usually during the upkeep step. (See rule 503, “Upkeep Step.”)

Arm's answer:
answered: True
citations: ['502.4', '117.3a', '503.1a', '703.4c', '731.2', '500.3']
text: Short answer: No. The untap step is a step during which no player receives priority, so you can’t cast spells or activate abilities then; any abilities that trigger during the untap step are held and put onto the stack at the beginning of the upkeep (before the active player gets priority).

Definitions and details you can act on:
- “Respond” here means casting spells or activating abilities in reaction to something during the untap step (i.e., using the game’s priority to put spells or activated abilities on the stack). Priority is the game’s mechanism that determines who may cast spells or activate abilities; which player has priority is described in rule [117.3a].
- The untap step is one of the game’s steps that gives no player priority ([500.3], [502.4]). That means “no spells can be cast or resolve and no abilities can be activated or resolve” during the untap step; triggered abilities that trigger during the untap step are held until players would next receive priority, normally at the beginning of the upkeep ([502.4], [503.1a]).
- The untap step includes turn-based actions such as phasing and the untap action itself; those occur during the untap step and any triggers they cause are treated the same way (see the turn-based action ordering in [703.4c] and the day/night check timing in [731.2]).
- When the upkeep begins, any abilities that triggered during the untap step (and any that triggered at the beginning of upkeep) are put onto the stack before the active player gets priority, and only then can players cast spells or activate abilities ([503.1a]).

Actionable takeaway: do not expect to be able to respond during the untap step itself; wait until the beginning of the upkeep, when the held triggers are put on the stack and players receive priority.


---

### Cell 6: id=q006

Question: are creatures still considered attacking creatures during the end of combat step?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: 511.3

Full text of each gold rule:
[511.3] As soon as the end of combat step ends, all creatures, battles, and planeswalkers are removed from combat. After the end of combat step ends, the combat phase is over and the postcombat main phase begins (see rule 505).

Arm's answer:
answered: True
citations: ['[Attacking Creature]', '[511.2]', '[511.1]', '[511.3]', '[506.4a]', '[500.5a]']
text: Definition: “Attacking creature” — A creature that has either been declared as part of a legal attack during the combat phase (once all costs to attack, if any, have been paid), or a creature that has been put onto the battlefield attacking. It remains an attacking creature until it’s removed from combat or the combat phase ends, whichever comes first. [Attacking Creature]

Answer: Yes. During the end of combat step creatures are still attacking creatures. The end of combat step is part of the combat phase, and creatures remain attacking until they’re removed from combat or the combat phase ends. “At end of combat” triggered abilities trigger as the end of combat step begins, and the active player gets priority once that step begins. Only when the end of combat step ends are all creatures removed from combat (and thus stop being attacking creatures). [511.2] [511.1] [511.3] [506.4a]

Practical summary for play: while the end of combat step is ongoing you can target or refer to creatures as attacking; “at end of combat” triggers see those creatures as attacking when they trigger at the start of that step. When the step finishes, the game removes creatures from combat and they cease to be attacking. [511.2] [511.3] [500.5a]

---

### Cell 7: id=q007

Question: Do you cast lands?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: 305.1

Full text of each gold rule:
[305.1] A player who has priority may play a land card from their hand during a main phase of their turn when the stack is empty. Playing a land is a special action; it doesn’t use the stack (see rule 116). Rather, the player simply puts the land onto the battlefield. Since the land doesn’t go on the stack, it is never a spell, and players can’t respond to it with instants or activated abilities.

Arm's answer:
answered: True
citations: ['701.18b', '601.1a', '701.18a', '116.2a', '305.1', '302.1', '202.1b', '305.9', '300.2a', '305.4', '305.3']
text: Short answer: No — you don’t cast lands. You play lands as a special action; they are not spells and aren’t cast. Definition and grounding from the rules:

- "Play" / "play a card": to play a card means to play it as a land or to cast it as a spell, whichever is appropriate (701.18b, 601.1a).
- "Play a land": to play a land is to put it onto the battlefield from the zone it’s in (usually your hand). Playing a land is a special action that doesn’t use the stack; a land played this way is never a spell (701.18a, 116.2a, 305.1).
- "Cast" (cast a spell): casting a spell (for example, casting a creature card) uses the stack (302.1). Because played lands aren’t spells, they aren’t cast.
- Additional relevant points: most land cards have no mana cost and are played without paying costs (202.1b, 305.1); an object that’s both a land and another card type can only be played as a land and can’t be cast as a spell (305.9, 300.2a); and effects that “put” lands onto the battlefield aren’t the same as playing a land (305.4). Also, playing a land is only possible when you have priority during a main phase, the stack is empty, and you haven’t already played a land that turn (701.18a, 116.2a, 305.3).

Practical ruling for a player: When you put a land from your hand onto the battlefield during your main phase, you are "playing" it (a special action), not casting it; you cannot cast a land.

---

### Cell 8: id=q008

Question: can I sacrifice an evoked creature before that creature's evoke triggered ability resolves?

Gold rules:
Match semantics: all
  ALL of these are required: 702.74a, 603.3

Full text of each gold rule:
[702.74a] Evoke Evoke represents two abilities: a static ability that functions in any zone from which the card with evoke can be cast and a triggered ability that functions on the battlefield. “Evoke [cost]” means “You may cast this card by paying [cost] rather than paying its mana cost” and “When this permanent enters, if its evoke cost was paid, its controller sacrifices it.” Casting a spell for its evoke cost follows the rules for paying alternative costs in rules 601.2b and 601.2f–h.
[603.3] Once an ability has triggered, its controller puts it on the stack as an object that’s not a card the next time a player would receive priority. See rule 117, “Timing and Priority.” The ability becomes the topmost object on the stack. It has the text of the ability that created it, and no other characteristics. It remains on the stack until it’s countered, it resolves, a rule causes it to be removed from the stack, or an effect moves it elsewhere.

Arm's answer:
answered: True
citations: ['702.74a', 'Evoke', '603.3d', '116.2e', '608.2d']
text: Short answer and definition
- “Evoke” — a permanent with evoke has a triggered ability that reads essentially, “When this permanent enters the battlefield, if its evoke cost was paid, its controller sacrifices it.” That is part of the evoke rules ([702.74a], [Evoke]).
- “Triggered ability” (for this case) — an ability that triggers when an event happens (the creature entering) and is then put onto the stack the next time a player would receive priority ([603.3d]).
Can you sacrifice it before the evoke trigger resolves?
- Yes. When the creature enters the battlefield its evoke triggered ability triggers ([702.74a]). That triggered ability is not resolved immediately; it is put onto the stack the next time a player would receive priority ([603.3d]). Before that triggered ability resolves (i.e., while players receive priority), a player may take actions they are allowed to take with priority (for example, activating an ability or using an effect that causes that creature to be sacrificed), and so the creature can be sacrificed then ([116.2e] establishes that special actions can be taken any time a player has priority; in general the trigger is put on the stack and there is an opportunity to act before it resolves per [603.3d]).
What happens when the evoke trigger later resolves?
- If the creature is no longer on the battlefield when the evoke triggered ability resolves, its instruction to sacrifice “it” can’t be carried out (the controller no longer controls that permanent), so the sacrifice part does nothing. The triggered ability still resolves (it is on the stack), but there is no legal sacrifice to perform — the player cannot choose an illegal sacrifice option ([608.2d]).
Practical result: you can sacrifice an evoked creature after it enters but before the evoke triggered ability resolves; doing so prevents the evoke trigger from causing an additional sacrifice when it later resolves.


---

### Cell 9: id=q009

Question: if a card loses all abilities, does that include keyword abilities?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: 702.1

Full text of each gold rule:
[702.1] Most abilities describe exactly what they do in the card’s rules text. Some, though, are very common or would require too much space to define on the card. In these cases, the object lists only the name of the ability as a “keyword”; sometimes reminder text summarizes the game rule.

Arm's answer:
answered: True
citations: ['[702.1]', '[113.10b]', '[613.1f]', '[113.12]']
text: Short answer: Yes. "Keyword abilities" are still abilities, so an effect that makes an object lose all abilities removes keyword abilities unless the effect or text instead sets a characteristic or states a quality.

Definition of key terms
- Keyword ability: an ability whose name appears as a keyword on the object rather than full rules text (see rule [702.1]).
- "Loses all abilities": an effect that removes abilities from an object (see rules below); such effects remove instances of abilities the object has.

Why: Rule [702.1] treats keywords as abilities. Effects that remove abilities remove those abilities (they remove all instances of an ability) as explained in rule [113.10b], and ability-adding/ability-removing effects (including keyword-related effects) are applied in layer 6 of the continuous-effects system (rule [613.1f]).

Exception: If something isn’t actually granting an ability but instead sets a characteristic or states a quality (for example, an effect that says a permanent "can’t be blocked" or "is red"), that isn’t an ability and so wouldn’t be removed by an effect that merely makes a permanent lose abilities (see rule [113.12]).

---

### Cell 10: id=q010

Question: can i draw cards if i'm already at my maximum hand size?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: 402.2

Full text of each gold rule:
[402.2] Each player has a maximum hand size, which is normally seven cards. A player may have any number of cards in their hand, but as part of their cleanup step, the player must discard excess cards down to the maximum hand size.

Arm's answer:
answered: True
citations: ['402.2', '514.1', '703.4n', '121.2', '121.5', '104.3c', '121.6a', '614.11a']
text: Short answer: Yes. Nothing in the provided rules forbids you from drawing cards while you already have your maximum hand size; the maximum hand size is enforced later during your cleanup step when you must discard down.

Definitions
- “Maximum hand size”: the number of cards a player may have before being forced to discard as part of the cleanup step (normally seven). The cleanup-step discard is how the maximum hand size is enforced (see rule 402.2 and the turn‑based action in 514.1 / 703.4n).
- “Draw” (in this context): an effect that uses the word “draw” to move card(s) from the top of a player’s library into that player’s hand. (Effects that move cards from library to hand without using the word “draw” are not considered drawing for rules that care about “draw.” See 121.5. Also note that card draws are performed one at a time; see 121.2.)

What this means for play
- You may draw cards even if you currently have as many cards in hand as your maximum hand size; no rule here prevents doing so during the turn (the maximum hand size is only enforced by discarding during the cleanup step) (see 402.2; 514.1; 703.4n).
- If a draw would require you to draw more cards than remain in your library, that can cause a player to lose under the rule about drawing more cards than are left (see 104.3c).
- If an effect replaces or prevents draws, that replacement or prevention applies according to the replacement rules (see 121.6a / 614.11a). If an effect moves cards from the library to the hand but does not use the word “draw,” it is not a draw for draw‑related effects (see 121.5).

Actionable summary: You can draw while at your maximum; expect to discard down to your maximum during your cleanup step afterward.

---

### Cell 11: id=q011

Question: what happens when a planeswalker has 0 or less loyalty counters?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: 704.5i, 306.9

Full text of each gold rule:
[704.5i] The state-based actions are as follows: If a planeswalker has loyalty 0, it’s put into its owner’s graveyard.
[306.9] If a planeswalker’s loyalty is 0, it’s put into its owner’s graveyard. (This is a state-based action. See rule 704.)

Arm's answer:
answered: False
citations: ['[122.1e]', '[306.5c]', '[120.3c]', '[306.8]', '[704.5i]', '[306.9]']
text: Definitions (from the provided rules):
- A loyalty counter is a counter placed on a planeswalker; the number of loyalty counters on a planeswalker equals its loyalty [122.1e], [306.5c].
- Damage dealt to a planeswalker removes that many loyalty counters from it [120.3c], [306.8].
What the provided rules say: If a planeswalker has loyalty 0, it’s put into its owner’s graveyard as a state-based action (checked as part of state-based actions) [122.1e], [704.5i], [306.9].
What the provided rules do not say: The excerpted rules specify what happens at loyalty 0 but do not state what to do if a planeswalker somehow has fewer than 0 loyalty counters (negative loyalty). The provided rules do not describe negative loyalty or an explicit consequence for "less than 0" loyalty, so that part of the question is not settled by the material given.

Because the rules excerpt does not address negative loyalty, I cannot answer the "or less" portion from these rules alone.

---

### Cell 12: id=q012

Question: do non-creature artifacts die?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: 700.4

Full text of each gold rule:
[700.4] The term dies means “is put into a graveyard from the battlefield.”

Arm's answer:
answered: True
citations: ['[700.4]', '[404.1]', '[701.8b]']
text: Short answer: Yes. "Dies" means “is put into a graveyard from the battlefield” (the zones involved are the battlefield and the object's owner’s graveyard). Any non-creature artifact that is put into its owner’s graveyard from the battlefield dies — whether it was destroyed, sacrificed, discarded, or put there by some other effect. Note that “dies” is just a zone-change definition and does not necessarily mean the permanent was "destroyed" (destroy is only some ways a permanent can go to the graveyard) — see the cited rules for the exact wording and examples.

---

### Cell 13: id=q013

Question: what happens if i should draw a card when my library is empty?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: 704.5b, 121.4

Full text of each gold rule:
[704.5b] The state-based actions are as follows: If a player attempted to draw a card from a library with no cards in it since the last time state-based actions were checked, that player loses the game.
[121.4] A player who attempts to draw a card from a library with no cards in it loses the game the next time a player would receive priority. (This is a state-based action. See rule 704.)

Arm's answer:
answered: True
citations: ['121.1', 'Draw', '504.1', '121.4', '704.5b', '104.3c', '609.3', '121.3', '121.3a', '121.6a', '614.11', '121.5']
text: Definition — “draw”: To put the top card of a player’s library into that player’s hand (this happens as a turn-based action during the draw step or as the result of an effect that uses the word “draw”). [121.1; Draw; 504.1]

What happens if you should draw while your library is empty:
- If you attempt to draw a card from an empty library, you lose the game the next time a player would receive priority. This is handled as a state-based action. [121.4; 704.5b]
- If an effect requires you to draw more cards than are left in your library, you draw as many as possible (the remaining cards) and then you lose the game the next time a player would receive priority. [104.3c; 609.3]
- If an effect offers a choice to draw when your library is empty, you may choose to do so unless another effect says you can’t draw cards. (The same applies if you’re the one choosing for another player who has an empty library.) [121.3; 121.3a]
- Replacement effects that replace a card draw are applied even if no cards could be drawn because the library is empty. That can change what actually happens when a draw would occur. [121.6a; 614.11]
- If an effect moves cards from a library to a hand without using the word “draw,” that action is not a draw and the rules about drawing from an empty library do not apply to it. [121.5]

Practical summary: when a draw is attempted from an empty library you will lose as soon as state-based actions are next checked (i.e., the next time a player would receive priority), unless a replacement effect or a non-draw effect changes what happens instead. [121.4; 704.5b; 121.6a; 614.11; 121.5]

---

### Cell 14: id=q014

Question: what are the steps in combat and when do I have priority as the defending player?

Gold rules:
Match semantics: all
  ALL of these are required: 506.1, 117.3a

Full text of each gold rule:
[506.1] The combat phase has five steps, which proceed in order: beginning of combat, declare attackers, declare blockers, combat damage, and end of combat. The declare blockers and combat damage steps are skipped if no creatures are declared as attackers or put onto the battlefield attacking (see rule 508.8). There are two combat damage steps if any attacking or blocking creature has first strike (see rule 702.7) or double strike (see rule 702.4).
[117.3a] Which player has priority is determined by the following rules: The active player receives priority at the beginning of most steps and phases, after any turn-based actions (such as drawing a card during the draw step; see rule 703) have been dealt with and abilities that trigger at the beginning of that phase or step have been put on the stack. No player receives priority during the untap step. Players usually don’t get priority during the cleanup step (see rule 514.3).

Arm's answer:
answered: False
citations: ['[506.1]', '[507.1]', '[703.4h]', '[506.2a]', '[117.3a]', '[511.1]']
text: Steps in the combat phase (in order): beginning of combat, declare attackers, declare blockers, combat damage, and end of combat. The declare blockers and combat damage steps are skipped if no creatures are declared as attackers or put onto the battlefield attacking, and there are two combat damage steps if any attacking or blocking creature has first strike or double strike. [506.1]

Who is the defending player at the beginning of combat (multiplayer): as the beginning of combat step starts, the active player chooses one of their opponents to be the defending player unless the multiplayer variant/option says all opponents are defending players. That choice is a turn-based action made immediately as the beginning of combat step begins. [507.1] [703.4h] [506.2a]

What the provided rules say about priority timing: the provided text says that "the active player receives priority at the beginning of most steps and phases, after any turn-based actions have been dealt with and abilities that trigger at the beginning of that phase or step have been put on the stack." This means the active player gets priority at the start of a step once turn-based actions (for example, choosing the defending player in multiplayer) and beginning-of-step triggers have been handled. [117.3a]

What is missing to fully answer "when do I have priority as the defending player": the supplied rules do not include the rule that describes how priority is passed between players after the active player receives it (the exact turn order or procedure by which priority moves from the active player to the nonactive/defending player). Because that passage is not in the provided rules, I cannot state precisely when the defending player will next receive priority (for example, whether immediately after the active player passes, and in what player order in multiplayer). Therefore I cannot fully specify every moment the defending player will have priority using only the supplied rules.

Short actionable summary a player can use from the supplied rules:
- Know the five combat steps and the conditions that skip steps or add a second combat-damage step. [506.1]
- In multiplayer, the defending player is chosen immediately as the beginning of combat step begins (unless the variant makes all opponents defending players). [507.1] [703.4h] [506.2a]
- At the start of most steps the active player is the one who receives priority after turn-based actions and triggers are handled. The exact rule that specifies when priority next passes to the defending player is not included in the provided material. [117.3a]

(If you want, I can answer the remainder — exactly when priority passes to the defending player and the usual passing order — if you provide the rule text that defines how priority is passed between players or allow me to use the standard MTG priority rules.)

---

### Cell 15: id=q015

Question: can i respond to a mana ability?

Gold rules:
Match semantics: all
  ALL of these are required: 605.3b, 605.4a

Full text of each gold rule:
[605.3b] Activating an activated mana ability follows the rules for activating any other activated ability (see rule 602.2), with the following exceptions: An activated mana ability doesn’t go on the stack, so it can’t be targeted, countered, or otherwise responded to. Rather, it resolves immediately after it is activated. (See rule 405.6c.)
[605.4a] Triggered mana abilities follow all the rules for other triggered abilities (see rule 603, “Handling Triggered Abilities”), with the following exception: A triggered mana ability doesn’t go on the stack, so it can’t be targeted, countered, or otherwise responded to. Rather, it resolves immediately after the mana ability that triggered it, without waiting for priority. An enchantment reads, “Whenever a player taps a land for mana, that player adds one mana of any type that land produced.” If a player taps lands for mana while casting a spell, the additional mana is added immediately and can be used to pay for the spell.

Arm's answer:
answered: True
citations: ['Mana Ability', '605.1', '113.4', '605.3b', '405.6c', '605.4a', '605.5a', '117.1d']
text: No. A mana ability is an activated or triggered ability that could create mana and doesn’t use the stack. Because mana abilities don’t use the stack, they resolve immediately when activated (or immediately when triggered, for triggered mana abilities) and can’t be targeted, countered, or otherwise responded to. You can only act (for example, cast a spell or activate an ability that would respond) before the mana ability is activated while you have priority. Note also that an ability with a target is not a mana ability and so can be responded to like any other ability.

---

### Cell 16: id=q016

Question: can I respond to a cost being paid?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: 601.2, 601.2g, 601.2h, 601.2i

Full text of each gold rule:
[601.2] To cast a spell is to take it from where it is (usually the hand), put it on the stack, and pay its costs, so that it will eventually resolve and have its effect. Casting a spell includes proposal of the spell (rules 601.2a–d) and determination and payment of costs (rules 601.2f–h). To cast a spell, a player follows the steps listed below, in order. A player must be legally allowed to cast the spell to begin this process (see rule 601.3). If a player is unable to comply with the requirements of a step listed below while performing that step, the casting of the spell is illegal; the game returns to the moment before the casting of that spell was proposed (see rule 733, “Handling Illegal Actions”).
[601.2g] To cast a spell is to take it from where it is (usually the hand), put it on the stack, and pay its costs, so that it will eventually resolve and have its effect. Casting a spell includes proposal of the spell (rules 601.2a–d) and determination and payment of costs (rules 601.2f–h). To cast a spell, a player follows the steps listed below, in order. A player must be legally allowed to cast the spell to begin this process (see rule 601.3). If a player is unable to comply with the requirements of a step listed below while performing that step, the casting of the spell is illegal; the game returns to the moment before the casting of that spell was proposed (see rule 733, “Handling Illegal Actions”). If the total cost includes a mana payment, the player then has a chance to activate mana abilities (see rule 605, “Mana Abilities”). Mana abilities must be activated before costs are paid.
[601.2h] To cast a spell is to take it from where it is (usually the hand), put it on the stack, and pay its costs, so that it will eventually resolve and have its effect. Casting a spell includes proposal of the spell (rules 601.2a–d) and determination and payment of costs (rules 601.2f–h). To cast a spell, a player follows the steps listed below, in order. A player must be legally allowed to cast the spell to begin this process (see rule 601.3). If a player is unable to comply with the requirements of a step listed below while performing that step, the casting of the spell is illegal; the game returns to the moment before the casting of that spell was proposed (see rule 733, “Handling Illegal Actions”). The player pays the total cost. First, they pay all costs that don’t involve random elements or moving objects from the library to a public zone, in any order. Then they pay all remaining costs in any order. Partial payments are not allowed. Unpayable costs can’t be paid. You cast Altar’s Reap, which costs {1}{B} and has an additional cost of sacrificing a creature. You sacrifice Thunderscape Familiar, whose effect makes your black spells cost {1} less to cast. Because a spell’s total cost is “locked in” before payments are actually made, you pay {B}, not {1}{B}, even though you’re sacrificing the Familiar.
[601.2i] To cast a spell is to take it from where it is (usually the hand), put it on the stack, and pay its costs, so that it will eventually resolve and have its effect. Casting a spell includes proposal of the spell (rules 601.2a–d) and determination and payment of costs (rules 601.2f–h). To cast a spell, a player follows the steps listed below, in order. A player must be legally allowed to cast the spell to begin this process (see rule 601.3). If a player is unable to comply with the requirements of a step listed below while performing that step, the casting of the spell is illegal; the game returns to the moment before the casting of that spell was proposed (see rule 733, “Handling Illegal Actions”). Once the steps described in 601.2a–h are completed, effects that modify the characteristics of the spell as it’s cast are applied, then the spell becomes cast. Any abilities that trigger when a spell is cast or put onto the stack trigger at this time. If the spell’s controller had priority before casting it, they get priority.

Arm's answer:
answered: False
citations: ['118.1', '118.2', '118.3', '118.10', '118.13c', '601.2g', '601.2h', '608.2g']
text: Short definition: “Respond to a cost being paid” means taking actions that use the stack (for example, casting an instant or activating an activated ability) at the time another player is in the middle of paying a cost for something (for example, while they are paying a spell’s total cost or sacrificing something as an additional cost).

What the provided rules do say
- Paying a cost is part of the casting/activation process: a spell is put on the stack and its costs are determined and paid as part of casting (rules 601.2g and 601.2h). [601.2g] [601.2h]
- If a cost includes a mana payment, the player paying that cost has a chance to activate mana abilities to produce that mana before costs are paid (rule 118.2). [118.2]
- Some details about how costs are paid are given (which parts are paid first, how choices for special mana symbols are made, and that each payment applies to only one spell/ability) (rules 601.2h, 118.13c, 118.10). [601.2h] [118.13c] [118.10]
- Definition of “cost” (rule 118.1) and that unpayable costs can’t be paid (rule 118.3). [118.1] [118.3]
- When an effect allows casting during resolution, that casting uses the 601.2 steps but the rules explicitly state that no player receives priority after that spell is cast (rule 608.2g) — this is a special case that shows there are timing/priority consequences tied to the casting steps, but it does not answer whether responding during cost payment is allowed in the normal case. [608.2g]

What is missing (why I can’t give a definitive yes/no)
- The provided excerpt does not include the game’s priority and timing rules that say when players receive or don’t receive priority (for example, the rule that explains priority windows and whether any other player can act while a player is in the middle of paying costs). Those priority/timing rules (commonly found around the “priority” rule and the full 601.2 casting-step text) are required to determine whether other players may take actions during another player’s cost payment.

Conclusion
- Because the context you gave does not include the rules that define priority/timing windows around cost payment, I can’t definitively answer whether a player may respond while another player is paying a cost. The quoted rules allow the player paying a cost to activate their own mana abilities before paying (and show how costs are paid and locked in), but they do not state whether other players get an opportunity to cast spells or activate abilities in the middle of that payment process. Therefore I cannot answer yes or no from the provided rules alone.

If you want a complete answer, provide the rules that define priority and timing (the priority rule and the complete 601.2 casting steps including priority windows), and I will answer and cite them directly.

---

### Cell 17: id=q017

Question: can you explain layers?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: 613.1, 613.1a, 613.1b, 613.1c, 613.1d, 613.1e, 613.1f, 613.1g

Full text of each gold rule:
[613.1] The values of an object’s characteristics are determined by starting with the actual object. For a card, that means the values of the characteristics printed on that card. For a token or a copy of a spell or card, that means the values of the characteristics defined by the effect that created it. Then all applicable continuous effects are applied in a series of layers in the following order:
[613.1a] The values of an object’s characteristics are determined by starting with the actual object. For a card, that means the values of the characteristics printed on that card. For a token or a copy of a spell or card, that means the values of the characteristics defined by the effect that created it. Then all applicable continuous effects are applied in a series of layers in the following order: Layer 1: Rules and effects that modify copiable values are applied.
[613.1b] The values of an object’s characteristics are determined by starting with the actual object. For a card, that means the values of the characteristics printed on that card. For a token or a copy of a spell or card, that means the values of the characteristics defined by the effect that created it. Then all applicable continuous effects are applied in a series of layers in the following order: Layer 2: Control-changing effects are applied.
[613.1c] The values of an object’s characteristics are determined by starting with the actual object. For a card, that means the values of the characteristics printed on that card. For a token or a copy of a spell or card, that means the values of the characteristics defined by the effect that created it. Then all applicable continuous effects are applied in a series of layers in the following order: Layer 3: Text-changing effects are applied. See rule 612, “Text-Changing Effects.”
[613.1d] The values of an object’s characteristics are determined by starting with the actual object. For a card, that means the values of the characteristics printed on that card. For a token or a copy of a spell or card, that means the values of the characteristics defined by the effect that created it. Then all applicable continuous effects are applied in a series of layers in the following order: Layer 4: Type-changing effects are applied. These include effects that change an object’s card type, subtype, and/or supertype.
[613.1e] The values of an object’s characteristics are determined by starting with the actual object. For a card, that means the values of the characteristics printed on that card. For a token or a copy of a spell or card, that means the values of the characteristics defined by the effect that created it. Then all applicable continuous effects are applied in a series of layers in the following order: Layer 5: Color-changing effects are applied.
[613.1f] The values of an object’s characteristics are determined by starting with the actual object. For a card, that means the values of the characteristics printed on that card. For a token or a copy of a spell or card, that means the values of the characteristics defined by the effect that created it. Then all applicable continuous effects are applied in a series of layers in the following order: Layer 6: Ability-adding effects, keyword counters, ability-removing effects, and effects that say an object can’t have an ability are applied.
[613.1g] The values of an object’s characteristics are determined by starting with the actual object. For a card, that means the values of the characteristics printed on that card. For a token or a copy of a spell or card, that means the values of the characteristics defined by the effect that created it. Then all applicable continuous effects are applied in a series of layers in the following order: Layer 7: Power- and/or toughness-changing effects are applied.

Arm's answer:
answered: True
citations: ['[Layer]', '[613.1]', '[613.1a]', '[613.2a]', '[613.2c]', '[613.3]', '[613.1c]', '[613.1d]', '[613.1e]', '[613.1f]', '[613.4a]', '[613.5]', '[613.6]', '[613.8]', '[613.8a]']
text: TL;DR: “Layers” are the ordered system the game uses to apply continuous effects to objects. Start with an object’s printed/initial characteristics, then apply continuous effects in the layer order; within each layer use timestamp order unless dependency overrides it.

Full explanation

What a “layer” is
- Layer: “A system used to determine in which order continuous effects are applied.” [Layer]

How the layer system works (step by step)
1. Start with the object’s base characteristics (for a card, the printed values; for a token or copy, the values set when it was created). Then continuous effects are applied in a series of layers to produce the object’s current characteristics. [613.1]
2. Layer 1 (rules/effects that modify copiable values) is applied first; within layer 1 there are sublayers such as 1a for copiable effects (copy effects and similar “as … enters / is turned face up” copiable settings). Within each sublayer, effects are applied in timestamp order (unless dependency changes that). After layer 1 has been applied, the object’s characteristics are its copiable values. [613.1a] [613.2a] [613.2c]
3. Layers 2–6 are then applied (these include things like control-changing effects in layer 2, text-changing in layer 3, type-changing in layer 4, color-changing in layer 5, and ability changes in layer 6). Within layers 2–6, characteristic-defining abilities are applied first, then other effects in timestamp order (subject to dependency). [613.3] [613.1c] [613.1d] [613.1e] [613.1f] [613.6]
4. Layer 7 (power/toughness effects) is applied after layers 1–6. Layer 7 itself has sublayers (apply those sublayers in order; within each sublayer use timestamp order unless dependency overrides it). [613.4a]

Rules about ordering inside layers
- Within a given layer or sublayer, effects are normally applied in timestamp order. [613.2c] [613.2a] [613.4a]
- If a dependency exists between two effects in the same layer/sublayer, dependency overrides timestamp order. An effect A depends on effect B if applying B would change A’s text, existence, what it applies to, or what it does to those things (and some additional conditions from the rule). [613.8] [613.8a]
- For layers 2–6, characteristic-defining abilities (CDAs) are applied before other continuous effects in that layer. [613.3]

Other important points
- The layer system is applied continually and automatically; the resulting changes are instantaneous. Examples in the rules show that a color change applied in a color layer can change whether a static effect (like “white creatures get +1/+1”) applies, and P/T-setting vs P/T-modifying effects are applied in the appropriate sublayers so their interactions are predictable. [613.5]
- If one continuous effect contains multiple parts that belong in different layers (for example, “becomes a color” and “gets +1/+1”), each part is applied in its appropriate layer; and once an effect starts applying to a set of objects it will continue to be applied in the other relevant layers to that same set of objects even if the ability that generated the effect is removed during the process. [613.6]

Concrete objects/zones mentioned
- The system starts from the actual object (a card on the battlefield, a token, a copy, etc.) and modifies that object’s characteristics via the layers listed above. [613.1] [613.2a]

If you want a short playable rule of thumb to use at a table
- Start with the object’s printed/initial characteristics. Apply layer 1 effects (copiable changes), then layers 2–6 (remember CDAs first within those layers), then layer 7 (power/toughness sublayers). Within each layer use timestamp order unless dependency says otherwise. The game applies all this automatically. [613.1] [613.2a] [613.3] [613.4a] [613.8] [613.5]

Answered: true

---

### Cell 18: id=q018

Question: how does the legend rule work?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: 704.5j

Full text of each gold rule:
[704.5j] The state-based actions are as follows: If two or more legendary permanents with the same name are controlled by the same player, that player chooses one of them, and the rest are put into their owners’ graveyards. This is called the “legend rule.”

Arm's answer:
answered: True
citations: ['Legend Rule', '704.5j', '117.2d', '205.4d', '306.4']
text: Definition: The “legend rule” is a state-based action that handles when a player controls multiple legendary permanents with the same name. State-based actions are game rules that happen automatically and are dealt with before a player would receive priority (they don’t use the stack). (See rules below.)

How it works: Whenever state-based actions are checked, if a single player controls two or more legendary permanents that share the same name, that player chooses one of those permanents to keep and the rest are put into their owners’ graveyards. This choice and the putting-into-graveyard result happen as a state-based action (so automatically, not on the stack). The rule applies to any permanent that has the legendary supertype, including older planeswalker cards that have been given the legendary supertype and are therefore subject to this rule. In multiplayer (including Commander), the same procedure applies separately for each player who controls duplicates: each affected player chooses which one they keep, and the others they control are put into their owners’ graveyards.

Practical points you can act on:
- The game checks this automatically (you don’t get priority or a chance to cast spells in response to the legend rule itself).
- The player who controls the duplicates is the one who chooses which single permanent to keep; the others are put into their owners’ graveyards.
- This applies to any permanent with the legendary supertype (including the older planeswalker cards that are now legendary).

References: see the legend-rule definition and the state-based-action timing rules listed below.

---

### Cell 19: id=q019

Question: when does my creature die after its been marked with a lethal amount of damage?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: 704.5g, 302.7

Full text of each gold rule:
[704.5g] The state-based actions are as follows: If a creature has toughness greater than 0, it has damage marked on it, and the total damage marked on it is greater than or equal to its toughness, that creature has been dealt lethal damage and is destroyed. Regeneration can replace this event.
[302.7] Damage dealt to a creature by a source with neither wither nor infect is marked on that creature (see rule 120.3). If the total damage marked on that creature is greater than or equal to its toughness, that creature has been dealt lethal damage and is destroyed as a state-based action (see rule 704). All damage marked on a creature is removed when it regenerates (see rule 701.19, “Regenerate”) and during the cleanup step (see rule 514.2).

Arm's answer:
answered: True
citations: ['117.2d', '117.5', '704.3', '704.5g', '120.6', '302.7', '510.3a', '514.3a', '514.2', '703.4p']
text: Short answer
- A creature is destroyed the next time state‑based actions are checked once the total damage marked on it is greater than or equal to its toughness.

What “state‑based actions” means here
- State‑based actions are game checks performed automatically (without using the stack) whenever a player would receive priority; they include destroying creatures that have lethal damage marked on them (they happen before a player gets priority). See rules 117.2d and 117.5.

When this actually happens in play
- Damage marked on a creature remains until the cleanup step (it isn’t wiped off immediately) (120.6; 302.7).
- If the total damage marked on a creature is greater than or equal to its toughness, that creature “has been dealt lethal damage and is destroyed” as a state‑based action (704.5g; 120.6; 302.7).
- State‑based actions are checked whenever a player would get priority, and they are performed immediately (117.5; 704.3). That means:
  - Immediately after damage is dealt, before the next player gets priority, state‑based actions are checked and the lethal creature is destroyed (510.3a; 117.5; 704.3).
  - During the cleanup step the game also checks state‑based actions; if a creature already has lethal damage at that check it will be destroyed rather than be saved by the later removal of damage during cleanup (704.3; 514.3a; 514.2; 703.4p).

Practical result for a player
- As soon as lethal damage is marked, wait for the next state‑based check (which is effectively immediate whenever priority would be given). The creature will be destroyed at that check; it won’t survive until damage is later removed in cleanup.

Answered: true

---

### Cell 20: id=q020

Question: can I cast my commander from exile?

Gold rules:
Match semantics: all
  ALL of these are required: 903.8, 903.9a

Full text of each gold rule:
[903.8] A player may cast a commander they own from the command zone. A commander cast from the command zone costs an additional {2} for each previous time the player casting it has cast it from the command zone that game. This additional cost is informally known as the “commander tax.”
[903.9a] A commander may return to the command zone during a Commander game. If a commander is in a graveyard or in exile and that object was put into that zone since the last time state-based actions were checked, its owner may put it into the command zone. This is a state-based action. See rule 704.

Arm's answer:
answered: True
citations: ['903.3d', '903.3e', '601.3f', '406.3b', '903.8', '903.9a', '704.6d', '903.9b']
text: Short answer and definition
- Commander: the card designated as your deck’s commander (a legendary creature/Vehicle/Spacecraft card); that designation applies in all zones (command zone, exile, hand, library, etc.). See rule 903.3d/e for the definition and how “commander” is referred to in zones. 
- Casting from exile: you can begin to cast a spell that is in exile only if a rule or effect explicitly allows you to cast it from exile. Face-down cards in exile can be cast only if you are allowed to look at the face-down card and the effect specifically allows casting from among those face-down cards. See rules 601.3f and 406.3b.

Can you cast your commander from exile? (what actually happens)
- There is no general rule that lets you cast a commander from exile. You may cast a commander from the command zone (and doing so uses the commander tax) but not from exile unless a specific rule or effect allows casting it from exile (903.8; 601.3f). 
- If your commander was put into exile since the last time state-based actions were checked, you may instead put it into the command zone as a state-based action. That is optional; you may choose to leave it in exile if you prefer to keep it there for some effect that would let you cast it from exile (903.9a; 704.6d). 
- Separately, if an effect would put your commander into your hand or library from anywhere, you may choose to put it into the command zone instead (replacement effect). That replacement may apply more than once (903.9b). 

Practical guidance for playing
- If you want to cast a commander while it’s in exile, check for a specific effect that says you may cast it from exile (or from face-down exile and that you may look at it); without such an effect you cannot cast it from exile. If the commander was just exiled you can opt to move it to the command zone and then cast it from there (paying the additional costs from 903.8) instead.


---

### Cell 21: id=q021

Question: what happens during the cleanup step?

Gold rules:
Match semantics: all
  ALL of these are required: 514.1, 514.2

Full text of each gold rule:
[514.1] First, if the active player’s hand contains more cards than their maximum hand size (normally seven), they discard enough cards to reduce their hand size to that number. This turn-based action doesn’t use the stack.
[514.2] Second, the following actions happen simultaneously: all damage marked on permanents (including phased-out permanents) is removed and all “until end of turn” and “this turn” effects end. This turn-based action doesn’t use the stack.

Arm's answer:
answered: True
citations: ['514.3', '514.3a', '514.2', '703.4p', '704.3', '703.3', '500.5', '500.3', '724.1d', '724.1f']
text: Definition — Cleanup step: the cleanup step is the second and final step of the ending phase. During it certain turn-based actions happen and the normal priority rules for the step are modified (see rules 514 and 514.2). [Use the numbered-rule citations below for specifics.] 

What happens during the cleanup step (order and practical consequences):
- When the cleanup step begins, any turn-based actions for the step are dealt with first. In particular, after the active player discards cards if necessary, all damage is removed from permanents and all “until end of turn” / “this turn” effects end; these are simultaneous, turn-based actions that don’t use the stack (see rules 703.3; 703.4p; 514.2). 
- Normally no player receives priority during the cleanup step, so players can’t cast spells or activate abilities (see rule 514.3). However, there is an exception: the game checks for state-based actions and for any triggered abilities waiting to be put onto the stack (this includes abilities that say “at the beginning of the next cleanup step”). If any state-based actions are performed and/or any triggered abilities are waiting, the state-based actions are performed, then those triggered abilities are put onto the stack, and then the active player gets priority (see rules 514.3a and 704.3). Players may then cast spells and activate abilities; after the stack empties and all players pass in succession, another cleanup step begins (see rule 514.3a). 
- If, on the cleanup step’s first check, no state-based actions are performed and no triggered abilities are waiting to be put onto the stack, then no player gets priority and the cleanup step simply ends (see rule 704.3 and rule 514.3). 
- Interactions with effects that “end the turn”: when an effect ends the turn, the game skips ahead to the cleanup step (see rule 724.1d). If an effect ends the turn during a cleanup step, a new cleanup step begins (724.1d). When an effect ends the turn, no player gets priority during that ending process; if any triggered abilities have triggered during that process, those abilities are put onto the stack during the cleanup step and then the active player gets priority (see rule 724.1f). 
- As the step ends, any effects that last “until end of step/phase” expire and any unspent mana empties; that expiration is a turn-based action (see rule 500.5). 

Practical summary you can act on: the cleanup step removes damage and ends until-end effects, normally gives no priority and ends immediately unless state-based actions or triggered abilities are waiting (in which case those are handled and players get priority), and is the final step of the ending phase (see cited rules).

---

### Cell 22: id=q022

Question: when are state-based actions checked?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: 704.3

Full text of each gold rule:
[704.3] Whenever a player would get priority (see rule 117, “Timing and Priority”), the game checks for any of the listed conditions for state-based actions, then performs all applicable state-based actions simultaneously as a single event. If any state-based actions are performed as a result of a check, the check is repeated; otherwise all triggered abilities that are waiting to be put on the stack are put on the stack, then the check is repeated. Once no more state-based actions have been performed as the result of a check and no triggered abilities are waiting to be put on the stack, the appropriate player gets priority. This process also occurs during the cleanup step (see rule 514), except that if no state-based actions are performed as the result of the step’s first check and no triggered abilities are waiting to be put on the stack, then no player gets priority and the step ends.

Arm's answer:
answered: True
citations: ['704.1', '704.1a', '704.2', '704.3', '117.5', '117.2d', '117.2c', '703.3', '514.3a', '724.2c', '724.1c', '405.6f', '405.6e']
text: Definition: State-based actions are game actions that happen automatically whenever certain conditions are met; they don’t use the stack (see rules 704.1 and 704.1a). They are checked throughout the game (704.2) and are not actions controlled by any player (704.2).

When they are checked and how the checks are ordered:
- Whenever a player would get priority, the game first performs all applicable state-based actions as a single event, repeats the check until no state-based actions are performed, then (if any) puts triggered abilities waiting onto the stack, and repeats this whole process until nothing more happens; only then does the player receive priority (704.3, 117.5). State-based actions are dealt with before a player receives priority (117.2d; 405.6f).
- At the beginning of any step or phase that has turn-based actions, those turn-based actions are handled first, and then state-based actions are checked (703.3; 117.2c).
- During the cleanup step: normally no player receives priority, but there is an exception — the game checks for state-based actions and for triggered abilities waiting to be put on the stack; if any exist the state-based actions are performed, those triggered abilities are put on the stack, and then the active player gets priority (514.3a).
- If an effect ends the turn or ends the combat phase, the rules require checking state-based actions as part of that special sequence; in those cases the rules state to check state-based actions and that no player gets priority and no triggered abilities are put onto the stack as part of that special sequence (724.1c, 724.2c).

Process summary a player can act on: before you can receive priority or act, the game will automatically run state-based action checks (and repeat them until none apply); these checks occur whenever priority would be given, immediately after turn-based actions at the start of steps/phases, during the cleanup-step exception, and when an effect ends the turn or combat (704.3; 117.5; 703.3; 514.3a; 724.1c; 724.2c).

---

### Cell 23: id=q024

Question: when can I concede a game?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: 104.3a, 723.6

Full text of each gold rule:
[104.3a] There are several ways to lose the game. A player can concede the game at any time. A player who concedes leaves the game immediately. That player loses the game.
[723.6] The controller of another player can’t make that player concede. A player may concede the game at any time, even if they are controlled by another player. See rule 104.3a.

Arm's answer:
answered: True
citations: ['[104.3a]', '[405.6g]', '[101.1]', '[723.6]', '[810.8b]']
text: Definition — “Concede” means to quit the game. Conceding causes the conceding player to leave the game immediately and lose the game (see rule 104.3a).

When you can do it
- You may concede at any time; conceding is immediate and causes you to leave the game and lose (104.3a).  
- You may concede even while things are happening that don’t use the stack (for example, during a shortcut or other special-action times) (405.6g).  
- A card’s text cannot stop you from conceding; conceding at any time is the one exception to a card’s ability to override the rules (101.1).  
- Another player (including a player who controls you) cannot make you concede; you must choose to concede yourself (723.6).  
- In Two-Headed Giant games, if an individual player concedes, that player’s entire team leaves the game immediately and that team loses the game (810.8b).

---

### Cell 24: id=q025

Question: how do I know who the active player is?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: 102.1, Active Player

Full text of each gold rule:
[102.1] A player is one of the people in the game. The active player is the player whose turn it is. The other players are nonactive players.
[Active Player] Active Player. The player whose turn it is. See rule 102.1.

Arm's answer:
answered: True
citations: ['102.1', '805.4a', '101.4e', '805.9']
text: Definition and how to tell: The active player is simply “the player whose turn it is” (see rule [102.1]). In a game using the shared team turns option, the equivalent is the active team — the team whose turn it is (see rule [805.4a]).

What that means in play: the active player (the turn’s player) is the one who gets priority and who makes choices first when multiple players would make choices at the same time (the APNAP order) (see rule [101.4e]). If a card or effect refers to “the active player” in a situation with more than one possible active player (for example, team or special multiplayer cases), the wording refers to one specific active player, and the controller of the effect chooses which active player it means when the effect is applied (see rule [805.9]).

---

### Cell 25: id=q026

Question: when someone other than the active player casts a spell, who gets priority first?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: 117.3c

Full text of each gold rule:
[117.3c] Which player has priority is determined by the following rules: If a player has priority when they cast a spell, activate an ability, or take a special action, that player receives priority afterward.

Arm's answer:
answered: True
citations: ['117.3c', '101.4d', '117.3b']
text: Definitions you need: “Active player” is the player whose turn it is (see rule 101.4d). “Priority” is the game state that determines which player may cast spells, activate abilities, or take special actions; which player has priority is determined by rules such as 117.3a–c.

Answer: If a player other than the active player casts a spell, the player who had priority when they cast that spell receives priority afterward — so normally the nonactive player who cast the spell gets priority first (see rule 117.3c). After the spell resolves, the active player receives priority (see rule 117.3b).

---

### Cell 26: id=q027

Question: when the active player cast a spell, who gets priority first?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: 117.3c

Full text of each gold rule:
[117.3c] Which player has priority is determined by the following rules: If a player has priority when they cast a spell, activate an ability, or take a special action, that player receives priority afterward.

Arm's answer:
answered: True
citations: ['117.1', '117.3c', '601.7b']
text: Definition: "Priority" is the game rule that determines who may take actions (cast spells, activate abilities, take special actions) at a given time; the player with priority may do those things. [117.1]

Answer: If the active player had priority when they cast the spell, that same player receives priority immediately afterward. In other words, the player who had priority to cast the spell gets priority first after casting it. [117.3c]

Exception: If the spell’s casting instructs one of the caster’s opponents to do something while it’s being cast (choose a mode or targets, etc.), the spell’s controller does those things first, then the opponent does theirs. This is an exception to the normal order. [601.7b]

Practical note: This applies in multiplayer as well—the player who had priority when casting the spell gets priority back first, subject to the exception above. [117.1]  

---

### Cell 27: id=q028

Question: can I hold priority to cast more spells after I've cast one or more spells?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: 117.3c

Full text of each gold rule:
[117.3c] Which player has priority is determined by the following rules: If a player has priority when they cast a spell, activate an ability, or take a special action, that player receives priority afterward.

Arm's answer:
answered: True
citations: ['[117.1]', '[601.2i]', '[117.3c]', '[608.2g]', '[514.3a]']
text: Short answer: Yes—if you had priority when you cast a spell, you get priority afterward and can cast more spells; there are important exceptions (see below). 

Definitions you need: 
- Priority: the game’s system that determines who may take actions. The player with priority may cast spells, activate abilities, and take special actions ([117.1]).
- To cast a spell: to take it from where it is (usually the hand), put it on the stack, and pay its costs so it will eventually resolve ([601.2i]).

What happens when you cast a spell: 
- If you had priority immediately before you cast the spell, you receive priority after the casting finishes, so you may cast additional spells or take other actions ([601.2i]; [117.3c]).

Exceptions and important notes: 
- If you are casting a spell only because an effect instructs or allows you to cast it during the resolution of another spell or ability, follow the casting steps but no player receives priority after that cast—so you cannot hold priority to cast more spells at that moment ([608.2g]).
- During the cleanup step normally no player receives priority (so you can’t cast spells there), except where rule 514.3a’s exception applies (trigger checks then the active player gets priority). If you’re in cleanup, check that rule before assuming you can cast more spells ([514.3a]).

Practical takeaway: If you cast while you already have priority, you can keep casting spells in succession. If you cast as part of a resolving effect that grants a one-time casting, or you’re in the normal cleanup step, you won’t be able to “hold” priority afterward.


---

### Cell 28: id=q029

Question: when are lore counters put on sagas?

Gold rules:
Match semantics: all
  ALL of these are required: 714.3c, 714.3a

Full text of each gold rule:
[714.3c] Sagas use lore counters to track their progress. As a player’s precombat main phase begins, that player puts a lore counter on each Saga they control with one or more chapter abilities. This turn-based action doesn’t use the stack.
[714.3a] Sagas use lore counters to track their progress. Each Saga without read ahead has the intrinsic ability “This Saga enters with a lore counter on it.” This ability creates a replacement effect (see rule 614.1c).

Arm's answer:
answered: True
citations: ['714.3', '714.3a', '714.3b', '714.3c', '702.155a', '702.155b', '703.4f', '505.4']
text: Short answer
- Lore counters are put on Sagas in two ways:
  1) As they enter the battlefield (they enter with lore counters because of an intrinsic replacement ability). See rules [714.3a] and [714.3b]. Sagas without read ahead enter with one lore counter [714.3a]. Sagas with read ahead enter with the number of lore counters you choose as it enters (choose a number between one and the Saga’s final chapter number). See [714.3b] and [702.155b]/[702.155a].
  2) Immediately after a player’s precombat main phase begins, that player puts a lore counter on each Saga they control that has one or more chapter abilities. This is a turn‑based action that doesn’t use the stack. See [714.3c], [703.4f], and [505.4]. (In an Archenemy game that placement happens after the archenemy’s scheme action — see [703.4f].)

Definitions and key details you need to act on
- Lore counters: counters on Saga permanents used to track their progress [714.3].
- Read ahead: a keyword on some Sagas meaning “As this Saga enters, choose a number between one and this Saga’s final chapter number” and “This Saga enters with the chosen number of lore counters on it” (so entering with counters is controlled by that choice) [702.155a][702.155b][714.3b].
- The precombat main phase placement is a turn‑based action that doesn’t use the stack, so nothing can be put on the stack in response to that placement [714.3c][505.4].
- The precombat placement only affects Saga permanents you control that have one or more chapter abilities [714.3c][703.4f].

If you need to know what happens when a Saga reaches its final chapter number (sacrifice timing) or how chapter symbols trigger, those are covered elsewhere in the Saga rules but weren’t requested here.


---

### Cell 29: id=q030

Question: what is a delayed triggered ability?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: Delayed Triggered Ability, 603.7

Full text of each gold rule:
[Delayed Triggered Ability] Delayed Triggered Ability. An ability created by effects generated when some spells or abilities resolve, or when some replacement effects are applied, that does something later on rather than at that time. See rule 603.7.
[603.7] An effect may create a delayed triggered ability that can do something at a later time. A delayed triggered ability will contain “when,” “whenever,” or “at,” although that word won’t usually begin the ability.

Arm's answer:
answered: True
citations: ['603.7', '603.7a', '603.7b', '603.7c', '603.7d', '603.7e', '603.7f', '603.7g', '603.7h', '603.12', '107.3n', '603.3a']
text: Definition
A delayed triggered ability is an ability that an effect creates during the resolution of a spell or ability, as the result of a replacement effect, or as the result of a static ability that lets a player take an action, and that does something later (not immediately) by containing the words “when,” “whenever,” or “at.” It is created when that effect resolves or the replacement/static action is applied and will not trigger until after it actually exists (it won’t trigger for an event that happened before it was created). (See 603.7 and 603.7a.)

Key properties you need to know
- Creation timing: A delayed triggered ability is created while a spell or ability is resolving, when a replacement effect is applied, or when a static ability’s allowed action is taken. It therefore can’t trigger for a past event that happened before it was created. (603.7, 603.7a)
- Trigger words and triggering: It will contain “when,” “whenever,” or “at.” Unless it has a stated duration (for example, “this turn”), it triggers only once—the next time its trigger event occurs; if the trigger event happens multiple times simultaneously, its controller chooses which event causes the trigger. (603.7, 603.7b)
- Reflexive cases: If the creating spell or ability makes a reflexive delayed triggered ability, that ability is checked immediately after it’s created and can trigger based on events that occurred earlier during the same resolution. (603.12)
- Source and controller: If a spell created the delayed triggered ability, the ability’s source is that spell and its controller is the player who controlled that spell as it resolved. If an activated or triggered ability created it, its source and controller are the same as that creating ability’s source and controller as it resolved. If a static ability’s replacement effect created it, the source is the object with that static ability and its controller is the controller of that object when the replacement effect was applied. (603.7d, 603.7e, 603.7f, 603.7g)
- Interaction with referenced objects and zones: A delayed triggered ability that refers to a particular object still affects it if the object’s characteristics change, but the ability won’t affect the object if it isn’t in the zone the ability expects when the delayed ability resolves (and if the object left and returned, it’s a new object and won’t be affected). Example: “Exile this creature at the beginning of the next end step” will still exile the permanent even if it’s no longer a creature, but it won’t do anything if the permanent left the battlefield before then. (603.7c)
- X values: If the creating spell or ability used a chosen value for X, a delayed triggered ability it creates that refers to X uses that same chosen value. (107.3n)
- What happens when it triggers: Once a delayed triggered ability triggers, its controller will put it on the stack the next time a player would receive priority; the usual stack rules for triggered abilities apply. (603.3a)

Practical summary: delayed triggered abilities are “callbacks” created while something resolves or is replaced; they wait for a later event (or the next occurrence of an event) and then trigger once unless they state otherwise, with their source and controller determined by how they were created. (603.7, 603.7a, 603.7b, 603.7d–f, 603.7c, 603.12, 107.3n, 603.3a)


---

### Cell 30: id=q031

Question: can non-permanent spells have abilities?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: 113.3a, 113.6

Full text of each gold rule:
[113.3a] There are four general categories of abilities: Spell abilities are abilities that are followed as instructions while an instant or sorcery spell is resolving. Any text on an instant or sorcery spell is a spell ability unless it’s an activated ability, a triggered ability, or a static ability that fits the criteria described in rule 113.6.
[113.6] Abilities of an instant or sorcery spell usually function only while that object is on the stack. Abilities of all other objects usually function only while that object is on the battlefield. The exceptions are as follows:

Arm's answer:
answered: True
citations: ['[113.1c]', '[113.3a]', '[113.6]', '[604.5]', '[113.6e]', '[604.6]', '[610.5]', '[601.2a]', '[405.1]', '[405.4]', '[611.3d]']
text: Short answer: Yes. "Ability" here means one of the three ability types in the rules (an activated ability or a triggered ability that’s an object on the stack, a static ability, or other ability categories); specifically, any text on an instant or sorcery is a spell ability unless it’s an activated ability, a triggered ability, or a static ability that fits the exceptions below. For non-permanent spells (instants and sorceries):

- Spell abilities: Any text on an instant or sorcery is a spell ability and is followed as instructions while that instant or sorcery is resolving. Those abilities function while the card is the spell on the stack (the physical card is put on the stack when cast). See rules defining ability categories and spell abilities and the rule that the card is put on the stack when cast. [113.1c] [113.3a] [405.1]

- Static or other abilities that apply to spells on the stack: Some static abilities can apply while the spell is on the stack (for example, abilities that change how the spell can be cast, or abilities that act as additional costs). Abilities that restrict or modify how the object is cast or are written so they apply from zones you could cast the card from can function in those zones and on the stack. Effects that grant a spell an ability as you cast it take effect as it is put on the stack. In short, instants and sorceries can have (or be granted) abilities that function while they are on the stack. [113.6] [604.5] [113.6e] [604.6] [610.5] [601.2a]

- What this does not change: Abilities that normally function only while an object is on the battlefield won’t affect an instant or sorcery while it’s just a card in your hand or while it’s on the stack unless an applicable exception above says otherwise. The distinction between zones (hand, stack, battlefield) matters for which abilities apply. [405.4] [611.3d]

Practical takeaway for a player: read the instant/sorcery’s text — that text is a spell ability that works while it’s the spell on the stack; also be aware that continuous or one-shot effects can grant it extra abilities as you cast it or while it’s on the stack, and some static wording about casting can apply from your hand or other zones from which you could cast it. [113.3a] [113.6] [610.5] [601.2a]

---

### Cell 31: id=q032

Question: can I use a mana ability when a spell with split-second is on the stack?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: 702.61a, 702.61b

Full text of each gold rule:
[702.61a] Split Second Split second is a static ability that functions only while the spell with split second is on the stack. “Split second” means “As long as this spell is on the stack, players can’t cast other spells or activate abilities that aren’t mana abilities.”
[702.61b] Split Second Players may activate mana abilities and take special actions while a spell with split second is on the stack. Triggered abilities trigger and are put on the stack as normal while a spell with split second is on the stack.

Arm's answer:
answered: True
citations: ['702.61a', '702.61b', '113.4', '605.3b', '405.6c', '605.3a', '608.2g']
text: Short answer
Yes. While a spell with split second is on the stack you may activate mana abilities; you may not cast spells or activate non‑mana abilities.

Definitions (from the provided rules)
- Split second: a static ability that functions only while the spell with split second is on the stack. “Split second” means “As long as this spell is on the stack, players can’t cast other spells or activate abilities that aren’t mana abilities.” [702.61a]
- Mana ability: some activated or triggered abilities that are classified as mana abilities. Mana abilities follow special rules: they don’t use the stack, and under certain circumstances a player can activate them even if they don’t have priority. See rule 605, “Mana Abilities.” [113.4]

What actually happens at the table
- The split second spell sits on the stack and prevents players from casting spells or activating abilities that aren’t mana abilities. You can still activate mana abilities while that spell is on the stack. [702.61a] [702.61b]
- When you activate a mana ability it does not go on the stack and it resolves immediately (so it can’t be targeted or countered as a spell or ability could). If the mana ability produces mana and also has another effect, the mana is produced and the other effect happens immediately. After the mana ability resolves, priority is returned as described by the mana‑ability rules. [605.3b] [405.6c]
- You may also activate mana abilities when a rule asks for a mana payment or while casting/ resolving a spell or ability that allows/requests a mana payment. (Mana abilities can be activated in those situations per the mana rules.) [605.3a] [608.2g]

Practical example a player can act on
If an opponent casts a spell with split second and it’s on the stack, you can tap lands or other permanents to activate mana abilities to produce mana (those activations resolve immediately). You cannot cast a spell or activate an activated ability that is not a mana ability while that split second spell remains on the stack. [702.61a] [702.61b] [605.3b]


---

### Cell 32: id=c001

Question: [Counterspell] is on top of the stack targeting my [Divination]. When everyone passes priority, what resolves first, and does Divination still resolve?

Gold rules:
No gold rule set is recorded for this question -- grade based on whether the answer is internally coherent, directly responsive to the question, and not self-contradictory. You have no rule text here to check its substance against, so do not assert it is rules-correct beyond that coherence check; say so plainly in your reason.

Card data:
Counterspell {U}{U} -- Instant  (MV 2, color identity U)
Counter target spell.

Divination {2}{U} -- Sorcery  (MV 3, color identity U)
Draw two cards.

Arm's answer:
answered: True
citations: ['608.1', '117.7', '701.6a', '112.1', '601.2a', '608.2n', '701.6b', 'Counterspell', 'Divination']
text: Short answer — Counterspell (the instant on top of the stack) resolves first. When it resolves it counters the targeted Divination, so Divination is removed from the stack and doesn’t resolve; it’s put into its owner’s graveyard.

Definitions and reasoning a player can act on:
- “Resolve” — when the spell on top of the stack has its instructions followed and has its effect (see 608.1 and 608.2n). Each time all players pass in succession, the object on top of the stack resolves (608.1).
- “Counter” — to cancel a spell or ability so it doesn’t resolve and none of its effects occur; a countered spell is put into its owner’s graveyard (701.6a).

What happens here, step by step:
1. Both spells are on the stack; Counterspell is the topmost object. Spells on the stack remain there until they resolve or are countered (112.1, 601.2a).
2. When all players pass and the game attempts to resolve the top object, the top object (Counterspell) resolves first (608.1; see also that a spell played in response resolves first, 117.7).
3. Counterspell’s effect is “Counter target spell” (Counterspell). When Counterspell resolves, it counters the targeted Divination: that means Divination is canceled, removed from the stack, and put into its owner’s graveyard (701.6a; Counterspell).
4. Because Divination was countered, it does not get to resolve and therefore does not produce its draw effect. As a final cleanup note, as part of resolving an instant or sorcery the resolving spell is put into its owner’s graveyard (608.2n). Also, the player whose spell was countered doesn’t get a refund of costs paid (701.6b).

Zones named: the stack (where the spells are), and the owner’s graveyard (where the countered Divination is put).


---

### Cell 33: id=c002

Question: My [Charging Rhino] has trample and is blocked by [Vampire Nighthawk], which has deathtouch. How much combat damage do I have to assign to the blocker before I can trample the rest over to the player?

Gold rules:
No gold rule set is recorded for this question -- grade based on whether the answer is internally coherent, directly responsive to the question, and not self-contradictory. You have no rule text here to check its substance against, so do not assert it is rules-correct beyond that coherence check; say so plainly in your reason.

Card data:
Charging Rhino {3}{G}{G} -- Creature — Rhino -- 4/4  (MV 5, color identity G)
This creature can't be blocked by more than one creature.

Vampire Nighthawk {1}{B}{B} -- Creature — Vampire Shaman -- 2/3  (MV 3, color identity B)
Flying
Deathtouch (Any amount of damage this deals to a creature is enough to destroy it.)
Lifelink (Damage dealt by this creature also causes you to gain that much life.)

Arm's answer:
answered: True
citations: ['702.19b', '120.4a', '510.1a', 'Lethal Damage', '702.2c', '702.19a', 'Charging Rhino', 'Vampire Nighthawk']
text: Short answer
You must assign at least 3 damage from Charging Rhino to the blocking Vampire Nighthawk before you can assign any of the Rhino’s combat damage to the defending player.

Why (definitions and rules you can act on)
- Trample: a static ability that changes how an attacking creature assigns combat damage during the combat damage step (see Combat Damage Step). The controller of the attacking creature assigns damage to blocking creature(s) first; once all blocking creatures have been assigned lethal damage, any excess may be assigned to the defending player (see rules on trample and assigning combat damage). [702.19a, 702.19b, 510.1a]
- Lethal damage: an amount of damage greater than or equal to a creature’s toughness. When determining how much damage must be assigned as lethal, take into account damage already marked on the creature and damage from other creatures being assigned at the same time, but do not take into account abilities or effects that change the amount of damage actually dealt. [Lethal Damage, 120.4a, 702.19b]
- Deathtouch: any nonzero amount of damage dealt to a creature by a source that has deathtouch is considered lethal for the purposes of determining excess damage (this matters only if the source dealing the damage has deathtouch). [702.2c, 120.4a]

Apply to your board state
- Charging Rhino is a 4/4 attacker. Vampire Nighthawk is a 2/3 with deathtouch. (Card data: Charging Rhino; Vampire Nighthawk.)
- Because the Rhino (the source assigning damage to the blocker) does not have deathtouch, lethal damage equals the Nighthawk’s toughness: 3. You therefore must assign at least 3 damage to the Nighthawk before any of the Rhino’s combat damage can be assigned to the defending player. [Charging Rhino; Vampire Nighthawk; Lethal Damage; 702.19b; 510.1a]

Note
- The Nighthawk’s deathtouch does not reduce the amount the attacker must assign, because deathtouch only makes damage from a source with deathtouch count as lethal; the blocking creature’s own deathtouch is not the source of the damage the Rhino is assigning. [702.2c, 120.4a]


---

### Cell 34: id=c003

Question: I have [Monastery Swiftspear] on the battlefield and I cast [Shardless Agent]. When its cascade ability puts a noncreature spell onto the stack, does Monastery Swiftspear's prowess trigger before or after that cascaded spell resolves?

Gold rules:
No gold rule set is recorded for this question -- grade based on whether the answer is internally coherent, directly responsive to the question, and not self-contradictory. You have no rule text here to check its substance against, so do not assert it is rules-correct beyond that coherence check; say so plainly in your reason.

Card data:
Monastery Swiftspear {R} -- Creature — Human Monk -- 1/2  (MV 1, color identity R)
Haste
Prowess (Whenever you cast a noncreature spell, this creature gets +1/+1 until end of turn.)
Rulings:
- [Monastery Swiftspear ruling #2] Prowess goes on the stack on top of the spell that caused it to trigger. It will resolve before that spell.
- [Monastery Swiftspear ruling #3] Once it triggers, prowess isn't connected to the spell that caused it to trigger. If that spell is countered, prowess will still resolve.
- [Monastery Swiftspear ruling #1] Any spell you cast that doesn't have the type creature will cause prowess to trigger. If a spell has multiple types, and one of those types is creature (such as an artifact creature), casting it won't cause prowess to trigger. Playing a land also won't cause prowess to trigger.

Shardless Agent {1}{G}{U} -- Artifact Creature — Human Rogue -- 2/2  (MV 3, color identity G/U)
Cascade (When you cast this spell, exile cards from the top of your library until you exile a nonland card that costs less. You may cast it without paying its mana cost. Put the exiled cards on the bottom in a random order.)
Rulings:
- [Shardless Agent ruling #1] Cascade triggers when you cast the spell, meaning that it resolves before that spell. If you end up casting the exiled card, it will go on the stack above the spell with cascade.
- [Shardless Agent ruling #7] Due to a 2021 rules change to cascade, not only do you stop exiling cards if you exile a nonland card with lesser mana value than the spell with cascade, but the resulting spell you cast must also have lesser mana value. Previously, in cases where a card's mana value differed from the resulting spell, such as with some modal double-faced cards or cards with an Adventure, you could cast a spell with a higher mana value than the exiled card.

Arm's answer:
answered: True
citations: ['601.2i', '702.108a', '702.85a', '608.2g', 'Shardless Agent ruling #1', 'Monastery Swiftspear ruling #2', 'Monastery Swiftspear ruling #3']
text: Short answer: Prowess will trigger when you cast the cascaded noncreature spell and that prowess trigger will go on the stack above the cascaded spell, so the prowess ability resolves before the cascaded spell resolves.

Definitions (from the provided rules):
- "Cast": to take a card from where it is, put it on the stack, and pay its costs (see rule 601.2i). Casting a spell is the event that causes prowess to trigger.
- "Prowess": a triggered ability that says “Whenever you cast a noncreature spell, this creature gets +1/+1 until end of turn” (see rule 702.108a).
- "Cascade": a triggered ability that triggers when you cast the spell with cascade and may let you cast an exiled nonland card (see rule 702.85a).

Why, step by step:
1) When you cast Shardless Agent, its cascade ability triggers and will resolve before Shardless Agent (Shardless Agent ruling #1 and rule 702.85a).
2) As that cascade ability resolves you may cast the exiled noncreature card. A spell cast this way is put on the stack as the topmost object while the cascade ability continues resolving (rule 608.2g and Shardless Agent ruling #1).
3) Casting that exiled noncreature spell is a cast event that causes Monastery Swiftspear’s prowess to trigger (rule 601.2i and rule 702.108a).
4) Prowess goes on the stack on top of the spell that caused it to trigger and thus resolves before that spell (Monastery Swiftspear ruling #2). (If the cascaded spell is later countered, the prowess trigger still resolves — Monastery Swiftspear ruling #3.)

Result: The Swiftspear’s +1/+1 from prowess will be applied (by resolving the triggered ability) before the cascaded spell resolves.

---

### Cell 35: id=c004

Question: My opponent's [Grizzly Bears] has 2 damage marked on it. Do state-based actions make it die before my [Lightning Bolt] resolves?

Gold rules:
Match semantics: groups
  Group 1 (satisfied by ANY ONE of): 704.3
  Group 2 (satisfied by ANY ONE of): 120.5
  Group 3 (satisfied by ANY ONE of): 117.2d
  Group 4 (satisfied by ANY ONE of): 704.5g, 704.4, 120.6, 302.7
  ALL groups above must be satisfied.

Full text of each gold rule:
[704.3] Whenever a player would get priority (see rule 117, “Timing and Priority”), the game checks for any of the listed conditions for state-based actions, then performs all applicable state-based actions simultaneously as a single event. If any state-based actions are performed as a result of a check, the check is repeated; otherwise all triggered abilities that are waiting to be put on the stack are put on the stack, then the check is repeated. Once no more state-based actions have been performed as the result of a check and no triggered abilities are waiting to be put on the stack, the appropriate player gets priority. This process also occurs during the cleanup step (see rule 514), except that if no state-based actions are performed as the result of the step’s first check and no triggered abilities are waiting to be put on the stack, then no player gets priority and the step ends.
[120.5] Damage dealt to a creature, planeswalker, or battle doesn’t destroy it. Likewise, the source of that damage doesn’t destroy it. Rather, state-based actions may destroy a creature or otherwise put a permanent into its owner’s graveyard, due to the results of the damage dealt to that permanent. See rule 704. A player casts Lightning Bolt, an instant that says “Lightning Bolt deals 3 damage to any target,” targeting a 2/2 creature. After Lightning Bolt deals 3 damage to that creature, the creature is destroyed as a state-based action. Neither Lightning Bolt nor the damage dealt by Lightning Bolt destroyed that creature.
[117.2d] Other kinds of abilities and actions are automatically generated or performed by the game rules, or are performed by players without receiving priority. State-based actions happen automatically when certain conditions are met. See rule 704. They’re dealt with before a player would receive priority. See rule 117.5.
[704.5g] The state-based actions are as follows: If a creature has toughness greater than 0, it has damage marked on it, and the total damage marked on it is greater than or equal to its toughness, that creature has been dealt lethal damage and is destroyed. Regeneration can replace this event.
[704.4] Unlike triggered abilities, state-based actions pay no attention to what happens during the resolution of a spell or ability. A player controls Maro, a creature with the ability “Maro’s power and toughness are each equal to the number of cards in your hand” and casts a spell whose effect is “Discard your hand, then draw seven cards.” Maro will temporarily have toughness 0 in the middle of the spell’s resolution but will be back up to toughness 7 when the spell finishes resolving. Thus Maro will survive when state-based actions are checked. In contrast, an ability that triggers when the player has no cards in hand goes on the stack after the spell resolves, because its trigger event happened during resolution.
[120.6] Damage marked on a creature remains until the cleanup step, even if that permanent stops being a creature. If the total damage marked on a creature is greater than or equal to its toughness, that creature has been dealt lethal damage and is destroyed as a state-based action (see rule 704). All damage marked on a permanent is removed when it regenerates (see rule 701.19, “Regenerate”) and during the cleanup step (see rule 514.2).
[302.7] Damage dealt to a creature by a source with neither wither nor infect is marked on that creature (see rule 120.3). If the total damage marked on that creature is greater than or equal to its toughness, that creature has been dealt lethal damage and is destroyed as a state-based action (see rule 704). All damage marked on a creature is removed when it regenerates (see rule 701.19, “Regenerate”) and during the cleanup step (see rule 514.2).

Card data:
Grizzly Bears {1}{G} -- Creature — Bear -- 2/2  (MV 2, color identity G)

Lightning Bolt {R} -- Instant  (MV 1, color identity R)
Lightning Bolt deals 3 damage to any target.

Arm's answer:
answered: True
citations: ['117.2d', '704.3', '405.6f', '704.5g', '302.7', '120.6', '704.4', 'Grizzly Bears', 'Lightning Bolt']
text: Definition — State-based actions (SBAs) are game-rule checks that the game performs automatically whenever a player would get priority; they aren’t on the stack and happen without players receiving priority (see rules 117.2d, 704.3, 405.6f).

What causes the Bears to die — If a creature has damage marked on it and the total damage marked is greater than or equal to its toughness, it’s been dealt lethal damage and is destroyed as a state-based action (see rules 704.5g and 302.7). Damage marked on a creature remains until cleanup (see rule 120.6). Grizzly Bears is a 2/2 and Lightning Bolt deals 3 damage (see the Grizzly Bears and Lightning Bolt card data).

Timing vs. Lightning Bolt resolving — State-based actions are not checked during the resolution of a spell or ability (see rule 704.4). They are checked whenever the game would next give a player priority (see rule 704.3). Therefore:
- If Lightning Bolt is already in the process of resolving, SBAs will not be checked mid-resolution, so the Bears will not be destroyed by SBAs before that Lightning Bolt finishes resolving (704.4, 704.3). Lightning Bolt will deal its damage, then SBAs are checked afterward.  
- If the Bears already had lethal damage marked before you began resolving the Lightning Bolt (i.e., the lethal damage existed at the last time SBAs were checked), SBAs would already have destroyed it at the next SBA check prior to that point (704.5g, 302.7, 704.3).

Short play takeaway: SBAs aren’t checked during Lightning Bolt’s resolution (so they don’t interrupt a spell that’s resolving), but if the creature already had lethal damage before that point it would already have been removed by the previous SBA check.

---

### Cell 36: id=c005

Question: It's my upkeep. My [Phyrexian Arena]'s beginning-of-upkeep trigger and my opponent's own beginning-of-upkeep trigger both want to go on the stack. Who chooses the order, and when exactly do they trigger?

Gold rules:
No gold rule set is recorded for this question -- grade based on whether the answer is internally coherent, directly responsive to the question, and not self-contradictory. You have no rule text here to check its substance against, so do not assert it is rules-correct beyond that coherence check; say so plainly in your reason.

Card data:
Phyrexian Arena {1}{B}{B} -- Enchantment  (MV 3, color identity B)
At the beginning of your upkeep, you draw a card and you lose 1 life.

Arm's answer:
answered: True
citations: ['[500.6]', '[603.2b]', '[603.3b]', '[117.3a]', '[503.1a]', '[805.7]', '[Phyrexian Arena {1}{B}{B} -- Enchantment  (MV 3, color identity B) At the beginning of your upkeep, you draw a card and you lose 1 life.]']
text: Definitions —
- Triggered ability / “trigger”: an ability that automatically triggers when its trigger event happens (for example, “At the beginning of your upkeep…”). When the event happens, the ability “triggers” (it’s recorded as having triggered) but does not yet do anything until it’s put on the stack. [603.2b]
- Upkeep step: the upkeep step of the active player’s turn. Abilities that trigger “at the beginning of” a step trigger when that step begins. [500.6][503.1a]
- The stack: where triggered abilities are put and wait to resolve. Triggered abilities are put on the stack the next time a player would receive priority. [603.3b][117.3a]

What happens in your situation —
1) When your upkeep begins, both your Phyrexian Arena’s “At the beginning of your upkeep…” ability and your opponent’s beginning-of-upkeep ability trigger at that moment. (Both abilities trigger when the upkeep step begins.) [500.6][603.2b] Phyrexian Arena’s oracle text: “At the beginning of your upkeep, you draw a card and you lose 1 life.” (This is not optional.) [Phyrexian Arena {1}{B}{B} -- Enchantment  (MV 3, color identity B) At the beginning of your upkeep, you draw a card and you lose 1 life.]

2) Those triggered abilities are put onto the stack the next time a player would receive priority (which is immediately as the upkeep begins; the active player receives priority at the beginning of the step). [117.3a][503.1a][500.6]

3) If multiple triggered abilities have triggered since the last time a player received priority, they are placed on the stack using the APNAP placement rules: the active player (you) puts all triggered abilities you control that meet the first-part criteria on the stack in any order he or she chooses, then the nonactive player (your opponent) does the same. Concretely here, you put your upkeep-triggering ability (Phyrexian Arena) onto the stack first, then your opponent puts their beginning-of-upkeep trigger on top of it. That means your opponent’s trigger will resolve before your Arena trigger. [603.3b]

4) In a team game the same idea applies but the active team places all the team’s triggered abilities first, then each nonactive team in turn order. [805.7]

Summary action for the player: when your upkeep begins both triggers occur; you (the active player) put your upkeep triggers onto the stack first, then your opponent puts theirs on top, so your opponent’s upkeep ability will resolve before your Phyrexian Arena does. [500.6][603.2b][603.3b][117.3a][503.1a][805.7][Phyrexian Arena {1}{B}{B} -- Enchantment  (MV 3, color identity B) At the beginning of your upkeep, you draw a card and you lose 1 life.]

---

### Cell 37: id=c006

Question: I cast a sorcery with buyback and pay its buyback cost, then copy that spell with [Fork]. Once everything resolves, how many copies of the card end up back in my hand?

Gold rules:
No gold rule set is recorded for this question -- grade based on whether the answer is internally coherent, directly responsive to the question, and not self-contradictory. You have no rule text here to check its substance against, so do not assert it is rules-correct beyond that coherence check; say so plainly in your reason.

Card data:
Fork {R}{R} -- Instant  (MV 2, color identity R)
Copy target instant or sorcery spell, except that the copy is red. You may choose new targets for the copy.
Rulings:
- [Fork ruling #8] If you copy a spell for which Buyback has been paid, you get nothing back since the copied spell does not have a card to give you.
- [Fork ruling #10] The Fork card goes to the graveyard when it resolves and leaves the copy on the stack. There is no card representing the copy on the stack.
- [Fork ruling #9] The copy that is placed on the stack is not considered to have been "cast".

Arm's answer:
answered: True
citations: ['702.27a', '707.10', '112.1a', '704.5e', 'Fork ruling #8', 'Fork ruling #10', 'Fork ruling #9']
text: Short answer and why
- Only one card (the original sorcery card you cast) ends up back in your hand. The copied spell does not return a card.

Definitions
- Buyback: “Buyback [cost]” is a static ability on an instant or sorcery while it’s on the stack. If the buyback cost was paid as you cast the spell, that spell is put into its owner’s hand instead of that player’s graveyard as it resolves [702.27a].
- Copy of a spell: A copy is a spell put onto the stack by an effect; a copy is itself a spell but is not a card and was not cast [707.10], [112.1a].

What happens in this interaction
1. You cast the sorcery and pay its buyback cost. The original spell is a spell represented by its card on the stack and has buyback applied to it [112.1a], [702.27a].
2. You copy that spell with Fork. Fork puts a copy of the spell onto the stack; that copy is not a card and was not cast [Fork ruling #10], [Fork ruling #9], [707.10].
3. When the original spell resolves, because you paid buyback it’s put into its owner’s hand instead of the graveyard [702.27a]. The Fork card itself goes to its controller’s graveyard when Fork resolves [Fork ruling #10].
4. The copied spell, being a copy and not a card, can’t return a card to your hand. Official guidance explicitly says you get nothing back from a copied spell for which buyback was paid because the copied spell has no card to give you [Fork ruling #8]. Also, copies cease to exist if they would be in a zone other than the stack [704.5e], so there is no separate card created to put into your hand.

Result: only the original card returns to your hand (one card). The copy does not produce a card you can put into your hand.


---

### Cell 38: id=c007

Question: I have a face-down manifested card that's really [Lightning Bolt]. It dies and I imprint it on [Mimic Vat]. Later I activate Mimic Vat's copy ability -- do I get a token?

Gold rules:
No gold rule set is recorded for this question -- grade based on whether the answer is internally coherent, directly responsive to the question, and not self-contradictory. You have no rule text here to check its substance against, so do not assert it is rules-correct beyond that coherence check; say so plainly in your reason.

Card data:
Lightning Bolt {R} -- Instant  (MV 1, color identity R)
Lightning Bolt deals 3 damage to any target.

Mimic Vat {3} -- Artifact  (MV 3)
Imprint — Whenever a nontoken creature dies, you may exile that card. If you do, return each other card exiled with this artifact to its owner's graveyard.
{3}, {T}: Create a token that's a copy of a card exiled with this artifact. It gains haste. Exile it at the beginning of the next end step.
Rulings:
- [Mimic Vat ruling #0] If the creature that dies is an instant or sorcery card that's been manifested, Mimic Vat may have a nonpermanent card exiled. You can't create a token that's a copy of a nonpermanent card. No token is created in this case.
- [Mimic Vat ruling #6] You may activate the second ability even if no card has been exiled with Mimic Vat. If no card has been exiled with Mimic Vat by the time the ability resolves, no token will be created.
- [Mimic Vat ruling #4] The token created by the second ability will be a copy of whatever card is exiled with Mimic Vat at the time the ability resolves. This might not be the same card that was exiled with Mimic Vat at the time the ability was activated. It also might not be a creature card.

Arm's answer:
answered: True
citations: ['[701.40g]', '[Mimic Vat ruling #0]']
text: No. A manifested Lightning Bolt is an instant card that was exiled with Mimic Vat. That means the card exiled with the artifact is a nonpermanent (an instant), and you can’t create a token that’s a copy of a nonpermanent card. Therefore when you later activate Mimic Vat’s ability and it resolves, no token is created.

Definitions and zones involved:
- "Manifested" (per rule [701.40g]): a manifested permanent represented by an instant or sorcery card is still treated as a face-down permanent on the battlefield, but the underlying card is an instant or sorcery. When that manifested face-down permanent dies and Mimic Vat exiles that card, the instant card ends up exiled with the artifact (the exile zone).
- Mimic Vat’s imprint/exile and token-creation ability then looks at the card exiled with the artifact. Because the exiled card is a nonpermanent card (Lightning Bolt, an instant), you can’t create a token that’s a copy of it, so no token is created.

You can act on this: do not expect a creature token when the exiled card is an instant or sorcery.

---

### Cell 39: id=c008

Question: My [Fiend Hunter]'s enters-the-battlefield ability is on the stack, about to exile a creature. I copy that ability with [Lithoform Engine] and target a second creature. Both get exiled. When Fiend Hunter later leaves the battlefield, do both come back?

Gold rules:
No gold rule set is recorded for this question -- grade based on whether the answer is internally coherent, directly responsive to the question, and not self-contradictory. You have no rule text here to check its substance against, so do not assert it is rules-correct beyond that coherence check; say so plainly in your reason.

Card data:
Fiend Hunter {1}{W}{W} -- Creature — Human Cleric -- 1/3  (MV 3, color identity W)
When this creature enters, you may exile another target creature.
When this creature leaves the battlefield, return the exiled card to the battlefield under its owner's control.
Rulings:
- [Fiend Hunter ruling #0] If Fiend Hunter leaves the battlefield before its first ability has resolved, its second ability will trigger and do nothing. Then its first ability will resolve and exile the target creature indefinitely. This is different from abilities on other cards that exile a permanent "until" something happens.
- [Fiend Hunter ruling #3] In a multiplayer game, if you lose the game, the creature exiled with Fiend Hunter remains exiled indefinitely. This is also different from abilities on other cards that exile a permanent "until" something happens.
- [Fiend Hunter ruling #1] Once the exiled creature returns, it's considered a new object with no relation to the object that it was. Auras attached to the exiled creature will be put into their owners' graveyards. Equipment attached to the exiled creature will become unattached and remain on the battlefield. Any counters on the exiled creature will cease to exist.

Lithoform Engine {4} -- Legendary Artifact  (MV 4)
{2}, {T}: Copy target activated or triggered ability you control. You may choose new targets for the copy.
{3}, {T}: Copy target instant or sorcery spell you control. You may choose new targets for the copy.
{4}, {T}: Copy target permanent spell you control. (The copy becomes a token.)
Rulings:
- [Lithoform Engine ruling #4] If an ability is linked to a second ability, copies of that first ability are also linked to that second ability. If the second ability refers to “the exiled card,” it refers to all cards exiled by the first ability and the copy. For example, if Fiend Hunter's enters-the-battlefield ability is copied and two creatures are exiled, they both return when Fiend Hunter leaves the battlefield.
- [Lithoform Engine ruling #5] Lithoform Engine can copy any spell or ability on the stack, not just one with targets. If a permanent spell is copied, new targets can't be chosen for it, if it has any (perhaps because it's an Aura or a mutating creature spell).

Arm's answer:
answered: True
citations: ['[607.2a]', '[607.3]', '[Lithoform Engine ruling #4]', '[Fiend Hunter]']
text: Short answer — Yes. Fiend Hunter’s leave-the-battlefield triggered ability will return both creatures that were exiled when its enters-the-battlefield ability and its Lithoform Engine copy resolved.

Why: Fiend Hunter has an enters-the-battlefield ability that instructs you to exile one or more cards and a leaves-the-battlefield ability that refers to “the exiled card.” Those two abilities are a pair of linked abilities (an ability that exiles cards and an ability that refers to cards exiled with that object) and the second ability refers only to cards exiled by the first ability [607.2a]. If the exile instruction exiled multiple cards (for example because you copied the exile ability with Lithoform Engine), the ability that refers to “the exiled card” refers to each of those exiled cards and performs its action on each of them [607.3]. Lithoform Engine’s ruling explicitly confirms this interaction using Fiend Hunter as an example: if Fiend Hunter’s enter-the-battlefield ability is copied and two creatures are exiled, they both return when Fiend Hunter leaves the battlefield [Lithoform Engine ruling #4].

Definitions and zones involved
- Linked abilities: a pair consisting of (a) an activated or triggered ability that instructs a player to exile one or more cards and (b) an ability that refers to “the exiled cards” or cards “exiled with [this object]”; the second ability refers only to the cards exiled by the first [607.2a].
- Zones named: the exile zone (where the creatures were put) and the battlefield (where Fiend Hunter’s leaves-the-battlefield trigger returns the exiled card(s)).

Practical result for players: If you copy Fiend Hunter’s ETB exile ability with Lithoform Engine and exile two creatures, then later Fiend Hunter leaves the battlefield, its LTB trigger will return both of those exiled creatures to the battlefield under their owners’ control.


---

### Cell 40: id=c009

Question: My own [Banishing Light] has an opponent's creature exiled. On my opponent's turn I cast [Teferi's Protection], phasing out my Banishing Light. Does the exiled creature return to the battlefield?

Gold rules:
No gold rule set is recorded for this question -- grade based on whether the answer is internally coherent, directly responsive to the question, and not self-contradictory. You have no rule text here to check its substance against, so do not assert it is rules-correct beyond that coherence check; say so plainly in your reason.

Card data:
Banishing Light {2}{W} -- Enchantment  (MV 3, color identity W)
When this enchantment enters, exile target nonland permanent an opponent controls until this enchantment leaves the battlefield.
Rulings:
- [Banishing Light ruling #1] If Banishing Light leaves the battlefield before its triggered ability resolves, the target permanent won’t be exiled.
- [Banishing Light ruling #5] If Banishing Light leaves the battlefield before its triggered ability resolves, the target permanent won't be exiled.
- [Banishing Light ruling #7] If a token is exiled this way, it will cease to exist and won't return to the battlefield.

Teferi's Protection {2}{W} -- Instant  (MV 3, color identity W)
Until your next turn, your life total can't change and you gain protection from everything. All permanents you control phase out. (While they're phased out, they're treated as though they don't exist. They phase in before you untap during your untap step.)
Exile Teferi's Protection.
Rulings:
- [Teferi's Protection ruling #21] Any one-shot effects that are waiting "until [this] leaves the battlefield," such as that of Banishing Light, won't happen when a permanent phases out.
- [Teferi's Protection ruling #26] If your untap step is somehow skipped as your next turn begins, your phased-out permanents won't phase in until the next untap step you actually have, but you'll no longer have protection from everything and your life total can change again.
- [Teferi's Protection ruling #17] Phasing out doesn't cause any "leaves the battlefield" abilities to trigger. Similarly, phasing in won't cause any "enters the battlefield" abilities to trigger.

Arm's answer:
answered: True
citations: ['Banishing Light', "[Teferi's Protection ruling #21]", '[702.26d]', '[702.26c]']
text: Short answer: No. The opponent’s creature stays exiled while your Banishing Light is phased out and will only return if Banishing Light actually leaves the battlefield.

Definition (phasing): When a permanent phases out it is treated as though it doesn’t exist until it phases in again; phasing doesn’t actually move the permanent to another zone or change its controller (the permanent’s status simply becomes “phased out,” and later “phased in” when it returns) [702.26d, 702.26c].

Why the creature stays exiled: Banishing Light’s effect exiles the creature “until this [Banishing Light] leaves the battlefield” (Banishing Light card text). Phasing Banishing Light out doesn’t cause it to leave the battlefield, and the game rules and Teferi’s Protection’s ruling make clear that a phasing event does not cause the one-shot “until [this] leaves the battlefield” effect to happen when the permanent phases out. In other words, the delayed return tied to Banishing Light leaving the battlefield won’t occur just because Banishing Light phased out [Banishing Light; [Teferi's Protection ruling #21]; 702.26d].

Practical outcome: The exiled creature remains in exile while Banishing Light is phased out. It will return only if Banishing Light actually leaves the battlefield later (for example, is destroyed or sacrificed); merely phasing Banishing Light back in does not itself make the creature return.


---

### Cell 41: id=c010

Question: I cast [Emrakul, the Promised End]. In response to its cast trigger, my opponent tries to [Counterspell] it. Can they even target it given protection from instants, and if it's countered, do I still control their next turn?

Gold rules:
No gold rule set is recorded for this question -- grade based on whether the answer is internally coherent, directly responsive to the question, and not self-contradictory. You have no rule text here to check its substance against, so do not assert it is rules-correct beyond that coherence check; say so plainly in your reason.

Card data:
Emrakul, the Promised End {13} -- Legendary Creature — Eldrazi -- 13/13  (MV 13)
This spell costs {1} less to cast for each card type among cards in your graveyard.
When you cast this spell, you gain control of target opponent during that player's next turn. After that turn, that player takes an extra turn.
Flying, trample, protection from instants
Rulings:
- [Emrakul, the Promised End ruling #1] Protection from instants means that Emrakul can’t be the target of instant spells or activated or triggered abilities from instant cards, and damage that would be dealt to it by instant spells or cards is prevented. Instant spells may still affect it in other ways; for example, it would still receive the bonus from Rally the Peasants.
- [Emrakul, the Promised End ruling #2] Protection abilities only apply while the object with the ability is on the battlefield. Notably, Emrakul may be the target of a spell that targets it while on the stack, such as Syncopate.
- [Emrakul, the Promised End ruling #14] Multiple player-controlling effects that affect the same player overwrite each other. The last one to be created is the one that works. If multiple players have cast Emrakul and targeted the same player, each ability’s effect will create an extra turn.

Counterspell {U}{U} -- Instant  (MV 2, color identity U)
Counter target spell.

Arm's answer:
answered: True
citations: ['405.1', '601.2i', '603.1a', '115.1a', '117.7', '608.2m', '113.9', '[Emrakul, the Promised End ruling #1]', '[Emrakul, the Promised End ruling #2]', 'Emrakul, the Promised End {13}']
text: Short answer
Yes — your opponent can cast Counterspell targeting Emrakul while Emrakul is on the stack, and if Counterspell resolves and counters Emrakul the triggered “When you cast this spell …” ability still exists and will resolve, so you will gain control of the targeted opponent during that player’s next turn and that player will then get an extra turn.

Why (definitions and step-by-step, with the exact zones/objects named)
- “Protection from instants” for Emrakul means Emrakul can’t be targeted by instant spells while Emrakul is on the battlefield, but that protection only applies while Emrakul is on the battlefield; a spell on the stack can be targeted (Emrakul may be targeted while it’s on the stack) ([Emrakul, the Promised End ruling #1], [Emrakul, the Promised End ruling #2]).
- When you cast Emrakul, the physical card is put on the stack (the spell object on the stack) and the spell’s “When you cast this spell…” triggered ability is created (that triggered ability is a separate object that will be put on the stack) ([405.1], [601.2i], [603.1a]).
- An opponent may cast an instant “in response” to that triggered ability (i.e., while the Emrakul spell is on the stack); that instant can target the Emrakul spell on the stack because protection doesn’t apply off the battlefield ([117.7], [Emrakul, the Promised End ruling #2]).
- If Counterspell resolves and successfully counters the Emrakul spell on the stack, that affects the spell object on the stack but does not remove or undo the triggered ability that was created when you cast Emrakul — the triggered ability is already on the stack (targets for that triggered ability were chosen when it was put on the stack) and is independent of whether the spell later resolves ([601.2i], [115.1a], [603.1a]).
- Triggered abilities on the stack are not spells and can only be countered by effects that specifically counter abilities; a generic Counterspell (which counters a spell) does not counter a triggered ability on the stack ([113.9]).
- Once that triggered ability starts to resolve, it will resolve fully and will apply its effect (you gain control of the targeted opponent during that player’s next turn; after that turn that player takes an extra turn) ([608.2m], Emrakul, the Promised End {13}).

Practical result: your opponent can target and counter the Emrakul spell while it’s on the stack, but that does not stop the already-created triggered ability from resolving; you will still gain control of the chosen opponent during that opponent’s next turn and they will then get an extra turn afterward.

---

### Cell 42: id=c011

Question: My cascade spell exiles cards until it hits [Valki, God of Lies], whose back face is the seven-mana planeswalker Tibalt, Cosmic Impostor. Is that a legal cascade hit, and can I cast the Tibalt side for free?

Gold rules:
Match semantics: any
  ANY ONE of these satisfies it: 702.85a

Full text of each gold rule:
[702.85a] Cascade Cascade is a triggered ability that functions only while the spell with cascade is on the stack. “Cascade” means “When you cast this spell, exile cards from the top of your library until you exile a nonland card whose mana value is less than this spell’s mana value. You may cast that card without paying its mana cost if the resulting spell’s mana value is less than this spell’s mana value. Then put all cards exiled this way that weren’t cast on the bottom of your library in a random order.”

Card data:
Valki, God of Lies // Tibalt, Cosmic Impostor  (modal_dfc, MV 2, color identity B/R)
Face 1: Valki, God of Lies {1}{B} -- Legendary Creature — God -- 2/1
When Valki enters, each opponent reveals their hand. For each opponent, exile a creature card they revealed this way until Valki leaves the battlefield.
{X}: Choose a creature card exiled with Valki with mana value X. Valki becomes a copy of that card.
Face 2: Tibalt, Cosmic Impostor {5}{B}{R} -- Legendary Planeswalker — Tibalt -- loyalty 5
As Tibalt enters, you get an emblem with "You may play cards exiled with Tibalt, Cosmic Impostor, and you may spend mana as though it were mana of any color to cast those spells."
+2: Exile the top card of each player's library.
−3: Exile target artifact or creature.
−8: Exile all graveyards. Add {R}{R}{R}.
Rulings:
- [Valki, God of Lies // Tibalt, Cosmic Impostor ruling #16] If an effect allows you to play a land or cast a spell from among a group of cards, you may play or cast a modal double-faced card with any face that fits the criteria of that effect.
- [Valki, God of Lies // Tibalt, Cosmic Impostor ruling #20] If an effect instructs a player to choose a card name, the name of either face may be chosen. If that effect or a linked ability refers to a spell with the chosen name being cast and/or a land with the chosen name being played, it considers only the chosen name, not the other face's name.
- [Valki, God of Lies // Tibalt, Cosmic Impostor ruling #19] If an effect puts a double-faced card onto the battlefield, it enters with its front face up. If that front face can't be put onto the battlefield, it doesn't enter the battlefield.

Arm's answer:
answered: True
citations: ['[702.85a]', '[702.85b]', '[712.8c]', '[712.11c]', '[406.3b]', '[601.3e]', 'Valki, God of Lies // Tibalt, Cosmic Impostor ruling #16']
text: Short answer: Yes. Valki, God of Lies // Tibalt, Cosmic Impostor is a legal cascade hit and you may cast the Tibalt (back) face without paying its mana cost, provided the cascade spell’s mana value is greater than Valki’s mana value.

Why and how (rules you can act on):
- Cascade means “when you cast this spell, exile cards from the top of your library until you exile a nonland card whose mana value is less than this spell’s mana value. You may cast that card without paying its mana cost...” so cascade exiles from your library into exile and then gives you the option to cast the exiled card (see 702.85a and the timing of that action in 702.85b).
- Exiled cards are by default kept face up, so you can see the Valki//Tibalt card you exiled from your library (406.3b).
- A modal double-faced card’s mana value is calculated using the mana cost of its front face (712.8c). Valki’s front face has mana value 2, so the card qualifies as a cascade target if the cascade spell’s mana value is greater than 2 (702.85a combined with 712.8c).
- By default a double-faced card is cast with its front face up and only that face is evaluated when determining whether it can be cast (712.11c). However, the card’s specific ruling for Valki//Tibalt says: “If an effect allows you to play a land or cast a spell from among a group of cards, you may play or cast a modal double-faced card with any face that fits the criteria of that effect.” That ruling authorizes choosing the back (Tibalt) face when cascade lets you cast the exiled card (Valki, God of Lies // Tibalt, Cosmic Impostor ruling #16).
- Putting that together: cascade exiles Valki//Tibalt face up from your library; because its mana value is 2 (calculated from the front face), it is a legal nonland card to stop the cascade if your cascade spell’s mana value is greater than 2 (702.85a, 712.8c). When cascade gives you the option to cast that exiled card, the Valki//Tibalt ruling lets you choose to cast it with the Tibalt (back) face, and the mana-value requirement for cascade still uses the card’s mana value as above, so you may cast Tibalt without paying its mana cost.

Practical note: this assumes the cascade spell’s mana value is greater than 2. If it isn’t greater than 2, Valki wouldn’t be a legal cascade stop.

---

### Cell 43: id=c012

Question: I cast [Emrakul, the Promised End]. With its cast trigger on the stack, I copy that trigger with [Lithoform Engine]. Then I untap Lithoform Engine with [Voltaic Key] and use it again to copy [Emrakul, the Promised End] itself as a permanent spell. How many of my opponent's turns do I control, do I get a second Emrakul, and does copying the Emrakul spell give me another control-a-turn trigger?

Gold rules:
No gold rule set is recorded for this question -- grade based on whether the answer is internally coherent, directly responsive to the question, and not self-contradictory. You have no rule text here to check its substance against, so do not assert it is rules-correct beyond that coherence check; say so plainly in your reason.

Card data:
Emrakul, the Promised End {13} -- Legendary Creature — Eldrazi -- 13/13  (MV 13)
This spell costs {1} less to cast for each card type among cards in your graveyard.
When you cast this spell, you gain control of target opponent during that player's next turn. After that turn, that player takes an extra turn.
Flying, trample, protection from instants
Rulings:
- [Emrakul, the Promised End ruling #14] Multiple player-controlling effects that affect the same player overwrite each other. The last one to be created is the one that works. If multiple players have cast Emrakul and targeted the same player, each ability’s effect will create an extra turn.
- [Emrakul, the Promised End ruling #16] If the targeted player skips their next turn, you’ll control the next turn the affected player actually takes, and the extra turn the player takes will be after that turn.
- [Emrakul, the Promised End ruling #17] If the targeted player loses the game while you control their turn during a multiplayer game, the extra turn never begins.

Lithoform Engine {4} -- Legendary Artifact  (MV 4)
{2}, {T}: Copy target activated or triggered ability you control. You may choose new targets for the copy.
{3}, {T}: Copy target instant or sorcery spell you control. You may choose new targets for the copy.
{4}, {T}: Copy target permanent spell you control. (The copy becomes a token.)
Rulings:
- [Lithoform Engine ruling #5] Lithoform Engine can copy any spell or ability on the stack, not just one with targets. If a permanent spell is copied, new targets can't be chosen for it, if it has any (perhaps because it's an Aura or a mutating creature spell).
- [Lithoform Engine ruling #6] The copy is created on the stack, so it's not “cast” or “activated.” Creating the copy won't cause abilities that trigger when a player casts a spell or activates an ability to trigger. Abilities that say that a triggered ability triggers additional times won't apply to copying a triggered ability.
- [Lithoform Engine ruling #3] Lithoform Engine's first ability targets an activated or triggered ability that is on the stack and creates another instance of that ability on the stack. It doesn't cause any object to gain an ability.

Voltaic Key {1} -- Artifact  (MV 1)
{1}, {T}: Untap target artifact.

Arm's answer:
answered: False
citations: ['707.10', 'Lithoform Engine ruling #3', 'Lithoform Engine ruling #6', 'Lithoform Engine ruling #5', '707.12', '111.13', 'Emrakul, the Promised End ruling #14', 'Emrakul, the Promised End ruling #16', 'Emrakul, the Promised End ruling #17']
text: Short definitions grounded in the provided rules
- “To copy a triggered ability” means putting a copy of that triggered ability onto the stack; the copy is itself an ability and is put on the stack when the copy effect creates it (see 707.10 and Lithoform Engine ruling #3).  The copy has the same text and decisions as the original ability.
- “To copy a permanent spell” with Lithoform Engine means the Engine creates a copy on the stack; that copy is not cast and, if it resolves, it becomes a token permanent (see Lithoform Engine ruling #6, Lithoform Engine ruling #5, 707.12, and 111.13).

What happens in your exact sequence (all statements are supported by the cited rules/rulings):
1) When you cast Emrakul, the Promised End, its “When you cast this spell…” triggered ability is put on the stack. You use Lithoform Engine to copy that triggered ability; Lithoform Engine creates another instance of that triggered ability on the stack (Lithoform Engine ruling #3; copying a triggered ability is putting a copy on the stack per 707.10).
2) You untap Lithoform Engine and copy the Emrakul permanent spell. That copy is created on the stack (Lithoform Engine ruling #6) and is not a casting of Emrakul, so it does not itself cause any “When you cast this spell…” triggers to be created (Lithoform Engine ruling #6; compare with 707.12 which covers effects that instruct a player to cast a copy). If that copied permanent spell resolves, it becomes a token Emrakul as it resolves (111.13).
3) The two triggered abilities (the original Emrakul trigger and the copy-of-that-trigger) can both resolve. Each triggered ability, when it resolves, will (a) create the effect that you gain control of the targeted opponent during that player’s next turn, and (b) create the effect that after that turn that player takes an extra turn (these are the effects of Emrakul’s triggered ability; see Emrakul card text and Emrakul ruling #14 about multiple such effects).
4) Multiple player-control effects that affect the same player overwrite each other; the last control effect to be created is the one that actually determines who controls that player’s turn (Emrakul ruling #14). Creation of those control effects happens when the triggered abilities resolve, so the control effect created by the triggered ability that resolves last is the one that will be in effect for the target player’s next turn. Because the copy-of-the-trigger was created later and thus placed on the stack above the original, the copy resolves first and the original resolves afterward; therefore the original trigger (which resolves last) will be the last control effect created and so will be the one that actually determines who controls the player’s next turn (Emrakul ruling #14).
5) Both triggers create the “extra turn” effect. Emrakul’s rulings explicitly say that multiple Emrakul-trigger effects each create an extra turn for that player (Emrakul ruling #14). So you will get two extra turns for that player after the relevant turn (barring other outside effects).

Direct answers to your questions (precise and limited to the provided rules):
- How many of my opponent’s turns do I control? You will control that opponent’s next turn only once (the control effect created last by the resolving triggers is the one that works; see Emrakul ruling #14). You will not control the same next turn twice; the later-created control effect overwrites the earlier-created one.
- Do I get a second Emrakul? The Lithoform Engine copy of the Emrakul permanent spell, if it resolves, becomes a token Emrakul (111.13). Whether both Emrakul permanents remain on the battlefield afterward (for example, whether one is put into its owner’s graveyard because of the legendary rule) is not determinable from the provided rules, because the state-based/legendary rules that would govern keeping or removing multiple legendary permanents are not included in the material you gave me. I cannot answer that part without those rules.
- Does copying the Emrakul spell give me another control-a-turn trigger? No. The copy of the Emrakul permanent spell created by Lithoform Engine is created on the stack and is not cast, so it does not itself cause Emrakul’s “When you cast this spell…” trigger to be put on the stack (Lithoform Engine ruling #6). You only get the triggers you already had on the stack (the original trigger and the Lithoform-created copy of that trigger). Both of those triggers can resolve and each will create an extra-turn effect; the control effect that ends up applying for the next turn is the one created last (Emrakul ruling #14).

Multiplayer notes from the provided rulings: if the targeted player skips their next turn, you control the next turn that player actually takes and the extra turns follow that (Emrakul ruling #16). If the targeted player loses the game while you control their turn in a multiplayer game, an extra turn that would follow that never begins (Emrakul ruling #17).

Summary (TL;DR): you end up controlling the opponent’s next turn only once; the Lithoform copy of the Emrakul permanent spell becomes a token if it resolves; copying the permanent spell does not create an additional “when you cast” trigger. Whether both Emrakul permanents remain on the battlefield after resolution cannot be answered from the provided rules (legend/rulebook material about legendary permanents/state-based actions is missing).

---

### Cell 44: id=c013

Question: I've imprinted a creature on [Mimic Vat] and activate its ability to make a token copy. While that ability is on the stack, I copy it with [Lithoform Engine]. Do I get two tokens?

Gold rules:
No gold rule set is recorded for this question -- grade based on whether the answer is internally coherent, directly responsive to the question, and not self-contradictory. You have no rule text here to check its substance against, so do not assert it is rules-correct beyond that coherence check; say so plainly in your reason.

Card data:
Mimic Vat {3} -- Artifact  (MV 3)
Imprint — Whenever a nontoken creature dies, you may exile that card. If you do, return each other card exiled with this artifact to its owner's graveyard.
{3}, {T}: Create a token that's a copy of a card exiled with this artifact. It gains haste. Exile it at the beginning of the next end step.
Rulings:
- [Mimic Vat ruling #4] The token created by the second ability will be a copy of whatever card is exiled with Mimic Vat at the time the ability resolves. This might not be the same card that was exiled with Mimic Vat at the time the ability was activated. It also might not be a creature card.
- [Mimic Vat ruling #6] You may activate the second ability even if no card has been exiled with Mimic Vat. If no card has been exiled with Mimic Vat by the time the ability resolves, no token will be created.
- [Mimic Vat ruling #1] If a melded permanent dies and triggers Mimic Vat's triggered ability, both of its component cards are exiled. As Mimic Vat's second ability resolves, its controller chooses one of those cards to make a token copy of.

Lithoform Engine {4} -- Legendary Artifact  (MV 4)
{2}, {T}: Copy target activated or triggered ability you control. You may choose new targets for the copy.
{3}, {T}: Copy target instant or sorcery spell you control. You may choose new targets for the copy.
{4}, {T}: Copy target permanent spell you control. (The copy becomes a token.)
Rulings:
- [Lithoform Engine ruling #3] Lithoform Engine's first ability targets an activated or triggered ability that is on the stack and creates another instance of that ability on the stack. It doesn't cause any object to gain an ability.
- [Lithoform Engine ruling #5] Lithoform Engine can copy any spell or ability on the stack, not just one with targets. If a permanent spell is copied, new targets can't be chosen for it, if it has any (perhaps because it's an Aura or a mutating creature spell).
- [Lithoform Engine ruling #0] The source of the copy from Lithoform Engine's first ability is the same as the source of the original ability.

Arm's answer:
answered: True
citations: ['[707.10]', '[Lithoform Engine ruling #3]', '[Lithoform Engine ruling #0]', '[Mimic Vat ruling #4]', '[Mimic Vat ruling #6]', '[111.12]']
text: Short definition: “To copy ... a triggered ability” means putting a copy of that ability onto the stack; the copy is itself an ability and has the same source as the original ability ([707.10]). What happens here: Lithoform Engine’s first ability makes another instance of the Mimic Vat activated/triggered ability and puts that instance onto the stack ([Lithoform Engine ruling #3]). Each instance on the stack resolves separately. When an instance of Mimic Vat’s second ability resolves, it creates a token that’s a copy of whatever card is exiled with Mimic Vat at the time that instance resolves ([Mimic Vat ruling #4]). If no card is exiled with Mimic Vat when a particular instance resolves, that instance creates no token ([Mimic Vat ruling #6]; see also [111.12]). Because the copy’s source is the same as the original ability’s source ([Lithoform Engine ruling #0] and [707.10]), both instances refer to the same Mimic Vat and look at the card(s) exiled with it at their respective resolutions. Practical outcome: if a card is exiled with Mimic Vat when each instance resolves, you will get two tokens (one from the original ability and one from Lithoform’s copy). If there is no exiled card at the time one of the instances resolves, that instance produces no token.

---

### Cell 45: id=c014

Question: An opponent controls an untapped [Trinisphere], and I have a permanent that makes my green spells cost {1} less. I want to cast [Awaken the Woods] for value. If I cast it with X=0, what does it cost and what do I get, and what X should I actually choose?

Gold rules:
No gold rule set is recorded for this question -- grade based on whether the answer is internally coherent, directly responsive to the question, and not self-contradictory. You have no rule text here to check its substance against, so do not assert it is rules-correct beyond that coherence check; say so plainly in your reason.

Card data:
Trinisphere {3} -- Artifact  (MV 3)
As long as this artifact is untapped, each spell that would cost less than three mana to cast costs three mana to cast. (Additional mana in the cost may be paid with any color of mana or colorless mana. For example, a spell that would cost {1}{B} to cast costs {2}{B} to cast instead.)
Rulings:
- [Trinisphere ruling #0] To determine the total cost of a spell, start with the mana cost or alternative cost you're paying, add any cost increases, then apply any cost reductions. Finally, apply Trinisphere's effect if the mana component of the spell's cost is less than three mana. The mana value of the spell remains unchanged, no matter what the total cost to cast it was.
- [Trinisphere ruling #1] If Trinisphere leaves the battlefield or becomes tapped or untapped as a cost to cast a spell, this cost is paid after you've locked in the total cost.

Awaken the Woods {X}{G}{G} -- Sorcery  (MV 2, color identity G)
Create X 1/1 green Forest Dryad land creature tokens. (They're affected by summoning sickness.)

Arm's answer:
answered: True
citations: ['[601.2f]', '[107.3b]', '[118.7a]', '[118.7c]', '[Trinisphere ruling #0]', 'Trinisphere', 'Awaken the Woods']
text: Definitions (key terms you need):
- X: a placeholder in a spell’s mana cost that the spell’s controller chooses when casting the spell unless an effect specifically makes X equal 0 (see 107.3b). [107.3b]
- Total cost: the mana (and other) cost the player actually has to pay to cast the spell after you determine the mana/alternative cost, add cost increases, then apply cost reductions; that total cost is locked in during the casting process. [601.2f]

Step-by-step, using the cards and rules you provided:
1) Start with Awaken the Woods’ mana cost: {X}{G}{G}. (That’s the spell’s mana cost.) [Awaken the Woods]
2) You choose X when you cast the spell (you’re not casting it for free), so X can be 0, 1, etc. [107.3b]
3) Apply any cost reductions next. Your permanent that “makes my green spells cost {1} less” is a cost-reduction effect; how it reduces the mana cost matters under the cost-reduction rules: if it reduces generic mana, it only affects the generic component; if it specifically reduces a green mana, it reduces a green component. [118.7a] [118.7c]
4) After cost reductions are applied, apply Trinisphere’s effect (per Trinisphere’s ruling): if the spell’s mana component would be less than three mana, the spell’s mana cost becomes three mana (the additional mana is generic as needed to reach three). Do this after you’ve applied the reductions. [Trinisphere ruling #0] [Trinisphere]
5) The resulting total cost is locked in and then you pay it. [601.2f]

Concrete outcome for X=0:
- Base cost with X=0 is {G}{G} (two green mana). [Awaken the Woods]
- After your reduction: either
  a) If the reduction targets generic mana, it doesn’t reduce anything (there’s no generic component), so the cost remains {G}{G}. [118.7a]
  b) If the reduction removes one green mana, the cost becomes {G}. [118.7c]
- In either case the mana component is less than three, so Trinisphere raises the mana component to three. That produces a locked-in total mana requirement of three mana: concretely either {1}{G}{G} (case a) or {2}{G} (case b). [Trinisphere ruling #0] [Trinisphere]
- What you get: Awaken with X=0 creates X 1/1 Forest Dryad tokens, i.e. zero tokens. So you pay three mana and create no tokens. [Awaken the Woods]

What X you should choose:
- Choose X = 1 if you want tokens. With X=1 you will create one 1/1 Forest Dryad and, after the same sequence (apply your reduction then Trinisphere), the locked-in total cost will still be three mana (either {1}{G}{G} or {2}{G}, matching the color split determined by how your reduction applies). In short: paying the same three mana that X=0 would cost, you can instead set X=1 and get one token. [Awaken the Woods] [118.7a] [118.7c] [Trinisphere ruling #0]

Short practical summary: casting Awaken with X=0 costs three mana (due to Trinisphere) and makes zero tokens. You should pick X=1 to get one 1/1 token for that same three-mana outlay; larger X will cost more (increase the locked-in total cost accordingly). [Awaken the Woods] [Trinisphere ruling #0] [601.2f]


---

### Cell 46: id=c015

Question: [Grist, the Hunger Tide] is in my graveyard. Can I return it with [Animate Dead], and what happens?

Gold rules:
No gold rule set is recorded for this question -- grade based on whether the answer is internally coherent, directly responsive to the question, and not self-contradictory. You have no rule text here to check its substance against, so do not assert it is rules-correct beyond that coherence check; say so plainly in your reason.

Card data:
Grist, the Hunger Tide {1}{B}{G} -- Legendary Planeswalker — Grist -- loyalty 3  (MV 3, color identity B/G)
As long as Grist isn't on the battlefield, it's a 1/1 Insect creature in addition to its other types.
+1: Create a 1/1 black and green Insect creature token, then mill a card. If an Insect card was milled this way, put a loyalty counter on Grist and repeat this process.
−2: You may sacrifice a creature. When you do, destroy target creature or planeswalker.
−5: Each opponent loses life equal to the number of creature cards in your graveyard.
Rulings:
- [Grist, the Hunger Tide ruling #4] Count the number of creature cards in your graveyard as the third loyalty ability resolves to determine how much life each opponent loses. If Grist is in your graveyard at this time, it'll be a creature card and will contribute to the count.
- [Grist, the Hunger Tide ruling #1] Anywhere but on the battlefield, Grist is a Legendary Planeswalker Creature — Grist Insect. Once it enters the battlefield, it is no longer a creature and is just a planeswalker. Anything that could search for or affect a creature or planeswalker card in zones other than the battlefield could affect Grist. For example, you could put it onto the battlefield with Chord of Calling, it could be countered by Essence Scatter (but not by Negate), and opponents couldn't make you discard it with Duress.
- [Grist, the Hunger Tide ruling #0] Grist, the Hunger Tide can be your commander as its first ability works before the game begins during deck construction.

Animate Dead {1}{B} -- Enchantment — Aura  (MV 2, color identity B)
Enchant creature card in a graveyard
When this Aura enters, if it's on the battlefield, it loses "enchant creature card in a graveyard" and gains "enchant creature put onto the battlefield with this Aura." Return enchanted creature card to the battlefield under your control and attach this Aura to it. When this Aura leaves the battlefield, that creature's controller sacrifices it.
Enchanted creature gets -1/-0.
Rulings:
- [Animate Dead ruling #4] If the creature put onto the battlefield has protection from black—or if the creature can't legally be enchanted by Animate Dead for another reason—Animate Dead won't be able to attach to it. It will be put into the graveyard as a state-based action, causing its delayed triggered ability to trigger. When the trigger resolves, if the creature's still on the battlefield, its controller will sacrifice it.
- [Animate Dead ruling #0] If Animate Dead isn't on the battlefield as its triggered ability resolves, none of its effects happen. The creature card won't be returned to the battlefield.
- [Animate Dead ruling #1] Animate Dead is an Aura, albeit with an unusual enchant ability. You target a creature card in a graveyard when you cast it. It enters the battlefield attached to that card. Then it returns that card to the battlefield, and attaches itself to the card again (since the card is a new object on the battlefield). Animate Dead itself never moves into a graveyard during this process.

Arm's answer:
answered: True
citations: ['Grist, the Hunger Tide ruling #1', 'Animate Dead ruling #1', 'Animate Dead ruling #4']
text: Short answer and definitions
- "Creature card in a graveyard": a card in the graveyard that is a creature in that zone. Grist is a creature card while it’s in your graveyard, so it’s a legal target for Animate Dead. [Grist, the Hunger Tide ruling #1]
- "Attach/Enchant": Animate Dead is an Aura that enters attached to the creature card in the graveyard, then (as its enter resolution) returns that card to the battlefield and attaches itself to the new object. [Animate Dead ruling #1]
- "State-based action": the game will automatically put an Aura that can’t legally be attached to a permanent into its owner’s graveyard; that causes the Aura’s leave-the-battlefield trigger to trigger. [Animate Dead ruling #4]
What happens step by step
1) You can cast Animate Dead targeting Grist in your graveyard because Grist is a creature card there. [Grist, the Hunger Tide ruling #1; Animate Dead ruling #1]
2) When Animate Dead enters the battlefield, its triggered effect attempts to return the enchanted creature card (Grist) to the battlefield and attach the Aura to it. [Animate Dead ruling #1]
3) As soon as Grist is on the battlefield, it is not a creature there (it’s just a planeswalker). Because Animate Dead’s effect is to “enchant creature put onto the battlefield with this Aura,” Animate Dead won’t be able to legally attach to that object. [Grist, the Hunger Tide ruling #1; Animate Dead ruling #4]
4) Animate Dead will be put into the graveyard as a state-based action for having no legal attachment; that causes its “When this Aura leaves the battlefield, that creature’s controller sacrifices it” effect to trigger. When that trigger resolves, if Grist is still on the battlefield you must sacrifice it. The net result is that Grist briefly returns but is then sacrificed, ending up back in your graveyard, and Animate Dead ends up in the graveyard. [Animate Dead ruling #4]
Conclusion
You can target and return Grist with Animate Dead, but because Grist becomes only a planeswalker on the battlefield Animate Dead can’t remain attached; Animate Dead goes to the graveyard and its leave-the-battlefield trigger causes you to sacrifice Grist, so Grist doesn’t stick on the battlefield.


---

### Cell 47: id=c016

Question: My commander [Skullbriar, the Walking Grave] has four +1/+1 counters on it. It dies, I move it to the command zone, then recast it. Does it keep the counters, and does [Doubling Season] double them as it re-enters?

Gold rules:
No gold rule set is recorded for this question -- grade based on whether the answer is internally coherent, directly responsive to the question, and not self-contradictory. You have no rule text here to check its substance against, so do not assert it is rules-correct beyond that coherence check; say so plainly in your reason.

Card data:
Skullbriar, the Walking Grave {B}{G} -- Legendary Creature — Zombie Elemental -- 1/1  (MV 2, color identity B/G)
Haste
Whenever Skullbriar deals combat damage to a player, put a +1/+1 counter on it.
Counters remain on Skullbriar as it moves to any zone other than a player's hand or library.
Rulings:
- [Skullbriar, the Walking Grave ruling #2] The counters that remain on Skullbriar as it changes zones aren't "placed" on Skullbriar. Effects like Doubling Season's and Melira, Sylvok Outcast's won't affect those counters.
- [Skullbriar, the Walking Grave ruling #1] Skullbriar retains all counters, not just +1/+1 counters.
- [Skullbriar, the Walking Grave ruling #3] Counters that adjust power and/or toughness affect Skullbriar's power and/or toughness in zones other than the battlefield. For example, a Skullbriar in the command zone with a +1/+1 counter on it will be 2/2.

Doubling Season {4}{G} -- Enchantment  (MV 5, color identity G)
If an effect would create one or more tokens under your control, it creates twice that many of those tokens instead.
If an effect would put one or more counters on a permanent you control, it puts twice that many of those counters on that permanent instead.
Rulings:
- [Doubling Season ruling #2] Doubling Season affects permanents that enter with counters.
- [Doubling Season ruling #4] If there are two Doubling Seasons on the battlefield, then the number of tokens or counters is four times the original number. If there are three on the battlefield, then the number of tokens or counters is eight times the original number, and so on.
- [Doubling Season ruling #0] Planeswalkers will enter with double the normal number of loyalty counters. However, if you activate an ability whose cost has you put loyalty counters on a planeswalker, the number you put on isn't doubled. This is because those counters are put on as a cost, not as an effect.

Arm's answer:
answered: True
citations: ['[122.2]', '[702.138c]', '[Skullbriar, the Walking Grave ruling #1]', '[Skullbriar, the Walking Grave ruling #2]', '[Skullbriar, the Walking Grave ruling #3]', '[Doubling Season ruling #2]']
text: Yes — Skullbriar keeps its counters while in the command zone, but Doubling Season does not double those retained counters when you recast it. Explanation grounded in the provided rules/rulings:

- Normally counters don't move with an object when it changes zones ([122.2]).
- Skullbriar’s text/rulings explicitly override that for Skullbriar: “Counters remain on Skullbriar as it changes zones” and it “retains all counters” (Skullbriar, the Walking Grave ruling #1 and #2). Those retained counters even apply to its power/toughness while in the command zone (Skullbriar, the Walking Grave ruling #3).
- Doubling Season’s documented behavior is that it affects permanents that enter with counters (Doubling Season ruling #2). However, Skullbriar’s ruling #2 states the counters that remain on Skullbriar as it changes zones aren’t being “placed” on it, and explicitly says effects like Doubling Season won’t affect those counters. Therefore, when you move Skullbriar to the command zone with four +1/+1 counters and later recast it, it will have those four counters, but Doubling Season will not double them as it re-enters.

Relevant notes: “Enter with counters” as a phrase is used for replacement effects that cause counters to be placed as the object enters (see rule about entering with counters, e.g. escape — [702.138c]). Skullbriar’s retained counters are a different case because they weren’t placed as it entered the battlefield; they were carried by Skullbriar across zones per its oracle/rulings and thus aren’t doubled.


---

### Cell 48: id=c017

Question: I cast [Final Fortune] to take an extra turn. During that extra turn I use [Sundial of the Infinite] to end the turn before the end step. Do I still lose the game?

Gold rules:
No gold rule set is recorded for this question -- grade based on whether the answer is internally coherent, directly responsive to the question, and not self-contradictory. You have no rule text here to check its substance against, so do not assert it is rules-correct beyond that coherence check; say so plainly in your reason.

Card data:
Final Fortune {R}{R} -- Instant  (MV 2, color identity R)
Take an extra turn after this one. At the beginning of that turn's end step, you lose the game.
Rulings:
- [Final Fortune ruling #1] If you end up skipping the extra turn that is gained, you do not lose the game.
- [Final Fortune ruling #0] If multiple "extra turn" effects resolve in the same turn, take them in the reverse of the order that the effects resolved. In other words, the most recently created extra turn is taken first.

Sundial of the Infinite {2} -- Artifact  (MV 2)
{1}, {T}: End the turn. Activate only during your turn. (Exile all spells and abilities from the stack. Discard down to your maximum hand size. Damage wears off, and "this turn" and "until end of turn" effects end.)
Rulings:
- [Sundial of the Infinite ruling #1] If Sundial of the Infinite's ability is activated before the end step, any "at the beginning of the end step"-triggered abilities won't get the chance to trigger that turn because the end step is skipped. Those abilities will trigger at the beginning of the end step of the next turn. The same is true of abilities that trigger at the beginning of other phases or steps (except upkeep).
- [Sundial of the Infinite ruling #4] Ending the turn this way means the following things happen in order: 1) All spells and abilities on the stack are exiled. This includes spells and abilities that can't be countered. 2) All attacking and blocking creatures are removed from combat. 3) State-based actions are checked. No player gets priority, and no triggered abilities are put onto the stack. 4) The current phase and/or step ends. The game skips straight to the cleanup step. The cleanup step happens in its entirety.

Arm's answer:
answered: True
citations: ['724.1e', 'Sundial of the Infinite ruling #1', 'Final Fortune', 'Final Fortune ruling #1']
text: Short answer: No. If you activate Sundial of the Infinite to end that extra turn before its end step, you won’t lose the game at that time.

Why: "End the turn" means performing an expedited process that skips most of the rest of that turn (see 724.1e). A triggered ability that triggers "at the beginning of the end step" won’t trigger on a turn whose end step was skipped (724.1e). Sundial’s ruling explicitly says that if its ability is activated before the end step, any "at the beginning of the end step" triggered abilities won’t get a chance to trigger that turn and instead will trigger at the beginning of the end step of the next turn (Sundial of the Infinite ruling #1). Final Fortune’s text creates a triggered ability that loses you the game "at the beginning of that turn’s end step," so if that end step is skipped by Sundial you do not lose the game at that time (Final Fortune; also see Final Fortune ruling #1 for the related case of a skipped extra turn).

---

### Cell 49: id=c018

Question: I cast [Clone]. When and how do I choose what it copies, and can my opponent respond to that choice?

Gold rules:
No gold rule set is recorded for this question -- grade based on whether the answer is internally coherent, directly responsive to the question, and not self-contradictory. You have no rule text here to check its substance against, so do not assert it is rules-correct beyond that coherence check; say so plainly in your reason.

Card data:
Clone {3}{U} -- Creature — Shapeshifter -- 0/0  (MV 4, color identity U)
You may have this creature enter as a copy of any creature on the battlefield.
Rulings:
- [Clone ruling #2] If Clone somehow enters at the same time as another creature, Clone can't become a copy of that creature. You may choose only a creature that's already on the battlefield.
- [Clone ruling #5] You can choose not to copy anything. In that case, Clone enters as a 0/0 Shapeshifter creature, and is probably put into the graveyard immediately.
- [Clone ruling #0] Clone's ability doesn't target the chosen creature.

Arm's answer:
answered: True
citations: ['707.6', '707.2', '616.1c', 'Clone ruling #2', 'Clone ruling #5', 'Clone ruling #0']
text: When Clone is entering the battlefield you (Clone’s controller) choose what it will copy as part of the “as this enters” / replacement process. The choice is made while applying the effect that causes it to enter as a copy, so you must choose a creature that is already on the battlefield (you can’t choose a creature that is entering at the same time) and you may instead choose not to copy anything.

How to apply that in practice
- As Clone is entering the battlefield you choose the creature it will enter as a copy of (this is an “as this enters” choice that determines Clone’s copiable values as it enters). See [707.6] and [707.2].
- You may only choose a creature that is already on the battlefield; Clone can’t become a copy of a creature that is entering the battlefield at the same time as Clone [Clone ruling #2].
- Clone’s choosing a creature is not a targeting action (Clone’s ability doesn’t target) [Clone ruling #0].
- You may also choose not to copy anything; Clone then enters as a 0/0 Shapeshifter [Clone ruling #5].

Can an opponent respond to that choice?
- No separate spell or ability is put on the stack for that choice; the choice is made as part of the object entering the battlefield (the replacement/“as this enters” process). That choice is applied when the object enters, not as a separate action on the stack, so opponents do not get to respond to the choice itself — any responses must wait until after Clone has entered the battlefield (and players next receive priority). See [707.6], [707.2], and the procedure for applying competing replacement effects [616.1c].

---

### Cell 50: id=c019

Question: I activate my [Flooded Strand]'s ability, then activate [Gogo, Master of Mimicry] with X=2 to copy it twice. How many lands do I get from that one Flooded Strand?

Gold rules:
No gold rule set is recorded for this question -- grade based on whether the answer is internally coherent, directly responsive to the question, and not self-contradictory. You have no rule text here to check its substance against, so do not assert it is rules-correct beyond that coherence check; say so plainly in your reason.

Card data:
Flooded Strand -- Land  (MV 0)
{T}, Pay 1 life, Sacrifice this land: Search your library for a Plains or Island card, put it onto the battlefield, then shuffle.

Gogo, Master of Mimicry {2}{U} -- Legendary Creature — Wizard -- 2/4  (MV 3, color identity U)
{X}{X}, {T}: Copy target activated or triggered ability you control X times. You may choose new targets for the copies. This ability can't be copied and X can't be 0. (Mana abilities can't be targeted.)
Rulings:
- [Gogo, Master of Mimicry ruling #6] Gogo's ability targets an activated or triggered ability that is on the stack and creates one or more additional instances of that ability on the stack. It doesn't cause any object to gain any abilities.
- [Gogo, Master of Mimicry ruling #9] The source of the copy from Gogo's ability is the same as the source of the original ability.
- [Gogo, Master of Mimicry ruling #8] Gogo's ability can copy any activated or triggered ability on the stack, not just one with targets.

Arm's answer:
answered: True
citations: ['[707.10]', '[707.10b]', '[701.23h]', '[Gogo, Master of Mimicry ruling #6]', '[Gogo, Master of Mimicry ruling #9]', 'Flooded Strand']
text: Definitions (from the provided rules):
- “To copy a … ability” means to put a copy of that ability onto the stack; a copy of an activated ability isn’t activated and the copy is itself an ability and is controlled by the player who put it on the stack. A copy copies the characteristics of the original ability and all decisions made for it. [707.10] [707.10b]
- “Search” interactions: if a player is instructed to search a library more than once before being told to shuffle, those searches are treated as a single combined search; otherwise separate instructions that each include a shuffle are handled separately. [701.23h]

What happens in this line of play:
1) You activate Flooded Strand by paying {T}, 1 life, and sacrificing the Flooded Strand; that puts the Flooded Strand’s activated ability on the stack. (Flooded Strand’s ability: “Search your library for a Plains or Island card, put it onto the battlefield, then shuffle.”) [Flooded Strand]
2) You activate Gogo, Master of Mimicry with X=2 targeting that Flooded Strand ability. Gogo creates two additional instances (copies) of that activated ability on the stack. The copies are put onto the stack (they are not additional activations and you don’t pay the Flooded Strand’s activation costs again). [Gogo, Master of Mimicry ruling #6] [707.10b]
3) There are now three instances of the Flooded Strand ability on the stack (the original + two copies). Each instance, as it resolves, instructs you to search your library for a Plains or Island card, put that card onto the battlefield, then shuffle. Because each instance includes its own “then shuffle” instruction, the searches are not combined into a single search; they resolve one at a time with a shuffle between them. [Flooded Strand] [701.23h]
4) As a result, when all three instances resolve you will put three lands onto the battlefield (one per resolving instance). Note that the Flooded Strand itself was sacrificed once as the activation cost of the original ability; the copies do not cause additional sacrifices. [707.10] [Gogo, Master of Mimicry ruling #9]

Short answer: you get three lands (the original ability + two copies).

---

## Output instructions

Grade all 50 cells above per the rubric. For EACH cell, write exactly one JSON line to:

    evals/opus_grader_v2_out/gpt-5-mini.jsonl

Each line is a single JSON object with EXACTLY these fields and nothing else:

    {"id": "<cell id, e.g. q007 or c012>", "arm": "gpt-5-mini", "verdict": "correct"|"partial"|"wrong", "reason": "<one-line reason>"}

Every one of the 50 cells above must be accounted for -- one line per cell, any order, no duplicates, no extra fields, no commentary outside the JSONL lines. If a cell is genuinely ungradeable, still write a line with your best-effort verdict and say why in the reason -- never silently drop a cell.