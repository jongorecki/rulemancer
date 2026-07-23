# Opus-Grader Calibration v2 -- Batch: sonnet-v2

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
citations: ['702.26d', '702.26a', '703.4a', '702.26n', '702.26j', '603.6a', '603.6b']
text: No. Phasing does not cause a permanent to change zones or control at all — a phased-out permanent is only treated as though it isn't on the battlefield, but it never actually leaves the battlefield zone. Because of this, rule 702.26d explicitly states that zone-change triggers (which include 'enters the battlefield' triggers, as defined in rule 603.6a/b) don't trigger when a permanent phases in or phases out. Similarly, effects that check a permanent's history won't treat the phasing event as having caused it to leave or enter the battlefield or its controller's control, so any 'enters the battlefield' ability on that permanent (or on other permanents watching for creatures entering) will not fire when it phases back in.

This holds true in any number of players. In multiplayer games, phasing still follows the same rule: during the untap step, phased-in permanents with phasing phase out and previously phased-out permanents controlled by that player phase in simultaneously (rule 702.26a, 703.4a), and none of this counts as entering or leaving the battlefield for trigger purposes. Even the special case where a permanent that phased out under a player who left the game phases back in later (rule 702.26n) is still just a phasing event, not a zone change, so it still won't trigger 'enters the battlefield' abilities.

Note also that attach/unattach triggered abilities are similarly unaffected by phasing (rule 702.26j) — reinforcing the general principle that phasing in and out is invisible to zone-change and state-change triggers.

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
citations: ['702.19b', '702.2c', '120.4a', '702.2b', '704.5h', '302.7', 'Lethal Damage', '702.19c', '702.19d', '702.19e']
text: Trample and deathtouch combine so that an attacking creature with both keywords only needs to assign a very small amount of damage to each blocking creature before it can send the rest of its damage through to the player, planeswalker, or battle it's attacking.

Normally, when an attacking creature has trample, its controller must assign at least *lethal damage* to each blocking creature before assigning any excess damage to the defending player or planeswalker [702.19b]. Lethal damage is normally an amount equal to or greater than the blocker's toughness, taking into account damage already marked on it and damage from other creatures assigned in the same step [Lethal Damage].

Deathtouch changes what counts as 'lethal' for this calculation. Rule 702.2c states that any nonzero amount of combat damage assigned to a creature by a source with deathtouch is considered to be lethal damage for the purpose of determining excess damage. This is echoed in the general damage rules: when calculating excess damage, 'any amount of damage greater than 1 is excess damage if the source dealing that damage to a creature has deathtouch' [120.4a]. In effect, as soon as the attacker assigns just 1 damage to a given blocker, that blocker is treated as having been assigned lethal damage for trample-assignment purposes.

