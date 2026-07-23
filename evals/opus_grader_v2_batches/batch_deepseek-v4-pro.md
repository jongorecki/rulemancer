# Opus-Grader Calibration v2 -- Batch: deepseek-v4-pro

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
citations: ['702.26d', '603.6a']
text: No. Phasing in does not cause a permanent to enter the battlefield; it simply changes the permanent's status from "phased out" to "phased in." The rules explicitly state that zone-change triggers (which include enters-the-battlefield abilities) don't trigger when a permanent phases in or out, and effects that check a permanent's history won't treat the phasing event as having caused it to leave or enter the battlefield.

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
citations: ['702.2c', '120.4a', '702.19b']
text: When a creature has both trample and deathtouch, assigning combat damage becomes very efficient. Deathtouch means any nonzero amount of combat damage assigned to a creature is lethal for excess damage calculations (rule 702.2c). Trample requires you to assign lethal damage to all blockers before assigning excess damage to the defending player or planeswalker (rule 702.19b). Because 1 damage from a deathtouch source is already lethal, you only need to assign 1 damage to each blocking creature. Any remaining damage can then trample over to the player or planeswalker being attacked. Rule 120.4a confirms that for deathtouch sources, any damage greater than 1 is excess damage when dealing damage to a creature, so exactly 1 damage is sufficient to satisfy the lethal requirement for trample.

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
citations: ['702.40a', '113.9', '603.3']
text: Yes. Storm is defined as a triggered ability that functions on the stack (rule 702.40a). When you cast a spell with storm, the triggered ability goes on the stack above that spell. As a triggered ability on the stack, it can be countered by effects that specifically counter abilities (rule 113.9); it remains on the stack until it's countered, it resolves, or another effect removes it (rule 603.3). It cannot be countered by effects that only counter spells, because triggered abilities are not spells.

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
citations: ['903.5c', '903.4f', '107.4e']
text: No, you cannot. A card's color identity includes all colors of mana symbols in its mana cost and rules text. A hybrid mana symbol like {R/G} is both red and green (rule 107.4e), so a card with that symbol has a color identity containing both colors. Commander deck construction requires that every color in a card's color identity be present in the commander's color identity (rule 903.5c). If your commander has only one of those colors, the card's other color is not in the commander's identity, making the card illegal.

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
citations: ['502.4', '117.3a', '500.3']
text: No, you cannot respond to the untap step. During the untap step, no player receives priority ([502.4], [117.3a]). Since priority is never given, no player can cast spells or activate abilities. Any abilities that trigger during the untap step are held and will be put on the stack when a player would next receive priority, which is usually in the upkeep step ([503.1a]). The untap step is one of the steps where no priority is ever given ([500.3]).

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
citations: ['Attacking Creature', '508.1k', '511.3', '511.2']
text: Yes, creatures remain attacking creatures during the end of combat step. An attacking creature remains an attacking creature until it's removed from combat or the combat phase ends, whichever comes first (rule 508.1k and the Attacking Creature definition). The end of combat step is the final step of the combat phase (see [End of Combat Step]), and creatures are only removed from combat as the step ends (rule 511.3). Additionally, effects that last 'until end of combat' expire at the end of the combat phase, not at the start of the end of combat step (rule 511.2), so those effects keep creatures attacking throughout the step. Of course, a creature could be removed from combat earlier by an effect that specifically removes it (rule 506.4a), but absent such an effect, it's still attacking during the end of combat step.

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
citations: ['305.1', '305.9', '300.2a', '202.1b']
text: No, you do not cast lands. Lands are never spells and are never cast. Instead, you **play** a land as a special action that doesn't use the stack. This is true even for cards that are both a land and another card type (like artifact lands) — they can only be played as lands, not cast as spells. Lands have no mana cost, and playing them doesn't involve paying any costs.

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
citations: ['702.74a', '113.7a']
text: Yes, you can sacrifice an evoked creature before its evoke triggered ability resolves. The evoke ability creates a triggered ability that goes on the stack when the creature enters. You can respond to that trigger by activating an ability or casting a spell that sacrifices the creature. Once the trigger is on the stack, it exists independently of its source (rule 113.7a). When the evoke trigger resolves, it instructs you to sacrifice the creature, but if the creature is no longer on the battlefield, you can't sacrifice it, and the trigger does nothing (or as much as possible).

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
citations: ['702.1', '113.10', '113.2a']
text: Yes, losing all abilities includes keyword abilities. Keyword abilities are simply a shorthand way of writing common abilities (rule 702.1), and they are still abilities. An effect that removes abilities (rule 113.10) will remove all abilities, including keyword ones, because any game text that defines what a permanent can or can't do is an ability (rule 113.2a).

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
citations: ['[402.2]', '[514.1]']
text: Yes, you can draw cards even if you're already at your maximum hand size. The maximum hand size only matters during your cleanup step: at that point, if you have more cards than your maximum hand size, you must discard down to that number. There is no rule that prevents you from drawing cards simply because your hand is already full.

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
citations: ['306.9', '704.5i', '306.5c']
text: When a planeswalker has exactly 0 loyalty counters, its loyalty is 0 (rule 306.5c), and it is put into its owner's graveyard as a state-based action (rules 306.9, 704.5i). The provided rules do not explicitly address a planeswalker having less than 0 loyalty counters, so the outcome in that case is not covered by these rules. In practice, damage removes loyalty counters and you cannot have negative counters, but that principle is not stated in the given rules.

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
citations: ['[Dies]', '[700.4]']
text: No, non-creature artifacts do not die. The term "dies" is defined as "is put into a graveyard from the battlefield" and applies only to creatures and planeswalkers. A non-creature artifact put into a graveyard from the battlefield is simply moved to the graveyard; it hasn't "died."

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
citations: ['[121.4]', '[704.5b]', '[121.6a]', '[614.11]']
text: When you are required to draw a card (e.g., during your draw step or from a spell) and your library has no cards, you attempt to draw but no card moves from your library to your hand. Then, the next time state-based actions are checked, you lose the game [121.4][704.5b]. This is true even if you are forced to draw more cards than remain—you draw nothing and then lose [104.3c].

