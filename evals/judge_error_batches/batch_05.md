# Reference-grading batch batch_05

You are the reference grader for an audit of an automated LLM judge. Your
verdicts become ground truth, so grade each cell carefully and independently.

Apply EXACTLY this criterion (the audited judge's own frozen system prompt,
reproduced verbatim -- do not substitute your own standard):

---
You compare a CANDIDATE answer to a REFERENCE answer that is known correct, for the same Magic: The Gathering rules question. Decide whether the candidate reaches the SAME core ruling/conclusion as the reference. Focus ONLY on the final ruling -- ignore wording, length, and how much supporting detail each gives. If the candidate reaches the same bottom-line answer, verdict is 'same'. If it reaches a different, wrong, or materially incomplete conclusion (e.g. it now declines, or gets the ruling backwards), verdict is 'different'.

Additional context for this question set: player names starting with 'A' are the active player; other letters are nonactive players in turn order. Questions refer to objects by their original names even after copy effects.
---

Ground every Magic ruling judgement in what the two answers actually say. You
are not being asked which answer is correct in absolute terms -- only whether
the CANDIDATE reaches the SAME core ruling as the REFERENCE. Two answers that
state the same outcome in different words are `same`. An answer that reaches a
different outcome, reverses the ruling, declines to answer, or omits a
materially load-bearing part of the conclusion is `different`.

There are 19 cells below. Grade every one. Do not skip cells and do
not batch-guess: the cells are a deliberate mix and the proportion of `same` to
`different` is not something you should try to infer.

**Output**: write one JSON object per line to
`evals/judge_error_out/batch_05.jsonl` -- nothing else, no prose, no markdown
fence:

    {"cell": "c0001", "verdict": "same", "reason": "<one sentence>"}

`verdict` must be exactly `same` or `different`. Write one line per cell, in
the order the cells appear.

---

### CELL c0077

**Question**
At the beginning of the game, Alianna announced [Zirda, the Dawnwaker] as their companion. During the game, Alianna cast [Glistening Goremonger] from their sideboard with [Wish]. Later, Alianna restarts the game with [Karn Liberated]. What happens?

**REFERENCE (correct)**
Glistening Goremonger will be shuffled into Alianna's library along with the rest of the cards in the game. Because Glistening Goremonger violates Zirda, the Dawnwaker's companion restriction, Alianna can't announce it as their companion for the restarted game.

**CANDIDATE**
Short answer: the game restarts, and Alianna's Pyretic Prankster // Glistening Goremonger card — which came in from outside the game via Wish — is shuffled into Alianna's library for the new game. During the new game's pregame procedure Alianna may reveal Zirda, the Dawnwaker as their companion again, and the condition is still met, because Pyretic Prankster // Glistening Goremonger is a permanent card that has an activated ability ({3}{B/P}: Transform this creature).

Details:

1. Restarting. Karn Liberated's −14 immediately ends the current game with no winner, loser, or drawer, and the same players begin a new game using the normal starting procedure of rule 103, with the exception in rule 727.2 [727.1] [727.2] [Karn Liberated]. Non-Aura permanent cards exiled with Karn Liberated stay in exile and enter the battlefield under Alianna's control after the pregame procedure finishes [Karn Liberated].

2. The Wished card. Rule 727.2 says every Magic card involved in the ended game is involved in the new game, even if it wasn't originally part of it — its example is exactly a creature card brought in from outside the game with a Wish-style effect, which becomes part of that player's library in the new game [727.2] [Wish]. So Pyretic Prankster // Glistening Goremonger is now one of Alianna's deck cards; it can't be shuffled back into the sideboard, since players can't move cards between deck and sideboard before the new game [Karn Liberated]. (Pedantic note: Glistening Goremonger is the back face; what Alianna actually cast with Wish was the front face, Pyretic Prankster.)

3. Companion in the new game. Companion is a keyword that functions from outside the game: before the game begins you may reveal one card you own from outside the game whose companion condition is satisfied by your starting deck, and once during the game you may pay {3} as a special action to put it into your hand [702.139a] [103.2b]. Because a restart runs the full starting procedure, the companion-reveal step happens again [727.1] [103.2b], and the "once during the game" {3} special action is fresh for the new game [702.139a].

4. Is Zirda, the Dawnwaker still legal? Zirda, the Dawnwaker requires that each permanent card in your starting deck have an activated ability [Zirda, the Dawnwaker]. Pyretic Prankster // Glistening Goremonger is a creature (permanent) card, and it has the activated ability "{3}{B/P}: Transform this creature. Activate only as a sorcery." — activated abilities are the ones written "[Cost]: [Effect]" [Zirda, the Dawnwaker]. So adding it to the deck does not break the condition, and Alianna may reveal Zirda, the Dawnwaker again. Zirda, the Dawnwaker itself was never brought into the game (it stayed outside the game as a revealed companion), so it is available to be revealed once more.

5. Timing assumption. I'm assuming Alianna never paid the {3} to put Zirda, the Dawnwaker into their hand before the restart. If Alianna had already paid {3} and Zirda, the Dawnwaker was in hand (or graveyard, battlefield, etc.) when the game restarted, then Zirda, the Dawnwaker would be a card "involved in the game" and would be shuffled into Alianna's library for the new game [727.2], and a card sitting in your starting deck can't function as your companion — the companion ability has no effect from inside the deck [Zirda, the Dawnwaker]. Alianna would then have no companion in the new game.

6. Two players vs. multiplayer. With more than two players, the controller of the restarting ability (Alianna) is the starting player in the new game, any player who had already left the game before the restart is not in the new game [Karn Liberated], and companions are revealed starting with the starting player and proceeding in turn order — once a player declines, they can't change their mind [103.2b] [Zirda, the Dawnwaker]. In a two-player game that just means Alianna declares first. Nothing else about this interaction differs by player count.

Card data from Scryfall (scryfall.com).

### CELL c0078

