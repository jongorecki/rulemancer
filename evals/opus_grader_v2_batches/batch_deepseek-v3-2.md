# Opus-Grader Calibration v2 -- Batch: deepseek-v3-2

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
text: No, creatures phasing back in do not trigger "enters the battlefield" abilities.

Phasing is a status change, not a zone change. Rule 702.26d states that the phasing event does not cause a permanent to change zones, and zone-change triggers (which include enters-the-battlefield triggers) do not trigger when a permanent phases in or out. Rule 603.6a defines enters-the-battlefield triggers as a type of zone-change trigger, which only trigger when a permanent enters the battlefield from another zone. Since a phased-out permanent is still on the battlefield (just treated as though it does not exist), phasing in does not constitute entering the battlefield.

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
text: Trample and deathtouch work together by modifying the definition of 'lethal damage' when assigning combat damage. Deathtouch means any nonzero amount of combat damage assigned to a creature by a source with deathtouch is considered lethal damage for the purposes of determining if excess damage is being dealt [702.2c]. Trample allows the controller of an attacking creature to assign excess damage to the defending player, planeswalker, or battle after assigning lethal damage to all blocking creatures [702.19b]. Therefore, when a creature with both trample and deathtouch is blocked, its controller only needs to assign 1 damage to each blocking creature to satisfy the lethal damage requirement, because that 1 damage from a deathtouch source is lethal. All remaining damage from that creature can then be assigned as trample damage to the defending player, planeswalker, or battle. This is further supported by rule 120.4a, which states any amount of damage greater than 1 is excess damage if the source dealing that damage to a creature has deathtouch [120.4a].

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
citations: ['702.40a', '113.9']
text: Yes, Storm is a triggered ability that can be countered. Storm is defined as a triggered ability that functions on the stack [702.40a]. Triggered abilities on the stack are not spells, but they are objects on the stack that can be countered by effects that specifically counter abilities [113.9]. Therefore, while Storm cannot be countered by effects that counter only spells, it can be countered by effects that counter abilities.

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
citations: ['903.5c', '903.4', '202.2d', '107.4e']
text: No, you cannot use cards with hybrid mana symbols in a Commander deck if your commander's color identity does not include all colors of those symbols. The rules for Commander deck construction state that a card can be included only if every color in its color identity is also found in the color identity of the deck's commander [903.5c]. A card's color identity is determined by the colors of any mana symbols in its mana cost or rules text [903.4]. A hybrid mana symbol, such as {R/G} or {W/U}, is considered to be all of its component colors [107.4e]. Therefore, an object with a hybrid mana symbol in its mana cost is the color of all those component colors [202.2d]. For example, a card with a {W/U} hybrid symbol in its mana cost has a color identity of both white and blue. To include it in your Commander deck, your commander's color identity must include both white and blue. If your commander's color identity is only white (or only blue), you cannot include that card.

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
citations: ['502.4', '117.3a']
text: No, you cannot respond to the untap step. The untap step is a step in which no player receives priority [502.4]. This means that no spells can be cast, no abilities can be activated, and no player (including the active player) can take any actions that require priority during this step [117.3a]. Any abilities that trigger during the untap step are held until the next time a player would receive priority, which is usually during the following upkeep step [502.4].

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
citations: ['511.3', 'Attacking Creature', '508.1k', '508.4', '508.4b', '508.4d']
text: Yes, creatures are still considered attacking creatures during the end of combat step. An 'attacking creature' is defined as a creature that has been declared as an attacker or put onto the battlefield attacking, and it remains an attacking creature until it is removed from combat or the combat phase ends, whichever comes first [Attacking Creature]. The combat phase ends after the end of combat step concludes [511.3]. Therefore, creatures are not removed from combat until the end of the end of combat step. Rules about creatures put onto the battlefield attacking also state they remain attacking creatures until removed from combat or the combat phase ends [508.4, 508.4b, 508.4d], reinforcing that the status lasts for the entire combat phase, which includes the end of combat step. The rule for declaring attackers also states a creature remains attacking until removed from combat or the combat phase ends [508.1k]. Since the combat phase ends after the end of combat step, creatures are attacking throughout that step.

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
citations: ['305.1', '505.6b', '701.18a', 'Play', '116.2a', '305.9', '300.2a', '601.1a', '701.18b', '202.1b']
text: No, you do not cast lands. You play lands. Playing a land is a special action that does not use the stack and is not casting a spell.

Key definitions:
- To "play a land" means to put a land card from your hand onto the battlefield as a special action [Play, 701.18a]. This action does not use the stack, is not a spell, and cannot be responded to [305.1, 505.6b].
- To "cast" means to cast a card as a spell, which uses the stack [302.1].
- Lands are not spells and have no mana cost [202.1b]. An object that is both a land and another card type (like an artifact land) can only be played as a land; it cannot be cast as a spell [305.9, 300.2a].
- The term "play a card" encompasses both playing a land and casting a spell, depending on the card type [601.1a, 701.18b]. For a land card, "playing" it means using the special action to put it onto the battlefield, not casting it.

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
citations: ['702.74a', '603.3d', '113.7a', '118.10']
text: No, you cannot sacrifice an evoked creature before its own evoke triggered ability resolves, because you do not have priority to take actions while that ability is resolving. The evoke ability is a triggered ability that goes on the stack when the creature enters the battlefield. According to rule 702.74a, the evoke ability triggers and is put on the stack. Rule 603.3d states that once a triggered ability is on the stack, it remains there until it resolves, is countered, or is removed. Players only get priority to take actions (like activating abilities or casting spells) after a spell or ability finishes resolving and before the next one begins. While the evoke triggered ability is resolving, no player gets priority, so you cannot interrupt it to sacrifice the creature. Furthermore, rule 118.10 clarifies that you cannot use a single sacrifice to pay for multiple costs or effects. The sacrifice from the evoke ability is part of the resolution of that specific triggered ability, not a cost you can pay separately at an earlier time. Even if the creature leaves the battlefield before the trigger resolves, rule 113.7a indicates the ability will use the creature's last known information, but the sacrifice is still performed by the resolving trigger, not by a separate action you take.

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
citations: ['[113.10]', '[702.1]', '[113.10b]']
text: Yes, if a card loses all abilities, that includes keyword abilities.