However, if an effect would replace that card draw (such as "If you would draw a card, instead …"), that replacement effect is applied even though your library is empty, and you may not actually draw a card—potentially avoiding the loss [121.6a][614.11].

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
citations: ['506.1', '117.3a', '506.2', '802.2', '511.1', '507.1']
text: The combat phase has five steps, which proceed in order: beginning of combat, declare attackers, declare blockers, combat damage, and end of combat. The declare blockers and combat damage steps are skipped if no creatures are declared as attackers or put onto the battlefield attacking. There are two combat damage steps if any attacking or blocking creature has first strike or double strike [506.1].

As the defending player, you receive priority during each of these steps after the active player has passed priority. At the start of each step (except end of combat, which has no turn-based actions [511.1]), any turn-based actions are performed and triggered abilities go on the stack. Then the active player gets priority. Once the active player passes, you (the defending player) get priority [117.3a]. In a two-player game, the nonactive player is automatically the defending player [506.2]. In a multiplayer game using the Attack Multiple Players option, all opponents are defending players and receive priority in APNAP order after the active player [802.2]. In other multiplayer variants, the active player may choose a defending player as a turn-based action at the start of the beginning of combat step [507.1], and that player (along with any other defending players dictated by the variant) will get priority after the active player in each step.

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
citations: ['605.3b', '113.4', '405.6c']
text: No, you cannot respond to a mana ability. Mana abilities don't use the stack; they resolve immediately after being activated. This means they can't be targeted, countered, or otherwise responded to. This applies to both activated mana abilities (like tapping a land for mana) and triggered mana abilities (like an enchantment that adds mana when a land is tapped).

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
citations: []
text: The provided rules don't settle whether you can respond to a cost being paid. They describe how costs are paid as part of casting spells or activating abilities, but they don't include the rules about the stack, priority, or the fact that paying costs doesn't use the stack and doesn't allow responses. Without those rules, I can't give a definitive answer.

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
citations: ['613.1', '613.1a', '613.1c', '613.1d', '613.1e', '613.1f', '613.2a', '613.4a', '613.5', '613.6', '613.8', '613.8a', 'Layer']
text: Layers are the system Magic uses to determine the order in which continuous effects modify an object's characteristics. The game starts with the object's printed values (or the values defined by the effect that created it for tokens/copies) and then applies all applicable continuous effects in a strict sequence of layers, from 1 to 7 [613.1]. The layers are:

