# Opus-Grader Calibration v2 -- Batch: deepseek-v4-flash

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
citations: ['702.26c', '702.26d', '603.6a']
text: No, creatures phasing back in do not trigger enter-the-battlefield abilities. Phasing does not cause a permanent to change zones; it only changes its status from 'phased out' to 'phased in' (rule [702.26c]). The phasing event is explicitly not a zone-change event, so zone-change triggers such as enters-the-battlefield abilities do not trigger when a permanent phases in (rule [702.26d]). Additionally, rule [603.6a] defines enters-the-battlefield triggers as zone-change triggers, and rule [702.26d] states that zone-change triggers don't trigger when a permanent phases in or out. Therefore, even though the creature becomes present on the battlefield again, it is not entering the battlefield from another zone, so no enters-the-battlefield ability triggers.

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
citations: ['702.2c', '702.19b', '702.19c', 'Lethal Damage', 'Excess Damage', '702.2b', '704.5h', '302.7']
text: When a creature with both trample and deathtouch assigns combat damage, deathtouch modifies what counts as lethal damage for the purpose of trample's damage assignment. Specifically, any nonzero amount of combat damage assigned to a blocking creature by a source with deathtouch is considered lethal damage [702.2c]. This means that, for each blocking creature, the attacking creature's controller need only assign 1 damage to that creature to satisfy the lethal-damage requirement for trample [702.19b]. Any remaining damage (excess) can then be assigned to the defending player, planeswalker, or battle the creature is attacking, as long as all blocking creatures have been assigned at least 1 damage each [702.19b]. For example, a 5/5 creature with trample and deathtouch blocked by a 3/3 can assign 1 damage to the blocker (which is lethal due to deathtouch) and 4 damage to the defending player. This is because deathtouch makes any amount of damage (even 1) lethal for the purpose of determining excess damage [702.2c]. The same principle applies to trample over planeswalkers [702.19c] and to cases where the blocking creature has protection or damage prevention, as lethal damage is still assigned based on the rules, even if the damage will be prevented [702.19b example].

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
citations: ['113.9', '702.40a', '603.1a', '603.3']
text: Storm is a triggered ability, and as such it is not a spell. Rule [113.9] states that triggered abilities on the stack are not spells and cannot be countered by anything that counters only spells; they can only be countered by effects that specifically counter abilities. Therefore, storm itself cannot be countered by typical counterspells (which counter spells), but it could be countered by an effect that explicitly says it counters a triggered ability. The storm ability triggers when you cast the spell with storm, and the copies it creates are also not spells (they are copies of a spell on the stack), so they similarly cannot be countered by effects that counter spells unless those effects specifically say they can counter copies or abilities.

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
citations: ['903.5c', '202.2d', '903.4', '107.4e']
text: Yes, you can include a card with hybrid mana symbols in a Commander deck even if your commander’s color identity includes only one of the hybrid symbol’s colors, provided that every mana symbol in the card’s mana cost and rules text is within the commander’s color identity. For example, a card with {G/W} in its mana cost can go in a mono-green or mono-white Commander deck because {G/W} is both green and white, and the card’s color identity is green and white (see rule 202.2d: a hybrid symbol is all of its component colors). However, the card’s color identity is determined by all mana symbols in its mana cost and rules text (rule 903.4). If the card also has a mana symbol of a color outside the commander’s color identity (e.g., a {U} symbol in its rules text), it cannot be included. The key is that the card’s entire color identity must be a subset of the commander’s color identity (rule 903.5c). For example, a card with mana cost {G/W} and no other colored symbols has color identity green and white, so it is legal in a commander deck whose commander’s color identity includes both green and white, or just green, or just white. If the commander is mono-green, the card’s white component is fine because the hybrid symbol is both colors, and the card’s color identity (green and white) is not a subset of mono-green (which is only green) — wait, that would be illegal. Actually, rule 903.5c says: 'A card can be included in a Commander deck only if every color in its color identity is also found in the color identity of the deck’s commander.' So if the card’s color identity is green and white, and the commander’s color identity is only green, then white is not in the commander’s color identity, so the card is not allowed. Therefore, a card with a hybrid symbol that includes a color outside the commander’s color identity is illegal. For example, a card with {G/W} in its mana cost has color identity green and white, so it can only go in a commander deck whose commander’s color identity includes both green and white (e.g., a green-white commander). It cannot go in a mono-green or mono-white deck because the other color is missing. This is confirmed by the example in rule 903.5c: Wort, the Raidmother has color identity red and green, so each card in the deck must have only red, only green, both red and green, or no color. A card with {R/G} is both red and green, so it’s allowed. But a card with {R/W} would have color identity red and white, and white is not in Wort’s color identity, so it’s not allowed. In summary: a hybrid mana symbol contributes all its component colors to the card’s color identity. The card is legal only if every one of those colors is present in the commander’s color identity. If the commander has only one of the hybrid symbol’s colors, the card is not legal because the other color is missing from the commander’s color identity.

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
citations: ['[502.4]', '[500.3]', '[503.1a]']
text: No, you cannot respond to the untap step. According to rule [502.4], no player receives priority during the untap step, so no spells can be cast and no abilities can be activated or resolve. Any triggered abilities that trigger during this step are held until the next time a player would receive priority, which is usually during the upkeep step (rule [503.1a]). The untap step is one of the steps in which no players receive priority, as specified in rule [500.3]. Therefore, there is no opportunity to respond during the untap step itself.

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
citations: ['508.1k', '508.4', '511.1', '511.3']
text: Yes, creatures are still considered attacking creatures during the end of combat step. According to rule [508.1k], a creature remains an attacking creature until it is removed from combat or the combat phase ends, whichever comes first. The end of combat step is part of the combat phase (see [511.1]), so the combat phase has not yet ended during this step. Therefore, creatures that were declared as attackers or put onto the battlefield attacking (per [508.4]) continue to be attacking creatures throughout the end of combat step. They are only removed from combat when the combat phase ends, which occurs after the end of combat step concludes (see [511.3]).

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
citations: ['305.9', '300.2a', '305.1', '202.1b', '116.2a', '505.6b', '701.18a', 'Play', '701.18b', '601.1a']
text: No, you do not cast lands. Playing a land is a special action that does not use the stack, whereas casting a spell (including a creature, instant, or sorcery) uses the stack. A land card has no mana cost and cannot be cast as a spell; it can only be played as a land. This is explicitly stated in the rules: 'If an object is both a land and another card type, it can be played only as a land. It can’t be cast as a spell' ([305.9], [300.2a]). Additionally, 'Playing a land is a special action; it doesn’t use the stack' ([305.1]), and 'lands are played without paying any costs' ([202.1b]). Therefore, lands are never cast.

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
citations: ['702.74a', '603.3d', '118.10']
text: No, you cannot sacrifice an evoked creature before its own evoke triggered ability resolves. The evoke ability (rule 702.74a) consists of two parts: an alternative cost to cast the spell, and a triggered ability that says "When this permanent enters, if its evoke cost was paid, its controller sacrifices it." This triggered ability goes on the stack the next time a player would receive priority after the creature enters the battlefield (rule 603.3d). You, as the controller, do not receive priority to activate any abilities (including sacrificing the creature) until after that triggered ability has been put on the stack and all players have passed priority. Since the evoke triggered ability itself instructs you to sacrifice the creature, you cannot sacrifice it earlier via another effect (such as an activated ability) because you never have priority before that sacrifice instruction resolves. Additionally, rule 118.10 confirms that paying a cost for one spell or ability does not pay another's cost; sacrificing the creature for evoke is part of the triggered ability's resolution, not a cost you can pay early.

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
citations: ['113.10b', '702.1', '702.22b', '702.11e']
text: Yes, losing all abilities includes keyword abilities. Rule [113.10b] states that an effect which removes an ability removes all instances of it. Keyword abilities (defined in [702.1]) are abilities, so they are removed by an effect that says an object "loses all abilities." This is further supported by [702.22b], which specifies that if an effect causes a permanent to lose banding, it loses all "bands with other" abilities as well, and [702.11e], which states that any effect causing an object to lose hexproof causes it to lose all "hexproof from [quality]" abilities. These examples confirm that keyword abilities are included when an object loses all abilities.

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
citations: ['514.1', '703.4n', '402.2', '121.6a', '614.11', '104.3c']
text: Yes, you can draw cards even if you are already at your maximum hand size. The maximum hand size rule only applies during the cleanup step of a turn, as a turn-based action: if the active player has more cards in hand than their maximum hand size (normally seven), they must discard down to that number ([514.1], [703.4n]). Drawing cards is a separate action that is not restricted by your current hand size. For example, if you have seven cards in hand and an effect says “draw a card,” you draw that card, ending up with eight cards in hand. You do not discard until the cleanup step begins ([402.2]). This is true in all game variants, including Commander and multiplayer games, as the maximum hand size rule is universal and only enforced during the cleanup step. Note that if an effect replaces a card draw (e.g., “if you would draw a card, instead…”), that replacement is applied regardless of hand size ([121.6a], [614.11]). Also, if your library is empty and you are instructed to draw, you draw the remaining cards (if any) and then lose the game the next time a player would receive priority ([104.3c]).

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
answered: True
citations: ['306.9', '122.1e', '704.5i', '120.3c', '306.8', '306.5c', '104.3b', '724.1c', '724.2c']
text: When a planeswalker has 0 loyalty counters on it, its loyalty is 0 (rule [306.5c]). This causes the planeswalker to be put into its owner’s graveyard as a state-based action (rules [306.9], [704.5i]). The rules do not define a loyalty value less than 0; if an effect would reduce loyalty counters below 0, the planeswalker simply has 0 loyalty counters and is put into the graveyard. Damage dealt to a planeswalker removes that many loyalty counters (rule [120.3c]), which can result in 0 loyalty. This state-based action is checked before any player would receive priority (rule [104.3b]), and also during turn-ending effects (rule [724.1c]) or combat-phase-ending effects (rule [724.2c]). The planeswalker’s owner is the player who put it into their deck at the start of the game (see rule [800.4a] for multiplayer implications, though not detailed here).

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
citations: ['Dies', '700.4', '701.8b']
text: No, non-creature artifacts do not die. The term "dies" is defined as being put into a graveyard from the battlefield, but it applies only to creatures and planeswalkers. Rule [Dies] states: "A creature or planeswalker 'dies' if it is put into a graveyard from the battlefield." Rule [700.4] confirms: "The term dies means 'is put into a graveyard from the battlefield.'" However, the definition explicitly limits the term to creatures and planeswalkers. Non-creature artifacts are neither creatures nor planeswalkers, so when a non-creature artifact is put into a graveyard from the battlefield, it is not said to "die." Instead, it is simply put into the graveyard via other means (e.g., being destroyed, sacrificed, or having its defense reduced to 0 if it is a battle). For example, a non-creature artifact destroyed by a spell is destroyed (see [701.8b]) but does not "die." The trigger condition "whenever a creature dies" would not trigger for a non-creature artifact. The rules do not extend the term "dies" to any other permanent type.

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
citations: ['121.4', '704.5b', '121.3', '121.3a', '121.6a', '614.11', '121.5', '609.3']
text: If you are instructed to draw a card (or it is a turn-based action during your draw step) and your library is empty, you attempt to draw a card from an empty library. This causes you to lose the game the next time a player would receive priority, as a state-based action. This is covered by rule [121.4] and [704.5b]. If the draw is replaced by an effect (e.g., a replacement effect that says “if you would draw a card, instead do X”), the replacement effect is applied even if your library is empty, per [121.6a] and [614.11], and you do not lose the game from that draw attempt. If an effect offers you the choice to draw a card (e.g., “you may draw a card”), you may choose to do so even with an empty library, per [121.3] and [121.3a], and that choice will also cause you to lose the game as above. If an effect says you can’t draw cards, you cannot choose to draw even if your library is empty. Note that if an effect moves cards from your library to your hand without using the word “draw,” that is not a draw and does not cause loss from an empty library, per [121.5] and [609.3] (it moves as many as possible, which is zero if the library is empty).

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
answered: True
citations: ['506.1', '506.2', '507.1', '511.1', '117.3a', '703.4h', '703.4k', '510.1', '510.2', '802.2', '805.10f']
text: The combat phase consists of five steps in order: beginning of combat, declare attackers, declare blockers, combat damage, and end of combat ([506.1]). The declare blockers and combat damage steps are skipped if no creatures are declared as attackers ([506.1]). There are two combat damage steps if any creature has first strike or double strike ([506.1]).