**Question**
Ari controls [Bludgeon Brawl] and [Soldevi Digger]. They cast [Titania's Song]. Once it resolves, what are the characteristics of Soldevi Digger?

**REFERENCE (correct)**
It's a 2/2 artifact creature with no abilities. Applying Titania's Song would cause Bludgeon Brawl to no longer apply (since Soldevi Digger would be a creature). However, applying Bludgeon Brawl would not change how Titania's Song's effect is applied, so Bludgeon Brawl is dependent on Titania's Song. Titania's Song applies first, and then Bludgeon Brawl won't affect Soldevi Digger since it's a creature.

**CANDIDATE**
Soldevi Digger ends up as a colorless 2/2 artifact creature named Soldevi Digger, with no subtypes (no longer an Equipment) and no abilities at all — it loses both its own "{2}: Put the top card of your graveyard on the bottom of your library" and the equip ability Bludgeon Brawl was granting it.

Why, layer by layer (CR 613.1, 613.6, 110.3):

- Layer 4 (types/subtypes): Bludgeon Brawl only applies to "each noncreature, non-Equipment artifact." Titania's Song makes Soldevi Digger an artifact creature. Because applying Titania's Song changes whether Bludgeon Brawl applies to Soldevi Digger at all, Titania's Song is applied first in layer 4 as a dependency; once Soldevi Digger is a creature, Bludgeon Brawl's ability simply doesn't apply to it anymore, so the Equipment subtype goes away. (Either way you order it, re-checking Bludgeon Brawl's condition against the live state gives the same result — Soldevi Digger is a creature, so no Equipment.) Note Titania's Song says "becomes an artifact creature," and per CR 205.1b such an effect lets the object keep its prior card types, so it's Artifact Creature, not just Creature.
- Layer 6 (abilities): Titania's Song's "loses all abilities" removes Soldevi Digger's activated ability. Even in a hypothetical where Bludgeon Brawl's grant were still applying (older timestamp), Titania's Song's later-timestamped removal would strip equip {2} and "Equipped creature gets +X/+0" anyway.
- Layer 7b (P/T setting): Titania's Song sets power and toughness each equal to mana value. Soldevi Digger's mana cost is {2} — two generic mana — so its mana value is 2, making it 2/2. This applies even though the definition of the effect refers to noncreature artifacts (CR 613.6).

Color is unchanged: nothing here changes color, and Soldevi Digger's mana cost has no colored symbols, so it stays colorless.

Also note the "leaves the battlefield" clause on Titania's Song: if Titania's Song leaves the battlefield, its effect continues until end of turn, so Soldevi Digger stays a 2/2 ability-less artifact creature (and thus still not an Equipment) for the rest of that turn.

None of this depends on player count — Bludgeon Brawl and Titania's Song affect artifacts regardless of controller, so the answer is the same in a two-player or multiplayer game.

Card data from Scryfall (scryfall.com).

### CELL c0079

**Question**
Ashley controls [Bolas's Citadel] and has [Lovestruck Beast] on top of their library. Can they cast [Heart's Desire]? If so, how much life do they pay?

**REFERENCE (correct)**
Yes and it will cost Ashley 1 life. As part of putting Lovestruck Beast on the stack Ashley chooses whether or not they want to cast the Adventure or not. If they casts Heart's Desire they will need to pay life equal to the mana value of the spell they are casting, which in this case is one.

**CANDIDATE**
Yes. Ashley may cast Heart's Desire off the top of the library because Bolas's Citadel's static ability says "You may... cast spells from the top of your library." Heart's Desire is one of the two faces of the card Lovestruck Beast // Heart's Desire, and its own mana cost is {G} — a mana value of 1. Bolas's Citadel's text overrides the normal payment: "If you cast a spell this way, pay life equal to its mana value rather than pay its mana cost." Since the spell being put on the stack is Heart's Desire (mana cost {G}, mana value 1), Ashley pays 1 life instead of paying {G}.

A couple of notes: Bolas's Citadel's card text is a printed rule that overrides the general rule that spells are normally paid for with their mana cost — this is an alternative-cost substitution applied when the total cost is determined and locked in (rule 601.2f). Also, remember Heart's Desire is a sorcery, so this can only be done at a time Ashley could normally cast a sorcery (main phase, stack empty, Ashley's priority) — Bolas's Citadel doesn't change that timing restriction, it only lets the spell be accessed from the library and changes how it's paid for.

Card data from Scryfall (scryfall.com).

### CELL c0080

**Question**
Alex controls an [Oracle of Mul Daya] and has played 2 lands this turn. They casts [Flicker], targeting the Oracle of Mul Daya. After if resolves, can they play a 3rd land?

**REFERENCE (correct)**
No. Alex has 1 land play this turn by default, which Oracle of Mul Daya increase to 2. Alex has already played 2 lands this turn, so no more lands can be played.

**CANDIDATE**
No — Alex cannot play a third land.

Alex's land allowance is 1 (the normal land play) + 1 from Oracle of Mul Daya's static ability, for a total of 2, and Alex has already played 2 lands this turn. Flickering Oracle of Mul Daya doesn't reset or add to that count. To determine legality you compare the number of lands the player may play this turn with the number already played this turn; if the allowance isn't greater, the play is illegal (305.2a, 305.2b).