- **Layer 1:** Effects that modify copiable values, including copy effects and "as . . . enters" abilities that set power/toughness [613.1a]. Within this layer, sublayer 1a applies copiable effects [613.2a].
- **Layer 2:** Control-changing effects (e.g., Act of Treason's "gain control" part) [613.6].
- **Layer 3:** Text-changing effects [613.1c].
- **Layer 4:** Type-changing effects (card type, subtype, supertype) [613.1d].
- **Layer 5:** Color-changing effects [613.1e].
- **Layer 6:** Ability-adding effects, keyword counters, ability-removing effects, and effects that say an object can't have an ability [613.1f].
- **Layer 7:** Power- and toughness-changing effects. This layer has sublayers: 7a applies characteristic-defining abilities that define power/toughness [613.4a]; 7b applies effects that set power/toughness to a specific value; 7c applies effects that modify power/toughness (e.g., +1/+1 counters, +N/+N boosts) [613.5].

Within each layer or sublayer, effects are normally applied in timestamp order, but dependency can override that order if one effect depends on another [613.8, 613.8a]. If an effect has parts that belong in different layers, each part is applied in its appropriate layer, and the effect continues to apply to the same set of objects even if the ability generating it is removed [613.6]. The entire process is automatic and instantaneous—any change to an object's characteristics is immediately reflected [613.5].

This layered system ensures that all continuous effects interact in a predictable way, regardless of the order they entered the battlefield or resolved.

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
citations: ['[Legend Rule]', '[704.5j]', '[205.4d]', '[306.4]']
text: The legend rule is a state-based action that prevents a player from controlling two or more legendary permanents with the exact same name. Whenever state-based actions are checked (right before a player would receive priority), if a single player controls multiple legendary permanents that share a name, that player must choose one of them to keep. All the others are put into their owners' graveyards. This is not a sacrifice or destruction effect; it simply moves them to the graveyard as a game rule. The rule applies to any permanent with the legendary supertype, including creatures, artifacts, enchantments, lands, and planeswalkers (since planeswalkers now have the legendary supertype instead of the old planeswalker uniqueness rule). The choice of which permanent to keep is made by the player who controls them, and the rest are put into the graveyard simultaneously.

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
citations: ['704.5g', '704.3', '117.5', '120.6', '120.5', '117.2d']
text: Your creature dies the next time state-based actions are checked after the lethal damage is marked on it. State-based actions are checked right before any player would receive priority (for example, after a spell or ability resolves, or after combat damage is dealt). The game sees that the total damage marked on the creature is greater than or equal to its toughness, and the creature is destroyed as a state-based action. This destruction doesn't use the stack and can't be responded to. The damage itself doesn't destroy the creature; the state-based action does.

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
citations: ['704.6d', '903.9a', '903.8']
text: No, you cannot cast your commander from exile simply because it is your commander. The Commander rules provide a state-based action that allows you to put your commander into the command zone if it is in exile (or the graveyard) since the last time state-based actions were checked [704.6d, 903.9a]. This is a move to the command zone, not a cast. The only zone from which the rules explicitly allow you to cast your commander is the command zone, with an additional cost for each previous cast from that zone [903.8]. To cast your commander from exile, you would need a specific effect that allows you to cast spells from exile (such as a card like 'Eternal Scourge' or 'Karn, the Great Creator'), and no such permission is inherent to the commander designation.

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
citations: ['514.2', '514.3', '514.3a', '704.3', '703.4p', '500.3']
text: During the cleanup step, the following happens in order:

1. **Discard to hand size**: If the active player has more cards in hand than their maximum hand size (usually seven), they discard cards until they have that many. This is a turn-based action that doesn't use the stack (implied by [703.4p], which references discarding as a prerequisite for the next actions).

2. **Simultaneous turn-based actions**: Immediately after any discarding, all damage marked on permanents is removed, and all "until end of turn" and "this turn" effects end. These happen at the same time and don't use the stack [514.2, 703.4p].

3. **Priority (normally none)**: Normally, no player receives priority during the cleanup step, so no spells can be cast and no abilities can be activated [514.3]. However, there is an exception: the game checks for state-based actions and waiting triggered abilities (including those that trigger "at the beginning of the next cleanup step"). If any are found, those state-based actions are performed, then those triggered abilities are put on the stack, and then the active player gets priority. Players may cast spells and activate abilities. Once the stack is empty and all players pass in succession, another cleanup step begins [514.3a, 704.3]. If no state-based actions are performed and no triggered abilities are waiting, the step ends without any player receiving priority [704.3, 500.3].

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
citations: ['704.3', '117.5', '514.3a', '724.2c', '724.1c', '703.3']
text: State-based actions are checked automatically by the game rules, not controlled by any player, and they don't use the stack. They are checked:

- **Whenever a player would get priority** (including during the cleanup step if any state-based actions or triggered abilities are waiting). This is the primary timing: before any player receives priority, the game performs all applicable state-based actions, then repeats until none are performed, then puts waiting triggered abilities on the stack, and repeats again until nothing further happens. Only then does the player get priority. [704.3, 117.5]
- **During the cleanup step**, if state-based actions need to be performed or triggered abilities are waiting, they are checked and performed, then the active player gets priority. If nothing happens, no player gets priority and the step ends. [514.3a]
- **When an effect ends the combat phase** (e.g., Mandate of Peace) or **ends the turn**, state-based actions are checked as part of that process, and no player gets priority during that check. [724.2c, 724.1c]
- **After turn-based actions** at the beginning of a step or phase, state-based actions are checked before triggered abilities are put on the stack and before players receive priority. [703.3]

In all cases, state-based actions are performed as a single event, and the check repeats if any were performed, ensuring the game state is cleaned up before players can act.

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
citations: ['104.3a', '723.6', '405.6g', '101.1']
text: A player can concede the game at any time. This is a special action that doesn't use the stack, and it causes that player to leave the game immediately and lose. Even if another player controls your turn (e.g., via Mindslaver), you may still concede at any time. In Two-Headed Giant, if a player concedes, their entire team leaves the game and loses.

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
citations: ['[102.1]']
text: The active player is simply the player whose turn it is. Rule 102.1 defines the active player as "the player whose turn it is," with all other players being nonactive players. So at any point in the game, look at whose turn is currently taking place—that player is the active player. In games using the shared team turns option, the active team is the team whose turn it is (rule 805.4a), but the concept of an individual active player still follows the same principle: the player currently taking their turn.

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
citations: ['117.3c']
text: When a player casts a spell, they must have priority. After the spell is cast, the player who cast it receives priority again. This applies regardless of whether that player is the active player or not. So if a non-active player casts a spell, that non-active player gets priority first afterward.

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
citations: ['117.3c']
text: When the active player casts a spell, they had priority to do so. According to rule 117.3c, the player who had priority when they cast a spell receives priority again immediately afterward. Therefore, the active player gets priority first after casting their own spell.

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
citations: ['601.2i', '117.3c']
text: Yes. After you cast a spell, if you had priority before casting it, you receive priority again (rule 601.2i). This means you can immediately cast another spell or activate an ability before any other player gets a chance to respond. The general rule 117.3c also confirms that a player who casts a spell receives priority afterward. This is commonly referred to as "holding priority."

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
citations: ['714.3a', '714.3b', '702.155b', '714.3c', '703.4f', '505.4']
text: Lore counters are put on Sagas in two ways:

1. **As they enter the battlefield** – A Saga without read ahead enters with one lore counter (rule 714.3a). A Saga with read ahead enters with a number of lore counters chosen by its controller between one and its final chapter number (rules 714.3b, 702.155b). Both are replacement effects.

2. **At the start of your precombat main phase** – As a turn-based action that doesn't use the stack, you put a lore counter on each Saga you control that has one or more chapter abilities (rules 714.3c, 703.4f, 505.4). This happens immediately after that phase begins.

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
citations: ['Delayed Triggered Ability', '603.7']
text: A delayed triggered ability is an ability created by effects generated when some spells or abilities resolve, or when some replacement effects are applied, that does something later on rather than at that time. It contains “when,” “whenever,” or “at,” although that word won’t usually begin the ability. It triggers only after it has been created, even if the trigger event occurred just beforehand.

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
citations: ['113.6', '113.3a', '405.4']
text: Yes, non-permanent spells (instants and sorceries) can have abilities. Rule 113.6 states that abilities of an instant or sorcery spell usually function only while that object is on the stack. Rule 113.3a explains that any text on an instant or sorcery spell is a spell ability unless it's an activated, triggered, or static ability that fits the criteria in rule 113.6. Additionally, rule 405.4 says each spell has all the characteristics of the card associated with it, so any abilities printed on the card are present on the spell while it's on the stack.

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
citations: ['702.61b', '702.61a']
text: Yes, you can activate a mana ability while a spell with split second is on the stack. Split second only prevents casting other spells and activating non-mana abilities. The split second rules explicitly state that players may activate mana abilities and take special actions while such a spell is on the stack.

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
citations: ['[117.7]', '[701.6a]']
text: Counterspell resolves first because it's on top of the stack. When it resolves, it counters Divination, removing Divination from the stack and putting it into your graveyard. Divination never resolves and none of its effects occur.

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
citations: ['702.19b', 'Lethal Damage', '702.2c']
text: You must assign at least 3 damage to Vampire Nighthawk before trampling over. Trample requires you to assign lethal damage to all blockers first, and lethal damage is defined as damage equal to a creature's toughness (here, 3, since Nighthawk is a 2/3). The deathtouch ability on the blocker doesn't change this requirement—rule 702.2c only makes 1 damage count as lethal when the *source* dealing the damage has deathtouch, and your Charging Rhino does not have deathtouch.

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
citations: ['601.2i', '608.2g', '704.4', 'Monastery Swiftspear ruling #2']
text: Yes, Monastery Swiftspear's prowess triggers when you cast the noncreature spell during the resolution of Shardless Agent's cascade ability. However, triggered abilities that trigger during the resolution of a spell or ability aren't put onto the stack until that spell or ability finishes resolving. So the prowess trigger waits until cascade has completely resolved, then goes on the stack above the cascaded spell. Because prowess resolves before the spell that caused it (as stated in its ruling), Monastery Swiftspear gets +1/+1 before the cascaded spell resolves.

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
citations: ['704.3', '704.5g', '117.5', '120.6', '302.7']
text: Yes. The Grizzly Bears already has 2 damage marked on it, which equals its toughness of 2. That means it has been dealt lethal damage. State-based actions are checked right before any player would receive priority—including after you cast Lightning Bolt but before it resolves. When that check happens, the game sees a creature with toughness greater than 0, damage marked on it, and total damage greater than or equal to its toughness, so the Bears is destroyed as a state-based action. It will be put into the graveyard before Lightning Bolt ever resolves.

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
citations: ['500.6', '603.2b', '603.3b']
text: Both triggers go on the stack at the beginning of your upkeep. Yours goes on first, then your opponent's, so your opponent's resolves first. You don't get to choose the order between them.

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
citations: ['[702.27a]', '[Fork ruling #8]', '[707.10]']
text: Only the original sorcery card returns to your hand. The copy created by Fork is a spell on the stack but has no physical card associated with it. Buyback's replacement effect ("put this spell into its owner's hand instead of into that player's graveyard as it resolves") applies to the original spell because you paid its buyback cost. The copy inherits the decision that buyback was paid, but since it isn't a card, there is nothing to put into your hand. As Fork ruling #8 states, "If you copy a spell for which Buyback has been paid, you get nothing back since the copied spell does not have a card to give you." The copy simply ceases to exist after it resolves (rule 704.5e).

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
citations: ['Mimic Vat ruling #0']
text: No, you do not get a token. The Mimic Vat ruling explicitly states that if the exiled card is a nonpermanent card (like an instant or sorcery) that was manifested, you can't create a token that's a copy of it, so no token is created.

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
citations: ['Lithoform Engine ruling #4', 'Fiend Hunter']
text: Yes, both exiled creatures return. Fiend Hunter has two linked abilities: the enters-the-battlefield ability that exiles a creature, and the leaves-the-battlefield ability that returns “the exiled card.” When you copy the enters-the-battlefield ability with Lithoform Engine, the copy is also linked to that same leaves-the-battlefield ability. As a result, “the exiled card” refers to all cards exiled by both the original ability and the copy. When Fiend Hunter leaves the battlefield, its second ability triggers and returns both creatures to the battlefield under their owners’ control.

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
citations: ["Teferi's Protection ruling #21", '702.26d']
text: No, the exiled creature does not return to the battlefield. Banishing Light's exile effect is a one-shot effect that returns the exiled permanent when Banishing Light leaves the battlefield. Phasing out does **not** cause a permanent to leave the battlefield (rule 702.26d), so the condition for the return effect is not met. As stated in Teferi's Protection's rulings, any one-shot effects waiting for "until [this] leaves the battlefield" won't happen when a permanent phases out. The creature remains exiled.

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
citations: ['Emrakul, the Promised End ruling #2', '603.1a', '117.7']
text: Yes, your opponent can target Emrakul with Counterspell while it's on the stack. Protection from instants only functions while Emrakul is on the battlefield (see Emrakul ruling #2). On the stack, Emrakul is a spell and does not have that protection, so it's a legal target.

If Counterspell resolves and counters Emrakul, the spell is removed from the stack and goes to the graveyard. However, the triggered ability "When you cast this spell, you gain control of target opponent..." is a separate object on the stack that triggered when you cast Emrakul (rule 603.1a). It exists independently of the spell and will still resolve, even if Emrakul is countered. So you will still control that opponent's next turn and they will take an extra turn afterward.

Your opponent cast Counterspell in response to the cast trigger, which is allowed because players can cast instants while other spells/abilities are on the stack (rule 117.7). The trigger is above Emrakul on the stack, so Counterspell will resolve before the trigger, but that doesn't affect the trigger's existence.

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
citations: ['[702.85a]', '[712.8c]', '[Valki, God of Lies // Tibalt, Cosmic Impostor ruling #16]', 'Card data (MV 2)']
text: Valki, God of Lies // Tibalt, Cosmic Impostor is a modal double-faced card. While it's in your library, it has only the characteristics of its front face (Valki), so its mana value is 2. Cascade exiles cards until it hits a nonland card with mana value less than the cascade spell's mana value. Since Valki's mana value is 2, it's a legal hit as long as the cascade spell's mana value is 3 or greater.

When cascade lets you cast the exiled card, you may cast either face of a modal double-faced card that fits the criteria. The cascade ability then checks whether the resulting spell's mana value is less than the cascade spell's mana value. Tibalt, Cosmic Impostor has mana value 7. Therefore, you can cast Tibalt for free only if the cascade spell's mana value is 8 or more. If the cascade spell's mana value is 7 or less, you cannot cast Tibalt (but you can still cast Valki, whose mana value is 2).

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
citations: ['707.10', '707.10b', '111.13', 'Emrakul, the Promised End ruling #14', 'Lithoform Engine ruling #6']
text: You control **one** of your opponent’s turns (the next one), and they will take **two extra turns** after that turn. You **do** get a second Emrakul — a token copy — but copying the Emrakul spell **does not** give you another control-a-turn trigger.

Here’s why:

1. **Copying the cast trigger**  
   Lithoform Engine’s first ability copies the triggered ability “When you cast this spell, you gain control of target opponent during that player’s next turn. After that turn, that player takes an extra turn.” The copy is put onto the stack and resolves just like the original (rule 707.10). Both the original and the copy will set up a control effect and an extra turn.

   According to Emrakul’s ruling #14, multiple player‑controlling effects that affect the same player overwrite each other — the last one to be created is the one that works. However, **each** ability’s effect still creates an extra turn. So if both the original and the copy target the same opponent, the one that resolves last will control that opponent’s next turn, and the opponent will take two extra turns after that turn (one from each resolution).

2. **Copying the Emrakul spell**  
   Lithoform Engine’s third ability copies the Emrakul permanent spell on the stack. A copy of a spell is **not cast** (rule 707.10b; Lithoform Engine ruling #6 confirms this). Because the copy isn’t cast, Emrakul’s “When you cast this spell” ability does **not** trigger — you get no additional control‑a‑turn trigger from the copy.

   The copy of a permanent spell becomes a token as it resolves (rule 111.13). That token has all the characteristics of Emrakul, the Promised End (a 13/13 legendary Eldrazi with flying, trample, protection from instants). So you do get a second Emrakul on the battlefield, albeit as a token. (The legend rule, which is not covered by the provided rules, would normally force you to put one into your graveyard, but the token itself is created.)

**Summary of the outcomes:**
- Opponent’s turns you control: **1** (the next turn).
- Extra turns the opponent takes: **2** (after that turn).
- Second Emrakul: **Yes**, a token copy.
- Additional control trigger from copying the spell: **No**.

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
citations: ['707.10b', '201.5a', 'Mimic Vat ruling #4', 'Lithoform Engine ruling #0']
text: Yes, you get two tokens. When you copy Mimic Vat's activated ability with Lithoform Engine, the copy is put onto the stack and will resolve separately. The copy's source is the same Mimic Vat (Lithoform Engine ruling #0), so the phrase "this artifact" on the copy still refers to that specific Mimic Vat (rule 201.5a). When the copy resolves, it looks at the card currently exiled with that Mimic Vat and creates a token that's a copy of it, just as the original ability does (Mimic Vat ruling #4). Since the original ability hasn't resolved yet, the exiled card is still there, and both the original and the copy will each create a token. The copy of the ability has the same source as the original, so it functions identically (rule 707.10b).

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
citations: ['601.2f', '118.7a', 'Trinisphere ruling #0']
text: If you cast Awaken the Woods with X=0, the mana cost is {G}{G}. Your cost reduction of {1} is generic mana, and rule 118.7a says generic reductions affect only the generic component of a cost. Since {G}{G} has no generic component, the reduction does nothing, leaving the cost at {G}{G}. Then Trinisphere's effect applies (Trinisphere ruling #0): because the mana component of the cost is only two mana, Trinisphere forces it to cost three mana. You would pay {3} (three generic mana) and create zero tokens.

For the best value, you should choose X=2. The mana cost becomes {2}{G}{G}. After applying the {1} generic reduction, the cost is {1}{G}{G} (three mana total). Trinisphere sees a cost of three mana and does nothing. You pay {1}{G}{G} and create two 1/1 tokens. This is the most tokens you can get while still paying only three mana under Trinisphere.

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
citations: ['Grist, the Hunger Tide ruling #1', 'Animate Dead ruling #4']
text: Yes, you can cast Animate Dead targeting Grist, the Hunger Tide while it's in your graveyard. Because of Grist's first ability, it's a creature card in the graveyard, so it's a legal target for Animate Dead's "enchant creature card in a graveyard." When Animate Dead's enters-the-battlefield trigger resolves, it returns Grist to the battlefield. However, once on the battlefield, Grist is no longer a creature—it's just a planeswalker. Animate Dead's new enchant ability ("enchant creature put onto the battlefield with this Aura") can't legally attach to a noncreature planeswalker. As a state-based action, Animate Dead is put into its owner's graveyard. This causes its delayed triggered ability ("When this Aura leaves the battlefield, that creature's controller sacrifices it") to trigger. When that trigger resolves, you sacrifice Grist. The net result is that both Grist and Animate Dead end up in your graveyard.

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
citations: ['Skullbriar, the Walking Grave ruling #2', 'Skullbriar, the Walking Grave ruling #3', '903.9b']
text: Yes, Skullbriar keeps the four +1/+1 counters. Its ability says counters remain on it as it moves to any zone other than a player's hand or library. When it dies, you may apply the commander replacement effect (rule 903.9b) to put it into the command zone instead of the graveyard. The command zone is not a hand or library, so the counters stay on Skullbriar there (as confirmed by ruling #3). When you recast it, it moves from the command zone to the stack and then to the battlefield — all zones where counters remain — so it enters the battlefield with those four counters still on it.

Doubling Season does **not** double those counters. Its replacement effect only applies when an effect would put counters on a permanent you control. The counters on Skullbriar are not being put on by an effect; they are simply retained due to its own ability. Skullbriar's ruling #2 explicitly states that effects like Doubling Season won't affect counters that remain on it as it changes zones.

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
citations: ['724.1e', 'Sundial of the Infinite ruling #1']
text: No, you do not lose the game during that extra turn. When you activate Sundial of the Infinite before the end step, the turn ends immediately and the end step is skipped entirely. Because the end step never occurs, the delayed triggered ability from Final Fortune (“At the beginning of that turn’s end step, you lose the game”) never triggers. However, according to Sundial’s ruling, any “at the beginning of the end step” abilities that are skipped this way will trigger at the beginning of the next turn’s end step instead. So you will lose the game at the beginning of the next turn’s end step unless you prevent that trigger as well.

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
citations: ['616.1c', '707.6', 'Clone ruling #2', 'Clone ruling #5', 'Clone ruling #0']
text: You choose what Clone copies as it enters the battlefield, not when you cast it. Clone's ability is a replacement effect that modifies how it enters (rule 616.1c). When the Clone spell resolves, it would normally enter as a 0/0 creature, but you apply the replacement effect instead. At that moment, you choose a creature already on the battlefield to copy, or choose to copy nothing (Clone rulings #2, #5). This choice doesn't use the stack and can't be responded to. Your opponent can, however, respond to the Clone spell while it's on the stack, before it resolves. Once Clone enters, the choice is already made and the opponent can't interact with that decision. The choice is not a target (Clone ruling #0), so hexproof or shroud don't prevent copying. The chosen creature's "as enters" choices are not copied; you make any such choices for Clone as it enters (rule 707.6).

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
text: You get three lands total: one from the original Flooded Strand ability and two from the copies created by Gogo, Master of Mimicry.

Here’s why:
- Flooded Strand’s ability is an activated ability that goes on the stack. Its cost (tapping, paying 1 life, and sacrificing the land) is paid only once, when you activate it.
- Gogo’s ability with X=2 copies that ability twice. According to rule 707.10b, a copy of an ability copies all decisions made for the original (modes, targets, etc.) but does **not** require paying costs again. The copies are put onto the stack and will resolve separately.
- Each copy (and the original) instructs you to “Search your library for a Plains or Island card, put it onto the battlefield, then shuffle.” Because each ability is a separate effect that includes its own shuffle instruction, they resolve one after the other: you search, find a land, put it onto the battlefield, shuffle, then repeat for the next ability. Rule 701.23h (which merges multiple searches before a shuffle) does **not** apply here because each ability has its own shuffle step.
- Gogo’s ruling #6 confirms that the ability creates additional instances of the targeted ability on the stack, and ruling #8 confirms it can copy abilities without targets.

So you’ll end up with three lands from that one Flooded Strand activation.

---

## Output instructions

Grade all 50 cells above per the rubric. For EACH cell, write exactly one JSON line to:

    evals/opus_grader_v2_out/deepseek-v4-pro.jsonl

Each line is a single JSON object with EXACTLY these fields and nothing else:

    {"id": "<cell id, e.g. q007 or c012>", "arm": "deepseek-v4-pro", "verdict": "correct"|"partial"|"wrong", "reason": "<one-line reason>"}

Every one of the 50 cells above must be accounted for -- one line per cell, any order, no duplicates, no extra fields, no commentary outside the JSONL lines. If a cell is genuinely ungradeable, still write a line with your best-effort verdict and say why in the reason -- never silently drop a cell.