As the defending player, you receive priority at the beginning of most steps and phases, after any turn-based actions and triggered abilities have been handled ([117.3a]). Specifically:
- **Beginning of combat step**: The active player chooses a defending player (if applicable) as a turn-based action ([507.1], [703.4h]), then the active player gets priority first ([117.3a]). You get priority after the active player passes.
- **Declare attackers step**: After attackers are declared, the active player gets priority first ([117.3a]). You get priority after they pass.
- **Declare blockers step**: After blockers are declared, the active player gets priority first ([117.3a]). You get priority after they pass.
- **Combat damage step**: After combat damage is assigned and dealt ([510.1], [510.2]), the active player gets priority first ([117.3a]). You get priority after they pass.
- **End of combat step**: The active player gets priority first as soon as the step begins ([511.1], [117.3a]). You get priority after they pass.

In a multiplayer game using the "Attack Multiple Players" option, all of the attacking player's opponents are defending players ([802.2]), so the turn-based action to choose a defending player does not occur ([703.4h]). In other multiplayer variants, the active player chooses one opponent as the defending player during the beginning of combat step ([507.1]). The shared team turns option modifies how combat damage is assigned ([805.10f]) but does not change when you receive priority.

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
citations: ['605.3b', '605.4a', '113.4', '117.1d']
text: No, you cannot respond to a mana ability. Mana abilities do not use the stack [605.3b][605.4a][113.4]. Because they resolve immediately upon activation without going on the stack, they cannot be targeted, countered, or otherwise responded to [605.3b][605.4a]. This applies to both activated mana abilities (e.g., tapping a land for mana) and triggered mana abilities (e.g., an enchantment that adds mana when a land is tapped). The only actions that can be taken while a mana ability is resolving are activating other mana abilities or taking special actions (such as turning a face-down permanent face up) if allowed; no spells or non-mana abilities can be cast or activated in response [605.3b][605.4a][117.1d].

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
answered: True
citations: ['601.2g', '601.2h', '508.1j', '509.1f']
text: No, you cannot respond to a cost being paid. Paying a cost is part of the process of casting a spell or activating an ability, and it does not use the stack. Players do not receive priority during the payment of costs, so there is no opportunity to respond. Specifically, rule [601.2g] states that after determining the total cost, the player has a chance to activate mana abilities, then pays all costs in any order (rule [601.2h]). No player receives priority during this process. Similarly, during the declaration of attackers or blockers, costs are paid without the stack (rules [508.1j], [509.1f]). Once a spell or ability is on the stack, players can respond to it, but not to the individual cost payments that were made to put it there.

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
citations: ['613.1', '613.1a', '613.1c', '613.1d', '613.1e', '613.1f', '613.2a', '613.2c', '613.3', '613.4a', '613.5', '613.6', '613.8', '613.8a']
text: Layers are a system the game uses to determine the order in which continuous effects are applied to an object's characteristics. The process starts with the object's base characteristics (printed on a card, or defined by the effect that created a token or copy). Then, all applicable continuous effects are applied in a series of layers, in a fixed order: Layer 1 (copiable values, including copy effects), Layer 2 (control-changing effects), Layer 3 (text-changing effects), Layer 4 (type-changing effects, including card type, subtype, and supertype), Layer 5 (color-changing effects), Layer 6 (ability-adding, keyword counters, ability-removing, and effects that say an object can't have an ability), and Layer 7 (power- and toughness-changing effects, which itself has sublayers: 7a for characteristic-defining abilities, 7b for effects that set power and toughness, and 7c for effects that modify power and toughness without setting them). Within each layer or sublayer, effects are applied in timestamp order, unless a dependency exists (see rule 613.8), which overrides timestamp order. If an effect applies in multiple layers (e.g., an effect that both changes color and modifies power/toughness), each part applies in its appropriate layer (rule 613.6). The game continually and automatically applies these layers to determine the final characteristics of each object (rule 613.5). For example, a 2/2 black creature that becomes white (layer 5) and then gets +1/+1 from an effect like Honor of the Pure (layer 7c) becomes 3/3; if its color later changes to red (layer 5), the +1/+1 effect stops applying and it returns to 2/2 (rule 613.5).

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
citations: ['[Legend Rule]', '[704.5j]', '[205.4d]', '[306.4]', '[117.2d]', '[704.5k]', '[704.5y]']
text: The legend rule is a state-based action that applies when a player controls two or more legendary permanents with the same name. When this condition is checked (before a player would receive priority, per [117.2d]), that player chooses one of those permanents to keep, and the rest are put into their owners’ graveyards ([704.5j]). This rule applies to any permanent with the supertype “legendary” ([205.4d]), including planeswalkers that have received errata to be legendary ([306.4]). The legend rule does not apply to non-legendary permanents, even if they share a name with a legendary permanent. It is distinct from the world rule (for permanents with the world supertype, [704.5k]) and the Role rule (for Aura enchantments with the Role subtype, [704.5y]).

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
citations: ['704.3', '704.5g', '120.5', '510.3a', '724.1c', '724.2c', '514.2', '117.5']
text: Your creature dies as a state-based action the next time state-based actions are checked, which occurs just before a player would receive priority. Specifically, after lethal damage is marked on the creature (e.g., from a spell like Lightning Bolt), the game does not immediately destroy it. Instead, the destruction happens during the next state-based action check, which takes place before any player gets priority. This is explained by rule [704.3], which states that whenever a player would get priority, the game checks for state-based actions and performs them. Rule [704.5g] specifies that if a creature has damage marked on it greater than or equal to its toughness, it is destroyed as a state-based action. Rule [120.5] clarifies that the damage itself does not destroy the creature; the state-based action does. Additionally, rule [510.3a] notes that after combat damage is dealt, the active player gets priority, and state-based actions are performed before that priority is given. If an effect ends the turn or combat phase (e.g., via rules [724.1c] or [724.2c]), state-based actions are checked immediately as part of that process. Damage marked on a creature is removed during the cleanup step (rule [514.2]), but if the creature has lethal damage before that step, it will be destroyed by state-based actions first. In summary, the creature dies at the next state-based action check, which is typically right before a player would receive priority after the damage event.

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
citations: ['903.8', '903.9b', '601.3f', '406.3b', '903.9a']
text: No, you cannot cast your commander from exile unless a rule or effect specifically allows it. In a Commander game, a commander may be cast from the command zone (rule [903.8]), and if a commander would be put into its owner’s hand or library from anywhere, its owner may put it into the command zone instead (rule [903.9b]). However, there is no general rule allowing a commander to be cast from exile. A player can begin to cast a spell only if a rule or effect allows it (rule [601.3f]), and while some effects allow casting spells from among face-down cards in exile (rule [406.3b]), this does not apply to a commander in exile unless such an effect is present. Additionally, if a commander is in exile, its owner may put it into the command zone as a state-based action (rule [903.9a]), but this is optional and does not enable casting from exile. Therefore, without a specific effect (e.g., one that says “you may cast spells from exile”), you cannot cast your commander from exile.

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
citations: ['514.3a', '704.3', '703.4p', '724.1f', '724.1d', '514.2', '500.3', 'Cleanup Step', '514.3', '724.2c', '724.1c', '513.1', '511.1', '500.5', '703.3']
text: During the cleanup step, the following occurs in order:

1. **Turn-based actions** (rule [703.4p]): Immediately after the active player discards down to their maximum hand size (if necessary), all damage is removed from permanents and all “until end of turn” and “this turn” effects end. These happen simultaneously and do not use the stack (rule [514.2]).

2. **State-based actions and triggered abilities** (rule [514.3a]): Normally no player gets priority during the cleanup step. However, the game checks if any state-based actions need to be performed or if any triggered abilities are waiting to be put onto the stack (including those that trigger “at the beginning of the next cleanup step”). If so, those state-based actions are performed, then those triggered abilities are put on the stack, and the active player gets priority. Players may then cast spells and activate abilities. Once the stack is empty and all players pass in succession, another cleanup step begins.

3. **If no state-based actions or triggered abilities** are waiting after the first check, no player gets priority and the cleanup step ends immediately (rule [704.3] and [514.3a]).

4. **If an effect ends the turn** during the cleanup step (e.g., via a card like *Time Stop*), a new cleanup step begins (rule [724.1d]). If any triggered abilities triggered during that process, they are put onto the stack during the cleanup step, then the active player gets priority (rule [724.1f]).

Key zones involved: The battlefield (permanents), the stack (for triggered abilities and spells), and players’ hands (for discarding). The cleanup step is part of the ending phase (rule [Cleanup Step]).

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
citations: ['704.3', '117.5', '703.3', '514.3a', '724.2c', '724.1c', '704.1', '704.1a', '405.6f', '117.2d', '704.2']
text: State-based actions are checked immediately before a player would receive priority, as a single event, and are repeated until none are performed. This occurs at the start of each step or phase (after any turn-based actions for that step/phase), during the cleanup step (with a special exception for triggered abilities), and also when an effect ends the combat phase or ends the turn (in which case no player gets priority afterward). Specifically:

- **Before priority**: Whenever a player would get priority, the game first checks all state-based actions, performs them simultaneously, then repeats until none are performed. Then triggered abilities are put on the stack, and the process repeats until no state-based actions and no triggered abilities remain. Only then does the appropriate player receive priority. [704.3][117.5]
- **At the start of a step/phase**: Turn-based actions for that step/phase are dealt with first, then state-based actions are checked before any player receives priority. [703.3]
- **During the cleanup step**: Normally no player receives priority, but if state-based actions would be performed or triggered abilities are waiting, those are handled and then the active player gets priority. [514.3a]
- **When an effect ends the combat phase or the turn**: State-based actions are checked, but no player gets priority and no triggered abilities are put onto the stack. [724.2c][724.1c]

State-based actions do not use the stack and are not controlled by any player. [704.1][704.1a][405.6f][117.2d][704.2]

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
citations: ['104.3a', '101.1', '405.6g', '810.8b', '723.6']
text: You can concede a game at any time. This is a fundamental rule that overrides all other rules, including card effects. Specifically, rule [104.3a] states that a player can concede at any time, and rule [101.1] confirms that even when a card contradicts the rules, the player's right to concede is an exception that cannot be overridden. Concession does not use the stack (rule [405.6g]), so it cannot be responded to. In Two-Headed Giant, if a player concedes, their entire team leaves the game and loses (rule [810.8b]). Even if another player controls you, you may still concede (rule [723.6]). The concession takes effect immediately, causing you to leave the game and lose.

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
citations: ['Active Player', '102.1', '805.9', '805.4a', '506.2b', '504.2', '507.2', '509.2', '508.2', '510.3', '505.6']
text: The active player is the player whose turn it is. In a standard multiplayer game, this is determined by turn order: the player currently taking their turn is the active player. In a game using the shared team turns option (rule 805.4a), the team whose turn it is is the active team, but the term 'active player' still refers to one specific player on that team, chosen by the ability's controller when the effect is applied (rule 805.9). During combat, the active player is the attacking player (rule 506.2b). The active player is also the one who gets priority first in each step (rules 504.2, 507.2, 509.2, 508.2, 510.3, 505.6).

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
citations: ['117.3b', '117.3c']
text: After a spell (other than a mana ability) resolves, the active player receives priority, regardless of who cast the spell. This is stated in rule [117.3b]: "The active player receives priority after a spell or ability (other than a mana ability) resolves." The identity of the player who cast the spell does not change this rule. Additionally, if a player casts a spell while they have priority, rule [117.3c] says that player receives priority afterward, but that applies only to the player who had priority before casting. If a nonactive player casts a spell, they must have had priority at that moment (e.g., because the active player passed priority), and after that spell resolves, priority returns to the active player per [117.3b]. Therefore, the answer is: the active player gets priority first after any spell resolves, no matter who cast it.

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
citations: ['117.3c', '117.3a', '117.3b']
text: After the active player casts a spell, the active player receives priority first. This is because rule 117.3c states that if a player has priority when they cast a spell, that player receives priority afterward. The active player is the one who had priority before casting the spell (as per the start of the step or after a spell resolves, per rules 117.3a and 117.3b), so they get priority again after the spell is cast. No other player gets priority before the active player does in this situation.

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
citations: ['117.3c', '117.1', '608.2g', '514.3a', '508.2', '509.2']
text: Yes, you can hold priority to cast more spells after casting one, but only under specific circumstances. According to rule [117.3c], if a player has priority when they cast a spell, that player receives priority afterward. This means that after you finish casting a spell (including paying costs and putting it on the stack), you get priority again before any other player does. You can then cast additional spells or activate abilities, as long as you have priority (rule [117.1]). However, note that during the resolution of a spell or ability, if an effect instructs you to cast a spell, no player receives priority after that spell is cast (rule [608.2g]). Also, during the cleanup step, normally no player receives priority unless state-based actions or triggered abilities are waiting (rule [514.3a]). In combat phases, after declaring attackers or blockers, the active player gets priority (rules [508.2], [509.2]), and you can cast spells then. So, in most cases, after casting a spell, you retain priority and can cast more spells before passing priority to opponents.

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
citations: ['714.3a', '714.3b', '702.155b', '714.3c', '703.4f', '505.4', '714.4', '704.5s', '702.155a']
text: Lore counters are put on Sagas in two ways: (1) As a Saga enters the battlefield, it gets a number of lore counters determined by its intrinsic abilities. A Saga without read ahead enters with one lore counter [714.3a]. A Saga with read ahead enters with a number of lore counters you choose between one and its final chapter number [714.3b][702.155b]. (2) During each of your precombat main phases, you put one lore counter on each Saga you control that has one or more chapter abilities [714.3c][703.4f][505.4]. This is a turn-based action that does not use the stack. Additionally, if the number of lore counters on a Saga is greater than or equal to its final chapter number and no chapter ability from that Saga is still on the stack, the Saga’s controller sacrifices it as a state-based action [714.4][704.5s]. Note that read ahead prevents chapter abilities from triggering the turn the Saga entered unless the number of lore counters on it exactly matches the chapter symbol’s number [702.155a].

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
citations: ['Delayed Triggered Ability', '603.7', '603.7a', '603.7b', '603.7c', '603.7d', '603.7e', '603.7f', '603.7g', '603.7h', '610.2', '107.3n', '603.12', '701.66b', '603.3a']
text: A delayed triggered ability is a triggered ability created by the effects of resolving spells or abilities, replacement effects, or static abilities that allow a player to take an action. It contains 'when,' 'whenever,' or 'at' and triggers later based on a specified event. Its source and controller are determined by how it was created (see rules 603.7d–f). For example, if a spell creates a delayed triggered ability, the source is that spell and the controller is the player who controlled the spell as it resolved [603.7d]. If an activated or triggered ability creates it, the source is the same as that ability and the controller is the player who controlled that ability as it resolved [603.7e]. If a static ability generates a replacement effect that creates it, the source is the object with that static ability and the controller is the controller of that object when the replacement effect was applied [603.7f]. A delayed triggered ability typically triggers only once unless it has a stated duration [603.7b]. If it refers to a particular object, it still affects that object even if its characteristics change, but not if the object has left its expected zone and returned (it’s a new object) [603.7c]. If a delayed triggered ability refers to X, and the creating spell or ability had a value of X chosen for any of its costs, the triggered ability uses that same value for X [107.3n].

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
citations: ['113.6', '113.6e', '604.5', '113.1c', '113.9', '405.4', '405.1']
text: Yes, non-permanent spells (instant and sorcery spells) can have abilities. While on the stack, an instant or sorcery spell is an object with all the characteristics of the card associated with it, including any abilities printed on that card. These abilities are called spell abilities and function only while the spell is on the stack, as per rule [113.6]. For example, an instant spell with the text "Counter target spell" has a spell ability that instructs its controller to counter a target spell when it resolves. Additionally, some static abilities on instant or sorcery spells apply while they are on the stack, such as those that refer to countering the spell or that modify how the spell can be cast (see [604.5] and [113.6e]). However, activated and triggered abilities on the stack are not spells and are separate objects (see [113.1c] and [113.9]).

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
citations: ['702.61b', '702.61a', '605.1', '605.3b', '605.3a']
text: Yes, you can activate mana abilities while a spell with split second is on the stack. Rule [702.61b] explicitly states that players may activate mana abilities while a spell with split second is on the stack. This is an exception to the general restriction imposed by split second (rule [702.61a]), which normally prevents players from casting other spells or activating non-mana abilities. Mana abilities are defined in rule [605.1] and follow special rules: they don’t use the stack (rule [605.3b]) and can be activated even without priority in certain circumstances (rule [605.3a]). Therefore, during the time a split-second spell is on the stack, you are allowed to activate mana abilities, such as tapping lands for mana or using other mana-producing activated abilities.

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
citations: ['608.1', '701.6a', '112.1', '608.2n']
text: Counterspell resolves first, and Divination does not resolve. When all players pass priority, the spell on top of the stack resolves ([608.1]). Since Counterspell is on top, it resolves first. Counterspell's effect is to counter target spell ([701.6a]), which removes Divination from the stack and puts it into its owner's graveyard ([701.6a], [112.1]). A countered spell does not resolve and none of its effects occur ([701.6a]). Divination is no longer on the stack when it would be the next to resolve, so it never resolves. The stack is a zone; objects on it are spells ([112.1]). Counterspell targets the Divination spell on the stack; when Counterspell resolves, it counters that spell, removing it from the stack ([701.6a]). The Divination spell is put into its owner's graveyard as a countered spell, not as part of its own resolution ([608.2n] applies only to spells that resolve normally).

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
citations: ['702.2c', '702.19b', '702.2b', '704.5h', 'Lethal Damage', 'Excess Damage']
text: You must assign at least 1 damage to Vampire Nighthawk (the blocker) before any excess damage can trample over to the defending player. This is because deathtouch makes any nonzero amount of combat damage lethal for the purpose of determining excess damage [702.2c]. Since Charging Rhino has trample, you first assign damage to the blocking creature; once lethal damage (here, 1 damage due to deathtouch) is assigned, the remaining 3 damage (4 power minus 1) can be assigned to the defending player [702.19b]. The fact that Vampire Nighthawk has deathtouch itself does not change how much damage you must assign to it—it only affects what counts as lethal for your trample calculation.

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
citations: ['702.108a', '702.108b', '702.85a', '702.85b', '702.85c', '601.2i', '608.2g', 'Monastery Swiftspear ruling #2', 'Monastery Swiftspear ruling #3', 'Shardless Agent ruling #1']
text: Monastery Swiftspear's prowess triggers **after** the cascaded spell is put onto the stack, but **before** that cascaded spell resolves. Here's the sequence:

1. You cast Shardless Agent. Its cascade ability triggers (rule 702.85a).
2. Cascade resolves: you exile cards until you exile a nonland card with lesser mana value, then you may cast that card without paying its mana cost (rule 702.85a). Casting that card during resolution follows the normal steps (rule 608.2g), and that spell becomes the topmost object on the stack.
3. **At the moment you cast that noncreature spell**, Monastery Swiftspear's prowess triggers (rule 702.108a). This trigger goes on the stack on top of the cascaded spell (Monastery Swiftspear ruling #2).
4. Prowess resolves first, giving Swiftspear +1/+1 until end of turn, **before** the cascaded spell resolves.

Key definitions:
- **Prowess**: A triggered ability that triggers whenever you cast a noncreature spell (rule 702.108a).
- **Cascade**: A triggered ability that functions while the spell with cascade is on the stack; it exiles cards and lets you cast one without paying its mana cost during resolution (rule 702.85a).
- **Casting during resolution**: The spell is cast following steps 601.2a–i, but no player gets priority after it's cast (rule 608.2g). Triggered abilities like prowess still trigger at the moment the spell is cast (rule 601.2i).

Thus, prowess triggers immediately upon casting the cascaded noncreature spell and resolves before that spell resolves.

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
citations: ['704.3', '704.4', '704.5g', '120.6', '302.7', '117.2d', '405.6f']
text: No, state-based actions do not make the Grizzly Bears die before Lightning Bolt resolves. State-based actions are checked only when a player would receive priority (rule 704.3), not during the resolution of a spell or ability (rule 704.4). Lightning Bolt resolves as a single spell; during its resolution, the 3 damage is dealt and marked on the Grizzly Bears (rule 120.6, 302.7). The Bears now have 5 total damage marked (2 existing + 3 new), which exceeds its toughness of 2, but state-based actions are not checked until after the spell finishes resolving and a player would next get priority (rule 117.2d, 405.6f). At that point, the lethal damage condition is met and the Bears are destroyed as a state-based action (rule 704.5g).

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
citations: ['603.2b', '603.3b', '503.1a', '503.1', '500.6', '117.3a']
text: Both triggers happen at the same time—the beginning of the upkeep step. According to rule [603.2b], when a phase or step begins, all abilities that trigger “at the beginning of” that phase or step trigger simultaneously. Then, per [603.3b], the next time a player would receive priority (which is at the start of the upkeep step, per [503.1a]), these triggered abilities are put onto the stack in a two-part process: first, each player, in APNAP order (active player, then nonactive player), puts each triggered ability they control with a trigger condition that isn’t another ability triggering on the stack in any order they choose. Since both triggers are “at the beginning of your upkeep” and are not triggering off each other, they fall into the first part. The active player (you) chooses the order of your own triggers, then the nonactive player (your opponent) chooses the order of theirs. So you choose the order of your Phyrexian Arena trigger relative to any other triggers you control, and your opponent does the same for theirs. The triggers themselves all triggered at the same moment—the beginning of the upkeep step—and are put on the stack in APNAP order before any player gets priority.

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
citations: ['702.27a', '707.10', '608.2n', 'Fork ruling #8', 'Fork ruling #10']
text: Zero copies of the card end up back in your hand. The original sorcery with buyback returns to your hand because you paid the buyback cost (rule 702.27a). The Fork copy, however, is not a card—it is a copy of a spell with no card associated (rule 707.10). When the Fork copy resolves, it is put into its owner’s graveyard as part of resolution (rule 608.2n), but since it has no card, nothing goes to your hand. Additionally, the Fork ruling explicitly states that if you copy a spell for which buyback has been paid, you get nothing back because the copied spell does not have a card to give you (Fork ruling #8). The Fork card itself goes to the graveyard after resolving (Fork ruling #10). So only the original card returns to your hand; the copy does not produce a card to return.

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
citations: ['Mimic Vat ruling #0', 'Mimic Vat ruling #6', '708.12']
text: No, you do not get a token. When the manifested Lightning Bolt dies, you may exile it face up (since it was a face-down permanent that died, it is turned face up as it leaves the battlefield; see rule 708.12). However, Lightning Bolt is an instant card, not a permanent card. Mimic Vat's activated ability creates a token that is a copy of a card exiled with it, but a token can only be a copy of a permanent card. Since Lightning Bolt is an instant, it is a nonpermanent card, and no token is created. This is explicitly stated in Mimic Vat's ruling: "If the creature that dies is an instant or sorcery card that's been manifested, Mimic Vat may have a nonpermanent card exiled. You can't create a token that's a copy of a nonpermanent card. No token is created in this case."

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
citations: ['607.2a', '607.3', 'Lithoform Engine ruling #4', 'Fiend Hunter ruling #1']
text: Yes, both exiled creatures return when Fiend Hunter leaves the battlefield. The two abilities are linked: the first ability (the enters-the-battlefield trigger) exiles cards, and the second ability (the leaves-the-battlefield trigger) refers to “the exiled card.” When you copy the first ability with Lithoform Engine, the copy is also linked to the same second ability. Therefore, the second ability refers to all cards exiled by both the original and the copy. When Fiend Hunter leaves the battlefield, the second ability returns each of those exiled cards to the battlefield under their owner’s control.

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
citations: ['702.26d', '702.26g', '603.6e', '610.4a', '610.4c', "Teferi's Protection ruling #21", 'Banishing Light ruling #1', 'Banishing Light ruling #5']
text: No, the exiled creature does not return to the battlefield. Banishing Light's one-shot effect that returns the exiled creature is waiting "until this enchantment leaves the battlefield." When Banishing Light phases out, it does not leave the battlefield (it remains in the battlefield zone but is treated as though it doesn't exist). Therefore, the condition "leaves the battlefield" is not met, and the delayed one-shot effect that would return the creature does not happen. This is confirmed by the ruling that any one-shot effects waiting "until [this] leaves the battlefield" won't happen when a permanent phases out. Additionally, phasing out does not cause zone-change triggers, so Banishing Light's own "leaves the battlefield" ability does not trigger. The exiled creature remains in exile indefinitely until Banishing Light actually leaves the battlefield (e.g., by being destroyed, exiled, or returned to hand).

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
citations: ['Emrakul, the Promised End ruling #2', 'Emrakul, the Promised End ruling #1', '115.5', '601.2i', '608.2m']
text: No, your opponent cannot target Emrakul with Counterspell while it is on the stack, and if it were somehow countered, you would still control their next turn.

**Why Counterspell cannot target Emrakul on the stack:**
- Emrakul has protection from instants. Rule [Emrakul, the Promised End ruling #2] states that protection abilities only apply while the object with the ability is on the battlefield. However, the same ruling explicitly notes that Emrakul *may* be the target of a spell that targets it while on the stack (such as Syncopate). This means protection from instants does **not** prevent Emrakul from being targeted by instant spells while it is a spell on the stack. Therefore, Counterspell (an instant) can legally target Emrakul on the stack.
- However, rule [115.5] says a spell or ability on the stack is an illegal target for itself. That rule does not apply here because Counterspell is a different spell.
- So the opponent **can** target Emrakul with Counterspell while it is on the stack.

**If Emrakul is countered, do you still control the opponent’s next turn?**
- Emrakul’s triggered ability says “When you cast this spell, you gain control of target opponent during that player’s next turn.” The trigger goes on the stack when Emrakul is cast (rule [601.2i]). The trigger is separate from the spell itself. Even if Emrakul is countered and leaves the stack, the triggered ability is already on the stack and will resolve normally (rule [608.2m] confirms that a resolving ability continues even if its source leaves the stack).
- Therefore, you will still gain control of the opponent during their next turn, regardless of whether Emrakul is countered.

**Summary:** The opponent can target Emrakul with Counterspell (protection from instants does not apply on the stack per ruling #2), but countering Emrakul does not stop the cast trigger from giving you control of the opponent’s next turn.

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
citations: ['712.8c', '702.85a', '712.11c', '712.11d', '702.162a']
text: No, you cannot cast Tibalt, Cosmic Impostor via cascade from exiling Valki, God of Lies. Cascade checks the mana value of the card you exile, and for a double-faced card, the mana value is always that of its front face (rule [712.8c]). Valki’s front face has mana value 2. Cascade requires the exiled nonland card’s mana value to be *less than* the cascade spell’s mana value (rule [702.85a]). If your cascade spell’s mana value is greater than 2, Valki is a legal hit *only* for its front face. Cascade allows you to cast the card itself, not a specific face; you cast the card with its front face up by default (rule [712.11c]). To cast the back face (Tibalt), you would need an effect that specifically allows casting “transformed” or “converted” (rules [712.11d], [702.162a]), which cascade does not provide. Therefore, you may cast Valki (the front face) for free if its mana value (2) is less than the cascade spell’s mana value, but you cannot cast Tibalt.

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
answered: True
citations: ['Emrakul, the Promised End ruling #14', 'Emrakul, the Promised End ruling #16', 'Emrakul, the Promised End ruling #17', 'Lithoform Engine ruling #3', 'Lithoform Engine ruling #5', 'Lithoform Engine ruling #6', '707.10', '707.10b', '707.10d', '111.13', '702.40a', '702.144a', '702.192a', '601.2i', '112.1a', '112.1b']
text: You will control one of your opponent's turns (from the original Emrakul's cast trigger), and you will get a second Emrakul token from copying the permanent spell. Copying the Emrakul spell with Lithoform Engine does **not** give you another control-a-turn trigger, because the copy is created directly on the stack and is not cast—the cast trigger only happens when you *cast* Emrakul, not when you copy it.

Here is the detailed breakdown:

1. **Original Emrakul cast trigger**: When you cast Emrakul, its triggered ability ("When you cast this spell, you gain control of target opponent...") goes on the stack. This is a cast trigger, and it will resolve normally, giving you control of that opponent's next turn and causing them to take an extra turn after that.

2. **Copying the cast trigger with Lithoform Engine**: You activate Lithoform Engine's first ability targeting the Emrakul cast trigger on the stack. Per [Lithoform Engine ruling #3], this creates another instance of that triggered ability on the stack. The copy is not cast or activated ([Lithoform Engine ruling #6]). When that copy resolves, it will also give you control of the same opponent's next turn and cause an extra turn. However, per [Emrakul, the Promised End ruling #14], multiple player-controlling effects that affect the same player overwrite each other—the last one to be created is the one that works. Since the copy resolves after the original, the copy's effect will overwrite the original's. The net result is still **one** turn you control (the one from the copy), and the opponent will take one extra turn after that (since the original's extra turn is also overwritten? Actually, the ruling says "each ability’s effect will create an extra turn," so you get two extra turns for the opponent, but you only control one of their turns. The copy's control effect overwrites the original's, so you control the turn specified by the copy, and the opponent takes an extra turn after that turn. The original's extra turn still happens? The ruling says "each ability’s effect will create an extra turn," so both extra turns happen, but the control effect is overwritten. So the opponent will take two extra turns total, but you only control one of them (the one from the copy).

3. **Untapping Lithoform Engine with Voltaic Key**: You activate Voltaic Key's ability to untap Lithoform Engine. This is straightforward and legal.

4. **Copying the Emrakul permanent spell with Lithoform Engine**: You activate Lithoform Engine's third ability targeting the Emrakul spell on the stack. Per [Lithoform Engine ruling #5], the copy is created on the stack. Per [111.13], a copy of a permanent spell becomes a token as it resolves. So you will get a token copy of Emrakul that enters the battlefield. This token has all of Emrakul's characteristics (flying, trample, protection from instants, 13/13) but does **not** have the cast trigger because it was not cast—it was copied directly onto the stack ([707.10] and [Lithoform Engine ruling #6] state that a copy of a spell is not cast). Therefore, copying the Emrakul spell does **not** give you another control-a-turn trigger.

**Summary**: You control one of your opponent's turns (from the copied trigger), the opponent takes two extra turns (one from each trigger), and you get a second Emrakul token. You do not get an additional control-a-turn trigger from copying the Emrakul spell.

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
citations: ['707.10b', '607.3', 'Lithoform Engine ruling #0', 'Mimic Vat ruling #4']
text: No, you do not get two tokens. You get only one token.

Here is the reasoning:

1. **What the abilities do:** Mimic Vat's activated ability (the one you activate) says: "Create a token that's a copy of a card exiled with this artifact. It gains haste. Exile it at the beginning of the next end step." When you activate it, that ability goes on the stack. Lithoform Engine's first ability says: "Copy target activated or triggered ability you control. You may choose new targets for the copy." You target the Mimic Vat ability on the stack with Lithoform Engine's ability, creating a copy of that ability on the stack.

2. **What the copy of the ability does:** Rule [707.10b] states that a copy of an ability copies all decisions made for it, including targets, the value of X, and additional or alternative costs. The original Mimic Vat ability has no targets and no choices made for it (it simply creates a token based on the card exiled with Mimic Vat at the time it resolves). The copy of the ability will also try to create a token that is a copy of a card exiled with Mimic Vat. However, the copy's effect refers to "a card exiled with this artifact" – the word "this" refers to the specific Mimic Vat object that is the source of the original ability, not the copy. Rule [707.10b] also says: "A copy of an ability has the same source as the original ability." And Lithoform Engine ruling #0 confirms: "The source of the copy from Lithoform Engine's first ability is the same as the source of the original ability." So both the original ability and the copy refer to the same Mimic Vat object.

3. **What happens when the copy resolves:** When the copy of the ability resolves, it checks for a card exiled with that Mimic Vat. At that moment, the original ability has not yet resolved (it is still on the stack), so the card exiled with Mimic Vat is still there. The copy will create a token that is a copy of that exiled card. Then, when the original ability resolves later, it will also check for a card exiled with Mimic Vat. But by that time, the copy has already created a token, and the exiled card is still there (the copy did not remove it). So the original ability will also create a token. That would seem to give two tokens.

4. **The critical point – the copy's effect refers to the same exiled cards:** However, rule [607.3] applies here. The Mimic Vat's two abilities are linked: the first ability (the triggered "Imprint" ability) exiles cards, and the second ability (the activated ability) refers to "a card exiled with this artifact." When the activated ability is copied, the copy is a separate instance of that ability, but it still refers to the same set of exiled cards (the cards exiled by the original Mimic Vat's triggered ability). Rule [607.3] says: "If, within a pair of linked abilities, one ability refers to a single object as 'the exiled card,' ... and the other ability has exiled multiple cards (usually because it was copied), the ability refers to each of the exiled cards. ... If that ability creates a token that is a copy of 'the' card, then for each exiled card, it creates a token that is a copy of that card." But here, the original ability and the copy are two separate abilities on the stack, not a single ability that has exiled multiple cards. The original Mimic Vat's triggered ability (the Imprint ability) exiles cards one at a time, and the activated ability (and its copy) each refer to "a card exiled with this artifact." The key is that the copy of the activated ability is a separate ability, but it still refers to the same Mimic Vat object. When the copy resolves, it will create a token based on the exiled card. When the original resolves, it will also create a token based on the exiled card. Since the exiled card is still there (the copy did not remove it), you will get two tokens.

5. **But wait – the copy's effect does not remove the exiled card:** The copy of the ability does not say to exile the card; it just creates a token. So the exiled card remains. The original ability will also create a token from the same exiled card. So you get two tokens.

6. **However, there is a nuance:** The copy of the ability is created by Lithoform Engine, not by Mimic Vat. The copy is a separate ability on the stack. When it resolves, it creates a token. Then the original ability resolves and creates another token. So you get two tokens.

7. **But the question might be about the interaction with the "Imprint" ability:** The Imprint ability exiles a card when a nontoken creature dies. If you have already imprinted a card, that card is exiled. When you activate the second ability, it creates a token copy of that exiled card. If you copy that ability with Lithoform Engine, the copy will also create a token copy of the same exiled card. So you get two tokens.

8. **Conclusion:** Based on the rules provided, you get two tokens. The copy of the ability is a separate instance that creates a token from the same exiled card, and the original ability also creates a token. There is no rule that prevents this. The only potential issue is if the copy's effect somehow removes the exiled card, but it does not. So the answer is yes, you get two tokens.

**Correction:** I initially said no, but the correct answer is yes. You get two tokens. The copy of the ability creates one token, and the original ability creates another token, both from the same exiled card.

**Key rules used:** [707.10b] (copying an ability), [607.3] (linked abilities referring to exiled cards), Lithoform Engine ruling #0 (source of copy is same as original), Mimic Vat ruling #4 (token is copy of card exiled at resolution).

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
citations: ['Trinisphere ruling #0', 'Trinisphere ruling #1', '118.7a', '601.2f', '118.7', '107.3b']
text: To determine the total cost of Awaken the Woods, you start with the mana cost or alternative cost you're paying, add any cost increases, then apply any cost reductions, and finally apply Trinisphere's effect if the mana component of the spell's cost is less than three mana (Trinisphere ruling #0).

If you cast Awaken the Woods with X=0, its mana cost is {0}{G}{G}. The cost reduction of {1} from your permanent reduces the generic mana component by {1} (rule 118.7a), making the cost {0}{G}{G} (since the generic component was already 0, the reduction has no effect—the cost remains {0}{G}{G}). Then Trinisphere sees the mana component is {G}{G} (2 mana), which is less than 3, so it sets the total cost to 3 mana (Trinisphere ruling #0). You must pay {3} (any combination of colored or colorless mana). You get X=0, so you create 0 tokens (Awaken the Woods creates X 1/1 tokens).

If you choose X=1, the mana cost is {1}{G}{G}. The cost reduction of {1} reduces the generic component by {1}, making the cost {0}{G}{G} (rule 118.7a). Then Trinisphere sees the mana component is {G}{G} (2 mana), still less than 3, so it sets the total cost to 3 mana. You pay {3} and get 1 token.

If you choose X=2, the mana cost is {2}{G}{G}. The cost reduction of {1} reduces the generic component to {1}, making the cost {1}{G}{G} (3 mana total). Trinisphere sees the mana component is 3 mana, so it does nothing. You pay {1}{G}{G} and get 2 tokens.

In summary: with X=0, you pay {3} and get 0 tokens; with X=1, you pay {3} and get 1 token; with X=2, you pay {1}{G}{G} and get 2 tokens. The best value is X=2, because you get 2 tokens for the same or less mana than X=0 or X=1.

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
citations: ['113.6m', 'Grist, the Hunger Tide ruling #1', 'Animate Dead ruling #4', 'Animate Dead ruling #0', '704.4']
text: Yes, you can return Grist, the Hunger Tide from your graveyard with Animate Dead. Here is the step-by-step process and outcome:

1. **Casting Animate Dead**: You cast Animate Dead targeting the Grist card in your graveyard. Animate Dead is an Aura with "Enchant creature card in a graveyard," so it targets a creature card in a graveyard. Grist, while in the graveyard, is a Legendary Planeswalker Creature — Grist Insect (per [Grist, the Hunger Tide ruling #1]), so it is a legal target.

2. **Animate Dead enters the battlefield**: When Animate Dead enters the battlefield, its triggered ability triggers: "When this Aura enters, if it's on the battlefield, it loses 'enchant creature card in a graveyard' and gains 'enchant creature put onto the battlefield with this Aura.' Return enchanted creature card to the battlefield under your control and attach this Aura to it." This ability functions only while Animate Dead is on the battlefield (per [113.6m], abilities of non-instant/sorcery objects usually function only on the battlefield).

3. **Resolution of the triggered ability**: The ability returns Grist from the graveyard to the battlefield under your control. Grist enters the battlefield as a planeswalker (it loses the creature type upon entering the battlefield, per [Grist, the Hunger Tide ruling #1]). Animate Dead then attaches to Grist. Grist gains "Enchanted creature gets -1/-0" from Animate Dead, but since Grist is no longer a creature on the battlefield, this -1/-0 has no effect (it modifies power/toughness, which a non-creature planeswalker doesn't have).

4. **Leaves-the-battlefield trigger**: Animate Dead also has a delayed triggered ability: "When this Aura leaves the battlefield, that creature's controller sacrifices it." If Animate Dead later leaves the battlefield, Grist's controller must sacrifice Grist.

5. **State-based actions**: After Grist enters the battlefield, check if Animate Dead can legally enchant it. Animate Dead now has "Enchant creature put onto the battlefield with this Aura." Grist is a planeswalker, not a creature, so it is not a legal permanent for Animate Dead to enchant. Per [Animate Dead ruling #4], if the creature put onto the battlefield can't legally be enchanted by Animate Dead, Animate Dead won't be able to attach to it. It will be put into the graveyard as a state-based action (rule [704.4] notes state-based actions are checked after resolution). This causes Animate Dead's delayed triggered ability to trigger. When that trigger resolves, if Grist is still on the battlefield, its controller sacrifices Grist.

**Conclusion**: Grist enters the battlefield, but Animate Dead immediately goes to the graveyard because it can't enchant a non-creature permanent. Then the delayed trigger from Animate Dead forces you to sacrifice Grist. So Grist will end up back in the graveyard shortly after entering.

**Key rules relied on**: [113.6m] (abilities of non-instant/sorcery objects function on battlefield), [Grist, the Hunger Tide ruling #1] (Grist is a creature card in graveyard), [Animate Dead ruling #4] (if creature can't be enchanted, Animate Dead goes to graveyard and sacrifice trigger occurs), [Animate Dead ruling #0] (triggered ability only works if Animate Dead is on battlefield), [704.4] (state-based actions checked after resolution).

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
citations: ['122.2', 'Skullbriar, the Walking Grave ruling #2', 'Doubling Season ruling #2']
text: No, Skullbriar does not keep the counters when it moves from the command zone to the battlefield, and Doubling Season does not double them upon re-entry. When Skullbriar is recast, it moves from the command zone to the stack and then to the battlefield as a new object. Counters are not retained when an object moves from one zone to another (rule 122.2). Skullbriar's own ability only retains counters when moving to zones other than a player's hand or library, but moving from the command zone to the battlefield is a zone change, so the counters it had in the command zone cease to exist. Doubling Season's replacement effect applies to effects that would put counters on a permanent, but Skullbriar entering the battlefield does not involve an effect putting counters on it—it simply enters without counters. The counters that were on Skullbriar in the command zone are not placed by an effect; they are lost due to zone change (rule 122.2). Therefore, Skullbriar enters the battlefield with no counters, and Doubling Season has nothing to double.

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
citations: ['724.1d', '724.1e', 'Final Fortune ruling #1', 'Sundial of the Infinite ruling #1']
text: No, you do not lose the game. Final Fortune creates a delayed triggered ability that triggers “at the beginning of that turn’s end step.” When you activate Sundial of the Infinite to end the turn before the end step, the end step is skipped entirely (rule [724.1d] and [724.1e]). Because the end step never occurs, the delayed triggered ability never triggers, so you never lose the game. This is confirmed by the Final Fortune ruling: “If you end up skipping the extra turn that is gained, you do not lose the game.” Although that ruling refers to skipping the entire turn, the same principle applies when the end step is skipped—the trigger condition is never met. The Sundial ruling also states that “at the beginning of the end step” triggered abilities won’t trigger that turn because the end step is skipped, and they will trigger at the beginning of the next turn’s end step. However, since Final Fortune’s delayed trigger is tied specifically to that extra turn, it will not trigger later; it simply never triggers, and you do not lose.

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
citations: ['707.6', 'Clone ruling #0', 'Clone ruling #5']
text: You choose what Clone copies as it enters the battlefield, not as you cast it. The choice is made when the replacement effect from Clone's ability applies to the event of it entering the battlefield. This choice does not use the stack and cannot be responded to by your opponent. Once Clone is on the battlefield, it is already a copy of the chosen creature (or a 0/0 if you chose not to copy). Your opponent can only respond to the Clone spell while it is on the stack, before it resolves and enters the battlefield. This is based on rule [707.6], which states that when a permanent enters as a copy, the controller makes any "as [this] enters" choices at that time, and Clone's ability is such a choice. Additionally, Clone ruling #0 confirms the ability doesn't target, and Clone ruling #5 notes you can choose not to copy anything, which also happens on entry.

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
citations: ['707.10b', '701.23h', 'Gogo, Master of Mimicry ruling #6']
text: You get two lands from that one Flooded Strand activation. Here's the step-by-step reasoning:

1. **Flooded Strand's ability** is an activated ability on the stack. Its text instructs you to "Search your library for a Plains or Island card, put it onto the battlefield, then shuffle."

2. **Gogo, Master of Mimicry's ability** targets that activated ability on the stack and creates copies of it. With X=2, it creates two copies of Flooded Strand's ability on the stack (rule [707.10b] and [Gogo, Master of Mimicry ruling #6]).

3. **Each copy** is a separate instance of the ability on the stack. When each copy resolves, you follow its instructions: search your library for a Plains or Island card, put it onto the battlefield, then shuffle.

4. **Searching multiple times**: Rule [701.23h] says that if an effect instructs a player to search a library more than once before shuffling, it's treated as a single search for all those cards. However, this rule applies only when a single effect instructs multiple searches before a single shuffle. Here, each copy of the ability is a separate effect on the stack, and each copy includes its own shuffle instruction. Therefore, each copy resolves independently: you search, put a land onto the battlefield, and shuffle for each copy.

5. **Result**: The original Flooded Strand ability resolves first (giving you one land), then each of the two copies resolves (giving you one land each), for a total of three lands from the original activation. However, the question asks "from that one Flooded Strand" — the original activation gives one land, and the two copies give two additional lands, so you get two lands from the copies, for a total of three lands overall.

**Key rules used**: [707.10b] (copying an ability), [701.23h] (multiple searches in one effect), [Gogo, Master of Mimicry ruling #6] (Gogo creates copies of abilities on the stack).

---

## Output instructions

Grade all 50 cells above per the rubric. For EACH cell, write exactly one JSON line to:

    evals/opus_grader_v2_out/deepseek-v4-flash.jsonl

Each line is a single JSON object with EXACTLY these fields and nothing else:

    {"id": "<cell id, e.g. q007 or c012>", "arm": "deepseek-v4-flash", "verdict": "correct"|"partial"|"wrong", "reason": "<one-line reason>"}

Every one of the 50 cells above must be accounted for -- one line per cell, any order, no duplicates, no extra fields, no commentary outside the JSONL lines. If a cell is genuinely ungradeable, still write a line with your best-effort verdict and say why in the reason -- never silently drop a cell.