According to the rules, an 'ability' is anything an object describes that it does or that affects how it works, including those summarized by a keyword [702.1]. An effect that removes an ability states that the object 'loses' that ability [113.10]. An effect that causes an object to 'lose all abilities' is an effect that removes abilities [113.10b]. Therefore, such an effect removes every ability the object has, including those represented by keywords.

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
citations: ['402.2', '514.1', '703.4n']
text: Yes, you can draw cards even if you are already at or above your maximum hand size. Your maximum hand size only matters during your cleanup step, when you must discard down to that number as a turn-based action [514.1, 703.4n]. At any other time, you can have any number of cards in your hand [402.2]. Therefore, effects that cause you to draw cards will function normally, and you will simply add those cards to your hand. You will only need to discard the excess cards when your cleanup step begins.

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
citations: ['306.9', '122.1e', '704.5i']
text: When a planeswalker has 0 loyalty counters, it is put into its owner's graveyard. This is a state-based action, meaning it is checked whenever a player would get priority. The rules define loyalty as the number of loyalty counters on the planeswalker [306.5c]. Therefore, having 0 or less loyalty counters means the planeswalker has 0 loyalty. According to the rules, if a planeswalker has loyalty 0, it is put into its owner's graveyard [306.9, 704.5i]. A planeswalker with 0 loyalty is put into its owner's graveyard as a state-based action [122.1e]. There is no separate rule for 'less than 0' loyalty; a planeswalker with 0 loyalty is already put into the graveyard, so it cannot exist with a negative number of loyalty counters.

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
text: No, non-creature artifacts do not die. The term 'dies' is specifically defined in the rules. According to rule 700.4, 'dies' means 'is put into a graveyard from the battlefield.' However, this term is only used for creatures and planeswalkers. The definition provided in the context states: 'A creature or planeswalker "dies" if it is put into a graveyard from the battlefield.' Since a non-creature artifact is neither a creature nor a planeswalker, it is not described as dying when it moves from the battlefield to the graveyard. It is simply put into the graveyard.

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
citations: ['121.4', '704.5b']
text: If you attempt to draw a card from an empty library, you lose the game the next time a player would receive priority. This is a state-based action. Specifically, rule 121.4 states: 'A player who attempts to draw a card from a library with no cards in it loses the game the next time a player would receive priority.' Rule 704.5b confirms this as a state-based action: 'If a player attempted to draw a card from a library with no cards in it since the last time state-based actions were checked, that player loses the game.' This means the loss is not immediate; it happens the next time the game checks state-based actions, which occurs whenever a player would get priority.

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
citations: ['506.1', '117.3a', '511.1', '507.1', '510.1', '510.2']
text: The combat phase has five steps in order: beginning of combat, declare attackers, declare blockers, combat damage, and end of combat [506.1]. The declare blockers and combat damage steps are skipped if no creatures are declared as attackers [506.1].

As the defending player, you receive priority during most of these steps. The active player (the attacking player) receives priority first at the beginning of most steps, after any turn-based actions and triggered abilities are handled [117.3a]. For example, in the beginning of combat step, if it's a multiplayer game where opponents don't all automatically become defending players, the active player first chooses a defending player as a turn-based action [507.1]. After that, the active player gets priority [117.3a]. Once the active player passes priority, you, as the defending player, will receive priority. This pattern repeats in the declare attackers, declare blockers, and end of combat steps [117.3a, 511.1].

There is an exception during the combat damage step. The step begins with a turn-based action where players announce how their creatures assign combat damage [510.1]. Then, all assigned combat damage is dealt simultaneously as another turn-based action [510.2]. No player, including the defending player, receives priority between the assignment and the dealing of combat damage [510.2]. After the damage is dealt, the active player will receive priority at the start of the next step (the end of combat step) [117.3a].

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
text: No, you cannot respond to a mana ability. A mana ability is an activated or triggered ability that could create mana and does not use the stack. According to the rules, an activated mana ability resolves immediately after it is activated and does not go on the stack, so it cannot be targeted, countered, or otherwise responded to [605.3b]. Mana abilities follow special rules: they do not use the stack, and a player can activate them even without priority under certain circumstances [113.4]. Furthermore, mana abilities resolve immediately; if a player had priority before a mana ability was activated, that player gets priority after it resolves [405.6c]. Because the ability resolves immediately and never uses the stack, there is no opportunity for any player to respond to it.

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
citations: ['118.2', '601.2g', '601.2h', '118.1', '118.10', '602.4', '608.2g']
text: No, you cannot respond to a cost being paid. Paying a cost is part of the action of casting a spell, activating an ability, or declaring attackers/blockers, and does not use the stack. Players do not receive priority to cast spells or activate abilities while a cost is being paid.

Here's why, based on the provided rules:
- A cost is an action or payment necessary to take another action [118.1].
- Paying a cost is a step performed as part of a larger action. For example, to cast a spell, a player follows steps in order, including determining and paying costs [601.2g]. The payment step [601.2h] is performed without interruption.
- Rule 118.2 states that if a cost includes a mana payment, the player paying the cost has a chance to activate mana abilities. This opportunity is part of the cost payment process, not a separate action that others can respond to.
- Similarly, for declaring attackers or blockers, if costs require mana, the player has a chance to activate mana abilities as part of the declaration process [508.1i, 509.1e], which is a turn-based action that doesn't use the stack.
- Once a player begins paying costs, they must pay all costs in any order, and partial payments are not allowed [601.2h, 508.1j, 509.1f]. This process is atomic; you cannot interrupt it.
- Furthermore, rule 118.10 clarifies that each payment of a cost applies to only one spell, ability, or effect, and the resolution of one effect does not pay another's cost. This reinforces that cost payment is a discrete part of an action, not a separate event on the stack.
- Abilities that alter costs do not affect spells and abilities already on the stack [602.4], which implies cost determination and payment happen before the object is fully on the stack and available for responses.
- During the resolution of a spell or ability, no player receives priority, and normally no other spells can be cast or abilities activated [608.2g]. While this rule specifically addresses resolution, it illustrates the principle that certain game actions are not interruptible.

Therefore, you cannot respond to the act of paying a cost itself. You can respond to the spell or ability after its costs are paid and it is put on the stack, or to the declaration of attackers/blockers after the declaration (including any cost payments) is complete, but not to the individual payment step.

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
citations: ['613.1', '613.1a', '613.1c', '613.1d', '613.1e', '613.1f', '613.2a', '613.2c', '613.3', '613.4a', '613.5', '613.6', '613.8', '613.8a', 'Layer']
text: The layer system is a set of rules that determines the order in which continuous effects are applied to an object's characteristics. Continuous effects are applied in a specific series of layers, and within some layers, there are sublayers. The system ensures that effects that change characteristics like type, color, or power and toughness are applied in a consistent order, so the final state of an object is predictable.