Why the exile-and-return doesn't help:
- Oracle of Mul Daya's ability is a continuous effect from a static ability, which isn't "locked in" and simply applies at any given moment to whatever its text says (611.3a). At the moment after Flicker resolves, Alex controls one Oracle of Mul Daya, so the allowance is still 2 total — not 3.
- The returned permanent is technically a new object with no memory of its previous existence (400.7i), but the count of lands Alex has already played is tracked per player, not per permanent, so it stays at 2.
- Only controlling multiple Oracle of Mul Daya at once stacks: with two on the battlefield you could play three lands (Oracle of Mul Daya ruling #0). Flicker returns the same single creature, so no stacking occurs.

If Alex wants a third land play, they need a second Oracle of Mul Daya (or another additional-land effect) on the battlefield before making the play. Note also that Oracle of Mul Daya's third ability only changes where lands can be played from (the top of the library), not how many or when — such a play still uses one of Alex's land plays for the turn (Oracle of Mul Daya ruling #2).

This analysis is independent of player count; nothing here changes between a two-player game and a multiplayer table.

Card data from Scryfall (scryfall.com).

### CELL c0081

**Question**
Nico controls [Vedalken Orrery]. Axl casts [Warrior's Oath]. After it resolves, Nico casts [Trouble in Pairs]. Axl passes the turn. Who takes the next turn?

**REFERENCE (correct)**
Nico will take the next turn. Trouble in Pairs generates a replacement effect that will replace Axl taking an extra turn with them not taking an extra turn. It doesn't matter that Trouble in Pairs was cast after Warrior's Oath was resolved, only that it is on the battlefield at the time the extra turn would begin.

**CANDIDATE**
Axl skips the extra turn, so the next turn belongs to the next player in turn order — Nico in a two-player game.

Why: Warrior's Oath gave Axl an extra turn after the current one. Trouble in Pairs says "If an opponent would begin an extra turn, that player skips that turn instead." Because Nico cast Trouble in Pairs (legally at instant speed thanks to Vedalken Orrery, which lets Nico cast spells as though they had flash) before that extra turn would begin, Trouble in Pairs is on the battlefield at the moment Axl's extra turn would begin, and Axl skips it instead. [Trouble in Pairs ruling #2] confirms the timing: extra turns can still be created while Trouble in Pairs is out; they aren't skipped until they would begin, and only if Trouble in Pairs is still there at that point.

Side effect: since Axl never takes that extra turn, its end step never happens, so the delayed trigger from Warrior's Oath ("At the beginning of that turn's end step, you lose the game") never triggers — Axl does not lose the game to Warrior's Oath.

Multiplayer note: with more than two players, the skipped extra turn simply passes to the next player in turn order after Axl (the player to Axl's left), not necessarily Nico. Turn order among players is the standard APNAP/turn-order sequence [101.4].

Timing caveat: this assumes Nico resolved Trouble in Pairs during Axl's current turn, before the extra turn began — which is what the question states (Nico had priority to cast it after Warrior's Oath resolved; the active player gets priority when a spell resolves [117.3b], and any player with priority may cast spells [117.1], with Vedalken Orrery supplying the flash timing). If instead Trouble in Pairs had entered the battlefield only after Axl's extra turn had already begun, that turn would not be skipped and Axl would take it (and would then lose the game at its end step).

Card data from Scryfall (scryfall.com).

### CELL c0082

**Question**
Anabella controls [Blood Moon] and enchants their [Sunlit Marsh] with [Urban Utopia]. What colors can it tap for?

**REFERENCE (correct)**
Any color. Blood Moon operates in the type-changing layer which is applied before the ability adding and removing layer. Sunlit Marsh is a Mountain, with the additional ability "{T}: Add one mana of any color.".

**CANDIDATE**
Sunlit Marsh can tap for any one color: {W}, {U}, {B}, {R}, or {G}. It has two separate mana abilities "{T}: Add {R}" (from Blood Moon making it a Mountain) and "{T}: Add one mana of any color" (from Urban Utopia) ut each tap you choose one of them and get one mana.

Why: Sunlit Marsh is a nonbasic land (no "basic" supertype), so Blood Moon sets its subtypes to Mountain. Per CR 305.7 and Blood Moon ruling #2, that makes it lose its old land types and the abilities generated from its rules text and old types  so the printed "{T}: Add {W} or {B}" and "This land enters tapped" are gone  and it gains "{T}: Add {R}" from the Mountain type (CR 305.6, Mountain entry). Blood Moon ruling #1 confirms it keeps its name and supertypes.

Crucially, CR 305.7 also says setting a land's subtype "doesn't remove any abilities that were granted to the land by other effects." Urban Utopia grants the enchanted land "{T}: Add one mana of any color," and Urban Utopia ruling #0 confirms the land keeps its other abilities and doesn't change land types. So the granted any-color ability survives regardless of whether Blood Moon or Urban Utopia arrived first  the timestamp order doesn't matter here, since Blood Moon's type-setting can't strip a granted ability.

So the practical answer: it taps for one mana of any color, and it no longer enters tapped. This doesn't depend on the number of players at the table; Blood Moon affects all nonbasic lands regardless of controller, so in multiplayer every opponent's nonbasic lands are Mountains too.

Timing note: I'm assuming both Blood Moon and Urban Utopia are on the battlefield simultaneously and Sunlit Marsh is already on the battlefield. If Sunlit Marsh were entering the battlefield while Blood Moon is out, it would enter untapped, since Blood Moon removes the "enters tapped" ability.

Card data from Scryfall (scryfall.com).

### CELL c0083

**Question**
Alvin controls [Mycosynth Lattice], a [Dance of the Dead] attached to a [Streetbreaker Wurm] that it returned to the battlefield, and a [Mizzium Transreliquat] that is currently a copy of [Sakashima of a Thousand Faces] due to its second ability. Alvin casts [Eureka], choosing to put [March of the Machines] onto the battlefield, then putting [Copy Artifact] onto the battlefield, which copies the Mizzium Transreliquat and then copies the Dance of the Dead with its new copy ability. (The one from Sakashima of a Thousand Faces.) They choose for it to enchant a [Viashino Warrior] in their graveyard. As Eureka continues resolving, they put [Shimatsu the Bloodcloaked] onto the battlefield and sacrifice March of the Machines. After Copy Artifact's trigger resolves and returns the Viashino Warrior to the battlefield, Alvin activates the ability of the Copy Artifact to turn it into a copy of Streetbreaker Wurm. What happens?

**REFERENCE (correct)**
The Copy Artifact becomes unattached from the Viashino Warrior. It still has the ability "enchant creature put onto the battlefield with Dance of the Dead", but it's not an Aura so nothing happens to it if it isn't enchanting a legal object. If Copy Artifact leaves the battlefield later, Alvin will have to sacrifice Viashino Warrior.

**CANDIDATE**
Short answer: Alvin's Copy Artifact stops being a Dance of the Dead and becomes a 6/4 copy of Streetbreaker Wurm that keeps only the Mizzium Transreliquat ability "{1}{U}{R}: This artifact becomes a copy of target artifact, except it has this ability." Because it never left the battlefield, its Dance of the Dead "when this Aura leaves the battlefield" trigger does not trigger, so the Viashino Warrior is NOT sacrificed 	it simply stays on the battlefield, no longer enchanted, no longer getting +1/+1 and no longer prevented from untapping.

Step by step:

1. Copy Artifact entering. Mizzium Transreliquat had used its second ability, which permanently makes it a copy of Sakashima of a Thousand Faces plus the {1}{U}{R} ability (Mizzium Transreliquat ruling #0). Copy effects are part of copiable values, so Copy Artifact copying Mizzium Transreliquat copies that result (707.2, 707.3, Mizzium Transreliquat ruling #3). Two replacement effects then apply as it enters, in the order Alvin chooses (616.1f): Copy Artifact's own effect first (giving it Sakashima of a Thousand Faces' copiable values, including "except it has Sakashima's other abilities" and the {1}{U}{R} ability, 707.9a/707.9b), then Sakashima of a Thousand Faces' copy ability.

2. Copying Dance of the Dead is legal because Mycosynth Lattice makes Dance of the Dead an artifact and March of the Machines then makes that noncreature artifact a creature (MV 2, so a 2/2) 	so it is "another creature you control." The resulting Copy Artifact is a Dance of the Dead with Sakashima of a Thousand Faces' other abilities, which includes the inherited {1}{U}{R} Mizzium Transreliquat ability (201.5b for the name-substitution in gained abilities).

3. Sacrificing March of the Machines to Shimatsu the Bloodcloaked before state-based actions are checked matters a lot. While March of the Machines was out, the Copy Artifact/Dance of the Dead was itself a creature, and a creature Aura can't enchant anything (Mycosynth Lattice ruling #3). Since March of the Machines is gone by the time state-based actions are next checked and by the time the trigger resolves, it is a normal (artifact) Aura again, so the trigger legally puts Viashino Warrior onto the battlefield tapped and attaches to it.

4. The activation. The Copy Artifact is still an artifact (Mycosynth Lattice), so it can activate {1}{U}{R}, and Streetbreaker Wurm is also an artifact thanks to Mycosynth Lattice, so it's a legal target. On resolution the Copy Artifact's copiable values are overwritten entirely by Streetbreaker Wurm's, except it keeps that {1}{U}{R} ability (707.2, 707.9a). It loses the Aura types and all Dance of the Dead text, and also loses Sakashima of a Thousand Faces' legend-rule and partner abilities.

5. No sacrifice trigger. Rule 707.4 states that a permanent copying a different object while remaining on the battlefield does not cause leaves-the-battlefield (or enters-the-battlefield) abilities to trigger. Dance of the Dead's "when this Aura leaves the battlefield, that creature's controller sacrifices it" therefore never triggers, and it isn't even an ability of the permanent anymore. Viashino Warrior stays, and is now unattached (it can untap normally on Alvin's next untap step). Alvin's original Streetbreaker Wurm and its real Dance of the Dead are unaffected.

Timing caveat: I'm assuming March of the Machines was sacrificed before state-based actions were next checked and before the Dance of the Dead trigger resolved, as described. If instead state-based actions were checked while March of the Machines was still on the battlefield, the creature-Aura Copy Artifact would have been unattached and put into its owner's graveyard (Mycosynth Lattice ruling #3), and then its leaves-the-battlefield ability would have made Alvin sacrifice the Viashino Warrior.

Player count: nothing here changes between two players and multiplayer, except that Eureka lets every player put permanents onto the battlefield; those choices are made in turn order starting with Alvin (101.4).

Card data from Scryfall (scryfall.com).

### CELL c0084

**Question**
Allison controls [Leyline of Anticipation]. In their draw step, they casts [Relentless Assault]. What happens?

**REFERENCE (correct)**
There is no "this main phase" to add the combat step after, so no additional phase is created. The turn proceeds as normal.

**CANDIDATE**
Relentless Assault resolves and does essentially nothing: no creatures untap and no extra phases are created.

Why:

1. **Casting it is legal.** Leyline of Anticipation says "You may cast spells as though they had flash," so Allison can cast the sorcery Relentless Assault during their own draw step, when they'd otherwise be unable to cast a sorcery. Card text like this overrides the general sorcery-timing restriction.

2. **The untap clause does nothing.** Relentless Assault untaps all creatures that attacked this turn. In the draw step, the combat phase of this turn hasn't happened yet, so no creature has attacked this turn. An effect that attempts to do something impossible (or that has no legal objects to affect) simply does as much as it can — here, nothing [609.3].

3. **No extra combat or main phase.** Relentless Assault says "After this main phase, there is an additional combat phase followed by an additional main phase," and its ruling is explicit: it creates an additional combat and main phase only if it resolves during a main phase [Relentless Assault ruling #1]. Since Allison cast it in the draw step, it resolves in the draw step, and there is no "this main phase" to attach the new phases to. Effects that add phases insert them directly after a specified phase [500.8]; with no specified phase, nothing is added. The turn proceeds normally into Allison's precombat main phase, and the {2}{R}{R} is wasted.

Timing assumption: since a step can't end with a spell on the stack, Relentless Assault both is cast and resolves during the draw step. If instead Allison waited and cast it during either main phase (which Leyline of Anticipation doesn't even require, since sorceries are already castable then), it would resolve in a main phase and would grant the extra combat phase plus extra main phase, and would untap any creatures that had already attacked that turn.

Player count doesn't change any of this — the answer is the same at a two-player table or in multiplayer, since everything here happens on Allison's own turn and affects only Allison's phases.

Card data from Scryfall (scryfall.com).

### CELL c0085

**Question**
Asa controls [Library of Leng] and is discarding a card due to [Azra Oddsmaker]'s ability. Can they put the discarded card on top of their library? If so, what happens?

**REFERENCE (correct)**
Yes. Discarding a cost to the ability is a cost [118.12], but that doesn't stop it from being an effect as well. Library of Leng only changes where the card moves to, not that it was discarded, so the cost was paid and the remainder of Azra Oddsmaker's ability will resolve as normal.

**CANDIDATE**
No — Asa must put the discarded card into their graveyard. Library of Leng does not apply to the discard from Azra Oddsmaker's ability, because that discard is a cost, not an effect.

Why: Azra Oddsmaker's triggered ability reads "At the beginning of combat on your turn, you may discard a card. If you do, choose a creature...." That is exactly the template covered by rule 118.12 — "[A player] may [do something]. If [that player] [does]..." — which states that the "[do something]" action is a cost, paid as the ability resolves. Library of Leng's replacement applies only "If an effect causes you to discard a card," and effects are what spells and abilities create as they resolve (rule 609.1). The card's own ruling settles it directly: you can't use Library of Leng to put a discarded card on top of your library when you discard as a cost, because costs aren't effects [Library of Leng ruling #5].

So the sequence is: Azra Oddsmaker's ability resolves, Asa chooses to pay the discard cost, the card goes from hand to graveyard (it still counts as a discard and will set off any "whenever a player discards" triggers, per [Library of Leng ruling #3]), and because Asa did pay, they then choose a creature; that creature gets "Whenever that creature deals combat damage to a player this turn, you draw two cards."

Related point on the "if you do" clause: rule 118.12 checks whether the player started to pay the cost, and rule 118.11 says the cost still counts as paid even if effects modify the actions performed. So even in cases where a replacement effect changes what actually happens to the discarded card, the "If you do" clause would still be satisfied — the choosing of a creature is never in danger here.

Contrast: if some other spell or ability instructed Asa to discard as part of its resolution (an effect, e.g. "discard a card, then draw a card"), Library of Leng would let Asa put that card on top of their library instead of into the graveyard [Library of Leng ruling #4].

Player count doesn't matter: Azra Oddsmaker's trigger and Library of Leng only involve Asa, so the answer is the same in a two-player game or at a multiplayer table.

Card data from Scryfall (scryfall.com).

### CELL c0086

**Question**
Ariyah controls [The Ozolith] and [Putrid Goblin] with a -1/-1 counter on it. What happens if Putrid Goblin dies?

**REFERENCE (correct)**
Putrid Goblin will not return to the battlefield. The Ozolith will have a -1/-1 counter put on it. The Ozolith's ability does not remove counters from the creature, it just puts counters on The Ozolith matching the number and types of counters that the creature had on it when it died. Persist will look back in time to determine if Putrid Goblin had a -1/-1 counter on it at the time it died. Since it did, persist will not trigger.

**CANDIDATE**
Putrid Goblin stays in the graveyard — its persist ability does not trigger, because Putrid Goblin already had a -1/-1 counter on it when it died — and The Ozolith's first ability triggers and puts one -1/-1 counter on The Ozolith.

Details:

1. Persist reads "When this creature dies, if it had no -1/-1 counters on it, return it to the battlefield... with a -1/-1 counter on it." Since Putrid Goblin had a -1/-1 counter on it as it left the battlefield, the intervening-"if" condition fails and persist doesn't trigger. (If instead Putrid Goblin had also had a +1/+1 counter, the state-based action in [704.5q]/[122.3] would have removed one of each, leaving no -1/-1 counter, and persist could return it — see [Putrid Goblin ruling #0]. That's not the case here.)

2. The Ozolith's ability, "Whenever a creature you control leaves the battlefield, if it had counters on it, put those counters on The Ozolith," triggers. It does not physically move the counter off the dead Putrid Goblin — the counter on Putrid Goblin simply ceases to exist when the card changes zones ([122.2], [400.7]). Instead Ariyah puts the same number and kind of counters Putrid Goblin had onto The Ozolith, i.e. one -1/-1 counter ([122.8], [The Ozolith ruling #3]).

3. Importantly, The Ozolith's ability resolving first does not "clean" Putrid Goblin's counter for persist's purposes: an ability that checks the counters a creature had as it left the battlefield uses the counters that were on it on the battlefield ([The Ozolith ruling #3]).

4. Afterward, at the beginning of combat on Ariyah's turn, The Ozolith's second ability may move all counters from The Ozolith onto a target creature — here that would dump a -1/-1 counter onto that creature, so Ariyah may prefer not to (the ability says "you may"). If the target is illegal on resolution, no counters leave The Ozolith ([The Ozolith ruling #5]); if The Ozolith itself leaves the battlefield first, no counters move ([The Ozolith ruling #2]).

This result is the same in a two-player game or at a multiplayer table; nothing here depends on the number of opponents.

Card data from Scryfall (scryfall.com).

### CELL c0087

**Question**
Ahmed casts [Bitter Ordeal], targeting Nico. At their first opportunity, Ahmed sacrifices their [Abandoned Outpost]. How many cards will Ahmed be able to exile from Nico's library?

**REFERENCE (correct)**
2. Gravestorm cares about the number of permanents put into the graveyard before the trigger resolves.

**CANDIDATE**
Two cards — one from the original Bitter Ordeal and one from a single gravestorm copy.

How it works:

1. Ahmed casts Bitter Ordeal targeting Nico. Gravestorm triggers on cast: "When you cast this spell, copy it for each permanent that was put into a graveyard from the battlefield this turn. If the spell has any targets, you may choose new targets for any of the copies" [702.69a].
2. Ahmed's first opportunity to sacrifice Abandoned Outpost is either while paying Bitter Ordeal's cost of {2}{B} (its "{T}, Sacrifice this land: Add one mana of any color" is a mana ability that can be activated during casting) or with priority after Bitter Ordeal is cast, while the gravestorm trigger is still on the stack. Either way, Abandoned Outpost is put into the graveyard from the battlefield before the gravestorm trigger resolves.
3. The number of copies is locked in only when the gravestorm ability actually resolves, not when it triggered [608.2h]. At that moment exactly one permanent (Abandoned Outpost) has gone to a graveyard from the battlefield this turn, so Ahmed gets one copy.
4. The copy and the original Bitter Ordeal each say "Search target player's library for a card and exile it. Then that player shuffles." Both targeting Nico (Ahmed may choose a new target for the copy) exiles two cards total from Nico's library, assuming Nico has at least two cards to find.

Timing caveat: this assumes Abandoned Outpost hits the graveyard before the gravestorm trigger resolves, which "first opportunity" guarantees. If instead Ahmed waited until after the gravestorm trigger had already resolved, the count would be zero copies and only one card would be exiled.

Note on the reminder text: Bitter Ordeal's reminder says "each permanent put into a graveyard this turn," but the actual gravestorm ability counts only permanents put into a graveyard from the battlefield [702.69a]. Abandoned Outpost qualifies either way.

Multiplayer: with only Ahmed and Nico, it's two exiled cards from Nico. At a table of three or more, the count is still "each permanent put into a graveyard from the battlefield this turn" by any player, so other players' permanents dying earlier in the turn would add copies, and Ahmed could redirect the copy to search a different opponent's library instead of Nico's [702.69a].

Card data from Scryfall (scryfall.com).

### CELL c0088

**Question**
At the beginning of the game, Alianna announced [Zirda, the Dawnwaker] as their companion. During the game, Alianna cast [Glistening Goremonger] from their sideboard with [Wish]. Later, Alianna restarts the game with [Karn Liberated]. What happens?

**REFERENCE (correct)**
Glistening Goremonger will be shuffled into Alianna's library along with the rest of the cards in the game. Because Glistening Goremonger violates Zirda, the Dawnwaker's companion restriction, Alianna can't announce it as their companion for the restarted game.

**CANDIDATE**
Short answer: the game ends immediately and a new game starts with Alianna as the starting player. The Pyretic Prankster // Glistening Goremonger card that Alianna brought in from outside the game with Wish is now "involved in the game," so it becomes part of Alianna's library in the new game — it does not go back to the sideboard. Zirda, the Dawnwaker, which never left the outside-the-game zone, is still outside the game, and Alianna may reveal it as their companion again during the new game's pregame procedure — but only if the new starting deck (which now contains Pyretic Prankster // Glistening Goremonger) still satisfies Zirda, the Dawnwaker's condition.

Details:

1. Restarting. Karn Liberated's −14 ends the current game with no winner, loser, or drawer, and all players still in the game immediately begin a new one following the normal pregame procedure of rule 103 [727.1, 104.6, Karn Liberated ruling #13]. Nothing that happened in the old game carries over [Karn Liberated ruling #2], and Alianna (the controller of the restarting ability) is the starting player in the new game [Karn Liberated ruling #10].

2. The Wish card. Every Magic card involved in the ended game is involved in the new game, even if it wasn't originally part of it; the rules give exactly this case as the example (a creature card fetched from outside the game with Living Wish ends up in that player's library in the new game) [727.2]. So Pyretic Prankster // Glistening Goremonger — the double-faced card whose front face Alianna cast off Wish — shuffles into Alianna's library, front face up, with no memory of having been transformed. Players also can't move cards between deck and sideboard before the new game [Karn Liberated ruling #6]. The one exception: if that card had instead been exiled by Karn Liberated's +4 or −3 as a non-Aura permanent card, it would stay in exile and be put onto the battlefield under Alianna's control after the pregame procedure [727.5, Karn Liberated ruling #5].

3. Zirda, the Dawnwaker. "Companion" is a keyword that functions outside the game: before the game begins you may reveal one card you own from outside the game whose companion condition your starting deck fulfills, and once per game you may pay {3} as a special action to put it into your hand [702.139a, 103.2b, 116.2g]. Assuming Alianna never paid the {3} (the question only says Zirda, the Dawnwaker was announced), Zirda, the Dawnwaker was never in the game at all, so 727.2 doesn't drag it into the new game's deck — it stays outside the game and can be re-revealed as a companion during the new pregame procedure. Because more than one player may want a companion, the starting player (here, Alianna) reveals first and the others follow in turn order [Zirda, the Dawnwaker ruling #7].

4. The catch — the condition is re-checked. Zirda, the Dawnwaker's condition is "each permanent card in your starting deck has an activated ability," and "starting deck" means your deck after setting aside sideboard cards [702.139b, Zirda, the Dawnwaker ruling #12]. Pyretic Prankster // Glistening Goremonger is a creature card, hence a permanent card [Zirda, the Dawnwaker ruling #10], and it does have an activated ability ({3}{B/P}: Transform this creature — note {B/P} is a Phyrexian colored symbol, payable with {B} or 2 life, not generic mana), so it does not break the condition. Alianna can legally announce Zirda, the Dawnwaker again. Had the Wished-for card been a permanent card with no activated ability, the new starting deck would fail the condition and Zirda, the Dawnwaker could not be a companion in the new game.

5. The {3} special action resets. The special action may be taken "only if they haven't done so yet this game" [116.2g]. The new game is a different game, so even if Alianna had paid {3} in the old game, that limit resets — but if Alianna had already paid the {3}, Zirda, the Dawnwaker would have been a card in the game (in hand, on the battlefield, or in the graveyard) [702.139c], and 727.2 would then shuffle Zirda, the Dawnwaker into Alianna's library for the new game rather than leaving it available as a companion.

6. Timing assumption: I'm assuming Zirda, the Dawnwaker was still outside the game when Karn Liberated restarted the game. If instead Alianna had already paid {3} to put Zirda, the Dawnwaker into hand at any point before the restart, see point 5 — Zirda, the Dawnwaker joins the library and Alianna has no companion in the new game.

Multiplayer: at a table of more than two, all players still in the game when it restarts are in the new game, including under the limited range of influence option [727.7], but anyone who had already left the game before the restart is not [Karn Liberated ruling #12]. Companion reveals then proceed from Alianna in turn order [Zirda, the Dawnwaker ruling #7]. With exactly two players the sequence is the same, just shorter.

Card data from Scryfall (scryfall.com).

### CELL c0089

**Question**
Alma deals combat damage to Nico with their [Ragavan, Nimble Pilferer]. They exile [Deceit] from Nico's library. Can Alma evoke Deceit?

**REFERENCE (correct)**
Yes. Ragavan, Nimble Pilferer's trigger creates a continuous effect that lets Alma cast Deceit this turn, with no restrictions on how it's cast. Alma is free to cast Deceit for its alternative cost by evoking it.

**CANDIDATE**
Yes. Ragavan, Nimble Pilferer's ability says "Until end of turn, you may cast that card," which is permission to cast Deceit from exile, and evoke is an alternative cost that works from any zone Deceit can be cast from. So Alma may cast Deceit from exile for its evoke cost of {U/B}{U/B} (two mana, each either blue or black) instead of its {4}{U/B}{U/B} mana cost, provided Alma casts it before end of turn and at a legal time for a creature spell (their main phase with an empty stack, since Deceit is a creature spell with no flash).

Details:
- Evoke is two abilities: a static ability that functions in any zone from which the card can be cast, meaning "You may cast this card by paying [cost] rather than paying its mana cost," plus a triggered ability "When this permanent enters, if its evoke cost was paid, its controller sacrifices it" [702.74a]. Because the static half works in whatever zone the card can be cast from, it works in exile once Ragavan, Nimble Pilferer's effect grants permission to cast Deceit from there.
- Alma announces the evoke alternative cost as part of casting, following the alternative-cost rules [601.2b], and the total cost {U/B}{U/B} is locked in [601.2f]. The Treasure token Ragavan, Nimble Pilferer created can help pay it, since Treasure produces one mana of any color and each {U/B} can be paid with blue or black.
- Because the evoke cost was paid, Deceit enters the battlefield under Alma's control and is then sacrificed by the evoke trigger. Its enter triggers still happen: if {U}{U} was spent, Alma returns up to one other target nonland permanent to its owner's hand; if {B}{B} was spent, a target opponent reveals their hand and Alma chooses a nonland card to be discarded. Deceit's rulings confirm those abilities look at what mana was spent on the total cost, not just on the hybrid symbols [Deceit ruling #0] — so paying {U/B}{U/B} as {U}{U} or {B}{B} turns on the corresponding trigger.
- Note Alma can't combine evoke with another alternative casting method; only one alternative cost may apply to a spell [601.2b].

This works the same in a two-player game or at a multiplayer table; the only multiplayer wrinkle is that Deceit's black trigger targets an opponent, and Alma chooses which opponent — it need not be Nico.

Card data from Scryfall (scryfall.com).

### CELL c0090

**Question**
Ari controls [Xathrid Gorgon]. Neriah controls a [Hexavus] and [Stonehewer Giant]. Ari activates Xathrid Gorgon to put a petrification counter on Stonehewer Giant which Neriah removes with Hexavus. Can Neriah activate Stonehewer Giant's activated ability?

**REFERENCE (correct)**
No, Neriah cannot activate Stonehewer Giant's ability. This is because the changes made by Xathrid Gorgon's ability are a continuous effect. The petrification counter serves only as a reminder of the changes and is not dependent on the counter. Stonehewer Giant will remain a defender that cannot activate it's abilities for the rest of the game.

**CANDIDATE**
No. Neriah still can't activate Stonehewer Giant's {1}{W}, {T} ability.

Xathrid Gorgon's ability creates a continuous effect that doesn't depend on the petrification counter staying on Stonehewer Giant. Per [Xathrid Gorgon ruling #0], if the counter is removed, the creature remains a colorless artifact with defender, and its activated abilities still can't be activated. The counter is just a marker; removing it with Hexavus's {1}, Remove a counter from another creature you control ability does not undo the effect.

Note that Neriah can legally use Hexavus this way (Hexavus's ability removes any kind of counter from another creature Neriah controls, and activating Hexavus is not activating Stonehewer Giant's ability). But the prohibition on Stonehewer Giant persists: a player can't begin to activate an ability that's prohibited from being activated [602.5], and a "can't" effect takes precedence over permission [101.2a]. This holds regardless of table size — the answer is the same in a two-player game or a multiplayer game, since the restriction is on Stonehewer Giant itself.

Timing note: I'm assuming the petrification counter was removed after Xathrid Gorgon's ability had already resolved. If Hexavus's ability were somehow used before Xathrid Gorgon's ability resolved, there would be no petrification counter yet to remove, and Xathrid Gorgon's ability would simply resolve and lock down Stonehewer Giant anyway (assuming Stonehewer Giant is still a legal target).

Card data from Scryfall (scryfall.com).

### CELL c0091

**Question**
Aminah controls [Shapers' Sanctuary], [Spellskite], and [Feral Krushok]. Nico casts [Pyromatics] targeting Feral Krushok. Aminah activates Spellskite to change the target of Pyromatics to Spellskite. How many times does Shapers' Sanctuary trigger?

**REFERENCE (correct)**
Twice. Shapers' Sanctuary will trigger the first time when Pyromatics is initially cast targeting Feral Krushok.. Shapers' Sanctuary will trigger again when Spellskite becomes the target of the spell.

**CANDIDATE**
Shapers' Sanctuary triggers twice in this sequence. First, when Nico casts Pyromatics targeting Feral Krushok, Feral Krushok (a creature Aminah controls) becomes the target of a spell Nico (an opponent) controls, which is exactly the trigger condition on Shapers' Sanctuary's text: "Whenever a creature you control becomes the target of a spell or ability an opponent controls, you may draw a card." That's trigger #1.

Second, when Aminah activates Spellskite's ability — "{U/P}: Change a target of target spell or ability to this creature" — that ability changes the (single) target of Pyromatics from Feral Krushok to Spellskite, following the "change a target" process ([Change a Target], [115.7], [115.7b]). Once that change happens, Spellskite is now the target of Pyromatics, a spell controlled by Nico, an opponent. Spellskite is also a creature Aminah controls, so Shapers' Sanctuary's trigger condition ("a creature you control becomes the target of a spell or ability an opponent controls") is met again, independently of the first trigger. That's trigger #2.

Note that Spellskite's own ability is activated by Aminah, its controller, so it doesn't itself cause Shapers' Sanctuary to trigger (that would require an opponent's spell or ability); it's specifically Pyromatics — Nico's spell — re-targeting Spellskite that causes the second trigger. Each trigger is a separate instance of "you may draw a card," so Aminah gets two separate optional draws (per Shapers' Sanctuary ruling #0/#1, each of these triggers even resolves before Pyromatics itself resolves, giving Aminah a chance to act with each draw before the spell/ability that caused it resolves). This holds the same whether it's a two-player game or a multiplayer game, since the rules cited here (target-changing rules and the card's own trigger text) don't vary by player count — no multiplayer-specific rule changes how targeting or this trigger works.

Card data from Scryfall (scryfall.com).

### CELL c0092

**Question**
Aaron equips [Skullclamp] onto [Champion of the Flame]. Does Champion of the Flame die?

**REFERENCE (correct)**
No, Champion of the Flame will be a 4/2 and not die. All continuous effects are applied instantly before state based actions are checked.

**CANDIDATE**
No. Champion of the Flame survives, and Skullclamp's draw-two trigger does not happen.

Math: Champion of the Flame is base 1/1. Its own ability gives it +2/+2 for each Aura and Equipment attached to it, and Skullclamp is an Equipment attached to it, so that's +2/+2. Skullclamp itself grants the equipped creature +1/-1. Total: 1/1 +2/+2 +1/-1 = 4/2. Since its toughness is 2, not 0 or less, the state-based action that puts a creature with toughness 0 or less into its owner's graveyard never applies [704.5f], and state-based actions are checked automatically without using the stack [704.1]. Because Champion of the Flame doesn't die (i.e., isn't put into a graveyard from the battlefield) [700.4], Skullclamp's "Whenever equipped creature dies, draw two cards" ability never triggers.

Two caveats:
- If Champion of the Flame already has 2 or more damage marked on it this turn, that damage is now lethal against its new toughness of 2 and it will be destroyed as a state-based action; Skullclamp would then trigger. I'm assuming no damage is marked. The reverse case is also worth knowing: if you later move Skullclamp to another creature, Champion of the Flame loses the +2/+2 as well as the -1, and previously nonlethal damage can become lethal [Champion of the Flame ruling #0].
- Nothing here depends on player count; the answer is the same in a two-player game or at a multiplayer table.

Card data from Scryfall (scryfall.com).

### CELL c0093

**Question**
Adriel controls [Wandering Ones] equipped with [Fleetfeather Sandals]. On Nico's turn, they enchant it with [Tightening Coils]. On Adriel's next turn, they activate Fleetfeather Sandals's equip ability, targeting Wandering Ones. After that resolves, does it have flying?

**REFERENCE (correct)**
No. Tightening Coils has the most recent timestamp, so its effect is applied last. Activating Fleetfeather Sandals's equip ability targeting Wandering Ones doesn't change its timestamp.

**CANDIDATE**
Yes — after the equip resolves, Wandering Ones has flying (and haste), and is a -5/1 creature.

Why: Fleetfeather Sandals and Tightening Coils both produce continuous effects in layer 6 (ability adding/removing), so they're ordered by timestamp [613.1f, 613.7a]. Neither depends on the other; the later one simply wins [613.9]. An Equipment receives a new timestamp each time it becomes attached to an object [613.7e], so re-activating Fleetfeather Sandals's Equip {2} and attaching it again to Wandering Ones gives its "Equipped creature has flying and haste" ability a timestamp later than Tightening Coils. Applying in order: Tightening Coils removes flying, then Fleetfeather Sandals grants flying and haste — so Wandering Ones ends up with flying. This matches Tightening Coils ruling #0: if an effect gives the enchanted creature flying after Tightening Coils became attached, the creature has flying.

Tightening Coils's -6/-0 applies in layer 7c regardless, so Wandering Ones is 1-6 = -5 power, 1 toughness (a negative power counts as 0 for dealing damage purposes). Multiple instances of flying would be redundant anyway [702.9c].

Note that Equip only works as a sorcery and can be activated even if Fleetfeather Sandals is already attached to that same creature; re-attaching it is what refreshes the timestamp [702.6d, 604.4]. Player count doesn't matter here — the same layer ordering applies in a two-player or multiplayer game.

Timing assumption: I'm assuming Tightening Coils became attached before the equip activation, as stated. If instead Fleetfeather Sandals had been attached last before Tightening Coils and never re-equipped, Tightening Coils would have the later timestamp and Wandering Ones would not have flying.

Card data from Scryfall (scryfall.com).

### CELL c0094

**Question**
Augustine controls [Butcher Ghoul] enchanted by their [Unhallowed Pact]. They attack with it and Nico blocks with [Scaled Wurm]. Will Butcher Ghoul have a +1/+1 counter when it returns to the battlefield?

**REFERENCE (correct)**
It's Augustine's choice. There are two triggers when Butcher Ghoul dies, so Augustine can choose the order to put them onto the stack. The first one to resolve will return the Butcher Ghoul to the battlefield, and the second one will do nothing.

**CANDIDATE**
Butcher Ghoul's return will or won't have a +1/+1 counter depending on which of its two triggered abilities Augustine chooses to resolve first — Augustine controls both abilities, so Augustine makes that choice.

When Butcher Ghoul dies (it will die to combat damage from Scaled Wurm, since a 7/6 blocker deals lethal damage to a 1/1), two abilities trigger simultaneously: Butcher Ghoul's own Undying ability, and Unhallowed Pact's "When enchanted creature dies, return that card to the battlefield under your control" ability. Undying reads "When this permanent is put into a graveyard from the battlefield, if it had no +1/+1 counters on it, return it to the battlefield under its owner's control with a +1/+1 counter on it" [702.93a]. Since Butcher Ghoul had no +1/+1 counters when it died, Undying is eligible to trigger and, if it resolves, returns Butcher Ghoul with a +1/+1 counter under its owner's control (Augustine).

Both of these triggered abilities are controlled by Augustine (Augustine owns/controls Butcher Ghoul and controls the Unhallowed Pact enchanting it), so Augustine chooses the order in which they're put on the stack, and thus which one resolves first.

- If the Undying trigger resolves first: Butcher Ghoul returns to the battlefield immediately with a +1/+1 counter, under Augustine's control. When Unhallowed Pact's trigger then tries to resolve, the card is no longer in the graveyard (it's a new object on the battlefield), so Unhallowed Pact's ability fails to find it and does nothing — this matches the explicit ruling that Unhallowed Pact only returns the card "if it's still in the graveyard when Unhallowed Pact's ability resolves" [Unhallowed Pact ruling #0], and more generally that a zone-change trigger whose target object has already left the zone it was supposed to act on simply fails to do anything [603.6e]. Result: Butcher Ghoul returns WITH a +1/+1 counter.

- If the Unhallowed Pact trigger resolves first: Butcher Ghoul returns to the battlefield under Augustine's control with no counters. When Undying's trigger then tries to resolve, it looks for the card in the graveyard, but it's already a new object on the battlefield, so Undying fails to find it and does nothing [603.6e]. Result: Butcher Ghoul returns WITHOUT a +1/+1 counter.

Either way Butcher Ghoul ends up on the battlefield under Augustine's control (since Augustine both owns the creature and controls the Aura), but only one of the two abilities actually does anything, and Augustine's choice of stacking order determines whether that's Undying (counter added) or Unhallowed Pact (no counter). If Augustine wants the counter, they should order Undying's trigger to resolve before Unhallowed Pact's.

Card data from Scryfall (scryfall.com).

### CELL c0095

**Question**
Averie attacks with [Pristine Angel]. While it's tapped, Nico activates [Cephalid Snitch]'s ability targeting Pristine Angel. After that resolves, Averie casts a spell and untaps Pristine Angel. Can Nico now target the Pristine Angel with [Mob]?

**REFERENCE (correct)**
Yes. "Protection from all colors" is shorthand for protection from each color individually. It loses protection from black, and still has protection from all the other colors.

(The timestamp of Pristine Angel's ability does not change when it becomes untapped.)

**CANDIDATE**
Yes. Nico can target Pristine Angel with Mob, and Mob will destroy it (barring other effects).

Why: Pristine Angel's static ability reads "As long as this creature is untapped, it has protection from artifacts and from each color." "Protection from each color" is shorthand for several independent protection abilities — protection from white, from blue, from black, from red, and from green — each functioning separately [702.16h], just as "protection from artifacts and from each color" behaves as separate protection abilities [702.16g]. Protection is what stops a permanent from being targeted by spells with the stated quality [702.16b], so only Pristine Angel's protection from black is relevant to Mob, which is a black instant.

Cephalid Snitch's ability said "Target creature loses protection from black until end of turn," and it resolved successfully (legal at the time, since a tapped Pristine Angel had no protection at all and so couldn't stop being targeted). That effect lasts until end of turn and doesn't care whether Pristine Angel is tapped or untapped afterward. Ordering the two effects is a timestamp question: the continuous effect from Pristine Angel's static ability has the same timestamp as Pristine Angel itself (the permanent the ability is on) [613.7a], and Pristine Angel was already on the battlefield before Cephalid Snitch's ability resolved. So Cephalid Snitch's effect has the later timestamp and is applied after Pristine Angel's own effect: Pristine Angel untaps and gains protection from artifacts and from each color, then immediately loses protection from black for the rest of the turn.

Result: for the rest of this turn Pristine Angel still has protection from artifacts, white, blue, red, and green, but not from black, so Mob (a black instant) may legally target it. Note that Mob's convoke doesn't change Mob's color or mana value — tapping creatures only helps pay its {4}{B} total cost — so Mob is black no matter how Nico pays for it (Mob rulings: convoke doesn't change a spell's mana cost or mana value; tapping a creature pays for {1} or one mana of that creature's color).

Timing assumption: I'm assuming Cephalid Snitch's ability was activated and resolved while Pristine Angel was tapped, then Averie's spell untapped it. If instead Cephalid Snitch's ability had been activated while Pristine Angel was untapped, the activation would have been illegal in the first place — an untapped Pristine Angel has protection from blue and couldn't be targeted by Cephalid Snitch's ability, since Cephalid Snitch is a blue source [702.16b].

Player count doesn't matter here: the rules provided (timestamps and protection) work identically in a two-player game and at a multiplayer table.

Card data from Scryfall (scryfall.com).

