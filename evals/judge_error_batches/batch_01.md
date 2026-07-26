# Reference-grading batch batch_01

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
`evals/judge_error_out/batch_01.jsonl` -- nothing else, no prose, no markdown
fence:

    {"cell": "c0001", "verdict": "same", "reason": "<one sentence>"}

`verdict` must be exactly `same` or `different`. Write one line per cell, in
the order the cells appear.

---

### CELL c0001

**Question**
Amiya controls [Fetid Gargantua] with two +1/+1 counters on it. Nico controls [Soul-Scar Mage] and casts [Scorching Lava] targeting Fetid Gargantua. After Scorching Lava resolves, can Fetid Gargantua adapt again?

**REFERENCE (correct)**
Yes. If a permanent has both -1/-1 and +1/+1 counters on it, they are removed as a state-based action. Adapt checks the number of +1/+1 counters on Fetid Gargantua as it resolves, it doesn't matter if it's been activated in the past.

**CANDIDATE**
Yes — Fetid Gargantua can adapt again, and it survives with no damage marked on it.

Step by step:

1. Scorching Lava would deal 2 noncombat damage to Fetid Gargantua, a creature an opponent of Nico controls, and Scorching Lava is a source Nico controls. Soul-Scar Mage's static ability replaces that damage: instead of 2 damage, two -1/-1 counters are put on Fetid Gargantua. Per the Soul-Scar Mage rulings, this is a replacement effect, not a prevention effect, so no damage is actually dealt.

2. Fetid Gargantua now has two +1/+1 counters and two -1/-1 counters. As a state-based action, N +1/+1 and N -1/-1 counters are removed, where N is the smaller number of the two — here N = 2, so all four counters come off [122.3] [704.5q]. This happens automatically the next time a player would receive priority; no one can respond in between.

3. Fetid Gargantua is left a 4/4 with zero counters and zero damage marked. Since "Adapt 2" means "If this permanent has no +1/+1 counters on it, put two +1/+1 counters on it" [701.46a], and the Fetid Gargantua ruling confirms that a creature that loses all its +1/+1 counters can adapt again, Amiya can activate {2}{B}: Adapt 2 and actually get the two counters. That will also trigger Fetid Gargantua's second ability (draw two cards, lose 2 life, if Amiya chooses).

Kicker note: if Nico kicked Scorching Lava (paying the extra {R}), the "can't be regenerated / exile it if it would die" clause is irrelevant here — Fetid Gargantua never takes damage and doesn't die, it just loses its counters.

Player count: this works the same in a two-player game and at a multiplayer table. Soul-Scar Mage's ability keys off "a creature an opponent controls" from the perspective of Soul-Scar Mage's controller, Nico, so as long as Amiya is Nico's opponent the replacement applies regardless of how many players are in the game; the counter-annihilation state-based action [704.5q] is likewise player-count independent.

Card data from Scryfall (scryfall.com).

### CELL c0002

**Question**
Avery manifests the top card of their library with [Soul Summons]. Then, they mutate [Trumpeting Gnarr] targeting the manifested creature. What are the characteristics of the resulting creature if Avery chooses to put the manifested creature on top?

**REFERENCE (correct)**
It is a 2/2 colorless face-down creature with no abilities. It is face-down because the topmost object is face-down, and this status defines its characteristics. This notably means that Trumpeting Gnarr's triggered ability won't trigger.