First, you start with the object's actual characteristics. For a card, this is what's printed on it. For a token or copy, it's what the effect that created it defined. Then, all applicable continuous effects are applied in this order:
1.  **Layer 1:** Rules and effects that modify copiable values are applied. This includes copy effects and 'as ... enters' abilities that set power and toughness. Within this layer, there are sublayers, with copiable effects applied first in sublayer 1a. After all effects in layer 1 are applied, the object's characteristics become its copiable values.
2.  **Layer 2:** Control-changing effects are applied.
3.  **Layer 3:** Text-changing effects are applied.
4.  **Layer 4:** Type-changing effects are applied (changing card type, subtype, or supertype).
5.  **Layer 5:** Color-changing effects are applied.
6.  **Layer 6:** Ability-adding effects, keyword counters, ability-removing effects, and effects that say an object can't have an ability are applied.
7.  **Layer 7:** Power- and toughness-changing effects are applied. This layer has its own sublayers:
    *   **Layer 7a:** Effects from characteristic-defining abilities that define power and/or toughness are applied first.
    *   **Layer 7b:** Effects that set power and/or toughness to a specific number or value are applied.
    *   **Layer 7c:** Effects that modify power and/or toughness (but don't set them) are applied.

Within layers 2 through 6, effects from characteristic-defining abilities are applied first, then all other effects in timestamp order. Within a layer or sublayer, the order of effect application is usually determined by timestamps (when the effect started), but a dependency system can override this. An effect depends on another if applying the other effect would change what the first effect applies to or what it does.

If a single effect has parts that apply in different layers, each part applies in its appropriate layer. For example, an effect that makes a land a 3/3 creature applies its type-changing part in layer 4 and its power/toughness-setting part in layer 7b. The game performs this layer application automatically and continually; all changes are instantaneous.

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
citations: ['Legend Rule', '704.5j', '205.4d']
text: The legend rule is a state-based action. It works as follows: whenever state-based actions are checked, if a player controls two or more legendary permanents with the same name, that player chooses one of those permanents. All the other legendary permanents with that same name that they control are put into their owners' graveyards. This rule applies to any permanent with the legendary supertype, including creatures, artifacts, enchantments, and planeswalkers (as older planeswalker cards have been given the legendary supertype). The rule does not use the stack and is performed automatically before any player would receive priority.

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
citations: ['704.5g', '117.5', '704.3', '120.6', '302.7']
text: Your creature is destroyed by a state-based action. State-based actions are checked automatically and repeatedly whenever a player would get priority, and also during the cleanup step. Specifically, the rule [704.5g] states that if a creature has toughness greater than 0, has damage marked on it, and the total damage marked on it is greater than or equal to its toughness, that creature is destroyed. This check happens immediately before a player would get priority [117.5, 704.3]. For example, after a spell like Lightning Bolt deals damage to your creature, the game checks state-based actions before any player gets a chance to cast spells or activate abilities in response. The damage remains marked on the creature until it is destroyed, regenerates, or the cleanup step occurs [120.6, 302.7]. Therefore, your creature dies the very next time state-based actions are checked after it has been marked with lethal damage.

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
citations: ['[903.3d]', '[903.9a]', '[903.9b]', '[406.3b]', '[601.3f]']
text: Yes, you can cast your commander from exile, but only if an effect specifically allows you to cast spells from exile. A commander is a card that retains its commander designation in all zones, including exile [903.3d]. There are two main ways a commander can be in exile: 1) It can be put into exile, and then its owner may choose to move it to the command zone as a state-based action [903.9a]. 2) It can be put into exile and remain there, for example, if its owner chooses not to move it to the command zone. However, simply being a commander in exile does not grant you permission to cast it from there. You can only cast a spell from exile if a rule or effect allows you to do so [601.3f]. For example, some cards have abilities that let you cast other cards from exile. If such an effect allows you to cast your commander and you can look at it (if it's face down), you may cast it [406.3b]. Note that if an effect would put your commander into your hand or library from anywhere, you may choose to put it into the command zone instead [903.9b], but this replacement effect does not apply to putting it into exile.

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
citations: ['514.2', '514.3a', '703.4p', '500.3', 'Cleanup Step']
text: The cleanup step is the second and final step of the ending phase [Cleanup Step]. During this step, the following happens:

1. First, the active player discards down to their maximum hand size if necessary. This is a turn-based action [703.4p].
2. Second, the following actions happen simultaneously: all damage marked on permanents is removed, and all "until end of turn" and "this turn" effects end. This is also a turn-based action and does not use the stack [514.2, 703.4p].

Normally, no player receives priority during the cleanup step, so no spells can be cast and no abilities can be activated, and the step ends once these actions are completed [500.3, 514.3a].

However, an exception occurs if, after performing these actions, the game checks and finds that any state-based actions would be performed or any triggered abilities are waiting to be put onto the stack (including those that trigger "at the beginning of the next cleanup step"). If so, those state-based actions are performed, then those triggered abilities are put on the stack, then the active player gets priority. Players may then cast spells and activate abilities. Once the stack is empty and all players pass in succession, another cleanup step begins [514.3a].

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
citations: ['704.3', '117.5', '514.3a', '703.3', '724.2c', '724.1c']
text: State-based actions are checked automatically by the game rules at specific moments. The primary rule is that they are checked whenever a player would get priority [704.3, 117.5]. This means before any player can cast a spell or activate an ability, the game performs all applicable state-based actions, repeats the check until none are performed, and then puts triggered abilities on the stack. This process repeats until no state-based actions are performed and no abilities are waiting to trigger, and only then does a player get priority.

There are also special times when state-based actions are checked:
- During the cleanup step, the game checks for state-based actions at the beginning of the step. If any are performed or if triggered abilities are waiting, the active player gets priority and the step repeats [514.3a].
- Whenever a step or phase begins, any turn-based actions for that step or phase are dealt with first, and then state-based actions are checked [703.3].
- When an effect ends the combat phase (like Mandate of Peace) or ends the turn, the process includes checking state-based actions, but no player gets priority and no triggered abilities are put on the stack afterward [724.2c, 724.1c].

In summary, state-based actions are checked: 1) whenever a player would get priority (which is the most common case), 2) at the start of the cleanup step, 3) after turn-based actions at the beginning of a step or phase, and 4) as part of the process when an effect ends the combat phase or the turn.

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
citations: ['104.3a', '405.6g', '101.1', '723.6']
text: You can concede the game at any time. This is a fundamental rule of the game that cannot be overridden by any card effect. Specifically, rule 104.3a states a player can concede at any time, and rule 405.6g confirms conceding is an action that does not use the stack. Rule 101.1 explicitly notes that the only exception to a card's text overriding the rules is that a player can concede at any time. Furthermore, rule 723.6 clarifies that even if another player controls you, you may still concede. Therefore, there is no restriction on the timing of a concession.

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
citations: ['102.1', 'Active Player']
text: The active player is the player whose turn it is. This is a fundamental definition of the game state. In a standard game, only one player is the active player at any given time. The rules define this directly: 'The active player is the player whose turn it is' [102.1]. The glossary entry for 'Active Player' confirms this same definition [Active Player]. Therefore, to know who the active player is, you simply identify which player is currently taking their turn.

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
citations: ['117.3b']
text: After a spell cast by a player other than the active player resolves, the active player gets priority first. This is because rule 117.3b states that the active player receives priority after a spell or ability (other than a mana ability) resolves, regardless of who cast it. Therefore, the sequence is: the non-active player's spell resolves, then the active player gets priority.

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
text: When the active player casts a spell, the active player gets priority first afterward. This is because rule 117.3c states that if a player has priority when they cast a spell, that player receives priority afterward. Since the active player must have priority to cast the spell, they will be the first to receive priority again after the spell is cast.

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
citations: ['117.3c', '601.2i']
text: Yes, you can hold priority to cast more spells after you've cast one or more spells. According to rule 117.3c, when a player has priority and they cast a spell, that player receives priority again afterward. This means that after you finish casting a spell, you retain priority and can immediately cast another spell or activate an ability before passing priority to your opponents. Rule 601.2i confirms this, stating that after a spell becomes cast, if the spell's controller had priority before casting it, they get priority. Therefore, you can 'hold priority' to take another action, such as casting another spell, without giving your opponents a chance to respond in between.

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
citations: ['714.3a', '714.3b', '702.155b', '505.4', '703.4f', '714.3c']
text: Lore counters are put on Sagas in two specific ways.