So a trampling, deathtouch creature's controller can assign just 1 damage to each blocking creature and put all the rest of that creature's power onto the defending player (or planeswalker/battle it's attacking), exactly as if it had assigned full lethal damage to each blocker [702.19b, 702.2c]. This works the same way in multiplayer or Commander games, since the trample-assignment rule and the deathtouch excess-damage rule aren't player-count dependent.

Once that 1 damage is actually dealt, the blocking creature (assuming it has toughness greater than 0) is destroyed as a state-based action because it was dealt damage by a deathtouch source, regardless of whether that 1 point would otherwise be enough to kill it through normal marked-damage rules [702.2b, 704.5h, 302.7].

If the attacker instead has trample over planeswalkers and is attacking a planeswalker, the rule for the planeswalker portion is different: damage assigned to the planeswalker must still equal at least that planeswalker's loyalty before any excess can go to its controller, because loyalty isn't affected by deathtouch (deathtouch only redefines lethal damage for creatures) [702.19c]. Deathtouch's 1-damage rule only reduces the amount that must be assigned to blocking *creatures*, not to a planeswalker itself.

If no creatures end up blocking when damage is assigned (e.g., all blockers were removed from combat), the trampling creature's damage is simply assigned to the defending player and/or planeswalker as though lethal damage had already been assigned to all blockers, so deathtouch has no additional effect in that case [702.19d, 702.19e].

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
citations: ['702.40a', '702.40b', '603.3', '113.9', '807.5b']
text: Storm is indeed a triggered ability, not a spell. Rule [702.40a] defines it as: "When you cast this spell, copy it for each other spell that was cast before it this turn..." — that trigger fires when you cast the spell and creates a triggered ability that goes on the stack as its own object (per [603.3], once triggered it's put on the stack as an object that isn't a card, with only the text of the ability).

Because it is a triggered ability and not a spell, storm can be countered — but only by something that specifically says it counters abilities, not by an effect that only counters spells. Rule [113.9] states that activated and triggered abilities on the stack aren't spells, so anything that counters 'only spells' has no effect on the storm trigger; however, effects that are written to counter abilities can counter it. Note also that if a card happens to have more than one instance of storm, each one triggers (and could be countered) separately [702.40b].

This works the same regardless of how many players are in the game (e.g., Commander) — the storm trigger still goes on the stack as a triggered ability tied to the casting of the spell, and the same counter-ability-vs-counter-spell distinction applies. (Note: if you're playing a variant like Grand Melee with multiple stacks [807.5b], the storm trigger must be put on the same stack as the spell that caused it, but the countering rules are otherwise unchanged.)

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
citations: ['903.5c', '903.4f', '107.4e', '202.2d', '903.4', '903.11a', '903.12e']
text: No. A hybrid mana symbol, like {R/G}, is treated as being ALL of its component colors, not just one of them — rule 107.4e states that '{G/W}{G/W} can be paid by spending {G}{G}, {G}{W}, or {W}{W}', but for color purposes the symbol is all of its component colors. Rule 202.2d confirms that an object with a hybrid mana symbol is all of the colors of those symbols. For Commander deck construction, rule 903.4f defines a card's color identity as the color or colors of any mana symbols in its mana cost or rules text — this includes every color present in a hybrid symbol, even the half you didn't intend to use. Rule 903.5c then requires that every color in a card's color identity also be found in the commander's color identity for that card to be legal in the deck (this applies the same way for cards brought in from outside the game per 903.11a, and note the Brawl exception in 903.12e only applies to colorless commanders' basic land choices, not hybrid-color cards). So if your commander's color identity is only, say, red, you cannot include a card whose mana cost or rules text contains a hybrid symbol like {R/G}, {R/W}, {B/R}, etc., because that card's color identity includes green (or whichever second color) as well as red — and green isn't part of the commander's color identity. You would need a commander whose color identity includes BOTH colors of the hybrid symbol to legally include such a card.

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
citations: ['502.4', '500.3', '117.3a', '703.4a', '703.4c', '503.1a', '503.1', '731.2', '500.12']
text: No. The untap step is one of the special steps in which no player ever receives priority [502.4][117.3a]. That means no one can cast spells, activate abilities, or otherwise 'respond' to anything happening during it. All that occurs during the untap step are turn-based actions: the active player's phased-in permanents with phasing phase out and their previously phased-out permanents phase in [703.4a], the game checks whether the day/night designation should change [731.2], and then the active player untaps their permanents simultaneously [703.4c]. Since these are automatic turn-based actions and not the resolution of a spell or ability, there's no window for responses, and the step simply ends once all these specified actions are completed [500.3]. If any ability triggers during the untap step (for example, from a permanent phasing in or out), it doesn't go on the stack immediately — it's held until the next time a player would actually receive priority, which is normally once the upkeep step begins and the active player gets priority [502.4][503.1a][503.1]. Also, no game events can occur in the gap between the untap step and the next step, so there's no in-between window there either [500.12]. This applies the same way in multiplayer and Commander games — the active player still gets priority first once the upkeep step begins, after any triggered abilities from the untap step are put on the stack.

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
citations: ['511.1', '511.2', '511.3', '508.1k', '508.4', '506.4a', '508.5', 'Attacking Creature', '724.2d', '724.2e']
text: Yes. A creature that has been declared as an attacker (or put onto the battlefield attacking) remains an "attacking creature" until it is either removed from combat or the combat phase itself ends — whichever happens first (see the definition of Attacking Creature, and rules [508.1k] and [508.4]).

The end of combat step is the fifth and final step of the combat phase, not something that occurs after the combat phase [511.1, End of Combat Step]. So creatures that are still attacking when that step begins remain attacking creatures throughout it — this is exactly why "at end of combat" triggered abilities (which trigger as the end of combat step begins, per [511.2]) can still refer to attacking creatures.

Creatures stop being attacking creatures only when they're removed from combat (e.g., leaving the battlefield, changing controller, phasing out, etc., per [506.4a]) or when the end of combat step ends. As soon as the end of combat step ends, all creatures, battles, and planeswalkers are removed from combat, and only then does the combat phase conclude and the postcombat main phase begin [511.3]. This applies the same way regardless of how many players or defending players are involved, since defending-player references for an attacking creature are simply resolved based on whichever player, planeswalker, or battle it's attacking [508.5].

One exception: if an effect like Mandate of Peace ends the combat phase early, all creatures and planeswalkers are removed from combat immediately as part of that effect, and the end of combat step is skipped entirely, so "at end of combat" triggers don't happen and creatures stop being attacking creatures at that point instead [724.2d, 724.2e].

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
citations: ['305.1', '505.6b', '701.18a', '116.2a', '305.9', '300.2a', '202.1b', '302.1', '305.3']
text: No. Lands are never cast — they are played. "Playing" a land is one of Magic's special actions: the player simply puts the land card directly onto the battlefield from their hand (or other zone it's in) without using the stack [305.1][701.18a][116.2a]. Because it doesn't use the stack, the land is never a spell, and neither the land nor the act of playing it can be countered or responded to with instants or activated abilities [305.1][505.6b]. "Casting," by contrast, is specifically how you put a spell (such as a creature card) onto the stack, which does use the stack and can be responded to [302.1]. If an object has both the land type and another card type (e.g., an artifact land), it can only ever be played as a land — it can never be cast as a spell [305.9][300.2a]. Also note that lands have no mana cost, since they're played rather than cast and no cost is paid to put them onto the battlefield [202.1b]. Playing a land is limited to your own turn, during a main phase when the stack is empty, and normally only once per turn unless an effect says otherwise [505.6b][116.2a][305.3]. This applies the same way in multiplayer/Commander games — you may still only play a land during your own main phase, never on another player's turn [305.3].

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
citations: ['702.74a', '603.3d', '118.10', '702.110a', '702.110b', '702.48b']
text: Yes. Evoke gives you two abilities: a static ability that lets you cast the creature for its evoke cost, and a triggered ability that reads "When this permanent enters, if its evoke cost was paid, its controller sacrifices it" [702.74a]. That triggered ability goes on the stack like any other triggered ability once it triggers [603.3d], and — as with any object on the stack — players get priority before it resolves. During that window (before the evoke trigger resolves) you're free to sacrifice the creature to something else, such as a sacrifice-cost activated ability, an Exploit ability [702.110a]/[702.110b], an Offering cost [702.48b], or any other effect that lets you sacrifice a creature. Note that a single sacrifice can only satisfy one cost/ability at a time [118.10], so sacrificing it to something else uses up that sacrifice; it isn't simultaneously feeding the evoke trigger. If you do sacrifice the creature this way, the creature is already gone by the time the evoke trigger resolves. The evoke trigger's instruction to sacrifice "it" refers to that specific permanent object; since it's no longer on the battlefield, there is nothing left for the ability to sacrifice, so the trigger simply does nothing when it resolves — you don't get to (or have to) sacrifice it a second time. This works the same way in a multiplayer or Commander game: whoever controls the evoke trigger and the alternate sacrifice effect just needs the timing where the trigger is still unresolved on the stack.

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
citations: ['113.10', '113.10b', '113.10c', '702.1', '603.6b', '113.2a', '113.12']
text: Yes. Rule [702.1] explains that a keyword is simply a shorthand name for an ability whose full rules text is defined elsewhere (or given as reminder text) — mechanically, a keyword like "flying" or "trample" is still an ability, just represented on the card by a single word instead of spelled-out rules text. Since keyword abilities are abilities, an effect that says a permanent "loses all abilities" removes every ability it has, including all of its keyword abilities, static abilities, triggered abilities, and activated abilities [113.10], [113.10b], [113.2a]. Rule [113.10c] confirms that ability-removing effects strip out abilities regardless of how they were granted or printed, and rule [603.6b] gives a concrete example: if an effect says "All creatures lose all abilities" and a creature (even one printed with a keyword-based enters-the-battlefield ability) enters the battlefield under that effect, it loses that ability the instant it enters, so even its zone-change/keyword trigger never fires. This applies the same way regardless of number of players — in multiplayer or Commander games, "loses all abilities" strips keywords no matter who controls the permanent or how many opponents are involved. Note the distinction in rule [113.12]: this only applies to genuine abilities. An effect that merely sets a characteristic (e.g., "this creature is red") or states a quality ("this creature can't be blocked") without granting an ability isn't itself removed by a "loses all abilities" effect, but true keyword abilities (flying, trample, deathtouch, hexproof, etc.) are abilities and are removed.

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
citations: ['514.1', '703.4n', '402.2', '104.3c', '902.5b', '313.6']
text: Yes. There is no rule that stops you from drawing cards (or having cards drawn for you) just because your hand is already at or above your maximum hand size. "Maximum hand size" (normally seven cards, as modified by things like a vanguard card's hand modifier) is not a hard limit that blocks drawing — it's only enforced at a specific turn-based action.

Specifically, a player's hand size is checked and trimmed down only as part of the cleanup step of their own turn: "Immediately after the cleanup step begins, if the active player's hand contains more cards than their maximum hand size (normally seven), they discard enough cards to reduce their hand size to that number" [514.1][703.4n]. Rule [402.2] confirms the same thing: a player may have any number of cards in hand at other times, and only has to discard excess cards down to the maximum as part of their own cleanup step.

Since the cleanup step belongs to the active player, in a multiplayer or Commander game a non-active player can freely sit above their maximum hand size for as long as it isn't their own turn — they only have to discard down to their maximum during their own cleanup step, not anyone else's.

So: you can draw cards at any time regardless of your current hand size, up to whatever your library allows (running out of required draws can even cause a loss under [104.3c]). The only consequence of drawing while already at your maximum is that you'll have to discard down to your maximum hand size when your own cleanup step arrives, unless something else changes your maximum hand size in the meantime (e.g., a vanguard card's hand modifier, as in [902.5b] and [313.6]).

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
citations: ['306.9', '122.1e', '704.5i', '120.3c', '306.8', '306.5c', '724.1c', '724.2c']
text: A planeswalker's loyalty is represented by loyalty counters placed on it [122.1e], and its current loyalty equals the number of loyalty counters it has [306.5c]. Loyalty can be reduced by damage, since damage dealt to a planeswalker causes that many loyalty counters to be removed from it [120.3c][306.8]. Note that since loyalty is defined as the number of counters actually on the permanent, it can't go 'below' 0 — if enough counters are removed, the planeswalker simply ends up with 0 loyalty counters, not a negative number. As soon as a planeswalker has loyalty 0, the game checks state-based actions [704.5i], and that planeswalker is put into its owner's graveyard [306.9][704.5i]. This happens automatically anytime a player would receive priority (or during the special state-based-action check that occurs when an effect ends the turn or ends combat, per [724.1c] and [724.2c]), regardless of how many players are in the game — the rule applies the same way in two-player and multiplayer/Commander games, since it's simply based on the loyalty counters on that specific permanent.

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
text: No. The rules reserve the word “dies” for creatures and planeswalkers. The glossary entry for “Dies” states: “A creature or planeswalker ‘dies’ if it is put into a graveyard from the battlefield” (rule 700.4 backs this up by defining the term as meaning “is put into a graveyard from the battlefield,” but the term is only applied to those two permanent types). A non-creature artifact that goes from the battlefield to its owner's graveyard—whether because it was destroyed, sacrificed, or removed some other way—is simply described as being 'put into the graveyard,' not as having 'died.' This matters for triggered abilities worded like 'Whenever a creature dies...': such an ability won't trigger off a non-creature artifact going to the graveyard, because it never 'dies' in the rules sense (unless that artifact also happens to be a creature, e.g., an animated artifact or artifact creature, in which case it is a creature and does die). This distinction is the same in two-player and multiplayer/Commander games, since the definition of 'dies' doesn't vary by player count.

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
citations: ['121.4', '704.5b', '104.3c', '121.6a', '614.11', '121.3', '121.1', '727.3']
text: Attempting to draw a card when your library has zero cards in it doesn't cause you to lose immediately. Instead, the game state is checked: as a state-based action, if you have attempted to draw from an empty library since the last time state-based actions were checked, you lose the game the next time a player would receive priority (rules [121.4] and [704.5b]). If you're required to draw more cards than remain in your library (e.g., "draw three cards" but only one is left), you draw whatever cards are actually there, and then lose the game the next time a player would receive priority ([104.3c]). This is a turn-based/effect-based draw governed by the basic drawing rule [121.1]. Note that if an effect *replaces* the draw (a replacement effect), that replacement is still applied even though no card could actually be drawn — the draw never happens, so the empty-library loss condition isn't triggered by it ([121.6a], [614.11]). Similarly, if an effect merely offers you the *choice* to draw a card, you can still choose to do so even with an empty library, but actually doing so would set up the loss condition described above ([121.3]). In multiplayer or Commander games, this state-based action applies individually to whichever player attempted the illegal draw — that player loses the game while the rest of the game continues normally, since the rule is stated in terms of "a player" losing, not the whole game ending; only if all but one player has lost does the game end for the remaining player (per the general loss-checking framework in [704.5b] and [121.4]). Also note this is exactly why, at the start of a new game, any player who begins with fewer than seven cards in their library will lose once everyone draws their opening seven-card hand and state-based actions are checked ([727.3]).

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
citations: ['506.1', '506.2', '506.2a', '507.1', '703.4h', '802.2', '802.5', '510.1', '510.2', '511.1', '117.3a']
text: Combat has five steps, always in this order: beginning of combat, declare attackers, declare blockers, combat damage, and end of combat [506.1]. If no creatures are declared as (or put onto the battlefield) attacking, the declare blockers and combat damage steps are skipped entirely [506.1]. If any attacking or blocking creature has first strike or double strike, there are two combat damage steps instead of one [506.1].

Who the 'defending player' is depends on the game type:
- In a two-player game, the nonactive player is automatically the defending player for the whole combat phase [506.2].
- In most multiplayer games (unless a variant like the Attack Multiple Players option is in use), the active player picks one opponent as the defending player as a turn-based action at the very start of the beginning of combat step [507.1] [703.4h] [506.2a].
- Under the Attack Multiple Players option, no single opponent is chosen — instead, all of the attacking player's opponents are defending players simultaneously throughout combat [802.2].

As for when you get priority as the defending player: in each step or phase, the active player receives priority first, after any turn-based actions for that step have been resolved and any triggered abilities have been put on the stack [117.3a]. Once the active player has priority and either passes it or finishes acting, priority passes around in turn order, meaning the defending player gets a chance to act (cast instants, activate abilities, etc.) after the active player has had their turn with priority in that step. This applies in beginning of combat, declare attackers, declare blockers, and end of combat [511.1] — the end of combat step itself has no turn-based actions, so the active player simply gets priority as soon as the step begins [511.1].

The one step where this differs is the combat damage step: combat damage assignment (announcing how each attacking/blocking creature assigns its damage) is a turn-based action done in APNAP (Active Player, Non-Active Player) order — the active player announces first, then each other player in turn order [510.1]. In a multiplayer game this APNAP order covers all defending players, not just one [802.5]. After damage is assigned, it's all dealt simultaneously as a turn-based action with no chance for anyone — attacking or defending — to cast spells or activate abilities in between [510.2]. Only after damage is dealt does the active player then receive priority normally, with the defending player(s) getting priority afterward in turn order [117.3a].

So in short: as the defending player, you don't act first in any step; the active player always gets priority (or performs the relevant turn-based action) first, and you get your chance to respond afterward, in turn order, once the active player has passed.

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
citations: ['605.3b', '605.4a', '113.4', '405.6c', '605.1', '605.5a']
text: No. Mana abilities never use the stack, so they resolve immediately when activated (for activated mana abilities) or immediately after the ability that triggered them (for triggered mana abilities), without ever waiting for priority. Because they don't go on the stack, they can't be targeted, countered, or otherwise responded to by any player – this is true in two-player games and in multiplayer/Commander games alike, since the rule is about the mana ability's resolution mechanics, not the number of players. Concretely: an activated mana ability resolves right after being activated (605.3b, 405.6c), and a triggered mana ability resolves right after the mana ability that triggered it, without anyone getting priority in between (605.4a). This is one of the special rules that sets mana abilities apart from ordinary activated/triggered abilities (113.4, 605.1). If a player had priority before the mana ability was activated, they simply get priority back afterward (405.6c), but there's no window in which anyone can respond to the mana ability itself. Note that an ability isn't a mana ability at all if it has a target, or if it's a triggered ability that triggers from something other than activating a mana ability but could produce mana, or a triggered ability that triggers from a mana ability activation but couldn't itself produce mana (605.5a) — those non-mana abilities DO use the stack and CAN be responded to normally.

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
citations: ['601.2g', '601.2h', '118.2', '602.4', '508.1i', '508.1j', '509.1e', '509.1f']
text: : No. Paying a cost is not itself a separate event that opens a priority window, so there's no way to "respond" to a cost being paid, whether that cost is for casting a spell, activating an ability, or paying an attack/block cost.

When you cast a spell, the process is: propose the spell, put it on the stack, and then determine and pay its total cost, all as part of the single action of casting (rules 601.2g, 601.2h). If mana is involved, you get a chance to activate mana abilities at that point (rule 118.2), but this still happens *during* the casting process, before the spell is fully cast and before any player receives priority. No other player can cast spells or activate abilities in response to the cost payment itself, because priority isn't passed until the whole casting process is finished.

The same is true for activating an activated ability, and for the turn-based actions of declaring attackers and declaring blockers: these declarations, including paying any associated costs, don't use the stack at all (rules 508.1i, 508.1j, 509.1e, 509.1f). Since nothing is put on the stack for the cost payment, there's no window for anyone to respond to it.

Once the spell or ability is fully cast/activated (costs paid) and is on the stack, players do get priority and can respond -- but what they're responding to is the spell or ability itself, not the act of paying its cost. In fact, rule 602.4 confirms that activating a cost-altering ability at that later point won't retroactively change a cost that's already been paid, because the cost was 'locked in' and paid before the stack object became responsive.

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
text: The “layer system” is the rule set that determines the order in which continuous effects are applied to figure out an object’s current characteristics (power, toughness, color, types, abilities, etc.).

How it works: You start with the object's actual, unmodified values — for a card, that's what's printed on it; for a token or copy, it's whatever the effect that created it specified [613.1]. Then all continuous effects currently active are applied, not in the order they were created, but in a fixed sequence of layers [613.1a]:

- Layer 1: Effects that modify copiable values (copy effects, merging with permanents, and 'as ... enters' or 'as ... is turned face up' abilities that set power/toughness) [613.1a]. This layer itself has sublayers (1a is copy effects) applied in timestamp order, and once layer 1 is fully applied, the result is the object's 'copiable values' [613.2c][613.2a].
- Layer 2: Control-changing effects (not explicitly given here, but referenced by example [613.6]).
- Layer 3: Text-changing effects [613.1c].
- Layer 4: Type-changing effects (card type, subtype, supertype) [613.1d].
- Layer 5: Color-changing effects [613.1e].
- Layer 6: Ability-adding effects, keyword counters, ability-removing effects, and effects saying an object can't have an ability [613.1f].
- Layer 7: Power/toughness-changing effects, which itself has sublayers: 7a is characteristic-defining abilities that set power/toughness [613.4a], followed by further sublayers (7b setting P/T, 7c modifying P/T, as shown in the examples) [613.5].

Within layers 2 through 6, characteristic-defining abilities are applied first, then all other effects in timestamp order (the order effects started to apply, generally the order they entered the game or were turned on) [613.3]. Within layer 1 and layer 7, similarly, effects within each sublayer are applied in timestamp order [613.2c][613.4a].

Dependency can override timestamp order: an effect 'depends on' another if both apply in the same layer/sublayer, applying one would change what the other does (its text, existence, targets, or effect), and the two effects aren't a mix of one characteristic-defining and one non-characteristic-defining ability [613.8][613.8a]. When a dependency exists, the dependent effect is applied after the effect it depends on, regardless of timestamps.

A single effect can have parts that apply in different layers — each part is applied in its own layer, and if the effect starts applying to a set of objects, it keeps applying to that same set in every relevant layer even if the source ability is later removed [613.6]. For example, 'gains control and gains haste' applies control-changing in layer 2 and ability-adding in layer 6; 'becomes the color of your choice and gets +1/+1' applies color-change in layer 5 and P/T change in layer 7c.

All of this happens continuously and automatically — as soon as circumstances change (e.g., a creature's color changes), the game re-evaluates which effects apply and in what order, and the result is instantaneous, as shown by the Honor of the Pure example: a creature turned white in layer 5 immediately starts getting +1/+1 from Honor of the Pure in layer 7c, and if its color changes again to red, that boost disappears just as immediately [613.5].

This layer system applies the same way regardless of how many players are in the game — it's about resolving the state of individual objects based on all currently active continuous effects, not about turn structure or player count, so it works identically in two-player and multiplayer/Commander games.

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
citations: ['Legend Rule', '704.5j', '205.4d', '117.2d', '306.4', 'Planeswalker Uniqueness Rule (Obsolete)']
text: The legend rule is a state-based action (SBA), not a triggered ability, so it's checked automatically and continuously; it doesn't use the stack and players never get priority in between the check and its resolution [117.2d]. It applies whenever a single player controls two or more legendary permanents that share the exact same name [Legend Rule][704.5j]. Any permanent with the supertype "legendary" is subject to this check [205.4d]. When it applies, that player (the one controlling the duplicates) chooses one of the like-named legendary permanents to keep, and all the others are put into their owners' graveyards [704.5j]. Note that they go to their owners' graveyards, not the controller's graveyard, which matters if control of one of the permanents had changed. The rule only cares about the permanents' names and who currently controls them — it doesn't matter how many different players own copies, so in a multiplayer or Commander game the rule still only triggers when one specific player controls two or more of the same-named legendary permanents at once; it never forces a comparison across different players' permanents. Also relevant: planeswalkers used to have their own separate "planeswalker uniqueness rule" limiting a player to one planeswalker of a given planeswalker type, but that rule has been removed. Planeswalker cards that predate the change were given errata to add the legendary supertype, so they are now handled by the ordinary legend rule instead of a special rule [306.4][Planeswalker Uniqueness Rule (Obsolete)].

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
citations: ['120.5', '120.6', '302.7', '704.3', '704.4', '704.5g', '117.5', '405.6f', '510.3a', '514.2', '514.3a', '703.4p', '724.1c', '724.2c']
text: A creature doesn't die the instant it takes lethal damage — damage merely gets marked on it (rule 120.6, 302.7). Dying is actually a state-based action, not a direct result of the damage itself: rule 120.5 explicitly says damage doesn't destroy a creature; rather, the game checks whether the total damage marked on it is greater than or equal to its toughness, and if so it 'has been dealt lethal damage and is destroyed' as a state-based action (rules 704.5g, 302.7).

State-based actions (SBAs) aren't performed the instant damage is dealt. Instead, the game checks for them every time a player would receive priority: 'Whenever a player would get priority... the game checks for any of the listed conditions for state-based actions, then performs all applicable state-based actions simultaneously as a single event' (rule 704.3; see also 117.5 and 405.6f). So in practice, once the damage-dealing event (e.g., a spell resolving, or combat damage being assigned in the combat damage step) finishes, the next time any player would get priority, the game checks SBAs, and your creature with lethal damage marked on it is destroyed and put into its owner's graveyard at that moment — before anyone actually gets priority. For example, after combat damage is dealt, this SBA check (and any triggered abilities from the damage) happens before the active player gets priority in the combat damage step (rule 510.3a).

A few important nuances:
- If the damage was dealt mid-resolution of a spell or ability, SBAs still don't check until that resolution is fully complete — 'state-based actions pay no attention to what happens during the resolution of a spell or ability' (rule 704.4). So a creature could temporarily have lethal damage marked mid-resolution and survive if something changes its toughness before the spell finishes resolving.
- Regeneration can replace this destruction event if you have a regeneration shield in place (rule 704.5g).
- During the cleanup step, priority normally isn't given at all, so SBAs would just happen without anyone acting on them — 'the game checks to see if any state-based actions would be performed... If so, those state-based actions are performed... then the active player gets priority' (rules 514.3a, 704.3). All damage is removed from permanents during cleanup (rules 514.2, 703.4p, 120.6), so if your creature survives that SBA check (i.e., it wasn't destroyed) up through cleanup, its damage is wiped and it lives.
- Some effects (rules 724.1c, 724.2c) that end the turn or end combat still check state-based actions as part of that process, so a lethally damaged creature would be destroyed then too, even though no one gets priority and no triggers go on the stack.

This applies the same way regardless of how many players are in the game — SBAs are checked globally whenever any player would get priority, not on a per-player basis, so lethal damage in a multiplayer or Commander game is handled identically.

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
citations: ['903.9a', '903.8', '903.3d', '601.3f']
text: By default, no. In a Commander game your commander is normally cast from the command zone, and rule [903.8] specifically grants permission to cast a commander from the command zone (paying the extra {2} 'commander tax' for each previous cast that game). There is no blanket rule that lets you cast a commander straight out of exile just because it's your commander.

However, rule [903.3d] makes clear that the 'commander' designation is an attribute of the card itself and follows it into whatever zone it's in — including exile. So if your commander card is sitting in exile, a state-based action ([903.9a]) lets its owner move it into the command zone (as long as it went to exile since the last time state-based actions were checked), after which you can cast it normally from the command zone under [903.8].

Separately, if some other rule or card effect specifically grants permission to cast spells from exile (for example, an effect that exiles a card and lets you cast it from there), you could cast your commander directly from exile under that permission. Rule [601.3f] says you can cast a spell only if some rule or effect actually allows it, and since the commander designation travels with the card per [903.3d], such a spell would still count as 'casting a commander' for effects that care about that. In that specific case the commander tax from [903.8] wouldn't apply, since that cost only attaches to casts made specifically from the command zone.

This all applies the same way in multiplayer Commander games — there's nothing zone- or player-count-specific that changes it.

So: absent a special effect granting permission to cast from exile, move the commander to the command zone via the state-based action in [903.9a] and cast it from there per [903.8]; only cast it directly from exile if some other rule or card specifically lets you do so.

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
citations: ['514.3a', '704.3', '703.4p', '514.2', '514.3', '500.3', 'Cleanup Step', '500.5', '724.1d', '724.1f']
text: The cleanup step is the second and final step of the ending phase [Cleanup Step]. It normally proceeds without any player receiving priority, so nothing can be cast or activated during it — it's one of the two step types (along with the untap step) where priority isn't normally passed [500.3][514.3].

Sequence of events:
1. If the active player's hand contains more cards than their maximum hand size, they discard down to that number (this is a turn-based action that happens automatically as the step begins, before the rest of cleanup occurs) [514.3a].
2. Immediately afterward, two things happen simultaneously as turn-based actions that don't use the stack: all damage marked on permanents (including phased-out permanents) is removed, and all 'until end of turn' and 'this turn' effects end [514.2][703.4p]. Any leftover effects that specifically last until the end of the step/phase also expire at this time, and unspent mana empties from mana pools [500.5].
3. The game then checks whether any state-based actions need to be performed or any triggered abilities are waiting to be put on the stack (this includes abilities that trigger 'at the beginning of the next cleanup step'). Normally, at this point neither is true, so no player gets priority and the cleanup step simply ends [514.3][514.3a][704.3].
4. If, however, there ARE state-based actions to perform or triggers waiting, those state-based actions are performed, the triggered abilities are put on the stack, and the active player then gets priority — meaning players actually can cast spells and activate abilities during this cleanup step, contrary to the normal rule [514.3a]. Once the stack is empty and all players pass in succession, a brand new cleanup step begins, and the whole process (steps 2-4, though discarding to hand size only happens once) repeats. This applies in multiplayer/Commander games the same way as two-player games — it's the active player's hand size and priority that matter, but any player's spells/abilities can be cast/activated once priority is opened up, and any player's state-based actions/triggers can trigger this exception.

Separately, some effects can force the game to skip straight to the cleanup step or end the turn; if that happens during the cleanup step itself, a new cleanup step begins per the same rules above [724.1d][724.1f].

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
citations: ['704.1', '704.1a', '704.2', '704.3', '117.5', '117.2d', '117.2c', '405.6f', '405.6e', '703.3', '510.3a', '514.3a', '724.1c', '724.2c']
text: State-based actions (SBAs) are automatic game actions—like a creature with lethal damage being destroyed or a player at 0 life losing—that happen whenever certain conditions are met, without being cast, activated, or put on the stack [704.1][704.1a][704.2].

The key rule governing *when* they're checked is that every time a player would receive priority, the game first performs all applicable SBAs as a single simultaneous event, then checks again, repeating until no more SBAs apply; only after that do triggered abilities go on the stack, and then the player finally gets priority [704.3][117.5]. This check happens before any player actually receives priority, whether during a phase, step, or otherwise [117.2d][405.6f].

Other specific moments this plays out:
- At the start of a step or phase, turn-based actions (e.g., untapping, drawing a card) are handled automatically first, before SBAs are checked and before triggered abilities or priority [703.3][117.2c][405.6e].
- During combat damage, once damage is dealt, the active player is about to get priority, so SBAs are checked and any damage-triggered abilities are put on the stack first [510.3a].
- During the cleanup step, players normally don't get priority at all, but the game still checks for SBAs and waiting triggered abilities; if any exist, they're resolved/put on the stack and the active player then gets priority, restarting the cleanup step once the stack empties and all players pass [514.3a][704.3].
- When an effect directly ends the turn or ends the combat phase (e.g., an effect like Mandate of Peace ending combat), the game still checks SBAs as part of that special resolution process, even though no player gets priority and no triggered abilities are put on the stack in that moment [724.1c][724.2c].

This process is the same regardless of how many players are in the game—SBAs aren't tied to any one player's turn or priority, and in multiplayer or Commander games they're checked identically before any player (active or non-active) would receive priority, at cleanup, and whenever turn/combat-ending effects resolve [704.2][704.3].

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
citations: ['104.3a', 'Concede', '405.6g', '101.1', '723.6', '810.8b']
text: You may concede a game at any time. Conceding immediately causes you to leave that game and lose it [104.3a][Concede]. This right is absolute: it isn't a game action that uses the stack, so it can happen even in the middle of resolving something else [405.6g], and it's the one thing that can never be overridden or restricted by a card's text, since rule 101.1 explicitly carves out conceding as the sole exception to 'the card takes precedence' rule [101.1]. It also can't be taken away from you by another player's control effect — even if you're being controlled by another player's spell or ability, you may still concede on your own [723.6]. In a Two-Headed Giant game, if one player on a team concedes, that player's entire team leaves the game immediately and the team loses [810.8b]. The rules provided don't give separate special-case wording for Commander or Emperor beyond pointing to rule 903.10 and 809.5 for additional losing conditions, but the basic right to concede at any time is universal and not limited to two-player games.

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
citations: ['102.1', '508.2', '509.2', '504.2', '507.2', '510.3', '505.6', '507.1', '506.2b', '805.4a', '101.4e', '805.9']
text: The active player is simply the player whose turn it currently is. Every other player at the table is a nonactive player [102.1]. This stays true throughout the turn's phases and steps: at the start of upkeep, draw, combat, main phases, etc., the active player is the one who gets priority first in each of those steps (e.g. beginning phase, precombat/postcombat main phases, combat phase, ending phase) [508.2][509.2][504.2][507.2][510.3][505.6].

During the combat phase specifically, the active player is also the attacking player - the one whose creatures may attack. In a two-player game, the nonactive player is the defending player. In a multiplayer game not using the shared team turns variant, the active player picks one opponent to be the defending player as a turn-based action that doesn't use the stack [507.1][506.2b].

If you're playing with the shared team turns option (a multiplayer variant where teammates share a single turn), the concept scales up to teams: the team whose turn it is is the active team, and every other team is a nonactive team. During combat under that option, the active team is the attacking team and the nonactive team is the defending team [805.4a][506.2b].

Two more wrinkles worth knowing:
- When multiple players need to make choices or take actions simultaneously (including at the very start of the game, before a 'turn' technically exists), they resolve those choices in Active Player, Nonactive Player (APNAP) order: the active player (or the starting player, if it's before turns begin) decides first, then each other player in turn order, and only after everyone has decided do the actions actually happen together [101.4e].
- If a card or ability's text refers to 'the active player' in a context where there could be more than one active player concept in play (e.g. some unusual multiplayer setups), that phrase points to one specific active player, and whoever controls the ability gets to choose which active player it means when the ability's effect resolves [805.9].

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
citations: ['117.3c', '117.3b', '117.3a']
text: After a spell is cast (regardless of who casts it), priority doesn't automatically shift to the active player. Instead, rule [117.3c] states: 'If a player has priority when they cast a spell, activate an ability, or take a special action, that player receives priority afterward.' So if a nonactive player casts a spell, that same nonactive player receives priority again immediately after the spell finishes being cast (i.e., once it's on the stack). The active player only automatically receives priority in specific situations, such as after a spell or ability resolves [117.3b], or at the start of a step/phase [117.3a] — not immediately after another player casts a spell. This rule applies the same way in multiplayer/Commander games: whichever player (active or not) had priority and cast the spell is the one who gets priority back right after doing so, before anyone else acts.

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
citations: ['117.3c', '117.3b']
text: After the active player casts a spell (putting it on the stack), the active player is the one who gets priority next, not any opponent. This follows from rule [117.3c]: if a player has priority when they cast a spell, activate an ability, or take a special action, that same player receives priority afterward. Since the active player normally already had priority in order to cast the spell in the first place, they simply keep/receive priority again once the spell is on the stack, and can then choose to cast another spell, activate an ability, or pass. Only after the active player passes priority does it move to the next player in turn order (e.g., in a multiplayer or Commander game, to the next player in APNAP order), and so on around the table until all players pass in succession, at which point the spell resolves.

This is distinct from what happens after a spell or ability actually resolves: rule [117.3b] says the active player receives priority after a spell or ability (other than a mana ability) resolves, which is a separate moment in the process from the casting itself.

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
citations: ['117.3c', '601.2i', '116.3', '117.1', '608.2g']
text: Yes. This is commonly called "holding priority." Rule [117.3c] states that if a player has priority when they cast a spell, activate an ability, or take a special action, that player receives priority again immediately afterward. This is echoed in [601.2i], which says that once a spell finishes being cast, if the spell's controller had priority before casting it, they get priority back rather than passing it automatically. The same applies to special actions per [116.3].

What this means in practice: as long as you had priority to begin with, you can cast a spell, get priority back, and cast another spell (or activate an ability) in response to your own spell before anyone else gets a chance to act — the stack builds up in the order you put things on it. You can keep doing this as many times as you like, provided the game state and legality checks allow each new spell/ability. Only once you choose to pass priority does the next player in turn order (or, in multiplayer/Commander, the next player in the standard turn order sequence) get a chance to respond. Note that [117.1] establishes this priority system applies generally to any player able to take game actions, so this works identically for the active player or a nonactive player in a two-player game, and for any player at the table in a multiplayer or Commander game.

One nuance: this only works when you actually have priority to give yourself back. During resolution of a spell or ability, if that spell/ability instructs you to cast another spell as part of its effect, [608.2g] specifies no player receives priority after that spell is cast that way — it's a different mechanism, not "holding priority" in the normal sense.

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
citations: []
text: 

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
citations: ['Delayed Triggered Ability', '603.7', '603.7a', '603.7b', '603.7c', '603.7d', '603.7e', '603.7f', '603.7g', '603.7h', '603.12', '610.2', '107.3n', '603.3a']
text: A delayed triggered ability is a triggered ability that isn't created by a permanent's or card's printed static text at the time it's read, but is instead generated later by the resolution of a spell or ability, by a replacement effect being applied, or by a static ability that lets a player take an action [Delayed Triggered Ability][603.7]. Even though it's created 'after the fact,' it still works like any other triggered ability: it contains the word 'when,' 'whenever,' or 'at' somewhere in its text (even if not at the very start), and once its trigger condition is met, it goes on the stack the next time a player would receive priority [603.3a].

Key points about how delayed triggered abilities work:
- They're most often created by one-shot effects that tell you to do something later in the game rather than immediately [610.2].
- A delayed triggered ability only starts existing once it's actually been created by the resolving spell/ability/replacement effect/static-ability action - it won't trigger off an event that happened before it existed, even if that event would otherwise match its trigger condition. If the event it's waiting for becomes impossible (e.g., the referenced object already left the battlefield before the ability was even created), it simply never triggers. If the event already happened and won't happen again for a while, the ability waits for the next occurrence [603.7a].
- Normally it triggers only once, the next time its trigger event occurs, unless the ability specifies a duration like 'this turn'; if the event happens more than once simultaneously with no stated duration, its controller chooses which occurrence causes it to trigger [603.7b].
- If it refers to a specific object, it still affects that object even if it changes characteristics, but not if that object is no longer in the zone it's expected to be in when the delayed ability would resolve - notably, an object that left and returned to a zone is a new object and won't be affected [603.7c].
- Source and controller depend on what created the delayed ability: a spell's delayed ability has that spell as its source and is controlled by whoever controlled the spell as it resolved [603.7d]; one created by an activated/triggered ability has that ability's source, controlled by whoever controlled that ability as it resolved [603.7e]; one created by a replacement effect from a static ability has that object as source, controlled by whoever controlled the object when the replacement effect was applied [603.7f]; one created by a static ability that lets a player act has that object as source, controlled by whoever controlled the object when the action was taken [603.7g]. This differs from ordinary triggered abilities, which are controlled by whoever controlled their source at the time they triggered, unless they're delayed [603.3a].
- If an activated or triggered ability creates a delayed trigger that fires after a certain number of resolutions in a turn, that delayed ability is created only once, at the appropriate resolution [603.7h].
- If a delayed triggered ability refers to X and doesn't define its own value, and the spell/ability that created it had an X value chosen for a cost, it uses that same X value [107.3n].

A special case is the 'reflexive triggered ability': a resolving spell or ability may instruct a player to take an action and create a triggered ability that triggers 'when [a player] does or doesn't' take that action, or 'when [something happens] this way.' These follow the delayed triggered ability rules, except they're checked immediately upon creation, based on whether the trigger event occurred earlier during the resolution of the ability that created them [603.12].

In multiplayer or Commander games, these same rules for source and controller determine who controls the delayed ability and who makes any choices tied to it - there's no special multiplayer exception noted here.

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
citations: ['113.3a', '113.6', '113.6e', '604.5', '604.6', '610.5', '601.2a', '611.3d', '603.3', '405.1', '405.4', '113.9']
text: Yes. Non-permanent spells (instants and sorceries) can absolutely have abilities.

1. **Spell abilities** – Any text on an instant or sorcery card that isn't an activated ability, a triggered ability, or a qualifying static ability is treated as a *spell ability*: instructions that are followed while the spell is resolving on the stack [113.3a].

2. **Activated and triggered abilities** – Instants and sorceries can also carry activated or triggered abilities. Like any activated/triggered ability, once such an ability triggers or is activated it becomes its own object on the stack, separate from the spell, with only the text of the ability [603.3][405.1][405.4]. These aren't spells themselves, so they can't be countered by counterspell effects that target only spells [113.9].

3. **Static abilities** – Normally, a static ability of a non-permanent object only works while that spell is on the stack [113.6]. There are specific exceptions: abilities that talk about countering the spell, that let you pay an alternative cost, or that let you cast the spell without paying its mana cost all function while the spell is on the stack [604.5]. Abilities that restrict or modify how the object itself can be cast function in any zone you could cast it from (usually your hand) as well as on the stack [113.6e]. And abilities phrased as "You may cast [this card]...," "You can't cast [this card]...," or "Cast [this card] only..." apply in whatever zone you'd cast it from [604.6].

4. **One-shot casting effects** – Some static abilities from other sources cause a spell to gain an ability as it's put on the stack; these apply the moment the spell is cast [610.5][601.2a][611.3d].

This applies the same way in multiplayer/Commander games — there's nothing in these rules that differs by player count; the ability's controller is whoever cast the spell or controlled its source when it triggered [405.4].

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
citations: ['702.61a', '702.61b', '113.4', '605.3a']
text: Yes. Split second (rule 702.61a) says that while a spell with split second is on the stack, players can't cast other spells or activate abilities that aren't mana abilities. Mana abilities are explicitly carved out of that restriction. Rule 702.61b confirms that players may still activate mana abilities and take special actions while a split second spell is on the stack.

This works because mana abilities are special: per rule 113.4, mana abilities don't use the stack, and under certain circumstances can be activated even without priority. Rule 605.3a further clarifies that a player may activate a mana ability whenever they have priority, whenever they're casting a spell or activating an ability requiring mana payment, or whenever a rule or effect asks for a mana payment - even mid-resolution of another spell or ability. Since split second only blocks casting spells and activating non-mana abilities, mana abilities remain fully usable the whole time the split second spell is on the stack, in any number of players' game (including multiplayer/Commander).

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
citations: ['608.1', '701.6a', '701.6b', '112.1']
text: When both players pass priority in succession, the spell on top of the stack resolves first [608.1]. Since Counterspell is on top of the stack, it resolves before Divination gets a chance to. Counterspell's resolution counters (cancels) Divination as its targeted spell: to counter a spell means to remove it from the stack so it doesn't resolve and none of its effects occur, and the countered spell (Divination) goes to its owner's graveyard [701.6a]. Divination never resolves — you don't draw any cards — and you don't get back any mana or other costs you paid to cast it [701.6b]. Divination only remains 'on the stack as a spell' until it resolves or is countered [112.1], and being countered ends that existence entirely; nothing in the Divination card causes it to resolve, so the effect is simply skipped. This applies the same way in multiplayer or Commander games — whoever controls the countered spell puts it into their own graveyard, and no other player 'inherits' any effect from it.

Card data from Scryfall (scryfall.com).

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
citations: ['702.19b', '120.4a', '510.1a', 'Lethal Damage', '702.2c']
text: You must assign combat damage equal to at least the blocking creature's toughness before any excess can trample through to the defending player. Vampire Nighthawk has toughness 3, so you need to assign 3 damage to it as lethal damage; any damage beyond that (Charging Rhino has power 4, so 1 damage) can be assigned to the defending player instead.

Important: deathtouch on the *blocker* (Vampire Nighthawk) is irrelevant here — deathtouch only makes damage dealt *by* a source with deathtouch count as lethal in tiny amounts. Since Charging Rhino itself doesn't have deathtouch, the amount of damage it must assign to be considered lethal to the blocker is based on the blocker's toughness (and any damage already marked on it from other sources this combat damage step), not on the blocker's own deathtouch ability. If Charging Rhino already had damage marked on Vampire Nighthawk from an earlier source this step, that would reduce how much more is needed to reach lethal.

You (as the attacking creature's controller) aren't required to assign full lethal damage to the blocker, but if you don't, you can't assign any damage to the defending player at all — you'd have to put all 4 damage on the blocker instead.

Card data from Scryfall (scryfall.com).

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
citations: ['702.108a', 'Monastery Swiftspear ruling #1', 'Monastery Swiftspear ruling #2', '702.85a', '608.2g', '601.2i']
text: Monastery Swiftspear's prowess resolves before the cascaded spell, not after.

Here's the sequence: Shardless Agent is an Artifact Creature spell, so casting Shardless Agent itself does not trigger prowess [Monastery Swiftspear ruling #1]. However, cascade triggers when you cast Shardless Agent [702.85a], and its resolution includes exiling cards and then, if the mana-value condition is met, casting the exiled nonland card during the cascade ability's resolution, per the rules for casting spells during resolution [608.2g]. That act of casting the exiled spell is itself the casting of a spell [601.2i], and if that exiled card is noncreature, it causes Monastery Swiftspear's prowess to trigger [702.108a].

Any abilities that trigger during the resolution of a spell or ability (including cascade's cast-during-resolution step) are put on the stack the next time a player would receive priority — which is after the cascade ability finishes resolving. Since the cascaded spell is placed on the stack during cascade's resolution and prowess's trigger is placed on the stack afterward, prowess ends up on top of the cascaded spell on the stack. As with any prowess trigger, it goes on the stack on top of the spell that caused it and resolves before that spell [Monastery Swiftspear ruling #2]. So the stack order (top to bottom) ends up: prowess trigger, the cascaded noncreature spell, then Shardless Agent itself.

So prowess resolves before the cascaded spell resolves, giving Monastery Swiftspear +1/+1 until end of turn first, and then the cascaded spell resolves afterward. This holds regardless of number of players at the table, since it depends only on stack mechanics, not turn order.

Card data from Scryfall (scryfall.com).

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
citations: ['704.3', '117.2d', '704.5g', '302.7', '120.6', '120.5']
text: Yes — but it happens even earlier than you might expect: the Grizzly Bears (a 2/2) already has damage marked equal to its toughness, so it's already "been dealt lethal damage" as far as the rules are concerned. Whenever a player would receive priority, the game checks for state-based actions and performs them all before that player actually gets priority [704.3][117.2d]. One of those state-based actions is: if a creature has toughness greater than 0, has damage marked on it, and the marked damage is ≥ its toughness, it is destroyed [704.5g][302.7][120.6]. Damage dealt by a source doesn't itself destroy a creature — it's this state-based action that puts it into its owner's graveyard [120.5]. Since damage remains marked on a creature until the cleanup step (or until it regenerates) [120.6][302.7], a Grizzly Bears sitting with 2 damage already marked would be destroyed as a state-based action the moment any player would next receive priority — which happens before you could even finish casting Lightning Bolt, since you need priority to cast a spell in the first place. So the Bears dies well before Lightning Bolt ever resolves; if it's already dead, your Lightning Bolt either has no legal target left (if that was the only target) or you'd need to choose a different target when you cast it. This holds the same way in a multiplayer or Commander game, since state-based actions and priority work identically regardless of player count [704.3].

Card data from Scryfall (scryfall.com).

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
citations: ['500.6', '603.2b', '603.3b', '805.7', '503.1a', '117.3a']
text: Both abilities trigger at the same moment: the instant the upkeep step begins (rule 500.6, 603.2b). "At the beginning of your upkeep" (Phyrexian Arena) and any "at the beginning of upkeep" ability someone else controls both fire the moment that step starts, before anyone gets priority.

Because it's your upkeep, you are the active player. Per rule 603.3b (and the equivalent multiplayer rule 805.7), when multiple triggered abilities have triggered since a player/team last had priority, they're put on the stack in APNAP order: the active player first chooses the order for all triggered abilities they control (here, just Phyrexian Arena, so there's nothing to order), then each nonactive player, in turn order, does the same for the abilities they control. So your opponent chooses where their own trigger goes relative to any other abilities they control, but they don't get to interleave it with yours - your ability goes on the stack first (as the active player's), and then your opponent's trigger goes on top of it.

The practical result: since the stack resolves last-in-first-out, your opponent's upkeep trigger resolves before your Phyrexian Arena trigger does. Only after all these upkeep triggers are on the stack does the active player (you) actually receive priority (rules 503.1a, 117.3a).

In a multiplayer/Commander game with more than one nonactive player, the same process applies but the nonactive players place their triggered abilities on the stack one at a time in turn order after the active player, so the last player in turn order's upkeep trigger would end up resolving first.

Card data from Scryfall (scryfall.com).

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
citations: ['702.27a', '112.1a', '707.10', '707.10b', '707.10d', '704.5e', 'Fork ruling #8', 'Fork ruling #10']
text: Only the original card comes back to your hand — the Fork copy gives you nothing, so you end up with exactly one physical copy of the sorcery in hand.

Here's why: Buyback is a pair of static abilities on the spell: paying the buyback cost means "put this spell into its owner's hand instead of into that player's graveyard as it resolves" [702.27a]. That applies to the original sorcery card, so when it resolves it goes to your hand instead of the graveyard.

When Fork resolves, it puts a copy of your sorcery onto the stack; that copy is itself a spell, but it has no physical card behind it — the Fork card itself goes to the graveyard, leaving only a cardless copy on the stack [112.1a] [707.10] [Fork ruling #10]. Because copying a spell also copies all the decisions made for it, including which additional/alternative costs were paid, the copy is also considered to have had its buyback cost paid [707.10b] [707.10d]. So as that copy resolves, its own buyback ability tries to move "this spell" to your hand — but since it's not a card, there's nothing to put there. As soon as a copy of a spell is in a zone other than the stack, the state-based action rule causes it to simply cease to exist [704.5e]. This matches how Fork explicitly rules: if you copy a spell for which buyback was paid, you get nothing back, since the copied spell has no card to give you [Fork ruling #8].

This works the same regardless of how many players are at the table — the copy is controlled by whoever cast Fork [707.10], but it still has no card representation, so nobody gets an extra card back in a multiplayer or Commander game either.

End result: after everything resolves, you have exactly 1 copy of the sorcery card back in your hand (the original), not 2.

Card data from Scryfall (scryfall.com).

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
citations: ['Mimic Vat ruling #0', 'Mimic Vat ruling #6', 'Mimic Vat ruling #4', '110.5d', 'Mimic Vat', 'Lightning Bolt']
text: No, you won't get a token in this situation. Here's why: When your face-down manifested card (which is secretly Lightning Bolt, an instant) dies, it stops being a face-down permanent and simply becomes the Lightning Bolt card sitting in your graveyard — face-down status only applies to permanents on the battlefield, not to cards in other zones. Mimic Vat's imprint trigger lets you exile that card (Lightning Bolt) when it dies, so it can be legally exiled with Mimic Vat. However, Mimic Vat's activated ability creates 'a token that's a copy of a card exiled with this artifact,' and you cannot create a token copy of a nonpermanent card like an instant or sorcery. As confirmed by Mimic Vat's own rulings, if the creature that died was actually a manifested instant or sorcery card, Mimic Vat may end up with a nonpermanent card exiled, and no token is created when you activate the copy ability in that case. This holds true regardless of how many players are in the game — the restriction is about the card's type, not about turn order or opponents.

Card data from Scryfall (scryfall.com).

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
citations: ['Fiend Hunter ruling #1', 'Lithoform Engine ruling #4', '607.3']
text: Yes. Fiend Hunter's leaves-the-battlefield ability ("return the exiled card to the battlefield under its owner's control") is linked to its enters-the-battlefield exile ability. When you copy the enters-the-battlefield ability with Lithoform Engine and choose a new target, the copy is still linked to the same leaves-the-battlefield ability — copies of a linked ability remain linked to the corresponding ability, per Lithoform Engine's own ruling. Because two separate exile events now occurred as a direct result of that (copied) ability, the leaves-the-battlefield ability's reference to "the exiled card" refers to both exiled cards. Under the general linked-abilities rule, when an ability that says "the exiled card" actually has multiple cards exiled behind it (e.g., due to a copy), it performs its action — returning the card to the battlefield — on each of them. So when Fiend Hunter leaves the battlefield, both exiled creatures return to the battlefield under their owners' control simultaneously, each as a new object (any counters, auras, etc. from before exile do not carry over, per Fiend Hunter's normal behavior).

Card data from Scryfall (scryfall.com).

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
citations: ['702.26d', '702.26c', "Teferi's Protection ruling #21", "Teferi's Protection ruling #17", 'Banishing Light ruling #1']
text: No. Phasing does not count as the permanent leaving the battlefield. Rule [702.26d] explicitly states that zone-change triggers don't trigger when a permanent phases in or out, and the phasing event 'doesn't actually cause a permanent to change zones.' Teferi's Protection ruling #17 confirms phasing out doesn't cause any 'leaves the battlefield' abilities to trigger. Since Banishing Light's exile effect only ends 'until this enchantment leaves the battlefield,' and phasing out is not leaving the battlefield, that condition is never met while Banishing Light is phased out. Teferi's Protection ruling #21 directly addresses this: any one-shot effects waiting for something like Banishing Light to leave the battlefield 'won't happen when a permanent phases out.' So the opponent's creature stays exiled the whole time your Banishing Light is phased out. When Banishing Light phases back in (during your next untap step, per Teferi's Protection's own wording), it's simply treated as though it was continuously on the battlefield the whole time [702.26c], and the exiled creature remains exiled - it only returns if Banishing Light actually and permanently leaves the battlefield later (e.g., is destroyed or exiled), at which point the delayed trigger from Banishing Light's ability would resolve as normal (see Banishing Light ruling #1, which shows the exile only reverses if the ability triggering the return actually resolves after Banishing Light leaves for real).

Card data from Scryfall (scryfall.com).

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
citations: ['601.2i', '117.2a', '405.1', '603.1a', '113.9', '115.1a', 'Emrakul, the Promised End ruling #2', 'Emrakul, the Promised End ruling #14', 'Counterspell']
text: Yes, the opponent's Counterspell can target Emrakul while it's a spell on the stack. Emrakul's protection from instants (which protects against instant spells' targeting and damage) only applies while Emrakul is a permanent on the battlefield, not while it's a spell on the stack – as confirmed by the ruling that Emrakul "may be the target of a spell that targets it while on the stack, such as Syncopate" (Emrakul, the Promised End ruling #2). Counterspell says "Counter target spell," and while Emrakul is on the stack it's a spell, not yet a permanent creature, so protection doesn't stop the targeting [115.1a].

However, even if Counterspell resolves and counters the Emrakul spell, you still gain control of your opponent during their next turn. Here's why: Emrakul's ability "When you cast this spell, you gain control of target opponent during that player's next turn..." is a triggered ability that triggers at the moment the spell becomes cast, which happens as soon as all the steps of casting (proposal, targeting, and paying costs) are completed [601.2i]. That trigger is placed on the stack the next time a player would receive priority [117.2a], as its own object separate from the Emrakul spell itself [405.1]. Once that triggered ability is on the stack, it is no longer tied to whether the Emrakul spell resolves — a triggered ability, once triggered, will go on to resolve on its own regardless of what later happens to the spell that caused it to trigger [603.1a].

Additionally, Counterspell can only counter spells, not triggered abilities — "Activated and triggered abilities on the stack aren't spells, and therefore can't be countered by anything that counters only spells" [113.9]. So even a well-timed Counterspell aimed at the Emrakul spell cannot also stop the "when you cast this spell" trigger. So even though Counterspell can legally target and counter the Emrakul spell itself, the take-control trigger still resolves independently, and you'll control your opponent during their next turn (and they'll take an extra turn after that, per Emrakul's ability) — you just won't get the 13/13 flying trampler with protection from instants onto the battlefield.

One extra multiplayer note: if more than one player has cast an Emrakul-style effect targeting the same opponent, whichever effect's control-grant is the last one created is the one that actually applies, though each triggered ability still separately grants that player an extra turn afterward (Emrakul, the Promised End ruling #14).

Card data from Scryfall (scryfall.com).

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
citations: ['702.85a', '702.85c', '712.11', '712.11c', '712.11d', '712.8c', 'Valki, God of Lies // Tibalt, Cosmic Impostor ruling #16']
text: Yes, exiling Valki/Tibalt is a legal cascade hit, but casting the Tibalt side for free requires a much bigger cascade spell than casting the Valki side would.

Why it's a legal hit: Cascade [702.85a] tells you to exile cards from the top of your library until you hit a nonland card whose mana value is less than the cascading spell's mana value. While a card is sitting in your library/exile (i.e., not on the stack), a double‑faced card is evaluated using its default, front‑up characteristics [712.11], [712.11c]. Valki, God of Lies // Tibalt, Cosmic Impostor's card data confirms this: its mana value off the stack is 2 (Valki's front‑face cost {1}{B}), not 7. So as long as your cascade spell's mana value is greater than 2, exiling this card satisfies the 'mana value less than this spell's mana value' requirement, regardless of the fact that its back face is a seven‑mana planeswalker.

Casting it for free: Cascade lets you cast the exiled card 'if the resulting spell's mana value is less than this spell's mana value.' You're allowed to choose either face of a modal double‑faced card when an effect (like cascade) lets you cast a card from a group, as long as the chosen face fits the effect's criteria [Valki, God of Lies // Tibalt, Cosmic Impostor ruling #16]. However, the front‑face‑only mana‑value override described in [712.8c] applies specifically to nonmodal double‑faced cards being cast 'transformed' or 'converted' via a special ability (like Disturb) — it does not apply to the normal act of choosing a face of a modal double‑faced card. So if you choose to cast the Tibalt face, the resulting spell has Tibalt's own characteristics, including its own mana value from its printed cost {5}{B}{R}, which is 7.

Putting it together: the cascade trigger only checks the exiled card's off‑stack mana value (2) to determine whether it's a valid hit — that condition is met by almost any cascade spell. But to actually cast the Tibalt face for free, your cascade spell's mana value must be greater than 7 (Tibalt's own mana value). If your cascade spell's mana value is, say, 5, you could still cast the Valki front face for free (mana value 2 < 5), but not the Tibalt face. If you don't want to cast either face, the card is put on the bottom of your library in a random order along with any other uncast exiled cards, per the cascade ability's text [702.85a] (and if you had multiple instances of cascade, each would trigger and resolve separately [702.85c]). This works the same in multiplayer/Commander games — there's no special exception for more than two players in the cascade or double‑faced card rules provided.

Card data from Scryfall (scryfall.com).

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
citations: ['707.10', '707.10b', '707.10d', '111.13', '707.12', 'Lithoform Engine ruling #5', 'Lithoform Engine ruling #6', 'Emrakul, the Promised End ruling #14']
text: Let's break this into the two Lithoform Engine activations.

1) Copying the "cast trigger": Emrakul's triggered ability ("When you cast this spell, you gain control of target opponent during that player's next turn. After that turn, that player takes an extra turn.") is still on the stack when you copy it. A copied triggered ability is itself a full copy of that ability, with the same target unless you choose a new one [707.10, 707.10b, 707.10d]. So you now have two separate instances of this ability on the stack, each targeting the same opponent (assuming you don't retarget the copy).

Each instance, when it resolves, does two things: (a) creates a continuous effect giving you control of that opponent's next turn, and (b) sets up a delayed trigger that after that controlled turn ends, the opponent takes an extra turn. Per the Emrakul ruling on multiple such effects hitting the same player, the control-of-turn effects overwrite each other — only the last one to resolve actually determines who controls that turn — but each instance's "after that turn, take an extra turn" delayed trigger is independent and still happens [Emrakul, the Promised End ruling #14]. So you end up controlling the opponent's next turn only **once** (the two control effects target the same single "next turn," and since you control both, the overwrite is invisible in terms of who's in charge), but the opponent will then take **two** extra turns in a row afterward (one from the original trigger, one from the copy). This logic holds the same way in a multiplayer/Commander game if you retarget the copy at a different opponent — then you'd control two different players' next turns and each would separately owe an extra turn; but as described (no retarget), it's one controlled turn plus two stacked extra turns for the same opponent.

2) Copying the Emrakul spell itself: Lithoform Engine's {4} ability lets you copy a permanent spell you control, and the resulting copy becomes a token as it resolves, with the full characteristics of Emrakul, the Promised End (13/13 flying, trample, protection from instants) [111.13; Lithoform Engine ruling #5]. So yes — you get a second Emrakul, as a token permanent, once that copy resolves (assuming nothing removes it from the stack first).

3) Does copying the spell give you another "gain control" trigger? No. A copy of a spell created this way is put directly onto the stack and is never cast — casting triggers (like Emrakul's "When you cast this spell..." ability) only fire when a spell is actually cast, and rule 707.10 explicitly states a copy of a spell isn't cast. Lithoform Engine's own ruling confirms this: creating the copy won't cause cast-triggered abilities to trigger again [707.10; 707.12; Lithoform Engine ruling #6]. So the second Emrakul token enters without generating any additional control-a-turn trigger.

Bottom line: you control one opponent turn, that opponent ends up taking two extra turns afterward, you get a second 13/13 Emrakul as a token, and the token copy does not generate a new cast trigger.

Card data from Scryfall (scryfall.com).

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
citations: ['707.10', '707.10b', 'Mimic Vat ruling #4', 'Mimic Vat ruling #6', 'Lithoform Engine ruling #3']
text: Yes. Mimic Vat's activated ability reads "Create a token that's a copy of a card exiled with this artifact. It gains haste. Exile it at the beginning of the next end step." When you activate Lithoform Engine's first ability targeting that activated ability on the stack, it puts a copy of that ability onto the stack (per rule 707.10, copying an activated ability means putting a copy of it onto the stack; the copy isn't itself "activated," but it functions the same way when it resolves). You now have two instances of Mimic Vat's ability on the stack: the original and the copy.

Each instance resolves independently. Per Mimic Vat's own ruling, the token created is a copy of whatever card is exiled with Mimic Vat at the time that particular instance resolves (Mimic Vat ruling #4), and if no card happens to be exiled at that time, no token is created (Mimic Vat ruling #6). Since neither the original ability nor its copy removes the exiled card from exile (that only happens via Mimic Vat's separate triggered ability when another nontoken creature dies), the same imprinted card remains exiled with Mimic Vat when both instances resolve. So both the original ability and the copy will each create a token that's a copy of that exiled card, each with haste and each set to be exiled at the beginning of the next end step.

End result: you get two token copies of the imprinted creature.

Card data from Scryfall (scryfall.com).

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
citations: ['601.2f', '118.7', '118.7a', '107.3b', 'Trinisphere ruling #0', 'Trinisphere ruling #1', 'Awaken the Woods']
text: Awaken the Woods has the mana cost {X}{G}{G}. When you determine its total cost you (1) pick X, (2) apply any cost reductions to the generic-mana part of the cost, and (3) apply Trinisphere's increase if what's left is still less than three mana [601.2f], [Trinisphere ruling #0].

Your green-cost reducer can only ever reduce the generic component of the cost, never the colored {G}{G} [118.7a]. X itself counts as that generic component.

If you choose X=0: the printed cost is {0}{G}{G}. There's no generic mana to reduce (it's already {0}), so your reducer does nothing, and the cost after reductions is still {G}{G} — only two mana, which is less than three. Trinisphere then kicks in and raises the total cost to three mana, giving a final total cost of {1}{G}{G} (the extra generic mana can be paid with any color or colorless mana) [118.7], [Trinisphere ruling #0]. Since X=0, Awaken the Woods creates zero Forest Dryad tokens (Card data: Awaken the Woods). So with X=0 you'd be paying three mana for absolutely nothing — a pure waste, since your reduction effect gets completely eaten by Trinisphere's floor.

What you should actually do: pick X=2. The printed generic component is then 2, your reducer knocks it down by {1} to 1, giving a cost of {1}{G}{G} — three mana total. Because that's not less than three mana, Trinisphere's increase doesn't trigger at all [118.7], [Trinisphere ruling #0]. So for the exact same three-mana total cost you'd pay at X=0, you instead get two 1/1 Forest Dryad tokens. That's the best 'floor' value: any X below 2 wastes mana to Trinisphere's tax for fewer or no tokens, while X=2 is the smallest X where your reduction fully offsets Trinisphere and you're paying full price-per-token efficiency (each additional point of X above 2 simply adds one more generic mana for one more token, at {X-1}{G}{G} total).

Note: this all assumes normal casting with mana costs, not an alternative-cost route; if some effect let you cast it without paying its mana/alternative cost including X, X would default to 0 under a different rule, but that's not the situation here [107.3b].

Card data from Scryfall (scryfall.com).

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
citations: ['Grist, the Hunger Tide ruling #1', 'Animate Dead ruling #0', 'Animate Dead ruling #1', 'Animate Dead ruling #4']
text: Yes, you can cast Animate Dead targeting Grist while it's in your graveyard. Grist, the Hunger Tide's own text says that anywhere except the battlefield it is a Legendary Planeswalker Creature — Grist Insect, so while sitting in the graveyard it counts as a creature card and is a legal target for Animate Dead, which enchants a creature card in a graveyard [Grist, the Hunger Tide ruling #1] [Animate Dead ruling #1].

When Animate Dead resolves, it returns Grist to the battlefield under your control and tries to attach itself to it [Animate Dead ruling #1]. However, Grist's ability that makes it a creature only applies 'as long as Grist isn't on the battlefield.' The instant it enters the battlefield it is no longer a creature — it's just a planeswalker [Grist, the Hunger Tide ruling #1]. Because Animate Dead's 'enchant creature put onto the battlefield with this Aura' requirement is no longer met (the permanent isn't a creature), Animate Dead can't legally stay attached to it. As with the protection-from-black example given in the rulings, Animate Dead will be put into your graveyard as a state-based action because it's attached to an illegal object, and this triggers its 'when this Aura leaves the battlefield' delayed ability [Animate Dead ruling #4]. That trigger then resolves and, since Grist (now a planeswalker) is still on the battlefield, you as its controller must sacrifice it immediately.

Note also that if Animate Dead somehow isn't on the battlefield when its own triggered ability resolves, none of its effects happen and Grist stays in the graveyard [Animate Dead ruling #0] — but that's not the issue here; the problem is Grist losing its creature type the moment it lands on the battlefield, causing an almost immediate sacrifice.

Card data from Scryfall (scryfall.com).

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
citations: ['Skullbriar, the Walking Grave', 'Skullbriar, the Walking Grave ruling #1', 'Skullbriar, the Walking Grave ruling #2', 'Skullbriar, the Walking Grave ruling #3', '122.2', '903.9b', 'Doubling Season']
text: Yes — Skullbriar keeps all four +1/+1 counters, but Doubling Season does not double them.

Skullbriar's own ability overrides the normal counter rule. Normally, counters on a permanent cease to exist when it changes zones [122.2], but Skullbriar's text specifically says 'Counters remain on Skullbriar as it moves to any zone other than a player's hand or library.' Dying and moving to the command zone (via the commander replacement effect in rule [903.9b], since your owner may choose to put a commander into the command zone instead of the graveyard) is not a move to hand or library, so the four counters stay on it there. From the command zone Skullbriar's zone-changes when you cast it — command zone to the stack, then stack to the battlefield — are likewise not moves to hand or library, so the counters remain on it the whole way, including when it re-enters the battlefield. This works even though Skullbriar is a legendary creature that qualifies as your commander; nothing about being a commander changes this, and there's no meld/merged-permanent complication here since Skullbriar isn't such a permanent.

Doubling Season won't double these counters. Doubling Season's counter-doubling clause only applies when 'an effect would put one or more counters on a permanent you control.' Skullbriar's retained counters aren't being 'placed' or 'put' on it by an effect when it re-enters — they simply remain on it as part of its continuous static ability, per the official ruling that Doubling Season and similar effects (like Melira, Sylvok Outcast) don't interact with these retained counters. So Skullbriar re-enters the battlefield from the command zone with exactly the four +1/+1 counters it already had, not eight.

This applies the same way in multiplayer or Commander games generally — there's nothing player-count-specific about how the retention ability or the command-zone replacement effect works.

Card data from Scryfall (scryfall.com).

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
citations: ['724.1d', 'Sundial of the Infinite ruling #4', 'Final Fortune ruling #1']
text: No — you don't lose the game in that scenario.

Final Fortune's delayed triggered ability is worded to trigger "at the beginning of that turn's end step" — meaning the end step of the specific extra turn Final Fortune granted, not just any future end step. When you activate Sundial of the Infinite's ability during that extra turn (before its end step begins), the effect skips the current phase/step straight to the cleanup step, meaning any remaining steps of that turn — including the end step — are skipped entirely and never occur [724.1d]. Sundial's process exiles the stack, removes creatures from combat, checks state-based actions, and then jumps to cleanup without any player getting priority and without putting triggered abilities on the stack [Sundial of the Infinite ruling #4].

Because that turn's end step never happens, the delayed trigger tied specifically to "that turn's end step" never gets a chance to trigger — there is no future occurrence of *that* turn's end step to defer to, since the turn itself is over. This is the same underlying principle behind the ruling that if the extra turn granted by Final Fortune ends up being skipped, you don't lose the game [Final Fortune ruling #1]. Ending the turn early via Sundial before the end step produces the same practical result: the loss condition never triggers.

This holds the same way in multiplayer or Commander games — the effect only cares about whether that specific end step occurs, regardless of how many players are at the table.

Card data from Scryfall (scryfall.com).

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
citations: ['707.6', '616.1c', '707.10c', 'Clone ruling #2', 'Clone ruling #5', 'Clone ruling #0']
text: Clone's copying isn't an activated or triggered ability that uses the stack, so there's no window for anyone to "respond" to it in the normal sense. It's a replacement effect that modifies how Clone enters the battlefield. As Clone's spell resolves and it's about to enter the battlefield, its controller (you) applies the replacement effect described by its text ("You may have this creature enter as a copy of any creature on the battlefield") and makes the choice right then, as part of the entering-the-battlefield event itself [707.6]. You're choosing among creatures that are already on the battlefield at that moment — if another creature is entering at the exact same time as Clone, it isn't yet 'on the battlefield' for this purpose, so Clone can't copy it [Clone ruling #2]. You can also decline to copy anything, in which case Clone just enters as a 0/0 Shapeshifter [Clone ruling #5].

Because this choice isn't a target (Clone's ability doesn't target the chosen creature) [Clone ruling #0], and because it isn't a spell or ability being cast or activated, opponents don't get priority to respond to the act of choosing itself — there's no 'choosing a copy target' step on the stack the way there is with targeted spells [707.10c]. What opponents *can* do is act earlier, in response to the Clone spell before it resolves: if they remove the only creature you'd want to copy, or otherwise change the battlefield before Clone's spell resolves, they affect what's available for you to copy when the replacement effect is applied.

In multiplayer or Commander games, this doesn't change: it's still Clone's controller (you) who makes the copy choice as it enters, regardless of how many opponents are at the table, since 707.6 assigns 'as it enters' choices to the entering permanent's controller. The only added multiplayer wrinkle is rule 616.1c: if some other effect is also trying to make Clone (or the copied creature) enter as a copy of something at the same time, and the affected object's controller has to choose which replacement effect to apply, that choice is made in APNAP order among the players who need to decide, but that's about which replacement effect governs, not about giving opponents a chance to interrupt your copy choice.

Card data from Scryfall (scryfall.com).

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
citations: ['707.10', '707.10b', '701.23h', '701.23b', 'Gogo, Master of Mimicry ruling #6', 'Gogo, Master of Mimicry ruling #8', 'Gogo, Master of Mimicry ruling #9']
text: Flooded Strand's ability ("{T}, Pay 1 life, Sacrifice this land: Search your library for a Plains or Island card, put it onto the battlefield, then shuffle") is an activated ability. When you activate Gogo, Master of Mimicry with X=2 while that ability is on the stack, Gogo's ability targets the Flooded Strand ability already on the stack and creates two additional copies of it (Gogo's ability doesn't grant anyone an extra ability or let you re-pay costs — it just puts more instances of the existing ability onto the stack) [Gogo, Master of Mimicry ruling #6]. The source of each copy is the same Flooded Strand [Gogo, Master of Mimicry ruling #9], and Gogo can copy this ability even though it happens to have a target (its own controller choosing which card to search for) [Gogo, Master of Mimicry ruling #8].

Each copy is itself a full copy of the ability, carrying the same text and any choices already made for it [707.10], [707.10b]. Because the original ability and its two copies are three separate instances of the ability on the stack, each one resolves independently: each performs its own full 'search library for a Plains or Island card, put it onto the battlefield, then shuffle' sequence. This is different from the 'search a library more than once before instructing a shuffle' case, since here each instance shuffles before the next one resolves, so they don't collapse into a single search [701.23h].

So, resolving the original ability plus the two Gogo copies, you get up to three lands from that one Flooded Strand activation — one Plains/Island for the original ability and one for each copy — provided your library has enough qualifying cards each time. Note you're never required to find a card just because one is present, so you could choose to find fewer than three if you wanted [701.23b]. You do not need to sacrifice or tap the Flooded Strand again, and no additional life payment is required for the copies, since copying an ability doesn't involve paying its costs again.

Card data from Scryfall (scryfall.com).

---

## Output instructions

Grade all 50 cells above per the rubric. For EACH cell, write exactly one JSON line to:

    evals/opus_grader_v2_out/sonnet-v2.jsonl

Each line is a single JSON object with EXACTLY these fields and nothing else:

    {"id": "<cell id, e.g. q007 or c012>", "arm": "sonnet-v2", "verdict": "correct"|"partial"|"wrong", "reason": "<one-line reason>"}

Every one of the 50 cells above must be accounted for -- one line per cell, any order, no duplicates, no extra fields, no commentary outside the JSONL lines. If a cell is genuinely ungradeable, still write a line with your best-effort verdict and say why in the reason -- never silently drop a cell.