**CANDIDATE**
Direct answer: the merged permanent is a face-down 2/2 colorless creature with no name, no creature types, and no mana cost (the manifested card's face-down characteristics), but it has all of Trumpeting Gnarr's abilities in addition — including "Whenever this creature mutates, create a 3/3 green Beast creature token," which already triggered when the merge happened.

Why:
- Mutating merges the spell with the target rather than having Trumpeting Gnarr enter separately; the controller picks top or bottom, and the result is one mutated permanent represented by both cards [702.140c] [608.3d] [730.2e] [Mutating Creature Spell].
- A mutated permanent has all abilities of each card representing it, but its other characteristics (name, mana cost, color, types, power/toughness) come from the topmost component [702.140e]. With the manifested card on top, those come from the face-down manifested card, i.e. a 2/2 colorless nameless creature with no mana cost — that is what "manifest" produces (put onto the battlefield face down as a 2/2 creature, turnable face up for its mana cost if it's a creature card) per Soul Summons.
- Status is also set by the topmost component, so the merged permanent is face down [730.2e] [110.5]. These merge-derived characteristic changes are copiable and applied in layer 1a [613.2a].
- Trumpeting Gnarr's mutate trigger is an ability of a component, so the permanent has it; the mutate event occurred as the spell resolved, so Avery gets a 3/3 green Beast token.

Practical notes: any effect that referred to the mutating Trumpeting Gnarr spell now refers to the mutated permanent [702.140f]. If Avery later turns the permanent face up (paying the mana cost of the manifested card, if it's a creature card), the topmost component would then supply that card's name, cost, colors, types and power/toughness, while it still keeps Trumpeting Gnarr's abilities [702.140e]. Nothing in the provided rules covers whether a double-faced manifested card is involved; if the manifested component were double-faced, note only that a face-up merged permanent containing a double-faced component can't be turned face down [730.2j].

Assumption on timing: I'm assuming Soul Summons fully resolved before Trumpeting Gnarr was cast for its mutate cost, and that the manifested creature was still a legal target on resolution; if the target were illegal on resolution, no merge occurs and no mutate trigger happens [702.140c]. Also, the provided context contains no restriction against mutating onto a face-down creature, so this answer follows the rules as given; a face-down creature has no creature types, hence it is non-Human for Trumpeting Gnarr's targeting requirement. Player count doesn't matter here — none of the cited rules distinguish two-player from multiplayer games.

Card data from Scryfall (scryfall.com).

### CELL c0003

**Question**
Ainsley controls a [Blood Moon], a [Life and Limb], a [Cinder Glade], and a 1/1 Green Saproling Creature token, that entered the battlefield in that order. What do the Cinder Glade and Saproling look like?

**REFERENCE (correct)**
Cinder Glade is a noncreature Land - Mountain with "{T}: Add {R}." and no other abilities. The Saproling is a 1/1 Green Land Creature - Forest Saproling with "{T}: Add {G}." and no other abilities.

Applying Life and Limb's effect first would allow Blood Moon's effect to apply to the Saproling, and applying Blood Moon's effect first would prevent Life and Limb from applying to the Cinder Glade, so both effects are dependent on each other and those dependencies are ignored. Blood Moon has the earlier timestamp, so it's applied first.

As Blood Moon's effect is applied, Cinder Glade becomes a Mountain and loses the "Forest" subtype. Then Life and Limb's effect is applied, making the Saproling into a land.

**CANDIDATE**
Direct answer: Cinder Glade is just a nonbasic Land — Mountain with "{T}: Add {R}" (not a creature). The Saproling token is a 1/1 green Saproling Creature Land — Mountain with "{T}: Add {R}" (no green mana ability).

Why, layer by layer (both effects are type-changing effects in layer 4, CR 613.6):

Cinder Glade: Blood Moon says "Nonbasic lands are Mountains." Cinder Glade has no "basic" supertype, so it's nonbasic (CR 205.4c). Setting a land's subtype to a basic land type strips its old land types, its rules-text abilities, and gives it the intrinsic "{T}: Add {R}" (CR 305.7, 305.6, Blood Moon ruling #2). So it loses Forest, loses "{T}: Add {G}", and loses "This land enters tapped unless you control two or more basic lands." Because it is no longer a Forest, Life and Limb — which only affects Forests and Saprolings — never applies to it at all. (Blood Moon is applied first here both by timestamp and because Life and Limb's applicability depends on it, CR 613.8a-style dependency.)

Saproling token: Life and Limb makes all Saprolings 1/1 green Saproling creatures and Forest lands in addition to their other types (CR 205.1b, 205.3c; Life and Limb ruling #3 — Forest is the land type, Saproling the creature type). That makes the token a Forest land with no "basic" supertype, i.e. a nonbasic land, which is now something Blood Moon applies to. So Blood Moon is applied after Life and Limb here (its effect on the token exists only because Life and Limb applied). Blood Moon sets its land subtype to Mountain: it loses Forest and the {G} ability and gains "{T}: Add {R}" (CR 305.7). Setting a land's subtype doesn't remove card types or creature types (CR 305.7, 205.4b), so it keeps Creature and Land and keeps Saproling; Life and Limb's color and 1/1 parts still apply in layers 5 and 7b (CR 613.6). Result: a 1/1 green Saproling Creature Land — Mountain, subject to summoning sickness, and it can only be played as a land if it were ever a card (CR 305.9 — irrelevant for a token on the battlefield).

Note a loop-ish consequence: it is Life and Limb that made the token a Forest, and Blood Moon's dependent application then removes the Forest type — but under CR 613.6 Life and Limb's other parts keep applying, and the type-adding part still applied first, so the outcome above is stable.

Nothing here depends on player count; the answer is the same at a two-player or multiplayer table, since both enchantments affect all matching permanents regardless of controller.

Card data from Scryfall (scryfall.com).

### CELL c0004

**Question**
Ahmad controls [Conspiracy] (naming "Ferret"), [Kormus Bell], [Urborg, Tomb of Yawgmoth], and a [Vastwood Zendikon] enchanting Urborg, Tomb of Yawgmoth that entered the battlefield in that order. Is Urborg, Tomb of Yawgmoth a creature? If so, what are its creature types?

**REFERENCE (correct)**
It is an Elemental Ferret creature. Conspiracy has the earliest timestamp, but it's dependent on Vastwood Zendikon, and waits to apply until after Vastwood Zendikon is applied. Kormus Bell is dependent on Urborg, Tomb of Yawgmoth, so Urborg, Tomb of Yawgmoth is applied first, then Kormus Bell. At this point Conspiracy is no longer be dependent on Vastwood Zendikon, so Conspiracy is applied, and then Vastwood Zendikon. Since Vastwood Zendikon says that Urborg, Tomb of Yawgmoth is still a land, it retains its prior creature type of "Ferret" when it becomes an Elemental.

**CANDIDATE**
Yes — Urborg, Tomb of Yawgmoth is a creature, and its only creature type is Ferret. Its full type line ends up as "Legendary Land Creature — Swamp Ferret" (Swamp is a land type, Ferret the creature type), and it's a 6/4 green creature.

How it gets there, working through the type-changing effects in timestamp order:

1. Urborg, Tomb of Yawgmoth's own ability makes each land a Swamp in addition to its other land types, including itself while it's on the battlefield ([Urborg, Tomb of Yawgmoth ruling #0], [Urborg, Tomb of Yawgmoth ruling #2]).
2. Kormus Bell then sees a Swamp: "All Swamps are 1/1 black creatures that are still lands," so Urborg, Tomb of Yawgmoth becomes a land creature and keeps its land types and its Legendary supertype ([205.1b], [205.4b], [Kormus Bell ruling #0]).
3. Vastwood Zendikon makes the enchanted land a 6/4 green Elemental creature that's still a land ([Vastwood Zendikon ruling #5]). Since it's later than Kormus Bell, it sets the color to green and the power/toughness to 6/4.
4. Conspiracy, though it entered first, has to be applied after the others in the type-changing layer: it only affects creatures Ahmad controls, and whether Urborg, Tomb of Yawgmoth is a creature at all is determined by Kormus Bell and Vastwood Zendikon. Applying Conspiracy last, it sets the creature type to the chosen type, Ferret, and the permanent loses all other creature types — so the Elemental type from Vastwood Zendikon is gone ([Conspiracy ruling #4]). Conspiracy can grant a creature type to animated lands that would otherwise have none ([Conspiracy ruling #1]).

Notes: Conspiracy changes only creature types, so the land type Swamp ([205.3c] — subtypes correlate to the card type they belong to) and the Legendary supertype ([205.4b]) both remain. Urborg, Tomb of Yawgmoth still has all its card types (land and creature) and satisfies anything that cares about either ([205.2b]). Conspiracy also doesn't rewrite creature-type words in card text ([Conspiracy ruling #0]).

Nothing here depends on the number of players; the answer is the same in a two-player game or at a multiplayer table, since all four permanents are Ahmad's.

Card data from Scryfall (scryfall.com).

### CELL c0005

**Question**
Alfonso has 20 life and has cast a [Channel] previously this turn. Nancy casts [Word of Command], choosing [Squire] from Alfonso's hand. Can Nancy have Alfonso pay 20 life to add 20 colorless mana while casting the Squire, causing Alfonso to lose the game?

**REFERENCE (correct)**
Yes. There is no restriction on how much mana Alfonso can add while casting Squire. While Word of Command does prevent Alfonso from activating mana abilities that aren't used to cast Squire, paying 1 life to add {C} due to Channel is not a mana ability, it is a special action.

**CANDIDATE**
No. While Nancy controls Alfonso under Word of Command, Word of Command's own text says the controlled player "can activate mana abilities only if they're from lands that player controls and only if mana they produce is spent to activate other mana abilities of lands the player controls and/or to play that card." Channel's effect is not a mana ability of a land Alfonso controls — it's a floating effect from a resolved sorcery that lets him pay 1 life for {C} any time he could activate a mana ability — so Nancy cannot use it at all during the Word of Command play. This card-specific restriction overrides the general rule (723.5a) that a controller may otherwise freely use the controlled player's resources to pay costs.

Two further points, had the restriction not existed:
- Squire costs {1}{W}. The {W} must be white mana, which Channel's {C} can never pay; {C} is colorless specifically and only the {1} generic portion could be paid with it (202.1). So Channel mana alone can't even cast Squire.
- Under Word of Command, mana produced must be spent on that card or on other land mana abilities, so making 20 extra {C} "for nothing" isn't a legal use.

On the life question itself: paying 20 life at exactly 20 life would be legal in the abstract, since a player may pay life only if their life total is at least the payment (119.4, 118.3), and Alfonso would then be at 0 and lose the game the next time a player would receive priority (119.6, 104.3b). But per Channel ruling #0, once at 0 he could not pay any further life. That path just isn't available here because of Word of Command's mana-ability restriction.

This analysis doesn't depend on player count — Word of Command targets one opponent, so it reads the same in a two-player game or at a multiplayer table.

Card data from Scryfall (scryfall.com).

### CELL c0006

**Question**
Alex controls an [Oracle of Mul Daya] and has played 2 lands this turn. They casts [Flicker], targeting the Oracle of Mul Daya. After if resolves, can they play a 3rd land?

**REFERENCE (correct)**
No. Alex has 1 land play this turn by default, which Oracle of Mul Daya increase to 2. Alex has already played 2 lands this turn, so no more lands can be played.

**CANDIDATE**
No. Alex has already used up both of their land plays for the turn (their normal one plus the extra one granted by Oracle of Mul Daya's static ability), and flickering Oracle of Mul Daya doesn't reset that count or grant an additional play.

Oracle of Mul Daya's static ability "You may play an additional land on each of your turns" raises the number of lands Alex can play this turn from 1 to 2. Per rule [305.2a]/[305.2b], whether a land play is legal depends on comparing the number of lands Alex can play this turn (2, thanks to Oracle of Mul Daya) against the number already played (2). Since those numbers are equal, Alex can't play a land, for any reason — the "can't" language in [305.2b] is absolute.

Casting Flicker to exile and return Oracle of Mul Daya doesn't change this. When Oracle of Mul Daya is exiled and returns to the battlefield, it becomes a new object with no memory of its previous existence per [400.7i]. But that matters for tracking things like "activated this turn" or targeting, not for the land-play count. Oracle of Mul Daya's land-granting ability is a continuous effect from a static ability, and per [611.3a]/[611.3d] such an effect "isn't locked in"; it just applies at any given moment based on whether a permanent with that static ability is on the battlefield. Since the returned Oracle of Mul Daya (new object) still has the exact same static ability, Alex still has permission to play 2 lands total this turn — no more, no less. Nothing about exiling and returning the permanent resets Alex's count of lands already played, and Oracle of Mul Daya's own ruling [Oracle of Mul Daya ruling #0] confirms the additional-land effects from multiple copies are simply cumulative counts, not one-time triggers that reset.

So Alex remains capped at 2 land plays for the turn, both of which are already used, and cannot play a third land this turn.

Card data from Scryfall (scryfall.com).

### CELL c0007

**Question**
Nathaniel controls [Dryad Militant]. Armani casts [Hanabi Blast]. Does it return to their hand?

**REFERENCE (correct)**
Yes. Resolving spells do not leave the stack until they finish resolving. Returning the Hanabi Blast to its owner's hand is part of its resolution, so it is never put into exile.

**CANDIDATE**
Yes. When Hanabi Blast finishes resolving, its own text moves it directly to its owner's hand ("Return Hanabi Blast to its owner's hand, then discard a card at random") — it never passes through the graveyard, so Dryad Militant's replacement effect ("If an instant or sorcery card would be put into a graveyard from anywhere, exile it instead") has nothing to apply to. Dryad Militant only intercepts instants/sorceries that would actually go to a graveyard; a card that a resolving spell's own effect sends to hand is not such an event. Hanabi Blast returns to its owner's hand — Armani, assuming Armani is the owner as well as the caster — and Armani then discards a card at random as the spell's cost/effect finishes resolving.

Card data from Scryfall (scryfall.com).

### CELL c0008

**Question**
In a two-player game, Ally casts [Rushblade Commander]. Can they attack with it this turn?

**REFERENCE (correct)**
Yes. In a two-player game, "your team" means "you".

**CANDIDATE**
Yes. Rushblade Commander is itself a Warrior (Creature — Azra Warrior), and its own ability says "Warriors your team controls have haste," so Rushblade Commander gives itself haste and can attack the turn it comes down.

Why: normally the "summoning sickness" rule stops a creature from attacking (or activating abilities with {T} or {Q} in the cost) unless it has been under its controller's control continuously since the beginning of that player's most recent turn [302.6]. Haste turns that off: a creature with haste can attack even if its controller hasn't controlled it continuously since their most recent turn began [702.10b], and its {T}/{Q} abilities can be activated right away too [702.10c]. When declaring attackers, each chosen creature must be untapped and must either have haste or have been controlled since the turn began [508.1a] — Rushblade Commander satisfies the haste clause.

Note this is a static ability that applies as soon as Rushblade Commander is on the battlefield, so no waiting is needed. This works the same in a two-player game as at a multiplayer table; in formats with teams, the ability also grants haste to Warriors your teammates control ("your team controls"), which is card text beyond the general rules quoted here.

Assumption: Rushblade Commander resolved before your declare attackers step (e.g., cast in your main phase); if it somehow entered after the declare attackers step, haste wouldn't help — there would be no attacker declaration left this turn.

Card data from Scryfall (scryfall.com).

### CELL c0009

**Question**
Aiden controls [Volrath's Shapeshifter] and [Yixlid Jailer]. The top card of their graveyard is [Mistform Skyreaver]. Does Volrath's Shapeshifter have flying?

**REFERENCE (correct)**
Yes. Yixlid Jailer only removes abilities, not text, and text is what Volrath's Shapeshifter cares about. Volrath's Shapeshifter also gains the text of the Mistform Skyreaver before Yixlid Jailer removes the abilities.

**CANDIDATE**
No — Volrath's Shapeshifter does not have flying in this situation.

Why: Volrath's Shapeshifter says that as long as the top card of your graveyard is a creature card, it has the "full text" of that card plus the text "{2}: Discard a card." Per [612.6], "full text" changes not just the text box and type line but also the name, mana cost, color indicator, power, and toughness. So it would normally pick up Mistform Skyreaver's name, mana cost, color, types, 6/6 body, and Mistform Skyreaver's abilities (Flying and "{1}: This creature becomes the creature type of your choice until end of turn").

But Yixlid Jailer says "Cards in graveyards lose all abilities." A card's own printed text controls here, and Mistform Skyreaver is a card in a graveyard, so it currently has no abilities at all. There is no flying text on it to copy. What Volrath's Shapeshifter takes on is the text of the card as it exists — a Mistform Skyreaver with an empty ability set. The only exception is a characteristic-defining ability like changeling, which still functions from the graveyard per [Yixlid Jailer ruling #1]; flying is a normal static keyword ability ([702.9a], [Flying]), not a CDA, so it is stripped.

Result: Aiden's Volrath's Shapeshifter is a 6/6 blue creature named Mistform Skyreaver, Creature — Illusion, with mana cost {5}{U}{U}, whose only ability is the granted "{2}: Discard a card" ([Volrath's Shapeshifter ruling #1] — it keeps the granted ability in addition to those of the copied card). Without flying it can be blocked by any creature ([702.9b]).

Timing note: this is a static, continuously-checked condition. If Yixlid Jailer leaves the battlefield (or stops applying) while Mistform Skyreaver is still the top card of the graveyard, Mistform Skyreaver regains its abilities and Volrath's Shapeshifter immediately gains flying and the {1} type-changing ability.

Player count doesn't matter here: Yixlid Jailer affects cards in all graveyards, and none of the rules involved depend on the number of players, so the answer is the same in a two-player or multiplayer game.

Card data from Scryfall (scryfall.com).

### CELL c0010

**Question**
Nico controls [Humility]. Aitana casts [Finale of Devastation] with X = 10. Will the creature they find have haste?

**REFERENCE (correct)**
Yes. Both effects apply in layer 6, and are applied in timestamp order. Since Finale of Devastation's effect has the most recent timestamp, it's applied last.

**CANDIDATE**
Yes — the creature Aitana finds will have haste (and it'll be an 11/11).

Why: Humility creates a continuous effect that applies in layer 6 ("lose all abilities") and layer 7b ("base power and toughness 1/1") [613.1]. Finale of Devastation, resolving later, grants haste in layer 6 and +10/+10 in layer 7c, and both of its effects have a later timestamp than Humility's [113.10c]. Within layer 6 the effects are applied in timestamp order: Humility strips the creature's abilities first, then Finale of Devastation adds haste afterward, so haste sticks — when two effects add and remove abilities, the most recent one prevails [113.10c]. Note Humility says "lose all abilities," not "can't have abilities," so it can't stop a later grant [113.11].

Power/toughness: layer 7b sets base 1/1 (Humility), then layer 7c adds +10/+10 (Finale of Devastation), for 11/11.

Timing detail: Finale of Devastation's ruling confirms the creature you just put onto the battlefield gets +X/+X and haste when X is 10 or more [Finale of Devastation ruling #2], and no player can act in between [Finale of Devastation ruling #0]. Humility's ability-removal applies the moment the creature is on the battlefield, so any enters-the-battlefield triggered ability it had won't trigger [603.6b] — but that doesn't affect the haste grant, which comes from outside the creature. Haste itself lets the creature attack and use {T}/untap abilities despite summoning sickness [702.10c, 302.6].

Multiplayer: the analysis is identical regardless of player count — Humility affects all creatures and Finale of Devastation affects only creatures Aitana controls; the number of opponents doesn't change the layer ordering.

(If instead Humility had entered the battlefield after Finale of Devastation resolved, Humility's layer-6 removal would be the later timestamp and the creature would lose haste.)

Card data from Scryfall (scryfall.com).

### CELL c0011

**Question**
Ainsley controls [Furycalm Snarl], [Humility], [Magus of the Moon], and [Crosis's Catacombs] that entered the battlefield in that order. What are the characteristics of the Furycalm Snarl and Crosis's Catacombs?

**REFERENCE (correct)**
They are both Mountains with no abilities other than "{T}: Add {R}". Magus of the Moon's effect applies in layer 4, while Humility's effect applies in layer 6 and 7. Magus of the Moon is a 1/1 with no abilities, but it still turns nonbasic lands into Mountains.

**CANDIDATE**
Both Furycalm Snarl and Crosis's Catacombs are nonbasic lands with the single land subtype Mountain, and both have the intrinsic mana ability "{T}: Add {R}" from that subtype. Neither is a creature, so Humility does nothing to either land.

Why Magus of the Moon still works even though Humility is on the battlefield: continuous effects are applied in layer order (CR 613.1), not timestamp order across layers. Magus of the Moon's "Nonbasic lands are Mountains" is a type-changing effect applied in layer 4; Humility's "All creatures lose all abilities" is applied in layer 6. Layer 4 is applied first, at which point Magus of the Moon still has its ability, so the land-type change happens. Once an effect has started to apply, it keeps applying in later layers even though the ability generating it is stripped in layer 6 (CR 613.6). So Humility does not turn off Magus of the Moon's effect on lands (Humility does make Magus of the Moon itself a 1/1 with no abilities as a creature).

Both lands are nonbasic: neither has the "basic" supertype, and a land is nonbasic even if it has a basic land type (CR 205.4c). Crosis's Catacombs loses the Lair subtype, since the type-changing effect sets its land subtype to Mountain; Furycalm Snarl had no land subtype to begin with (Furycalm Snarl ruling #1) and now has Mountain. Being Mountains, each has "{T}: Add {R}" (CR 305.6, CR 107.4a). Neither is affected in color, card type (still just Land), or power/toughness — lands have none.

One gap: the provided context does not include the rule (CR 305.7) governing whether an effect that sets a land's subtypes also removes the land's other abilities. Under the rules given here I can only confirm the subtype change and the added "{T}: Add {R}"; in practice such effects also strip the lands' other abilities, so treat Furycalm Snarl's "{T}: Add {R} or {W}" and Crosis's Catacombs' "{T}: Add {U}, {B}, or {R}" and its sacrifice trigger as unreliable from this context. Both lands' enters-the-battlefield abilities already resolved before Magus of the Moon arrived, so they're moot now.

Assumed timing: Magus of the Moon entered after Humility and is on the battlefield now; if Magus of the Moon left the battlefield, the lands would immediately revert to their printed types and abilities. Nothing here depends on player count — the answer is the same in a two-player game or a multiplayer game, since Magus of the Moon affects all nonbasic lands regardless of controller.

Card data from Scryfall (scryfall.com).

### CELL c0012

**Question**
Armani controls [Soul Echo] with 0 counters on it and Nico controls [Spirit of the Hearth]. Will Armani have to sacrifice Soul Echo at the beginning of their upkeep?

**REFERENCE (correct)**
No. Since the ability has no legal targets, it would trigger at the beginning of the upkeep but would not be put on the stack.

**CANDIDATE**
Yes. At the beginning of Armani's upkeep, Soul Echo's triggered ability checks whether there are any echo counters on it. Soul Echo's text reads: "At the beginning of your upkeep, sacrifice this enchantment if there are no echo counters on it. Otherwise, target opponent may choose that for each 1 damage..." Since Soul Echo currently has 0 echo counters, the first branch of the ability applies and Armani sacrifices Soul Echo — the 'otherwise' clause (which is the only part that would target an opponent) never comes into play. Nico's Spirit of the Hearth grants Nico hexproof, meaning Nico "can't be the target of spells or abilities your opponents control," but that's irrelevant here: the sacrifice-if-empty branch of Soul Echo's ability doesn't target Nico (or anyone) at all — it's simply Armani sacrificing their own permanent. Hexproof only stops Armani's spells/abilities from targeting Nico; it does nothing to stop Armani from sacrificing their own enchantment. So Spirit of the Hearth's hexproof has no effect on this outcome, and Armani must sacrifice Soul Echo.

Card data from Scryfall (scryfall.com).

### CELL c0013

**Question**
Avery controls [Wayward Angel] and has 7 cards in their graveyard. Nathan casts [Turn to Frog], targeting Wayward Angel. What are Wayward Angel's characteristics after Turn to Frog resolves?

**REFERENCE (correct)**
It's a 4/4 blue Frog with no abilities. Wayward Angel's last ability begins to apply in layer 5. It's removed by Turn to Frog in layer 6, but since it's already started to apply, it will continue doing so in later layers. Wayward Angel has the earlier timestamp, so it gives itself trample and "At the beginning of your upkeep, sacrifice a creature" before Turn to Frog removes its abilities in layer 6.

**CANDIDATE**
Wayward Angel becomes a 4/4 blue Frog creature with no abilities.

Breakdown by layer (rule 613.1e–613.1g). Wayward Angel's Threshold ability is a static ability, so its continuous effect has Wayward Angel's own timestamp (rules 613.7a, 613.7d), which is earlier than the effect from Turn to Frog, which gets its timestamp when it resolves (rule 613.7b). Earlier timestamps apply first within a layer (rule 613.7).

- Color (layer 5, rule 613.1e): Threshold makes Wayward Angel black first (and only black — see the Wayward Angel ruling that it is black, not white and black); then Turn to Frog's later effect makes it blue. Final color: blue only ([Turn to Frog ruling #2]: it loses all other colors and creature types).
- Types: Turn to Frog makes it a Frog, so Angel and Horror are gone. It keeps any other card types or supertypes it had ([Turn to Frog ruling #2]) — Wayward Angel has none beyond "creature."
- Abilities (layer 6, rule 613.1f): The Threshold effect first grants trample and "At the beginning of your upkeep, sacrifice a creature"; then Turn to Frog's later ability-removal strips everything — flying, vigilance, trample, the upkeep sacrifice trigger, and the Threshold static ability itself. Wayward Angel has no abilities.
- Power/toughness (layer 7, rule 613.1g): Turn to Frog sets base power and toughness to 1/1 in layer 7b ([Turn to Frog ruling #1]). The Threshold effect's +3/+3 part still applies in layer 7c: under rule 613.6, once an effect starts applying, its other parts keep applying in their own layers even though the ability that generated it was removed in layer 6. That matches [Turn to Frog ruling #3], that power/toughness-modifying effects apply no matter when they started. So 1/1 base +3/+3 = 4/4.

Caveat on timing/graveyard size: this assumes Avery still has seven or more cards in the graveyard at the time Turn to Frog resolves, so the Threshold effect is already applying. If the graveyard had fewer than seven cards when Turn to Frog resolved, no Threshold effect would ever start applying (and the ability is then removed), leaving a 1/1 blue Frog with no abilities.

Nothing here depends on the number of players — the result is the same in a two-player game or at a multiplayer table.

Card data from Scryfall (scryfall.com).

### CELL c0014

**Question**
Ari attacks with [Suntail Hawk]. Nayeli casts [Vault Skyward] to give [Brimaz, King of Oreskos] flying until end of turn and blocks Suntail Hawk. Will the token created by Brimaz, King of Oreskos also be blocking Suntail Hawk?

**REFERENCE (correct)**
Yes. The only time the game checks to see if the declaration of blockers is illegal is as Nayeli declares blockers. A creature that's put onto the battlefield blocking isn't declared as a blocker and isn't affected by requirements or restrictions that normally alter what a player is allowed to declare as a blocker.

**CANDIDATE**
Yes. When Brimaz, King of Oreskos is declared as a blocker for Suntail Hawk, its triggered ability triggers and creates a 1/1 white Cat Soldier token with vigilance that's put onto the battlefield blocking Suntail Hawk — the effect itself specifies what the token is blocking, so no choice is made (509.4).

Importantly, the token does not need flying. A creature that's put onto the battlefield blocking isn't affected by requirements or restrictions that apply to the declaration of blockers, so Suntail Hawk's flying doesn't stop the token from blocking it (509.4b). Vault Skyward only mattered for letting Brimaz, King of Oreskos itself be legally declared as a blocker for the flier.

Two timing/technical notes:
- Vault Skyward must have been cast before blockers were declared for Brimaz, King of Oreskos to be declared as a blocker; if it were cast after the declare blockers step began, Brimaz, King of Oreskos couldn't have blocked Suntail Hawk at all and the block trigger would never have happened (Vault Skyward ruling #1).
- The token is "blocking" but for trigger purposes it never "blocked" and was never declared as a blocker, so abilities that trigger on a creature blocking won't trigger from it (509.4, 509.3a, 509.3b, Brimaz, King of Oreskos ruling #2). Likewise, Suntail Hawk already became a blocked creature when Brimaz, King of Oreskos was declared, so the token entering doesn't re-trigger "becomes blocked" abilities (509.3c).

The trigger is put on the stack before the active player gets priority in the declare blockers step (509.2a), so the token appears then, and Suntail Hawk must assign combat damage among both blockers. This works the same in two-player and multiplayer games; the only multiplayer wrinkle is that the token's controller must be a defending player for Suntail Hawk, which Nayeli is here (509.4a).

Card data from Scryfall (scryfall.com).

### CELL c0015

**Question**
Alden controls [Spark Double] and casts [Clone]. Alden would like to have Clone copy Spark Double, then they would like to apply the replacement effect Clone inherited from Spark Double and have it copy Spark Double again. If Alden has Clone copy Spark Double a total of four times, how many +1/+1 counters will Clone enter the battlefield with?

**REFERENCE (correct)**
One. Spark Double has a copy effect that includes an exception (entering with a +1/+1 counter). If another copy effect is applied afterwards, the exception from the first effect will not happen.

**CANDIDATE**
Clone enters the battlefield with exactly one +1/+1 counter — not four.

Why: Clone's own replacement effect lets it enter as a copy of Spark Double. Because copy effects are copiable, Clone now also has Spark Double's replacement effect: "You may have this creature enter as a copy of a creature or planeswalker you control, except it enters with an additional +1/+1 counter on it if it's a creature... and it isn't legendary." Alden may apply that inherited effect and copy Spark Double again, and again, and again.

But the "+1/+1 counter" part of Spark Double's text is an exception that is an additional effect, not a modification of the copied characteristics. Rule 707.9e says that if another copy effect is applied to the object after the copy effect that carried such an exception, that exception's effect doesn't happen. So each new application of a Spark Double copy effect wipes out the pending counter from the previous application. After four total copy applications, only the last one's exception survives, giving Clone one +1/+1 counter.

Result: Clone enters as a copy of Spark Double (a 0/0 Illusion with Spark Double's abilities, and non-legendary — the "isn't legendary" part is a characteristic modification and is copiable, per Spark Double's rulings), with a single +1/+1 counter on it, so it's a 1/1.

Two assumptions worth stating: (1) I'm assuming the Spark Double already on the battlefield isn't itself copying some other permanent; if it were, Clone would enter as whatever that Spark Double copied (per Spark Double's and Clone's rulings), though the counter math would be the same — one counter. (2) Spark Double's inherited effect can only copy a creature or planeswalker Alden controls, so every re-application must target Alden's own Spark Double (Clone's own effect, by contrast, could have copied any creature on the battlefield). That control restriction is the only thing that changes at a multiplayer table versus a two-player game: with more opponents there are simply more creatures Clone's original effect could have chosen, but the inherited Spark Double effect is still limited to permanents Alden controls, and the counter count is still one.

Card data from Scryfall (scryfall.com).

### CELL c0016

**Question**
Apollo controls [Realmwright] naming "Island", [Arcane Adaptation] naming "Saproling", and [Life and Limb], which entered the battlefield in that order. What are the types and subtypes of Realmwright?

**REFERENCE (correct)**
Realmwright is a 1/1 green Land Creature - Vedalken Wizard Saproling Forest.

All three cards have effects in layer 4, the type changing layer. The game first looks at Realmwright's effect since it's first in timestamp order, sees that it's not dependent on Arcane Adaptation nor on Life and Limb, and applies it. Next the game looks at Arcane Adaptation's effect, sees that it's not dependent on Life and Limb, and applies it, followed by Life and Limb last.

Life and Limb lets it keep its original creature types, but not its original colors.

**CANDIDATE**
Realmwright ends up as a **Land Creature — Forest Island Vedalken Wizard Saproling** (no supertypes), and it's a green 1/1.

How it gets there, all in layer 4 (type-changing effects, CR 613.1d):

1. **Arcane Adaptation** (naming Saproling) makes every creature Apollo controls that type in addition to its other types, so Realmwright becomes a Vedalken Wizard Saproling (CR 205.1b — "in addition to its other types" keeps all prior types).
2. **Life and Limb** then applies, because Realmwright is now a Saproling: "All Forests and all Saprolings are 1/1 green Saproling creatures and Forest lands in addition to their other types." Realmwright gains the card type land and the land type Forest, keeping creature and its creature types. Per [Life and Limb ruling #3], the subtypes stay correlated to the right card type — Forest is a land type, Saproling/Vedalken/Wizard are creature types (CR 205.3c).
3. **Realmwright's own ability** — "Lands you control are the chosen type in addition to their other types" — now applies to Realmwright itself, because Realmwright is a land. It gains the land type Island (a basic land type, per [Realmwright ruling #1]).

Ordering note: Realmwright's ability has the earliest timestamp, but the **dependency** rule overrides timestamps here (CR 613.7, CR 613.8, CR 613.8a). Applying Life and Limb changes what Realmwright's effect applies to (it makes Realmwright a land), so Realmwright's effect is applied after Life and Limb's; likewise Life and Limb depends on Arcane Adaptation, which is also the timestamp order anyway. Importantly, because Realmwright gains Island *in addition to* its other land types, this is not a subtype-setting effect, so CR 305.7's "loses its old land types and abilities" clause does **not** kick in — Realmwright keeps Forest, keeps its own rules text, and gains the Island mana ability ({T}: Add {U}) as well as Forest's ({T}: Add {G}).

Other characteristics for completeness: Life and Limb sets the color to green in layer 5 and the power/toughness to 1/1 in layer 7b, so Realmwright is a green 1/1 (it was already 1/1). It's also now subject to summoning sickness as a land creature. Nothing here depends on the number of players — the answer is the same in a two-player or multiplayer game, since all three permanents are Apollo's own and only affect permanents Apollo controls/owns.

Card data from Scryfall (scryfall.com).

### CELL c0017

**Question**
Nico controls Analia's [Bane Alley Blackguard] enchanted with their [Corrupted Conscience]. Analia casts their own [Lay Claim], targeting Nico's Corrupted Conscience. After it resolves, who controls the Bane Alley Blackguard? Who controls the Corrupted Conscience?

**REFERENCE (correct)**
Analia controls both permanents. Out of the two auras, Corrupted Conscience has the earlier timestamp, and would normally be applied first. However, the effects from both auras apply in the same layer, applying the Lay Claim's effect would change how the Corrupted Conscience's effect is applied, and applying the Corrupted Conscience's effect would not change how the Lay Claim's effect is applied, so the Corrupted Conscience's effect is dependent on the Lay Claim's effect. The Lay Claim's effect applies first, giving Analia control of Corrupted Conscience, and then the Corrupted Conscience's effect applies, giving Analia control of Bane Alley Blackguard.

**CANDIDATE**
Analia controls both. After Lay Claim resolves, Analia controls Corrupted Conscience, and because Corrupted Conscience reads "You control enchanted creature" — with "you" meaning Corrupted Conscience's current controller — Analia also controls Bane Alley Blackguard.

Why: Lay Claim enchants a permanent and says "You control enchanted permanent." Corrupted Conscience is a permanent (an Aura enchantment), so Lay Claim can legally enchant it, and on resolution Lay Claim enters the battlefield under Analia's control attached to Corrupted Conscience [608.3c]. That control-change effect makes Analia the controller of Corrupted Conscience. An Aura's controller is tracked separately from the controller of the thing it enchants, so Corrupted Conscience simply stays attached to Bane Alley Blackguard while changing controllers [303.4e]. Corrupted Conscience's own control-changing effect then applies for its new controller — as Lay Claim's ruling explains, an Aura's effect that refers to "you" affects the Aura's controller [Lay Claim ruling #0]. So Bane Alley Blackguard moves from Nico's control to Analia's.

Notes: Analia is the owner of Bane Alley Blackguard, but ownership is irrelevant to who controls it here [110.2]. Bane Alley Blackguard still has infect from Corrupted Conscience, and since Corrupted Conscience is now an Aura controlled by Bane Alley Blackguard's controller (Analia), Bane Alley Blackguard counts as modified [700.9]. Nico now controls neither permanent. This works the same at a two-player table or in multiplayer; nothing here depends on the number of players.

Timing note: I'm assuming Lay Claim resolved normally with Corrupted Conscience still on the battlefield and still attached to Bane Alley Blackguard. If Corrupted Conscience had left the battlefield before Lay Claim resolved, Lay Claim would be countered for having an illegal target and Nico would have kept nothing — Bane Alley Blackguard would revert to Analia's control anyway once Corrupted Conscience was gone.

Card data from Scryfall (scryfall.com).

### CELL c0018

**Question**
Andi controls [Karn Liberated], which has exiled an [Anvil of Bogardan]. They activate Karn Liberated's -14 ability, and restarts the game. How many cards will they draw during their first turn?

**REFERENCE (correct)**
0. Their entire draw step is skipped. Andi will be the starting player in the new game. Because they is the starting player they'll skip their first draw step. Anvil of Bogardan triggers at the beginning of the draw step, but it doesn't get a chance to trigger if that step is skipped.

**CANDIDATE**
Direct answer: In a two-player game, Andi draws zero cards during their first turn. In a game with three or more players, Andi draws two cards (their normal draw for the turn plus Anvil of Bogardan's extra card) and then discards one.

Why:

1. Karn Liberated's −14 restarts the game, and the player who controlled the restarting ability — Andi — is the starting player in the new game [727.1a]. Anvil of Bogardan, having been exiled with Karn Liberated by one of its first two abilities, stays in exile through the restart and is then put onto the battlefield under Andi's control after the pregame procedure but before the new game's first turn [Karn Liberated ruling #5, Karn Liberated ruling #7]. So Anvil of Bogardan is already on the battlefield when Andi's first turn begins, and it's treated as having been under Andi's control since the beginning of that turn [Karn Liberated ruling #3].

2. Two-player game: the player who plays first skips the draw step of their first turn [103.8a]. To skip a step is to proceed past it as though it didn't exist [500.11], and anything scheduled for a skipped step simply doesn't happen [614.10a]. Since Anvil of Bogardan's ability triggers "at the beginning of each player's draw step," and Andi has no first-turn draw step at all, the ability never triggers — no extra draw and no discard. Note this is different from Anvil of Bogardan ruling #1: that ruling covers the case where the draw *event* inside the resolving ability is replaced, in which case the discard still happens. Here the whole step, and therefore the trigger itself, never occurs. Total cards drawn on Andi's first turn: 0.

3. Three or more players: rule 103.8a's skipped draw step applies only "in a two-player game," so Andi does get a draw step on turn one. Andi draws their card for the turn, then Anvil of Bogardan's ability goes on the stack (it's put on the stack after the turn-based draw has already happened) [Anvil of Bogardan ruling #4], resolves, Andi draws an additional card and discards a card. Total drawn: 2, with one discard.

Not counted above: the seven-card opening hand (and any mulligans) is part of the new game's pregame procedure [727.1a], not a draw during Andi's first turn.

Card data from Scryfall (scryfall.com).

### CELL c0019

**Question**
Ari casts [Memories Returning]. Does Noor have a chance to exile it with [Dawnhand Dissident] before Ari can cast Memories Returning again for its flashback cost?

**REFERENCE (correct)**
No. After Memories Returning resolves, Ari receives priority.. At this point, Memories Returning is in the graveyard, and they can choose to cast it again. When it's cast, it goes from the graveyard to the stack. Noor does not receive priority until after Memories Returning is on the stack, so Memories Returning can't be exiled with Dawnhand Dissident.

(Unless there's something else on the battlefield that would create a triggered ability when Memories Returning resolves. In that case, Ari wouldn't be able to cast Memories Returning until the trigger has left the stack, and Noor could exile it in response to the trigger.)

**CANDIDATE**
No — assuming Ari has the mana and casts it right away, Noor gets no window. Ari can cast Memories Returning from the graveyard for its Flashback {7}{U}{U} before Noor ever receives priority.

Why:

1. While Memories Returning is on the stack the first time, Dawnhand Dissident's "{T}, Blight 2: Exile target card from a graveyard" has no legal target for it — Memories Returning is a spell on the stack, not a card in a graveyard (a spell is a card on the stack, [112.1]). Noor can respond to the spell ([117.7]), but not exile it.
2. Memories Returning resolves and is put into Ari's graveyard. Ari, as the player whose turn it is, receives priority at that point before any opponent can act — Memories Returning ruling #2 states this directly: "If a card with flashback is put into your graveyard during your turn, you can cast it if it's legal to do so before any other player can take any actions." With priority ([117.1a]) and an empty stack in Ari's main phase (flashback still obeys sorcery timing, Memories Returning ruling #0), Ari legally casts it from the graveyard by paying {7}{U}{U} instead of {2}{U}{U} ([702.34a], Memories Returning ruling #4). Once it's cast, Ari keeps priority ([601.2i]).
3. Now Memories Returning is on the stack again and again untargetable by Dawnhand Dissident's exile ability. And it won't matter: a spell cast with flashback is exiled no matter how it leaves the stack (Memories Returning ruling #3).

When Noor DOES get a chance: if Ari can't or doesn't cast it immediately and passes priority, or if Ari's main phase has ended, or Ari casts something else first, then Noor may activate "{T}, Blight 2" while Memories Returning sits in Ari's graveyard and exile it, denying the flashback. Note Dawnhand Dissident's last ability (casting creature spells from exile during your turn) is irrelevant here — Memories Returning is a sorcery.

Timing assumption: I read the question as Ari intending to flash it back at the first opportunity in the same main phase. If instead Ari waits (e.g., taps out, or the turn moves on), Noor's window opens as described above.

Two players vs. more: the answer is the same at any table size. Ari, the active player, receives priority first after Memories Returning resolves, so no opponent — whether one or several — gets to act in between ([117.1a], Memories Returning ruling #2).

Card data from Scryfall (scryfall.com).