First, when a Saga enters the battlefield, it enters with lore counters on it. This is a replacement effect that happens as it enters.
- A Saga without the read ahead keyword enters with exactly one lore counter on it [714.3a].
- A Saga with the read ahead keyword enters with a number of lore counters chosen by its controller. The chosen number must be between one and the Saga's final chapter number (the highest Roman numeral in its chapter symbols) [714.3b, 702.155b].

Second, during each of the active player's turns, lore counters are added as a turn-based action. Immediately after that player's precombat main phase begins, that player puts a lore counter on each Saga they control that has one or more chapter abilities [505.4, 703.4f, 714.3c]. This action does not use the stack.

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
citations: ['Delayed Triggered Ability', '603.7', '603.7a', '610.2']
text: A delayed triggered ability is an ability created during the resolution of a spell or ability, or when a replacement effect is applied, that is set to do something at a later time rather than immediately. It is a type of triggered ability that contains a triggering condition using the words "when," "whenever," or "at," but these words typically do not begin the ability's text. For example, an effect might say "When this creature leaves the battlefield" or "At the beginning of the next end step." Delayed triggered abilities are created as one-shot effects and wait for their specified trigger event to occur later in the game.

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
citations: ['113.6', '113.3a']
text: Yes, non-permanent spells (instant and sorcery spells) can have abilities. According to rule 113.6, abilities of an instant or sorcery spell usually function only while that object is on the stack. This means these spells can possess abilities that are active while they are spells on the stack. Furthermore, rule 113.3a defines spell abilities as abilities that are followed as instructions while an instant or sorcery spell is resolving, and it states that any text on an instant or sorcery spell is a spell ability unless it is an activated ability, a triggered ability, or a specific type of static ability. Therefore, the text of an instant or sorcery card constitutes abilities that the spell has.

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
citations: ['702.61a', '702.61b', '605.3a', '117.1d']
text: Yes, you can activate mana abilities while a spell with split second is on the stack.

Split second is a static ability that functions while the spell is on the stack. Rule 702.61a states that as long as a spell with split second is on the stack, players can't cast other spells or activate abilities that aren't mana abilities. This explicitly allows the activation of mana abilities.

Rule 702.61b further clarifies that players may activate mana abilities while a spell with split second is on the stack.

Mana abilities are a special category of abilities that follow different rules. According to rules 605.3a and 117.1d, a player may activate a mana ability whenever they have priority, whenever they are casting a spell or activating an ability that requires a mana payment, or whenever a rule or effect asks for a mana payment, even in the middle of casting or resolving a spell or ability. This permission is not overridden by split second.

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
citations: ['117.7', '608.1', '701.6a']
text: When everyone passes priority, the object on top of the stack resolves first. In this scenario, Counterspell is on top of the stack targeting Divination [117.7]. Therefore, Counterspell resolves first. When Counterspell resolves, it counters its target spell, which is Divination [701.6a]. Countering a spell cancels it, removing it from the stack. The countered spell does not resolve, and none of its effects occur. The Divination is put into its owner's graveyard [701.6a]. Since Divination is countered and removed from the stack, it never gets a chance to resolve.

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
citations: ['702.2c', '702.19b', '120.4a']
text: You must assign at least 1 damage to the Vampire Nighthawk before you can assign the rest to the defending player. This is because your Charging Rhino has trample, and the blocker has deathtouch.

Here's why: Trample requires you to assign lethal damage to all blocking creatures before you can assign any damage to the player or planeswalker being attacked [702.19b]. When checking for lethal damage, you consider damage already marked on the creature and damage being assigned at the same time, but not effects that change the damage dealt [702.19b].

Deathtouch means any nonzero amount of combat damage assigned to a creature by a source with deathtouch is considered lethal damage [702.2c]. Furthermore, rule 120.4a explicitly states that any amount of damage greater than 1 is excess damage if the source dealing that damage to a creature has deathtouch, which confirms that 1 damage from a deathtouch source is lethal.

