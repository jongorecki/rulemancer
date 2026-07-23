# Opus-Grader Calibration v2 -- Batch: gemini-flash-lite

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
citations: ['702.26b', '702.26d', '603.10b']
text: No, creatures phasing back in do not trigger enters-the-battlefield abilities. Phasing causes a permanent to be treated as though it does not exist, and zone-change triggers do not occur when a permanent phases in or out. Abilities that trigger when a permanent phases out do look back in time to see if they trigger, but this is an exception for phasing out, not phasing in. [702.26b] [702.26d] [603.10b]

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
citations: ['702.2c', '702.19b', '120.4a']
text: When a creature with trample and deathtouch deals combat damage, deathtouch modifies how lethal damage is determined. Any amount of damage dealt by a source with deathtouch is considered lethal damage for the purposes of determining excess damage [702.2c]. Trample allows the controller of an attacking creature to assign combat damage first to blocking creatures. Once all blocking creatures have been assigned lethal damage, any excess damage can be assigned to the player, planeswalker, or battle the creature is attacking [702.19b]. Because deathtouch makes any amount of damage lethal, even 1 damage from a creature with deathtouch and trample would be considered lethal to a blocker. This means that any remaining damage from that creature can be assigned as excess damage to the defending player, planeswalker, or battle [702.2c, 702.19b, 120.4a].

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
citations: ['702.40a', '603.3', '113.9']
text: Storm is a triggered ability that functions on the stack [702.40a]. Triggered abilities are put onto the stack when they trigger [603.3]. Abilities on the stack that are not spells can be countered by effects that specifically counter abilities [113.9].

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
citations: ['903.4', '107.4e', '903.5c']
text: Yes, you can use cards with hybrid mana symbols in a Commander deck even if only one of the colors in the hybrid symbol is present in your commander's color identity. The color identity of a card is determined by all mana symbols in its mana cost and rules text [903.4]. A hybrid mana symbol is considered to be all of its component colors [107.4e]. Therefore, a card with a hybrid mana symbol like {R/G} has a color identity that includes both red and green. If your commander's color identity is only red, you could include a card with {R/G} in your deck because red is one of the colors in the {R/G} hybrid symbol, and red is present in your commander's color identity [903.5c].

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
citations: ['[502.4]', '[117.3a]', '[500.3]']
text: No, you cannot respond to the untap step. No player receives priority during the untap step, which means no spells can be cast and no abilities can be activated or resolve. Any abilities that trigger during the untap step are held until the next time a player would receive priority, typically during the upkeep step. The untap step ends when all its specified actions are completed, as no players receive priority during this step.

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
citations: ['508.1k', '508.4', '508.4b', '508.4d', '506.4a', 'Attacking Creature']
text: Yes, creatures are still considered attacking creatures during the end of combat step. A creature remains an attacking creature until it is removed from combat or the combat phase ends, whichever comes first. The end of combat step is part of the combat phase, and creatures are only removed from combat at the end of that step if they leave the battlefield, their controller changes, they phase out, an effect specifically removes them, or they are a planeswalker or battle being attacked and stop being so, or if they are an attacking or blocking creature that regenerates, stops being a creature, or becomes a battle. [508.1k], [508.4], [508.4b], [508.4d], [506.4a], [Attacking Creature]

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
citations: ['305.1', '505.6b', '701.18a', '305.9', '300.2a', '302.1']
text: No, you do not cast lands. Playing a land is a special action that does not use the stack and is not a spell [305.1, 505.6b, 701.18a]. Lands are played, not cast [305.1, 701.18a]. Casting a spell is a separate action that uses the stack [302.1]. If an object is both a land and another card type, it can only be played as a land and cannot be cast as a spell [305.9, 300.2a].

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
citations: ['702.74a', '702.48b']
text: No, you cannot sacrifice an evoked creature before its evoke triggered ability resolves. The evoke ability is a triggered ability that goes on the stack when the permanent enters the battlefield [702.74a]. This triggered ability requires you to sacrifice the permanent if its evoke cost was paid [702.74a]. You can only sacrifice a creature as a cost for an ability or spell if that cost is being paid at that time [702.48b]. Since the sacrifice is part of the resolution of the evoke triggered ability, you cannot sacrifice the creature before that ability resolves.

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
citations: ['113.10b', '702.22b', '702.11e']
text: Yes, if a card loses all abilities, this includes keyword abilities. Keyword abilities are a type of ability, and effects that remove abilities remove all instances of them [113.10b]. For example, if a permanent loses banding, it also loses all "bands with other" abilities [702.22b]. Similarly, losing hexproof causes an object to lose all "hexproof from [quality]" abilities [702.11e].

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
citations: ['514.1', '402.2', '703.4n', '104.3c', '609.3', '121.5', '121.6a', '614.11']
text: You can draw cards even if you are at your maximum hand size. However, during your cleanup step, you must discard cards until your hand size is equal to your maximum hand size. If an effect instructs you to draw cards and your library is empty, you will draw the remaining cards and then lose the game the next time a player would receive priority. If an effect attempts to move cards from your library to your hand without using the word "draw," and your library is empty, it will move as many cards as possible. If an effect replaces a card draw, it applies even if no cards can be drawn because your library is empty.

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
citations: ['306.9', '122.1e', '704.5i', '120.3c']
text: When a planeswalker has 0 loyalty counters, it is put into its owner's graveyard. This is a state-based action. Damage dealt to a planeswalker causes that many loyalty counters to be removed from it.

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
citations: ['Dies', '700.4']
text: The term "dies" specifically applies to creatures and planeswalkers. It means that a creature or planeswalker is put into a graveyard from the battlefield [Dies, 700.4]. Non-creature permanents, such as artifacts, do not die. If an artifact is put into a graveyard from the battlefield, it has not died unless an effect specifically states that it dies.

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
citations: ['104.3c', '121.4', '704.5b', '121.3', '121.3a', '121.5']
text: If you are required to draw a card and your library has no cards left, you draw the remaining cards (which is zero cards in this case) and then lose the game the next time a player would receive priority. This is a state-based action. If an effect offers you the choice to draw a card when your library is empty, you can choose to do so. However, if another effect prevents you from drawing cards, you cannot choose to draw a card. If an effect moves cards from your library to your hand without using the word "draw," you have not drawn those cards, and this does not cause you to lose the game if your library is empty.

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
citations: ['506.1', '703.4h', '507.1', '506.2', '802.2', '117.3a', '511.1']
text: The combat phase consists of five steps: beginning of combat, declare attackers, declare blockers, combat damage, and end of combat [506.1]. The declare attackers and combat damage steps are skipped if no creatures are declared as attackers or put onto the battlefield attacking [506.1]. There are two combat damage steps if any attacking or blocking creature has first strike or double strike [506.1].