Therefore, since Vampire Nighthawk has deathtouch, assigning 1 damage from it to your Charging Rhino is considered lethal damage to your Rhino for the purpose of the trample calculation. This means you only need to assign 1 damage from your Charging Rhino to the Vampire Nighthawk to satisfy the 'lethal damage' requirement for trample. After assigning that 1 damage, you may assign the remaining 3 damage (since Charging Rhino is a 4/4) to the defending player.

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
citations: ['702.108a', '601.2i', '608.2g', 'Shardless Agent ruling #1', 'Monastery Swiftspear ruling #2']
text: Monastery Swiftspear's prowess triggers when you cast the noncreature spell via cascade, and that prowess trigger resolves before the cascaded spell does.

Here is the sequence:
1. You cast Shardless Agent. Its cascade ability triggers when it becomes cast [601.2i].
2. The cascade ability goes on the stack above the Shardless Agent spell. It will resolve before Shardless Agent [Shardless Agent ruling #1].
3. While resolving the cascade ability, you exile cards and may cast a nonland card with lesser mana value without paying its mana cost [702.85a]. Casting a spell during resolution follows the normal steps, but no player gets priority after it's cast [608.2g].
4. When you cast that spell (if it's a noncreature spell), Monastery Swiftspear's prowess triggers immediately, because the spell becomes cast [601.2i]. The prowess ability is a triggered ability that means "Whenever you cast a noncreature spell, this creature gets +1/+1 until end of turn." [702.108a].
5. The prowess trigger is put onto the stack on top of the spell that caused it [Monastery Swiftspear ruling #2]. Since the cascaded spell is currently on the stack and no player gets priority during resolution [608.2g], the prowess trigger goes on the stack above it.
6. After the cascade ability finishes resolving, the game checks for and puts any triggered abilities (like the prowess trigger) onto the stack. The prowess trigger is now the topmost object on the stack.
7. The prowess trigger resolves, giving Monastery Swiftspear +1/+1.
8. Then, the cascaded noncreature spell resolves.

Therefore, the prowess trigger from casting the cascaded spell resolves before that cascaded spell resolves.

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
citations: ['120.5', '704.3', '117.2d', '405.6f']
text: No, state-based actions do not destroy the Grizzly Bears before your Lightning Bolt resolves. State-based actions are not checked during the resolution of a spell or ability. They are checked only when a player would get priority, which happens after a spell or ability finishes resolving [704.3].

Here's the sequence: You cast Lightning Bolt targeting the Grizzly Bears. While Lightning Bolt is resolving, it deals 3 damage to the Bears. At this moment, the Bears would have a total of 5 damage marked on it (the existing 2 plus the new 3), which is greater than its toughness of 2. However, state-based actions are not checked during resolution [120.5, 704.3]. After Lightning Bolt finishes resolving completely, the game checks state-based actions. At that check, it sees a creature (the Grizzly Bears) with toughness greater than 0 and damage marked on it greater than or equal to its toughness. Therefore, the Grizzly Bears is destroyed as a state-based action [704.5g].

State-based actions happen automatically before a player gets priority, but they do not use the stack and cannot interrupt a spell that is currently resolving [117.2d, 405.6f].

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
citations: ['500.6', '503.1a', '603.3b']
text: Both Phyrexian Arena's ability and your opponent's beginning-of-upkeep ability trigger at the same time: when the upkeep step begins [500.6]. The abilities are put onto the stack the next time a player would receive priority, which is right after the upkeep step begins, before the active player (you) gets priority [503.1a]. The order they are placed on the stack is determined by the active player, nonactive player (APNAP) order rule for triggered abilities [603.3b]. Since you are the active player, you put all triggered abilities you control (your Phyrexian Arena trigger) on the stack in any order you choose first. Then your opponent, as the nonactive player, puts all triggered abilities they control (their own beginning-of-upkeep trigger) on the stack in any order they choose. Therefore, you choose the order for your triggers among themselves, and your opponent chooses the order for their triggers among themselves, but the active player's triggers are placed on the stack first (lower), followed by the nonactive player's triggers (higher).

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
citations: ['702.27a', '707.10', 'Fork ruling #8']
text: You will get zero copies of the card back in your hand. The original sorcery spell with buyback will return to your hand as it resolves because you paid its buyback cost. However, the copy created by Fork will not return a card to your hand.

Here's why: Buyback is a keyword ability that appears on instants and sorceries. It represents two static abilities that function while the spell is on the stack. The second ability states: "If the buyback cost was paid, put this spell into its owner’s hand instead of into that player’s graveyard as it resolves." [702.27a]. When you cast the original sorcery and pay its buyback cost, this ability applies to that spell, so when it resolves, it goes to your hand instead of your graveyard.

When Fork copies a spell, the copy is a new spell on the stack. A copy of a spell copies all decisions made for the original, including whether additional costs like buyback were paid [707.10]. Therefore, the copy 'knows' the buyback cost was paid. However, the copy is a spell that has no physical card associated with it [707.10]. The specific ruling for Fork directly addresses this interaction: "If you copy a spell for which Buyback has been paid, you get nothing back since the copied spell does not have a card to give you." [Fork ruling #8]. This means the copy's buyback ability tries to put the spell into its owner's hand, but since the copy is not a card, there is nothing to return. The copy will simply cease to exist after it resolves, as it is a spell with no card.

Therefore, after everything resolves, only the original sorcery card returns to your hand. The copy does not produce a card for your hand.

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
citations: ['Mimic Vat ruling #0', '111.12', '406.3a']
text: No, you do not get a token. The question involves a face-down manifested card that is an instant card (Lightning Bolt). When that manifested permanent dies, it is a creature card, so Mimic Vat's triggered ability can exile it [Mimic Vat ruling #0]. However, the card is exiled face down. A card exiled face down has no characteristics [406.3a]. Later, when you activate Mimic Vat's ability to create a token that's a copy of a card exiled with it, the ability looks for a card in exile. The exiled Lightning Bolt is face down and has no characteristics. Mimic Vat's ability cannot create a token that is a copy of a nonexistent object or a card with no characteristics [111.12]. A specific ruling for Mimic Vat confirms that if the exiled card is a nonpermanent card (like an instant), you cannot create a token that's a copy of it, and no token is created [Mimic Vat ruling #0]. Therefore, activating the ability results in no token being created.

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
citations: ['[607.2a]', '[607.3]', '[Lithoform Engine ruling #4]']
text: Yes, both exiled creatures will return to the battlefield when Fiend Hunter leaves the battlefield.

Fiend Hunter has two linked abilities: its first ability exiles a creature, and its second ability returns "the exiled card." According to rule [607.2a], these abilities are linked because the second refers to cards exiled by the first.

When you copy the first ability with Lithoform Engine, the copy is also linked to the second ability. Rule [607.3] states that if a linked ability exiles multiple cards (because it was copied), the other ability that refers to "the exiled card" refers to each of the exiled cards. It performs its action on each exiled card.

This is directly confirmed by [Lithoform Engine ruling #4], which uses Fiend Hunter as an example: if its enters-the-battlefield ability is copied and two creatures are exiled, they both return when Fiend Hunter leaves the battlefield.

Therefore, when Fiend Hunter's leaves-the-battlefield ability resolves, it will return both creature cards that were exiled by the original and the copied ability.

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
citations: ["Teferi's Protection ruling #21", '702.26d', '610.4a']
text: No, the exiled creature does not return to the battlefield when your Banishing Light phases out.

Teferi's Protection causes all permanents you control to phase out. Phasing out is not changing zones; the phased-out permanent is treated as though it doesn't exist but is still on the battlefield [702.26d].

Banishing Light's effect exiles a permanent "until this enchantment leaves the battlefield." This creates a one-shot effect that phases out the exiled permanent (using the rules for phasing out "until") [610.4a]. A second one-shot effect to phase it back in is waiting for Banishing Light to leave the battlefield.

Crucially, a ruling for Teferi's Protection directly addresses this interaction: "Any one-shot effects that are waiting 'until [this] leaves the battlefield,' such as that of Banishing Light, won't happen when a permanent phases out" [Teferi's Protection ruling #21]. Since phasing out is not leaving the battlefield, the waiting condition for the exiled permanent to phase back in is not met. Therefore, the creature remains exiled.

The creature will only return if Banishing Light actually leaves the battlefield (e.g., is destroyed, sacrificed, or exiled) or if another effect causes it to phase in [610.4a].

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
citations: ['Emrakul, the Promised End ruling #2', '601.2i', '603.1a', '117.7']
text: Yes, your opponent can target the Emrakul spell on the stack with Counterspell, and if it is countered, you will still control their next turn.

First, the key point is that protection abilities, including "protection from instants," only apply while the permanent is on the battlefield [Emrakul, the Promised End ruling #2]. While Emrakul is a spell on the stack, it does not have protection from instants. Therefore, it can be legally targeted by the instant spell Counterspell.

Second, the ability "When you cast this spell, you gain control of target opponent during that player's next turn. After that turn, that player takes an extra turn" is a triggered ability [603.1a]. This ability triggers at the moment Emrakul becomes cast, which is after the steps of casting are completed [601.2i]. The ability is put onto the stack on top of the Emrakul spell [117.7].

Your opponent casts Counterspell in response to this triggered ability. Counterspell resolves first, countering the Emrakul spell. However, the triggered ability is a separate object on the stack. Countering the source spell (Emrakul) does not counter or stop its triggered ability from resolving. The triggered ability will resolve independently, and you will gain control of the target opponent during their next turn.

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
citations: ['702.85a', '712.11c', '712.8c', 'Valki, God of Lies // Tibalt, Cosmic Impostor ruling #16']
text: Yes, Valki, God of Lies is a legal cascade hit, and you may cast the Tibalt, Cosmic Impostor side for free. Here's why:

Cascade exiles cards from the top of your library until you exile a nonland card whose mana value is less than the cascading spell's mana value [702.85a]. While in your library, Valki, God of Lies // Tibalt, Cosmic Impostor is a double-faced card with a front face (Valki) and a back face (Tibalt). The card's mana value is determined by the mana cost of its front face, which is {1}{B}, making its mana value 2 [712.8c]. Since 2 is less than the cascading spell's mana value (assuming the cascading spell's mana value is greater than 2), the card qualifies as a legal hit.

When you cascade into a double-faced card, you may cast either face that fits the criteria of the cascade effect [Valki, God of Lies // Tibalt, Cosmic Impostor ruling #16]. Cascade's criteria are that you may cast the exiled nonland card without paying its mana cost if the resulting spell's mana value is less than the cascading spell's mana value [702.85a]. The resulting spell's mana value is calculated using the mana cost of the face you choose to cast. If you choose to cast the back face, Tibalt, Cosmic Impostor, the resulting spell is a double-faced spell cast with its back face up. However, its mana value for the purpose of determining if it can be cast via cascade is still calculated using the mana cost of its front face (Valki), which is 2 [712.8c]. Since 2 is less than the cascading spell's mana value, you may cast Tibalt, Cosmic Impostor without paying its mana cost.

Note that a double-faced spell is normally cast with its front face up by default [712.11c], but an effect like cascade that allows you to cast a card from among exiled cards permits you to choose which face to cast, as per the specific ruling for modal double-faced cards.

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
citations: ['707.10', '707.10b', '111.13', 'Lithoform Engine ruling #6', 'Emrakul, the Promised End ruling #14']
text: You will control one of your opponent's turns, you will get a second Emrakul token, and copying the Emrakul spell does not give you another control-a-turn trigger.

First, you cast Emrakul, the Promised End. Its triggered ability, "When you cast this spell, you gain control of target opponent during that player's next turn. After that turn, that player takes an extra turn," goes on the stack. You use Lithoform Engine's first ability to copy that triggered ability. A copy of an ability is put onto the stack and copies all decisions made for the original, including its target [707.10, 707.10b]. The copy is not cast, so it won't trigger abilities that trigger when a spell is cast [Lithoform Engine ruling #6]. Both the original and the copy of the triggered ability will resolve. However, both abilities target the same opponent and create player-controlling effects. According to the rulings for Emrakul, multiple such effects that affect the same player overwrite each other, with the last one created being the one that works [Emrakul, the Promised End ruling #14]. Since you control both abilities and put them on the stack in the order you choose, you can arrange them so the last one to resolve (and thus be created) is the one you want. Regardless, only one effect will ultimately control the opponent's turn; the other is overwritten. The ruling also states each ability's effect will create an extra turn, so the targeted opponent will take two extra turns after the turn you control.

Second, you untap Lithoform Engine and use its third ability to copy the Emrakul, the Promised End permanent spell on the stack. A copy of a spell is put onto the stack and is itself a spell, but it is not cast [707.10]. The copy of the permanent spell will resolve and become a token that is a copy of Emrakul [111.13]. So, you will get a second Emrakul token. However, because the copy was not cast, its cast triggered ability ("When you cast this spell...") does not trigger [707.10, Lithoform Engine ruling #6]. Therefore, copying the Emrakul spell does not give you another control-a-turn trigger.

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
citations: ['707.10b', 'Mimic Vat ruling #6', 'Lithoform Engine ruling #3']
text: Yes, you get two tokens. Here's why:

- You activate Mimic Vat's ability, which reads "{3}, {T}: Create a token that's a copy of a card exiled with this artifact. It gains haste. Exile it at the beginning of the next end step." This ability goes on the stack.
- You then use Lithoform Engine's first ability, which copies a target activated or triggered ability you control [Lithoform Engine ruling #3]. This puts a copy of Mimic Vat's activated ability onto the stack [707.10b].
- When the original Mimic Vat ability resolves, it checks if a card is exiled with Mimic Vat. Since you have a creature imprinted, it creates a token copy of that card.
- When the copy of the ability (created by Lithoform Engine) resolves, it also checks if a card is exiled with Mimic Vat at that time [Mimic Vat ruling #6]. The imprinted card is still there, so it creates a second token copy of that card.
- Each token is created separately by a different instance of the ability resolving, so you end up with two tokens.

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
citations: ['601.2f', '118.7', '118.7a', '118.9d', '107.3b', 'Trinisphere ruling #0', 'Awaken the Woods']
text: You control a permanent that makes your green spells cost {1} less. You want to cast Awaken the Woods, a green sorcery with mana cost {X}{G}{G}, while an opponent controls an untapped Trinisphere.

First, to determine the total cost of a spell, you follow the steps in rule 601.2f. You start with the mana cost or alternative cost, add any cost increases, then apply any cost reductions, and finally apply effects like Trinisphere if the mana component is less than three mana [Trinisphere ruling #0].

Let's analyze casting Awaken the Woods with X=0. Its mana cost is {0}{G}{G}. This mana cost has a generic component of {0} and a colored component of {G}{G}. Your cost reduction effect makes your green spells cost {1} less. According to rule 118.7a, effects that reduce a cost by an amount of generic mana affect only the generic mana component of that cost. Therefore, the {1} reduction applies to the generic component. The generic component is {0}. Reducing {0} by {1} results in a negative generic component. Rule 118.7 states that if the mana component of a cost is reduced to nothing by cost reduction effects, it's considered to be {0}, and it can't be reduced to less than {0} [601.2f]. Therefore, after applying the cost reduction, the generic component is {0}, and the colored components remain {G}{G}. So the mana component of the total cost at this point is {G}{G}, which has a converted mana cost of 2.

Next, Trinisphere's effect applies because the mana component of the spell's cost ({G}{G}) is less than three mana. Trinisphere makes each spell that would cost less than three mana to cast cost three mana to cast. Therefore, the total cost becomes three mana. The additional mana required (one mana) may be paid with any color of mana or colorless mana. So the final total cost to cast Awaken the Woods with X=0 is three mana of any combination of colors and/or colorless. You must pay this cost.

When you cast a spell with X in its mana cost and choose X=0, you create X tokens. Since X is 0, you create 0 tokens [Awaken the Woods].

Now, what X should you actually choose? You want to get value, meaning you want to create at least some tokens. According to rule 107.3b, if a player is casting a spell that has an {X} in its mana cost, the value of X isn't defined by the text of that spell, and an effect lets that player cast that spell while paying neither its mana cost nor an alternative cost that includes X, then the only legal choice for X is 0. This does not apply here because you are paying the spell's mana cost (with modifications), not using an effect that lets you cast it without paying its mana cost or an alternative cost. Therefore, you may choose any value for X you wish. However, choosing a higher value for X increases the generic component of the mana cost, which is subject to cost reductions and Trinisphere.

Let's determine the optimal X. The goal is to maximize the number of tokens (X) for a reasonable cost. The cost reduction applies to the generic component. For any chosen X, the initial mana cost is {X}{G}{G}. The cost reduction of {1} applies to the generic component, reducing it by {1}. So the cost after reduction is {(X-1)}{G}{G}, but the generic component cannot be less than {0}. Therefore, if X is 0 or 1, the generic component after reduction is {0}. If X is 2 or more, the generic component after reduction is {X-1}. Then Trinisphere applies if the total mana component (generic + colored) is less than three mana.
- If X=0: Cost after reduction: {0}{G}{G} (CMC 2). Trinisphere applies, final cost: 3 mana. Tokens: 0.
- If X=1: Cost after reduction: {0}{G}{G} (CMC 2). Trinisphere applies, final cost: 3 mana. Tokens: 1.
- If X=2: Cost after reduction: {1}{G}{G} (CMC 3). Trinisphere does not apply because the cost is not less than three mana. Final cost: {1}{G}{G} (3 mana). Tokens: 2.
- If X=3: Cost after reduction: {2}{G}{G} (CMC 4). Trinisphere does not apply. Final cost: {2}{G}{G} (4 mana). Tokens: 3.

Thus, to get value, you should choose at least X=1. Choosing X=1 gives you one token for three mana. Choosing X=2 gives you two tokens for three mana (a better rate). Therefore, the most efficient choice to start getting value is X=2, which costs {1}{G}{G} (three mana) and creates two tokens. You could choose higher X for more tokens at an increased cost.

In summary: Casting Awaken the Woods with X=0 costs three mana (of any colors) and you get 0 tokens. To actually get tokens, you should choose at least X=1, but X=2 is more efficient as it creates two tokens for the same three-mana cost.

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
citations: ['[113.6m]', '[Animate Dead ruling #1]', '[Animate Dead ruling #4]', '[Grist, the Hunger Tide ruling #1]']
text: Yes, you can return Grist, the Hunger Tide from your graveyard with Animate Dead, and it will enter the battlefield as a creature planeswalker, but the Aura will likely fail to attach, causing Grist to be sacrificed.

Here's the sequence:
1. **Targeting and Casting**: Animate Dead is an Aura spell that targets a creature card in a graveyard [Animate Dead ruling #1]. While Grist is in your graveyard, its first ability makes it a 1/1 Insect creature card in addition to its other types [Grist, the Hunger Tide ruling #1]. Therefore, it is a legal target for Animate Dead.
2. **Resolution**: When Animate Dead's enters-the-battlefield triggered ability resolves, it returns the targeted creature card (Grist) to the battlefield under your control [Animate Dead ruling #1]. Grist enters the battlefield. As soon as it is on the battlefield, it is no longer a creature and is just a legendary planeswalker [Grist, the Hunger Tide ruling #1].
3. **Attachment Problem**: Part of Animate Dead's effect tries to attach itself to the returned creature. However, the Aura has gained "enchant creature put onto the battlefield with this Aura." The permanent it is trying to enchant is now a planeswalker, not a creature. Auras can only enchant permanents that match their enchant ability. Since Grist is not a creature on the battlefield, Animate Dead cannot legally enchant it [Animate Dead ruling #4].
4. **State-Based Action**: Because Animate Dead is not attached to a legal permanent, it is put into its owner's graveyard as a state-based action.
5. **Sacrifice Trigger**: Animate Dead has a delayed triggered ability: "When this Aura leaves the battlefield, that creature's controller sacrifices it." When Animate Dead is put into the graveyard, this ability triggers. Even though Grist is now a planeswalker, the ability refers to "that creature," which means the object that was returned (Grist). When the trigger resolves, if Grist is still on the battlefield, its controller (you) must sacrifice it [Animate Dead ruling #4].

In summary, Grist will briefly enter the battlefield but will almost certainly be sacrificed shortly after.

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
citations: ['Skullbriar, the Walking Grave ruling #1', 'Skullbriar, the Walking Grave ruling #2', '903.9b', '122.2', '614.16', 'Doubling Season ruling #2']
text: Yes, Skullbriar keeps the counters, but Doubling Season does not double them as it re-enters.

First, Skullbriar's ability states that counters remain on it as it moves to any zone other than a player's hand or library. This includes moving to the command zone [Skullbriar, the Walking Grave ruling #1]. When Skullbriar dies, you may apply the replacement effect from rule 903.9b to put it into the command zone instead of the graveyard. As it moves from the battlefield to the command zone, its ability causes the four +1/+1 counters to remain on it; they are not removed and do not cease to exist as they normally would when an object changes zones [122.2]. Therefore, Skullbriar is in the command zone with four +1/+1 counters.

Second, when you recast Skullbriar from the command zone and it enters the battlefield, Doubling Season does not double those counters. Doubling Season's ability is a replacement effect that applies "if an effect would put one or more counters on a permanent you control" [614.16]. However, Skullbriar's counters are not being "put" on it as part of an effect as it enters the battlefield; they are simply remaining on it from its previous state due to its own ability. A specific ruling for Skullbriar confirms this: "The counters that remain on Skullbriar as it changes zones aren't 'placed' on Skullbriar. Effects like Doubling Season's ... won't affect those counters" [Skullbriar, the Walking Grave ruling #2]. Furthermore, Doubling Season ruling #2 states it affects permanents that "enter with counters," but this refers to counters generated by an effect as the permanent enters, not counters retained from a previous zone. Therefore, Skullbriar enters the battlefield with the same four +1/+1 counters it had in the command zone, and no doubling occurs.

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
text: No, you do not lose the game. Final Fortune creates a delayed triggered ability that triggers "At the beginning of that turn's end step." When you activate Sundial of the Infinite's ability during your extra turn, you end the turn. According to rule 724.1d, ending the turn causes the current phase or step to end and the game skips straight to the cleanup step, skipping the end step. Rule 724.1e explicitly states that when a turn ends, "at the beginning of the end step" triggered abilities do not trigger because the end step is skipped. Since the end step is skipped, the delayed trigger from Final Fortune never has a chance to trigger. This is further supported by the ruling for Sundial of the Infinite (ruling #1), which confirms that if the ability is activated before the end step, any "at the beginning of the end step" triggered abilities won't trigger that turn. The ruling for Final Fortune (ruling #1) directly states that if you skip the extra turn gained, you do not lose the game. While you are not skipping the entire turn here, you are skipping the specific step (the end step) where the losing condition would trigger. The principle is the same: by preventing the end step from occurring, you prevent the triggered ability from ever triggering, so you do not lose the game.

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
citations: ['[707.6]', '[Clone ruling #0]', '[Clone ruling #2]', '[Clone ruling #5]']
text: You choose what creature Clone copies as part of the process of it entering the battlefield, not before. This choice is made as the Clone is entering, not as you cast it. The choice is not targeted, and you can only choose a creature that is already on the battlefield at the moment Clone is entering. You can also choose not to copy anything. Your opponent cannot respond to the choice itself because it is made during the resolution of the effect putting Clone onto the battlefield, not as a separate action that uses the stack. They can, however, respond to the spell Clone before it resolves, potentially removing potential creatures you might copy.

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
citations: ['[701.23h]', '[707.10b]', '[Gogo, Master of Mimicry ruling #6]', '[Gogo, Master of Mimicry ruling #9]']
text: You will get three lands total from that one Flooded Strand activation.

Here's why: You activated Flooded Strand's ability, which is an activated ability that says "Search your library for a Plains or Island card, put it onto the battlefield, then shuffle." This ability goes on the stack. You then activated Gogo, Master of Mimicry's ability with X=2, targeting that Flooded Strand ability. Gogo's ability creates two copies of the targeted ability and puts them on the stack [Gogo, Master of Mimicry ruling #6]. The copies are controlled by you and have the same source as the original ability [Gogo, Master of Mimicry ruling #9].

A copy of an ability copies all decisions made for the original ability, including modes and targets [707.10b]. The original Flooded Strand ability has you search your library once. Rule 701.23h states that if an effect instructs you to search a library for one or more cards more than once before instructing you to shuffle that library, it is treated as a single instruction to search for all those cards, and you search only once. Therefore, when the original ability and the two copies resolve, they are all part of a single search instruction. You will search your library one time, but you will find a total of three cards (one for the original ability and one for each of the two copies) and put them all onto the battlefield. After that single search, you shuffle your library once.

Thus, from the one Flooded Strand activation and the two copies, you get three lands.

---

## Output instructions

Grade all 50 cells above per the rubric. For EACH cell, write exactly one JSON line to:

    evals/opus_grader_v2_out/deepseek-v3-2.jsonl

Each line is a single JSON object with EXACTLY these fields and nothing else:

    {"id": "<cell id, e.g. q007 or c012>", "arm": "deepseek-v3-2", "verdict": "correct"|"partial"|"wrong", "reason": "<one-line reason>"}

Every one of the 50 cells above must be accounted for -- one line per cell, any order, no duplicates, no extra fields, no commentary outside the JSONL lines. If a cell is genuinely ungradeable, still write a line with your best-effort verdict and say why in the reason -- never silently drop a cell.