In a two-player game, the nonactive player is the defending player [506.2]. In a multiplayer game, if not all opponents automatically become defending players, the active player chooses one opponent to be the defending player during the beginning of combat step [703.4h, 507.1]. If the "Attack Multiple Players Option" is in play, all opponents are defending players [802.2].

You, as the defending player, receive priority during the beginning of combat step after any turn-based actions have been dealt with and abilities that trigger at the beginning of that step have been put on the stack [117.3a]. You also receive priority during the end of combat step [511.1].

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
citations: ['605.3b', '605.4a', '405.6c']
text: No, you cannot respond to a mana ability. Mana abilities do not use the stack, which means they cannot be targeted, countered, or otherwise responded to. They resolve immediately after they are activated or triggered. [605.3b], [605.4a], [405.6c]

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
citations: ['601.2g', '508.1j', '509.1f', '601.2h', '118.2', '508.1i', '509.1e', '602.4']
text: You cannot respond to a cost being paid. The rules state that paying costs is part of the process of casting a spell [601.2g], declaring attackers [508.1j], declaring blockers [509.1f], or activating an ability [602.4]. Once a player has begun to pay costs, they must complete the payment, and partial payments are not allowed [509.1f, 508.1j, 601.2h]. If a player is unable to pay a cost, the action is illegal and the game returns to the state before the action began [601.2g, 508.1j, 509.1f]. However, you do have a chance to activate mana abilities before costs are paid if the cost includes mana [118.2, 601.2g, 508.1i, 509.1e].

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
citations: ['[613.1]', '[613.2c]', '[613.8]', '[613.1a]', '[613.1c]', '[613.1d]', '[613.1e]', '[613.1f]', '[613.3]', '[613.4a]', '[613.5]', '[613.6]', '[Layer]']
text: Layers are a system used to determine the order in which continuous effects are applied to objects in Magic: The Gathering [Layer]. Continuous effects are applied in a series of layers, and within each layer, effects are applied in sublayers, then by timestamp order, unless a dependency alters this order [613.1, 613.2c, 613.8]. The layers are as follows:

Layer 1: Rules and effects that modify copiable values are applied. This includes copy effects and effects that merge an object with a permanent. After this layer, an object's characteristics are its copiable values [613.1a, 613.2c].
Layer 2: Control-changing effects are applied [613.3].
Layer 3: Text-changing effects are applied [613.1c].
Layer 4: Type-changing effects are applied, including changes to card types, subtypes, and supertypes [613.1d].
Layer 5: Color-changing effects are applied [613.1e].
Layer 6: Ability-adding effects, keyword counters, ability-removing effects, and effects that prevent abilities are applied [613.1f].
Layer 7: Power and toughness modifying effects are applied. This layer has several sublayers:
Layer 7a: Effects from characteristic-defining abilities that define power and/or toughness are applied [613.4a].
Other sublayers within Layer 7 apply effects in timestamp order [613.4a]. For example, a +1/+1 counter is applied in layer 7c, followed by a spell that grants +4/+4, then an enchantment that grants +0/+2, and finally an effect that sets power and toughness to 0/1, with the final result determined by the order of application [613.5].

Some effects span multiple layers. For instance, an effect that grants +1/+1 and changes color applies the color change in layer 5 and the power/toughness bonus in layer 7c [613.6]. Similarly, an effect that changes an artifact to a creature and sets its power/toughness applies the type change in layer 4 and the power/toughness change in layer 7b [613.6].

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
citations: ['Legend Rule', '704.5j', '205.4d', '306.4']
text: The legend rule is a state-based action that applies when a player controls two or more legendary permanents that share the same name. In this situation, the player must choose one of those permanents to keep, and all the others are put into their owners' graveyards. This rule applies to any permanent with the supertype "legendary," including planeswalkers that have received errata to have this supertype [Legend Rule, 704.5j, 205.4d, 306.4].

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
citations: ['120.6', '302.7', '704.5g', '704.3', '514.3a', '514.2']
text: A creature with lethal damage marked on it is destroyed as a state-based action [120.6, 302.7, 704.5g]. State-based actions are checked automatically whenever a player would receive priority, or during the cleanup step [704.3, 514.3a]. If a creature has lethal damage marked on it, it will be destroyed at that time [704.5g]. Damage marked on a creature is removed during the cleanup step [120.6, 514.2].

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
citations: ['704.6d', '903.9a', '601.3f', '406.3b']
text: Yes, you can cast your commander from exile in a Commander game. If your commander is in the graveyard or in exile, and it was put into that zone since the last time state-based actions were checked, you may put it into the command zone. This is a state-based action. Additionally, some effects allow you to cast spells from exile, and if your commander meets the criteria of such an effect, you may cast it. Cards exiled face down can be cast if you are allowed to look at them and the spell has the specified qualities.

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
citations: ['514.2', '514.3', '514.3a', '704.3']
text: During the cleanup step, all damage marked on permanents is removed, and all "until end of turn" and "this turn" effects end. These actions happen simultaneously and do not use the stack [514.2]. Normally, no player receives priority during the cleanup step, meaning no spells can be cast and no abilities can be activated [514.3]. However, if state-based actions need to be performed or triggered abilities are waiting to be put on the stack, those actions are performed, the abilities are put on the stack, and then the active player receives priority. If this happens, players may cast spells and activate abilities. Once the stack is empty and all players pass in succession, another cleanup step begins [514.3a]. If no state-based actions are performed and no triggered abilities are waiting to be put on the stack during the cleanup step's initial check, the step ends without any player receiving priority [704.3].

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
citations: ['704.2', '704.1a', 'State-Based Actions', '117.2d', '405.6f', '117.5', '704.3', '724.2c', '724.1c', '703.3', '405.6e']
text: State-based actions are checked throughout the game and happen automatically whenever certain conditions are met [704.2, 704.1a, State-Based Actions]. They are dealt with before a player would receive priority [117.2d, 405.6f]. Specifically, each time a player would get priority, the game first performs all applicable state-based actions as a single event [117.5]. This process repeats until no more state-based actions are performed [117.5]. State-based actions are also checked during the cleanup step [704.3]. Additionally, they are checked when an effect ends the combat phase or ends the turn [724.2c, 724.1c]. Turn-based actions, which happen before state-based actions are checked, occur at the beginning of each step and phase, and also when each step and phase ends [703.3, 405.6e].

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
citations: ['104.3a', '723.6', '810.8b', 'Concede', '405.6g', '101.1']
text: A player may concede the game at any time. Conceding causes that player to leave the game immediately and lose the game. This is true even if another player controls you, or if you are playing in a Two-Headed Giant game where your team will leave the game and lose. The only exception to this rule is that a card's text that directly contradicts the rules takes precedence, unless that card's text is about conceding, in which case a player can still concede at any time.

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
citations: ['Active Player', '101.4e', '805.9', 'Active Team']
text: The active player is the player whose turn it is [Active Player]. In a multiplayer game using the shared team turns option, the active team is the team whose turn it is, and each other team is a nonactive team [Active Team]. If multiple players would make choices or take actions at the same time, the active player makes their choices first, followed by the other players in turn order [101.4e]. Any ability that refers to the "active player" refers to one specific active player, and the ability's controller chooses which one at the time its effect is applied [805.9].

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
citations: ['117.3b', '101.4d', '101.4e']
text: When a player who is not the active player casts a spell, the active player receives priority first. This is because the active player generally receives priority after a spell resolves [117.3b]. If multiple players would make choices or take actions at the same time, the active player makes their choices first, followed by other players in turn order [101.4d, 101.4e].

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
text: When the active player casts a spell, that player receives priority afterward. This is because casting a spell is an action for which the active player would normally receive priority, and rule [117.3c] states that if a player has priority when they cast a spell, that player receives priority afterward.

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
citations: ['117.3b', '117.3c', '601.2i', '608.2g']
text: You can hold priority to cast more spells after you've cast one or more spells if the spell you are resolving instructs or allows you to cast another spell during its resolution. In this specific case, no player receives priority after the new spell is cast, and the current spell or ability continues to resolve. However, under normal circumstances, after a spell resolves, the active player receives priority [117.3b]. If you cast a spell, you receive priority afterward [117.3c]. When casting a spell, after the steps for casting are completed and effects that modify the spell are applied, the spell becomes cast. If you had priority before casting it, you get priority again [601.2i].

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
citations: ['714.3b', '714.3a', '714.3c', '505.4', '703.4f']
text: Lore counters are put on Sagas in two ways. First, when a Saga enters the battlefield, it gets lore counters based on whether it has "read ahead." If it has read ahead, its controller chooses a number between one and its final chapter number, and the Saga enters with that many lore counters [714.3b]. If it does not have read ahead, it enters with one lore counter [714.3a]. Second, as a player's precombat main phase begins, that player puts a lore counter on each Saga they control that has one or more chapter abilities [714.3c, 505.4, 703.4f]. This is a turn-based action and does not use the stack [703.4f, 505.4].

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
citations: ['Delayed Triggered Ability', '603.7a', '603.7', '603.7b', '603.7d', '603.7e', '603.7f', '603.7g', '603.7c', '107.3n', '603.12', '603.3a']
text: A delayed triggered ability is an ability created by effects that will do something later in the game, rather than when the spell or ability that created it resolves [Delayed Triggered Ability]. These abilities are created during the resolution of spells or abilities, as the result of a replacement effect being applied, or as the result of a static ability that allows a player to take an action [603.7a]. A delayed triggered ability will contain "when," "whenever," or "at," though that word won't usually begin the ability [603.7]. It will trigger only once, the next time its trigger event occurs, unless it has a stated duration [603.7b]. If a spell creates a delayed triggered ability, that spell is its source, and the player who controlled the spell as it resolved is its controller [603.7d]. If an activated or triggered ability creates a delayed triggered ability, the source and controller are the same as the original ability [603.7e]. If a static ability generates a replacement effect that creates a delayed triggered ability, the object with the static ability is the source, and the controller of that object when the replacement effect was applied is the controller of the delayed triggered ability [603.7f]. If a static ability allows a player to take an action and creates a delayed triggered ability if they do, the object with the static ability is the source, and the controller of that object when the action was taken is the controller of the delayed triggered ability [603.7g]. A delayed triggered ability that refers to a particular object still affects it even if the object changes characteristics, but it won't affect the object if it's no longer in the zone it's expected to be in when the delayed triggered ability resolves [603.7c]. If a delayed triggered ability refers to X, and X was chosen for the cost of the spell or ability that created it, the value of X for the triggered ability is the same as the value chosen for the spell or ability [107.3n]. A resolving spell or ability may also create reflexive triggered abilities that follow the rules for delayed triggered abilities, but they are checked immediately after being created [603.12]. A delayed triggered ability is controlled by the player who controlled its source at the time it triggered [603.3a].

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
citations: ['113.6', '604.5', '113.6e', '610.5', '601.2a', '113.1c', '113.9']
text: Yes, non-permanent spells can have abilities. Abilities of an instant or sorcery spell usually function while that object is on the stack [113.6]. Some static abilities can apply while a spell is on the stack, such as those that modify how the spell can be played or cast [604.5, 113.6e]. Additionally, effects can cause spells to gain abilities as they are cast [610.5]. When a spell is cast, it is put on the stack [601.2a]. Activated and triggered abilities that are on the stack are objects and can be countered by effects that specifically counter abilities [113.1c, 113.9].

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
citations: ['702.61a', '113.4', '405.6c', '605.3a', '117.1d']
text: Yes, you can use a mana ability when a spell with split second is on the stack. Split second is a static ability that prevents players from casting other spells or activating abilities that aren't mana abilities while the spell with split second is on the stack [702.61a]. Mana abilities do not use the stack and resolve immediately [113.4, 405.6c]. Players may activate mana abilities whenever they have priority, or when casting a spell or activating an ability that requires a mana payment, or when a rule or effect asks for a mana payment, even in the middle of casting or resolving a spell or activating or resolving an ability [605.3a, 117.1d].

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
citations: ['608.1', '112.1', '701.6a']
text: When everyone passes priority, the spell or ability on top of the stack resolves [608.1]. In this scenario, Counterspell is on top of the stack, and it is an instant spell [112.1]. Counterspell targets Divination, which is also a spell on the stack [112.1]. When Counterspell resolves, it will counter Divination [701.6a]. To counter a spell means to cancel it, removing it from the stack so it does not resolve and none of its effects occur [701.6a]. Therefore, Divination will not resolve.

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
citations: ['702.2c', '702.19b', 'Lethal Damage']
text: When your Charging Rhino, which has trample, is blocked by a Vampire Nighthawk with deathtouch, you must assign lethal damage to the Vampire Nighthawk before assigning any excess damage to the player. Lethal damage is an amount of damage greater than or equal to a creature's toughness [Lethal Damage]. Since the Vampire Nighthawk has deathtouch, any amount of damage you assign to it is considered lethal damage [702.2c]. Therefore, you must assign at least 1 damage to the Vampire Nighthawk to satisfy the lethal damage requirement. Any damage beyond that 1 point can be assigned to the defending player [702.19b].

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
citations: ['Shardless Agent ruling #1', '702.108a', 'Monastery Swiftspear ruling #2']
text: When Shardless Agent is cast, its cascade ability triggers and resolves before Shardless Agent itself does [Shardless Agent ruling #1]. If the cascade ability results in a noncreature spell being cast, that spell is put onto the stack. Prowess triggers when you cast a noncreature spell [702.108a]. Therefore, the prowess ability triggers when the cascaded spell is cast. Prowess triggers go on the stack on top of the spell that caused them to trigger and resolve before that spell [Monastery Swiftspear ruling #2]. Thus, Monastery Swiftspear's prowess will trigger and resolve before the cascaded spell resolves.

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
citations: ['117.2d', '405.6f', '704.3', '704.5g', '120.6', '302.7', '120.5']
text: State-based actions are checked automatically whenever a player would receive priority, and they happen before a player receives priority [117.2d, 405.6f, 704.3]. Damage marked on a creature is checked to see if it's lethal during the state-based action check [704.5g]. If a creature has damage marked on it equal to or greater than its toughness, it is destroyed as a state-based action [120.6, 302.7, 704.5g]. Damage itself does not destroy a creature; rather, state-based actions do so as a result of the damage [120.5]. Since your Lightning Bolt has not yet resolved, it has not dealt damage, and therefore state-based actions would not yet destroy the Grizzly Bears based on the 2 damage already marked on it. State-based actions are checked after your Lightning Bolt resolves and deals its damage.

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
citations: ['500.6', '503.1a', '603.3b', '405.3']
text: Both your Phyrexian Arena's trigger and your opponent's beginning-of-upkeep trigger trigger at the beginning of your upkeep step [500.6]. They are put onto the stack the next time a player would receive priority [500.6]. Since you are the active player, you receive priority first at the beginning of your upkeep [503.1a]. When multiple triggered abilities have triggered since the last time a player received priority, each player, in APNAP order (Active Player, Non-Active Player), puts each triggered ability they control onto the stack in any order they choose [603.3b]. Therefore, you would put your Phyrexian Arena's trigger on the stack first, and then your opponent would put their trigger on the stack on top of yours [603.3b]. The choice of order for abilities controlled by the same player is made by that player [405.3].

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
citations: ['702.27a', '707.10', 'Fork ruling #9', 'Fork ruling #8']
text: When you cast a sorcery with buyback and pay its buyback cost, the spell is put into your hand instead of your graveyard as it resolves [702.27a]. When Fork copies that spell, the copy is put onto the stack [707.10]. The copy of the spell is not cast [Fork ruling #9]. If you copy a spell for which buyback has been paid, you get nothing back because the copied spell does not have a card to give you [Fork ruling #8]. Therefore, only the original sorcery spell will end up back in your hand.

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
citations: ['Mimic Vat ruling #6', 'Mimic Vat ruling #0']
text: No, you will not get a token. Mimic Vat can only create a token that is a copy of a card exiled with it [Mimic Vat ruling #6]. If the exiled card is a nonpermanent card, no token is created [Mimic Vat ruling #0]. Since Lightning Bolt is an instant card, it is a nonpermanent card, and therefore Mimic Vat cannot create a token that is a copy of it.

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
citations: ['Fiend Hunter ruling #1', 'Lithoform Engine ruling #4']
text: Yes, both creatures will return to the battlefield. When Fiend Hunter's enters-the-battlefield ability is copied by Lithoform Engine, both the original ability and the copy exile a creature. These abilities are linked, meaning that when Fiend Hunter leaves the battlefield, its second ability will return all cards exiled by its first ability and its copies. Therefore, both creatures that were exiled will be returned to the battlefield under their owner's control.

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
citations: ["Teferi's Protection ruling #21", '702.26d', '702.26c', "Teferi's Protection ruling #17"]
text: When Teferi's Protection causes your permanents to phase out, any "until this leaves the battlefield" effects that are waiting to resolve will not happen. This means that if Banishing Light phases out before its triggered ability resolves, the exiled creature will not return to the battlefield. Phasing out does not cause "leaves the battlefield" abilities to trigger, and effects that are waiting for a permanent to leave the battlefield will not resolve when that permanent phases out. The exiled creature will return when Banishing Light phases back in, as the "until Banishing Light leaves the battlefield" effect will then end. Phased-out permanents phase back in before you untap during your untap step.

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
citations: ['Emrakul, the Promised End ruling #2', '601.2i']
text: Your opponent can target Emrakul, the Promised End with Counterspell. Emrakul's "protection from instants" ability only applies while Emrakul is on the battlefield [Emrakul, the Promised End ruling #2]. Since Emrakul is on the stack when your opponent casts Counterspell, it can be targeted. If Counterspell successfully resolves and counters Emrakul, Emrakul will be put into its owner's graveyard and will not resolve. Therefore, its triggered ability that causes you to gain control of an opponent will not happen, and you will not control their next turn [601.2i].

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
citations: ['702.85a', '712.11c', '712.8c']
text: A cascade spell exiles cards until a nonland card with a mana value less than the cascade spell's mana value is exiled [702.85a]. When casting a double-faced spell, it is cast with its front face up by default [712.11c]. However, if an effect allows a player to cast a nonmodal double-faced card "transformed" or "converted," the resulting spell will have its back face up [712.8c]. The mana value of a double-faced spell is calculated using the mana cost of its front face [712.8c]. Therefore, even though Tibalt, Cosmic Impostor has a mana value of seven, Valki, God of Lies has a mana value of two. If your cascade spell has a mana value greater than two, and it exiles Valki, God of Lies, it is a legal cascade hit. However, you can only cast the Tibalt side for free if its mana value is less than the cascade spell's mana value [702.85a]. Since the mana value of Valki, God of Lies is used for this determination, you can only cast it for free if the cascade spell's mana value is greater than two.

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
citations: ['702.144a', 'Lithoform Engine ruling #3', 'Lithoform Engine ruling #6', '707.12', '111.13', '707.10', 'Emrakul, the Promised End ruling #14']
text: You will control one of your opponent's turns, and you will get a second Emrakul, the Promised End. Copying the Emrakul spell with Lithoform Engine does not give you another control-a-turn trigger because the trigger is part of the spell's casting, not the spell itself. When you cast Emrakul, the Promised End, its triggered ability goes on the stack [702.144a]. Lithoform Engine's ability targets an activated or triggered ability on the stack and creates another instance of that ability on the stack [Lithoform Engine ruling #3]. This means you will have two instances of Emrakul's "When you cast this spell" trigger on the stack. Lithoform Engine's ability to copy a permanent spell creates a copy of the spell on the stack [Lithoform Engine ruling #6]. This copy is then cast [707.12]. A copy of a permanent spell becomes a token as it resolves [111.13]. Therefore, you will have two Emrakul, the Promised End spells on the stack, one original and one copy that becomes a token. The original Emrakul's trigger will resolve, giving you control of an opponent's next turn and then that player an extra turn [Emrakul, the Promised End ruling #14]. The copy of Emrakul, the Promised End, when it resolves, will become a token and will not have a "When you cast this spell" trigger, as that trigger is associated with casting the spell, not with the spell resolving or a copy of the spell being created [707.10].

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
citations: ['707.10', 'Lithoform Engine ruling #3', 'Mimic Vat ruling #6']
text: Yes, you will get two tokens. When you activate Mimic Vat's ability, you are creating a token that is a copy of a card exiled with Mimic Vat. This ability is put onto the stack [707.10]. Lithoform Engine's ability targets an activated ability on the stack and creates another instance of that ability on the stack [Lithoform Engine ruling #3]. This means you will have two separate abilities on the stack, each instructing you to create a token copy of a card exiled with Mimic Vat. When each of these abilities resolves, it will create a token that is a copy of a card exiled with Mimic Vat [707.10]. If no card has been exiled with Mimic Vat by the time an ability resolves, no token will be created [Mimic Vat ruling #6].

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
citations: ['Trinisphere ruling #0', '601.2f', '118.7', '118.7c', '107.3b']
text: To determine the total cost of casting Awaken the Woods with X=0, you first start with its mana cost, which is {X}{G}{G}. Since X=0, this is {0}{G}{G}. Then, you apply cost reductions. Your permanent makes green spells cost {1} less, so the {G} becomes {0}. The cost is now {0}{0}{0}. Finally, Trinisphere's effect is applied because the mana component of the spell's cost is less than three mana. Trinisphere increases the cost to three mana. Therefore, the total cost to cast Awaken the Woods with X=0 is {3}. You will get zero 1/1 green Forest Dryad land creature tokens because you cast it with X=0. To get any tokens, you should choose a value for X that is greater than 0. The rules do not specify what value of X you *should* choose, only how to calculate the cost for a chosen value of X.

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
citations: ['Animate Dead', 'Grist, the Hunger Tide ruling #1']
text: Yes, you can return Grist, the Hunger Tide from your graveyard to the battlefield with Animate Dead. When Animate Dead enters the battlefield, it will cause Grist, the Hunger Tide to return to the battlefield under your control, and Animate Dead will attach to it. Grist, the Hunger Tide will enter the battlefield as a creature, as per its ability that states it is a creature in addition to its other types while not on the battlefield [Grist, the Hunger Tide ruling #1]. Animate Dead will then cause the enchanted creature to get -1/-0 [Animate Dead]. If Grist, the Hunger Tide would leave the battlefield, its controller sacrifices it due to Animate Dead's effect.

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
citations: ['Skullbriar, the Walking Grave ruling #1', 'Doubling Season ruling #2', 'Doubling Season ruling #0']
text: Skullbriar, the Walking Grave retains its counters when it moves to the command zone, as long as it is not moved to your hand or library first [Skullbriar, the Walking Grave ruling #1]. When Skullbriar is recast and enters the battlefield, Doubling Season will double the number of counters it receives, as it affects permanents that enter with counters [Doubling Season ruling #2]. However, the counters Skullbriar already has on it do not get doubled by Doubling Season upon re-entering the battlefield; Doubling Season only affects counters that are put onto a permanent as it enters the battlefield [Doubling Season ruling #0].

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
citations: ['Final Fortune ruling #0', 'Sundial of the Infinite ruling #1', 'Final Fortune ruling #1', 'Sundial of the Infinite ruling #4']
text: When you cast Final Fortune, you take an extra turn after the current one. At the beginning of that extra turn's end step, you lose the game [Final Fortune ruling #0]. However, if you use the Sundial of the Infinite's ability to end the turn before the end step, the end step is skipped [Sundial of the Infinite ruling #1]. Since the end step is skipped, the triggered ability that causes you to lose the game does not trigger, and you do not lose the game [Final Fortune ruling #1]. Ending the turn via the Sundial of the Infinite exiles all spells and abilities on the stack, removes creatures from combat, checks state-based actions, and then skips to the cleanup step [Sundial of the Infinite ruling #4]. Triggered abilities that would have triggered at the beginning of the end step will trigger at the beginning of the end step of the next turn instead [Sundial of the Infinite ruling #1].

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
citations: ['Clone ruling #0', 'Clone ruling #2', 'Clone ruling #5']
text: When you cast Clone, you choose what it copies as part of the process of it entering the battlefield. This choice is made when Clone is on the stack, but it doesn't become a copy until it enters the battlefield. Your opponent can respond to the spell being cast, but they cannot respond to the choice of what Clone will copy because that choice is made as it enters the battlefield, not as it is cast. Clone's ability does not target the creature it copies [Clone ruling #0]. If Clone enters the battlefield at the same time as another creature, you cannot choose that creature as the copy target, as you can only choose a creature already on the battlefield [Clone ruling #2]. You also have the option to not copy any creature, in which case Clone enters as a 0/0 creature and is likely put into the graveyard immediately [Clone ruling #5].

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
citations: ['Flooded Strand', 'Gogo, Master of Mimicry ruling #6', '701.23h', '701.23f']
text: When you activate Flooded Strand's ability, you search your library for a Plains or Island card, put it onto the battlefield, and then shuffle your library. Gogo, Master of Mimicry's ability copies an activated or triggered ability that is on the stack [Gogo, Master of Mimicry ruling #6]. In this case, Gogo copies the Flooded Strand's search ability twice. Each copy of the ability will instruct you to search your library for a Plains or Island card, put it onto the battlefield, and then shuffle your library [Flooded Strand]. Because the search instruction is being performed multiple times, rule [701.23h] states that this is the same as a single instruction to search that library for all those cards, and you search the library only once. However, the rule also states that any other instructions that refer to searching the zone still apply [701.23f]. Therefore, you will get one land from the initial activation, and then two additional lands from the two copies of the ability, for a total of three lands. Each of these searches will result in a shuffle of your library [Flooded Strand].

---

## Output instructions

Grade all 50 cells above per the rubric. For EACH cell, write exactly one JSON line to:

    evals/opus_grader_v2_out/gemini-flash-lite.jsonl

Each line is a single JSON object with EXACTLY these fields and nothing else:

    {"id": "<cell id, e.g. q007 or c012>", "arm": "gemini-flash-lite", "verdict": "correct"|"partial"|"wrong", "reason": "<one-line reason>"}

Every one of the 50 cells above must be accounted for -- one line per cell, any order, no duplicates, no extra fields, no commentary outside the JSONL lines. If a cell is genuinely ungradeable, still write a line with your best-effort verdict and say why in the reason -- never silently drop a cell.