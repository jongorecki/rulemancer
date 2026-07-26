# Reference-grading batch batch_02

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
`evals/judge_error_out/batch_02.jsonl` -- nothing else, no prose, no markdown
fence:

    {"cell": "c0001", "verdict": "same", "reason": "<one sentence>"}

`verdict` must be exactly `same` or `different`. Write one line per cell, in
the order the cells appear.

---

### CELL c0020

**Question**
Autumn controls [Bolas's Citadel] and has [Sidisi's Pet] on top of their library, can they cast it for its morph cost? If so, how much life will they pay?

**REFERENCE (correct)**
No, they can't cast it. If Autumn uses Bolas's Citadel to cast a spell, they are applying an alternative cost. Morph is also an alternative cost. Only one alternative cost can be applied to a spell when casting it.

**CANDIDATE**
Yes — Autumn can cast Sidisi's Pet face down using its morph ability from the top of her library while she controls Bolas's Citadel, and she pays {3} generic mana for it, not life.

Here's why: Bolas's Citadel's static ability lets Autumn "cast spells from the top of your library," and morph is itself "a static ability that functions in any zone from which you could play the card it's on" [702.37a]. Since Bolas's Citadel gives permission to cast spells (of any type) from the top of the library, and casting Sidisi's Pet face down via morph still produces a spell (a 2/2 face-down creature spell with no name, text, subtypes, or mana cost) [702.37c], that permission covers casting it face down as well as face up.

Now for the cost. Morph is an alternative cost: "Morph [cost]" means "You may cast this card as a 2/2 face-down creature... by paying {3} rather than paying its mana cost" [702.37a][702.37c]. Alternative costs like this are paid instead of the mana cost [118.9b]. Bolas's Citadel's replacement ("pay life equal to its mana value rather than pay its mana cost") only substitutes for paying the card's actual mana cost when you cast it that way. Because Sidisi's Pet's morph ability already replaces "paying its mana cost" with paying {3}, Autumn is not paying the mana cost at all in this line — she's paying the morph alternative cost. Rule 601.2b is explicit that "a player can't apply two alternative methods of casting or two alternative costs to a single spell," so Bolas's Citadel's life-for-mana-value substitution and the morph {3} alternative cost don't stack; only the morph cost applies here.

So Autumn pays {3} (generic mana, not life) to cast Sidisi's Pet face down as a 2/2 with no name, text, subtypes, or mana cost. She does not pay any life for this cast, since Bolas's Citadel's life payment only kicks in when the mana cost itself would otherwise be paid [601.2f]. Later, at any time she has priority, she can turn it face up by paying its morph cost of {1}{B} as a special action that doesn't use the stack, per Sidisi's Pet's own text and [702.37e] and [Sidisi's Pet ruling #5][Sidisi's Pet ruling #3] — that's separate from casting it and unaffected by Bolas's Citadel.

This assumes she has no other alternative-cost effects in play that would also compete for the single alternative-cost slot; if some other effect also wanted to modify how she casts this spell, only one alternative method could apply per [601.2b].

Card data from Scryfall (scryfall.com).

### CELL c0021

**Question**
Alijah controls [Badlands] and [Conversion]. Alijah then casts [Magus of the Moon]. After that resolves, what color(s) of mana can Badlands tap for?

**REFERENCE (correct)**
Only {R}. Both Magus of the Moon and Conversion only apply in layer 4. The effects are applied in timestamp order, resulting in Conversion applying first to make Badlands a Plains, then Magus of the Moon applies making it a Mountain.

**CANDIDATE**
Badlands taps for white mana only — {W}.

Why: both Conversion ("All Mountains are Plains") and Magus of the Moon ("Nonbasic lands are Mountains") are type-changing continuous effects that apply in layer 4. Normally they'd be applied in timestamp order, but Conversion depends on Magus of the Moon: whether Conversion applies to Badlands at all, and what it does to it, is changed by applying Magus of the Moon first. So Magus of the Moon is applied first.

Step 1 — Magus of the Moon: Badlands is a nonbasic land, so its subtypes are set to just Mountain. It loses Swamp (and thus loses "{T}: Add {B}") and gains "{T}: Add {R}" [305.7, Magus of the Moon ruling #4].

Step 2 — Conversion: Badlands is now a Mountain, so Conversion makes it a Plains. Setting the subtype again removes Mountain and the red mana ability, and Badlands gains the intrinsic Plains ability "{T}: Add {W}" [305.6, 305.7, Conversion ruling #0].

So the Swamp/Mountain dual that used to add {B} or {R} [Badlands ruling #3] now adds only {W}. Note Conversion and Magus of the Moon don't touch supertypes or the card's name [Conversion ruling #1, Magus of the Moon ruling #1], and Badlands remains nonbasic, so Magus of the Moon keeps applying to it. Note also {W} is white mana specifically, not generic mana.

This analysis doesn't depend on the number of players — both effects apply to all Mountains/nonbasic lands regardless of controller, so the result is the same in two-player and multiplayer games. I'm assuming Magus of the Moon has resolved and is on the battlefield with both effects active; if Magus of the Moon were removed, Conversion would no longer see Badlands as a Mountain and Badlands would revert to adding {B} or {R}.

Card data from Scryfall (scryfall.com).

### CELL c0022

**Question**
Alaina has seven cards in their hand and controls [Recycle]. They cast [Trusted Advisor]. After that resolves, what is Alaina's maximum hand size?

**REFERENCE (correct)**
Four. Recycle sets the maximum hand size to two, and Trusted Advisor then modifies that maximum hand size by adding two to it.

**CANDIDATE**
Alaina's maximum hand size is four.

Maximum hand size is the number of cards a player must discard down to during their cleanup step; it's normally seven [402.2]. Effects that modify it are applied in timestamp order. Recycle sets Alaina's maximum hand size to two, and Trusted Advisor, entering the battlefield later, then increases it by two, for a total of four [Trusted Advisor ruling #0], [Recycle ruling #2]. If the permanents had entered in the opposite order (Trusted Advisor first, then Recycle), Recycle's later setting effect would win and the maximum hand size would be two.

Alaina's current seven cards in hand are fine right now — maximum hand size only matters as the cleanup step of their turn begins, at which point the active player discards down to that number as a turn-based action that doesn't use the stack [514.1], [703.4n], [Recycle ruling #1]. So on Alaina's next cleanup step, with a maximum hand size of four, they'd discard down to four cards. Note also that Recycle's "Whenever you play a card, draw a card" and Trusted Advisor's upkeep trigger will change how many cards are in hand before then.

This works identically in a two-player game and at a multiplayer table; maximum hand size is per-player and isn't affected by the number of opponents.

Card data from Scryfall (scryfall.com).

### CELL c0023

**Question**
Andre controls [Raugrin Triome] and [Prismatic Omen]. Nala casts [Blood Moon]. After it resolves, what land types does Raugrin Triome have?

**REFERENCE (correct)**
Just Mountain. Blood Moon and Prismatic Omen's effects are not dependent on each other, so they are applied in timestamp order.

**CANDIDATE**
Raugrin Triome ends up with just one land type: Mountain. Its only ability is the intrinsic "{T}: Add {R}" from that Mountain type.

Why: both Prismatic Omen and Blood Moon are type-changing continuous effects, applied in layer 4 in timestamp order. Prismatic Omen (older) first makes Raugrin Triome every basic land type — Plains, Island, Swamp, Mountain, Forest, on top of its own Island/Mountain/Plains. Then Blood Moon resolves (newer timestamp) and says nonbasic lands are Mountains, which sets the land's types to Mountain and removes all other land types and abilities it had, giving it "{T}: Add {R}" (Blood Moon ruling #2). There's no dependency that reverses this order: Prismatic Omen doesn't change whether Blood Moon applies to Raugrin Triome, because Raugrin Triome is still nonbasic — adding basic land types does not add the "basic" supertype (Prismatic Omen ruling #1, Blood Moon ruling #1, rule 205.4 via "Nonbasic Land"/"Basic" glossary). So Prismatic Omen's contribution is simply overwritten.

Raugrin Triome keeps its name and any supertypes (it has none); it is still not a basic land. It also loses Cycling {3} and its "enters tapped" ability going forward, since Blood Moon strips its abilities.

Note the timing assumption: this is after Blood Moon has resolved, i.e., Blood Moon's timestamp is later than Prismatic Omen's. If instead Prismatic Omen were to enter the battlefield after Blood Moon, Prismatic Omen would apply last and add all five basic land types back, leaving Raugrin Triome as Plains, Island, Swamp, Mountain, and Forest (able to tap for {W}, {U}, {B}, {R}, or {G}), though it still wouldn't get back Cycling {3}.

Player count doesn't matter here: Blood Moon affects all nonbasic lands regardless of controller, so the answer is the same in a two-player game or a multiplayer table.

Card data from Scryfall (scryfall.com).

### CELL c0024

**Question**
Andy controls 3 artifacts and casts [Rusted Relic]. Neriah controls [Imposing Sovereign]. Does Rusted Relic enter the battlefield tapped or untapped?

**REFERENCE (correct)**
Tapped. To determine what replacement effects apply to a permanent as it enters the battlefield, the game looks at the permanent as it would exist on the battlefield. On the battlefield Rusted Relic would be a creature, so Imposing Sovereign's effect will apply to it.

**CANDIDATE**
Rusted Relic enters the battlefield tapped.

Why: Imposing Sovereign's replacement effect ("Creatures your opponents control enter tapped") modifies how a permanent enters. To decide whether such an effect applies, you check the characteristics the permanent would have as it exists on the battlefield, including continuous effects from the permanent's own static abilities that would apply once it's there [614.12], [614.12a], [611.3c]. Rusted Relic's metalcraft ability says it is a 5/5 Golem artifact creature as long as you control three or more artifacts. Andy already controls 3 artifacts, and Rusted Relic itself counts once it's on the battlefield, so metalcraft is satisfied and Rusted Relic would be a creature on the battlefield. Since Neriah is Andy's opponent, Rusted Relic is a creature an opponent of Neriah controls, so Imposing Sovereign's effect applies and Rusted Relic enters tapped. This is analogous to Scarwood Treefolk / Orb of Dreams examples in [614.12].

Only one replacement effect is modifying this event, so there's no choice to make under [616.1]; if another "enters tapped/untapped" effect were also in play, Andy (as the affected permanent's controller) would choose the order [616.1], [616.1f].

Multiplayer note: nothing changes with more than two players — Imposing Sovereign affects creatures controlled by any of Neriah's opponents, so Rusted Relic still enters tapped. If several players had to make simultaneous replacement-effect choices, they'd do so in APNAP order [101.4].

Side note: being tapped doesn't stop Rusted Relic from being a creature, and "summoning sickness" for it is measured from how long Andy has continuously controlled it, not how long it has been a creature [Rusted Relic ruling #0].

Card data from Scryfall (scryfall.com).

### CELL c0025

**Question**
Amaris controls a [The Flame of Keld] with 2 lore counters on it and [Soul-Scar Mage]. Amaris puts the third lore counter on The Flame of Keld and resolves its final chapter ability. Amaris then casts [Shock], targeting Nico's [River Kaijin]. How many -1/-1 counters are placed on the River Kaijin?

**REFERENCE (correct)**
There are two replacement effects trying to apply to the damage being dealt, so Nico chooses which one to apply first. If they apply The Flame of Keld's effect first, Soul-Scar Mage's effect will then apply afterwards, and 4 -1/-1 counters will be placed on the River Kaijin. If they apply the Soul-Scar Mage's effect first, the The Flame of Keld's effect will no longer be applicable and the River Kaijin will only receive 2 -1/-1 counters.

**CANDIDATE**
Nico's River Kaijin ends up with 2 -1/-1 counters (assuming Nico, as the player who chooses the replacement order, picks the option that minimizes the damage). Here's why: Shock deals 2 damage to River Kaijin, and this damage is noncombat damage from a red source (the Shock spell, controlled by Amaris). Two replacement effects want to apply to this single damage event: (1) Soul-Scar Mage's ability, which says that noncombat damage a source Amaris controls would deal to an opponent's creature becomes that many -1/-1 counters instead of damage, and (2) The Flame of Keld's chapter III ability, whose text overrides the general damage rules and says a red source Amaris controls would deal 2 additional damage this turn to any permanent or player it damages. Since Soul-Scar Mage's ruling #0 establishes that when multiple prevention/replacement effects are trying to apply to the same damage, the controller of the creature that would be dealt the damage (here, Nico, who controls River Kaijin) chooses the order to apply them. If Nico applies The Flame of Keld's effect first, the event becomes '4 damage dealt to River Kaijin,' which Soul-Scar Mage then turns into 4 -1/-1 counters. If instead Nico applies Soul-Scar Mage's effect first, the 2 damage event is immediately replaced with '2 -1/-1 counters placed on River Kaijin' -- at that point it is no longer a damage event at all, so The Flame of Keld's damage-boosting effect (which only modifies damage events) has nothing left to modify, per the one-shot nature of replacement effects (a replacement effect only gets one opportunity to affect an event or its modified versions). Because Nico controls River Kaijin and gets to pick the order, Nico will choose the second option to minimize the counters, resulting in only 2 -1/-1 counters being placed on River Kaijin instead of 4. Note: this assumes Nico plays optimally; if Nico applied the effects in the other order, River Kaijin would instead receive 4 -1/-1 counters, but since Nico controls the choice, 2 is the expected outcome.

Card data from Scryfall (scryfall.com).

### CELL c0026

**Question**
Abdullah casts [Telemin Performance] targeting Nico. In response, Nico casts [Veil of Summer]. Abdullah responds with their own Veil of Summer. What happens?

**REFERENCE (correct)**
Abdullah's Veil of Summer resolves first. Then Nico's resolves and draws them a card. Then Telemin Performance tries to resolve and fails, since it has an illegal target.

(Abdullah's Veil of Summer didn't accomplish anything useful.)

**CANDIDATE**
Telemin Performance fizzles. Nico ends up safe, both players get their Veil of Summer effects, and Telemin Performance is removed from the stack and put into Abdullah's graveyard without doing anything.

How it plays out, top down (the stack resolves last-in, first-out; each spell cast in response to another resolves first) [117.7, 405.2, 405.5, 608.1]:

1. **Abdullah's Veil of Summer resolves first.** Abdullah draws a card only if an *opponent* cast a blue or black spell this turn. Abdullah's own Telemin Performance doesn't count, and Nico's Veil of Summer is green, so in a two-player game Abdullah draws nothing (unless Nico cast some other blue or black spell earlier this turn). Abdullah's spells can't be countered this turn, and Abdullah and Abdullah's permanents gain hexproof from blue and from black. None of this protects Telemin Performance's target — Abdullah's Veil of Summer only grants hexproof to Abdullah and Abdullah's own permanents, and Veil of Summer does not counter anything (Nico's Veil of Summer is unaffected and stays on the stack) [Veil of Summer].

2. **Nico's Veil of Summer resolves next.** Nico draws a card, because an opponent (Abdullah) cast a blue spell this turn — Telemin Performance is blue. Nico and Nico's permanents gain hexproof from blue and from black until end of turn, meaning Nico can't be the target of blue or black spells or abilities Nico's opponents control [Veil of Summer, 702.11d]. Note that rule 702.11d is written for permanents; Veil of Summer's own text explicitly extends the protection to the player as well, and card text wins over the general framing.

3. **Telemin Performance tries to resolve last, and doesn't.** On resolution the game rechecks targets. Nico, its only target, now has hexproof from blue, and Telemin Performance is a blue spell controlled by Nico's opponent, so Nico is an illegal target. Since every instance of "target" is illegal, Telemin Performance doesn't resolve; it's removed from the stack and put into its owner's graveyard [608.2b]. Nico reveals nothing, mills nothing, and Abdullah steals no creature. This is not a counter, so Abdullah's "spells you control can't be countered" from their own Veil of Summer doesn't save it [Veil of Summer].

Assumed timing: Telemin Performance is a sorcery, so it was cast in Abdullah's main phase with an empty stack, then Nico's Veil of Summer, then Abdullah's Veil of Summer on top. If instead Abdullah's Veil of Summer had somehow resolved before Nico's was cast, nothing changes for Telemin Performance — Nico's hexproof from blue still applies before Telemin Performance resolves.

Multiplayer difference: with more than two players, the only change is the card draws. Abdullah would draw a card if *any* opponent (not just Nico) had cast a blue or black spell this turn. Nico still draws off Telemin Performance being blue, and Telemin Performance still fizzles because it targeted Nico specifically.

Card data from Scryfall (scryfall.com).

### CELL c0027

**Question**
Ashley equips [Colossus Hammer] to [Ogre Warrior], then enchants it with [Phantom Wings]. Does Ogre Warrior have flying?

**REFERENCE (correct)**
Yes. The effects from Colossus Hammer and Phantom Wings apply in the same layer, and Phantom Wings has the more recent timestamp.

**CANDIDATE**
Yes — Ogre Warrior has flying, and it's a 13/13.

Both effects apply in layer 6 (ability-adding/removing), and neither depends on the other, so they're applied in timestamp order [613.9], [613.7a]. Colossus Hammer became attached first, so its "loses flying" applies first; Phantom Wings was attached later, so its "Enchanted creature has flying" applies afterward and wins. Colossus Hammer's +10/+10 applies separately in layer 7c, making Ogre Warrior 13/13. Note that an Aura or Equipment gets a new timestamp each time it becomes attached [613.7e] — so if Ashley later re-equipped Colossus Hammer (unattaching and re-attaching it), Colossus Hammer would get the newer timestamp and Ogre Warrior would lose flying again.

This matches the Colossus Hammer ruling that if the equipped creature gains flying after Colossus Hammer became attached, it keeps flying [Colossus Hammer ruling #2]. (The exception in [Colossus Hammer ruling #1] is only for "as long as" conditional flying from the creature's own ability, which isn't the case here — Phantom Wings is a separate, later-timestamped effect.)

I'm assuming the order stated: Colossus Hammer attached first, Phantom Wings second. If Phantom Wings had been attached first and then Colossus Hammer equipped, Colossus Hammer would have the later timestamp and Ogre Warrior would not have flying (still 13/13).

Nothing here depends on the number of players; the answer is the same in two-player and multiplayer games.

Card data from Scryfall (scryfall.com).

### CELL c0028

**Question**
Ashley controls [Underworld Breach] and has [Reveillark] in their graveyard. Can they evoke it?

**REFERENCE (correct)**
No. Escape and evoke are both alternative costs ([702.138a], [702.74a]), and Ashley may only pay one alternative cost for a spell. Since escape is the only thing that allows Ashley to cast Reveillark from their graveyard, they have to use that cost.

**CANDIDATE**
No. Ashley cannot pay Reveillark's evoke cost while casting it from the graveyard, because casting it from the graveyard requires using the escape ability granted by Underworld Breach, and escape and evoke are both alternative costs — a spell can only use one alternative cost method at a time.

Underworld Breach's static ability gives every nonland card in Ashley's graveyard escape, with the escape cost equal to the card's mana cost plus exiling three other cards from the graveyard [702.138a]. Escape is the only thing granting Ashley permission to cast Reveillark from the graveyard at all — evoke itself only lets you cast the creature 'by paying [cost] rather than paying its mana cost' [702.74a], it doesn't grant any ability to cast from the graveyard, and Reveillark's evoke ruling confirms evoke doesn't change where or when the spell can be cast, only the cost paid if you do cast it normally [Reveillark ruling #0]. Since Reveillark is sitting in the graveyard, the only legal way to cast it right now is via the escape alternative cost.

Rule 601.2b is explicit: 'A player can't apply two alternative methods of casting or two alternative costs to a single spell.' Escape and evoke are each alternative costs, so Ashley must pick one, not combine them. If Ashley casts Reveillark via escape, they pay the escape cost — {4}{W} (Reveillark's mana cost) plus exiling three other cards from the graveyard — and Reveillark enters the battlefield normally (not evoked, so its 'sacrifice when it enters' trigger from evoke won't fire, since that trigger only fires if the evoke cost was actually chosen to be paid, per [Reveillark ruling #5]).

If Ashley instead wants to use evoke, they'd need to be casting Reveillark from a zone/legal casting position where evoke normally applies (i.e., from hand), which isn't the case here since it's in the graveyard.

Card data from Scryfall (scryfall.com).

### CELL c0029

**Question**
Nixon has a [Southern Elephant] and a [Skullbriar, the Walking Grave] with 3 +1/+1 counters in their graveyard. Addison casts [Ghastly Conscription], targeting Nixon. What happens to the counters on the Skullbriar, the Walking Grave? Will Nixon know which manifested card is which?

**REFERENCE (correct)**
When in the graveyard, Skullbriar, the Walking Grave had the ability that allowed it to keep its counters, so it is exiled and shuffled with 3 +1/+1 counters. When it's moved to the battlefield, it's face down and no longer has that ability, so the counters cease to exist. It had the counters immediately before entering the battlefield however, so Nixon will know which face-down permanent is the Skullbriar, the Walking Grave and which is the Southern Elephant.

**CANDIDATE**
Short answer: the three +1/+1 counters stay on Skullbriar, the Walking Grave the whole way, so it arrives as a face-down manifested permanent that is a 2/2 with three +1/+1 counters on it — a 5/5. Because Southern Elephant will manifest as a plain 2/2, everyone at the table (including Nixon) can tell which face-down permanent is Skullbriar, the Walking Grave, even though the pile was shuffled.

Why the counters survive:
- Normally counters on an object cease to exist when it changes zones ([122.2]), but Skullbriar, the Walking Grave's own text says "Counters remain on Skullbriar as it moves to any zone other than a player's hand or library." Card text beats the general rule here.
- Ghastly Conscription moves the cards graveyard → exile → battlefield. Skullbriar, the Walking Grave has its abilities in the graveyard, so the counters remain when it's exiled, and it still has its abilities as a card in the face-down exile pile (being exiled face down only limits who may examine it — [406.3]), so the counters remain again when it's manifested onto the battlefield. That the ability must be present in the zone the card is leaving is exactly what [Skullbriar, the Walking Grave ruling #2] describes.
- Those counters aren't "placed" on it, so counter-doubling or counter-hosing effects don't interact with them ([Skullbriar, the Walking Grave ruling #1]), and it retains counters of every kind, not just +1/+1 ([Skullbriar, the Walking Grave ruling #6]).

What the manifested permanent is: manifesting turns the card face down and puts it onto the battlefield as a 2/2 face-down creature with no name, no text, no subtypes, and no mana cost ([701.40a], [708.2], [708.2a], [Ghastly Conscription ruling #9]). Face down, Skullbriar, the Walking Grave has no abilities and is not legendary — but the three counters are on the permanent independently of its characteristics, making it 5/5. Southern Elephant manifests as an ordinary 2/2.

So, does Nixon know which is which? Yes, in practice. The shuffle is meant to hide which manifested card is which ([Ghastly Conscription ruling #4]), and Nixon may not look at face-down permanents they don't control ([Ghastly Conscription ruling #14]) — Addison cast Ghastly Conscription, so Addison manifests and controls both permanents and may look at them. But the visible +1/+1 counters give it away: the 5/5 is Skullbriar, the Walking Grave and the 2/2 is Southern Elephant. Note also that Addison is the one who could turn either face up by paying its mana cost as a special action — {B}{G} for Skullbriar, the Walking Grave or {3}{G} for Southern Elephant ([Ghastly Conscription ruling #3]).

Player count: nothing here changes between a two-player game and a multiplayer table; Ghastly Conscription targets one player's graveyard either way. One multiplayer wrinkle from the card's own rulings: if Addison manifests a card owned by Nixon and Addison later leaves the game, that card is exiled ([Ghastly Conscription ruling #7]).

Timing note: I'm assuming the counters were already on Skullbriar, the Walking Grave in the graveyard before Ghastly Conscription resolved. If Skullbriar, the Walking Grave somehow had no counters at the moment Ghastly Conscription resolved, both manifested permanents would be indistinguishable 2/2s and Nixon would not know which is which.

Card data from Scryfall (scryfall.com).

### CELL c0030

**Question**
Anabella controls [Blood Moon] and enchants their [Sunlit Marsh] with [Urban Utopia]. What colors can it tap for?

**REFERENCE (correct)**
Any color. Blood Moon operates in the type-changing layer which is applied before the ability adding and removing layer. Sunlit Marsh is a Mountain, with the additional ability "{T}: Add one mana of any color.".

**CANDIDATE**
Sunlit Marsh can tap for any one color — {W}, {U}, {B}, {R}, or {G} — thanks to Urban Utopia, plus it separately has "{T}: Add {R}" from being a Mountain. (Each tap uses one of those abilities, so one tap yields one mana of whatever color you choose.)

Why: Sunlit Marsh is a nonbasic land, so Blood Moon's "Nonbasic lands are Mountains" sets its subtype to Mountain. Under CR 305.7, setting a land's subtype to a basic land type makes it lose its old land types and all abilities generated from its rules text and old types — so Sunlit Marsh loses "{T}: Add {W} or {B}" — and it gains the intrinsic Mountain ability "{T}: Add {R}" (CR 305.6, Mountain entry; Blood Moon ruling #2). Blood Moon does not change its name or supertypes (Blood Moon ruling #1).

Crucially, CR 305.7 also says this does not remove abilities that were granted to the land by other effects. Urban Utopia grants "Enchanted land has '{T}: Add one mana of any color'" as a separate continuous effect, so that ability sticks around regardless of the order in which Blood Moon and Urban Utopia started applying (Urban Utopia ruling #0 confirms the enchanted land doesn't lose other abilities or change land types). Both abilities coexist in layer 6.

Timing note: the result is the same whether Blood Moon was already on the battlefield when Urban Utopia entered or Urban Utopia came first, because Blood Moon's type-setting never strips externally granted abilities.

Nothing here depends on the number of players; the answer is identical in two-player and multiplayer games.

Card data from Scryfall (scryfall.com).

### CELL c0031

**Question**
Alessandro controls [Angel's Tomb] and no other creatures. They cast [Mirage Phalanx]. Can they pair it with Angel's Tomb?

**REFERENCE (correct)**
No. Soulbond is a triggered ability that will only go on the stack if Alessandro controls another eligible creature when Mirage Phalanx enters the battlefield. However, before Angel's Tomb's ability resolves, Alessandro doesn't control any other eligible creatures.

**CANDIDATE**
Yes — Alessandro can pair Mirage Phalanx with Angel's Tomb, but only if Angel's Tomb has already become a creature by the time the soulbond ability actually resolves. Here's why: when Mirage Phalanx enters the battlefield, two triggered abilities go on the stack from that same event, both controlled by Alessandro — Mirage Phalanx's soulbond trigger ("you may pair this creature with another unpaired creature when either enters") and Angel's Tomb's trigger ("Whenever a creature you control enters, you may have this artifact become a 3/3 white Angel artifact creature with flying until end of turn"). Since Alessandro controls both triggered abilities, he chooses the order they go on the stack, and the one put on top resolves first. If he stacks them so Angel's Tomb's ability resolves first and chooses to make it a 3/3 Angel artifact creature, then when the soulbond ability resolves afterward, Angel's Tomb is currently a creature, on the battlefield, and under Alessandro's control. Under rule [702.95c], the soulbond ability only checks these conditions at the moment it resolves — 'if either object that would be paired is no longer a creature, no longer on the battlefield, or no longer under the control of the player who controls the soulbond ability, neither object becomes paired' — so since Angel's Tomb currently satisfies all three conditions at that moment, the pairing succeeds and Mirage Phalanx becomes paired with Angel's Tomb (with the usual soulbond limit that each can only be paired with one other creature at a time, per rule [702.95d]). If instead Alessandro let the soulbond trigger resolve first, while Angel's Tomb is still just a non-creature artifact, the pairing would fail, since Angel's Tomb wouldn't be a creature at that point — soulbond pairing requires the other object to be a creature at resolution.

Card data from Scryfall (scryfall.com).

### CELL c0032

**Question**
Aydan casts [Kellan, the Fae-Blooded], and Nico answers by casting [Spell Queller], exiling Kellan, the Fae-Blooded with its triggered ability.
When Spell Queller leaves the battlefield, can Aydan choose to cast [Birthright Boon] or do they have to cast Kellan, the Fae-Blooded?

**REFERENCE (correct)**
Aydan can choose to cast either Kellan, the Fae-Blooded or Birthright Boon when Spell Queller leaves the battlefield.

**CANDIDATE**
Aydan may choose either one — he can cast Birthright Boon (the Adventure half) or Kellan, the Fae-Blooded (the creature half), and either way it's cast without paying its mana cost.

Why:

- An adventurer card has two sets of characteristics: the inset frame on the left gives the alternative (Adventure) characteristics the object may have while it's a spell, and the normal characteristics appear as usual [715.2]. As a player plays an adventurer card, that player chooses whether to play it normally or as an Adventure [715.3]. That choice is made each time the card is cast, so being cast as Kellan, the Fae-Blooded the first time doesn't lock Aydan in.
- Spell Queller's ability lets the exiled card's owner cast that card "without paying its mana cost." That normally shuts off alternative costs [Spell Queller ruling #6], but casting a card as an Adventure is expressly not casting it for an alternative cost, and effects that let you cast a spell without paying its mana cost may be applied to the Adventure [Kellan, the Fae-Blooded // Birthright Boon ruling #9]. So Birthright Boon is a legal choice and costs nothing.
- Timing: Aydan must cast it right then, as part of the resolution of Spell Queller's leaves-the-battlefield ability; he can't hold it for later. Timing permissions based on the card's type are ignored, so the fact that Birthright Boon is a sorcery doesn't stop him from casting it at instant speed during that resolution [Spell Queller ruling #2].
- The new spell has no relation to the original Kellan, the Fae-Blooded spell that was exiled; nothing from that first casting carries over [Spell Queller ruling #1].
- Follow-up if he picks Birthright Boon: when Birthright Boon resolves, Aydan exiles it instead of putting it into the graveyard, and for as long as it stays exiled he may later cast Kellan, the Fae-Blooded as a permanent spell [Kellan, the Fae-Blooded // Birthright Boon ruling #6] — but that later casting follows normal timing (main phase, empty stack) and costs {2}{R} [Kellan, the Fae-Blooded // Birthright Boon ruling #5].

Player count doesn't change this: Spell Queller's ability refers to the exiled card's owner, so Aydan makes the choice whether the game is two-player or multiplayer. Note also that the exile check was legal in the first place because the spell cast was Kellan, the Fae-Blooded with mana value 3, which is 4 or less.

Card data from Scryfall (scryfall.com).

### CELL c0033

**Question**
Nico controls [Thespian's Stage] that's currently a copy of [Temple of Triumph]. Alayna casts [Alpine Moon] and names "Temple of Triumph" as it resolves. Alayna then activates a second Thespian's Stage targeting Temple of Triumph. What does each Thespian's Stage look like?

**REFERENCE (correct)**
Both Thespian's Stages are lands named "Temple of Triumph" and have "{T}: Add one mana of any color." and no other abilities. Because Thespian's Stage gains its ability as part of the copying process, the ability applies in the copy layer, which is earlier than the adding and removing abilities layer.

**CANDIDATE**
Nico's Thespian's Stage is now a land named Temple of Triumph with no land types and exactly one ability, "{T}: Add one mana of any color" — it has lost the Thespian's Stage copy ability, so Nico can't re-copy anything with it. Alayna's second Thespian's Stage, once its ability resolves, is an untapped-or-tapped-as-it-already-was land that's a full copy of Temple of Triumph ("This land enters tapped," "When this land enters, scry 1," "{T}: Add {R} or {W}") plus the Thespian's Stage copy ability, and Alpine Moon does not touch it.

Why:

Nico's Stage — the copy effect from Thespian's Stage is applied in layer 1 (CR 613.1a, 613.2a), so its copiable values are those of Temple of Triumph, except it also keeps "{2}, {T}: This land becomes a copy of target land, except it has this ability" (CR 707.9a, and Thespian's Stage ruling #0: the copy has no duration and it loses the {T}: Add {C} ability). Its name is therefore "Temple of Triumph," so Alpine Moon's chosen name matches. Alpine Moon affects lands opponents of Alayna control, and Nico is such an opponent. Its type-changing part applies in layer 4 (removing land types — Temple of Triumph has none, and per Alpine Moon ruling #1 the land card type and any supertypes stay) and its ability part in layer 6: lose all abilities, then gain "{T}: Add one mana of any color." Because "lose all abilities" is applied before the grant within the same effect, the granted mana ability survives, but the copied Temple abilities and the Stage's own copy ability are gone. Nico's land is still tapped or untapped exactly as it was — becoming a copy never untaps it (Thespian's Stage ruling #2).

Alayna's Stage — Alpine Moon only hits lands Alayna's opponents control, so her own land is unaffected. When she copies "Temple of Triumph," she copies its copiable values: Alpine Moon is a type-changing/ability-changing continuous effect, not a copy effect, so those changes are not copied (CR 707.2, Thespian's Stage ruling #3). This is true whether she targets a real Temple of Triumph or Nico's Stage — copying Nico's Stage yields Nico's copiable values (Temple of Triumph + the Stage copy ability, per CR 707.3/707.9a), stripped of Alpine Moon's effect. No enters-the-battlefield effects apply, so "enters tapped" and the scry 1 do nothing now (Thespian's Stage ruling #1); it just sits there with those abilities as text, plus "{T}: Add {R} or {W}" and the copy ability.

One wrinkle worth naming: Alayna's Stage is now also named "Temple of Triumph," but Alpine Moon only affects lands Alayna's *opponents* control, so it stays untouched. In a multiplayer game the same logic scales: every land named Temple of Triumph controlled by any opponent of Alayna gets stripped and gains the any-color mana ability; lands Alayna controls never do.

Card data from Scryfall (scryfall.com).

### CELL c0034

**Question**
Armani controls [Soul Echo] with 0 counters on it and Nico controls [Spirit of the Hearth]. Will Armani have to sacrifice Soul Echo at the beginning of their upkeep?

**REFERENCE (correct)**
No. Since the ability has no legal targets, it would trigger at the beginning of the upkeep but would not be put on the stack.

**CANDIDATE**
Short answer: it depends on whether Nico is Armani's only opponent.

• Two-player game (Armani vs. Nico only): Soul Echo's triggered ability reads "At the beginning of your upkeep, sacrifice this enchantment if there are no echo counters on it. Otherwise, target opponent may choose..." — the ability requires a target opponent. Spirit of the Hearth gives its controller Nico hexproof ("You have hexproof"), so Nico can't be the target of spells or abilities Armani's opponents control — i.e., of Armani's ability. With no legal target available, Armani's trigger can't be put on the stack with a legal target and never resolves, so Soul Echo is not sacrificed even though it has 0 echo counters.

• Multiplayer with at least one other opponent who doesn't have hexproof: Armani must choose that player as the target, the ability resolves, and because Soul Echo has no echo counters on it Armani sacrifices Soul Echo. The "otherwise" damage-replacement clause never comes up.

Caveats and grounding: the conclusion for the two-player case rests on the general targeting rule that an ability with no legal targets is removed from the stack, which was not included in the rules context provided to me, so treat that half as reasoning from Spirit of the Hearth's card text rather than a cited rule. What is fully grounded is that Soul Echo's upkeep trigger targets an opponent and that hexproof stops Armani from targeting Nico, and that when the ability does resolve with 0 echo counters, Soul Echo is sacrificed. Note also that this sacrifice comes from a triggered ability that uses the stack, not from a state-based action, so it happens on resolution of the trigger, not automatically (compare the automatic, non-stack state-based actions in rules 704.1 and 117.5).

Card data from Scryfall (scryfall.com).

### CELL c0035

**Question**
Albert, Brielle, and Campbell are playing a multiplayer game. Brielle controls [Stalking Leonin]. Albert casts [Worst Fears] to take control of Brielle's next turn. After Brielle begins their turn, can Albert see which player was chosen for the Stalking Leonin?

**REFERENCE (correct)**
No. The choice was made as Stalking Leonin entered the battlefield, which already happened- it's no longer visible to Brielle. Albert can choose to activate the ability (at which point all players will know who was chosen), but otherwise the choice is not visible to any player.

**CANDIDATE**
Yes. Once Brielle's turn begins and Albert is controlling Brielle, Albert can see which opponent was secretly chosen for Brielle's Stalking Leonin.

Why: Stalking Leonin's enters-the-battlefield trigger has Brielle "secretly choose an opponent," and that choice is recorded somehow (for example, by writing the player's name on a slip of paper kept with Stalking Leonin) — it is hidden information about Stalking Leonin, an object in the game, that Brielle knows. Rule 723.4 says that if information about an object in the game would be visible to the player being controlled, it's visible to both that player and the controller of that player. So Albert, as the controller of Brielle, sees it. Worst Fears' own reminder text says the same thing in short form — "You see all cards that player could see and make all decisions for them" — and its rulings confirm that while controlling another player you can see all cards in the game that player can see, including cards in hand and face-down cards that player controls.

Two limits worth noting. First, this only extends to in-game information: rule 723.4 specifies that information about cards outside the game (such as a sideboard) that would be visible to Brielle is visible only to Brielle, not to Albert. The Stalking Leonin choice is in-game information, so it isn't covered by that exception. Second, Albert controls Brielle, not Brielle's permanents — per Worst Fears' rulings, Albert only controls the player and doesn't control any of Brielle's permanents, spells, or abilities. Albert still makes Brielle's decisions, so Albert could decide to activate Stalking Leonin's last ability, paying its cost by revealing the chosen player — but that ability needs a legal target, a creature attacking Brielle controlled by the chosen player, and during Brielle's own turn Brielle is the active player, so there generally won't be creatures attacking Brielle to target.

This answer is for the three-player game as described (Albert, Brielle, Campbell); rule 723.4 works the same regardless of the number of players, and Campbell's presence doesn't change it. Campbell does not gain any right to see the secret choice.

Card data from Scryfall (scryfall.com).

### CELL c0036

**Question**
Azariah controls [Magus of the Moon] and plays [Three Tree City]. Do they make a choice for it as it enters? If not, what happens if Magus of the Moon leaves the battlefield later?

**REFERENCE (correct)**
No. Making a choice for Three Tree City as it enters is a replacement effect. When determining which replacement effects apply to Three Tree City as it's entering the battlefield, the game looks at how it will exist on the battlefield after it enters. On the battlefield Three Tree City is a Mountain, and Mountains don't make choices as they enter.

If the Magus of the Moon leaves the battlefield later on, Three Tree City is not entering the battlefield again, so it will simply have had no choice made for it.

**CANDIDATE**
Yes — Azariah still has to choose a creature type for Three Tree City as it enters the battlefield; the choice is not skipped.

Here's why. Three Tree City's line "As Three Tree City enters, choose a creature type" is a replacement effect that modifies how the permanent enters the battlefield (rule [614.1c]: text of the form "As [this permanent] enters..." is a replacement effect, and per [603.6d] it's part of the static ability that occurs as part of the entering event, not a separate triggered ability). Meanwhile, Magus of the Moon's static ability "Nonbasic lands are Mountains" is a continuous effect that already exists on the battlefield and applies to Three Tree City as it enters, so under [614.12]/[614.12a] you check Three Tree City's characteristics as it would exist on the battlefield, taking that continuous effect into account — meaning Three Tree City does become a Mountain (in addition to being a Legendary Land) the moment it enters, per [611.3c] (continuous effects that modify characteristics apply simultaneously with entering, not after).

However, Magus of the Moon's printed text only says nonbasic lands *are Mountains* — it does not say those lands lose their own abilities. Nothing in Magus of the Moon's text or its ruling ([Magus of the Moon ruling #0], which only confirms the type-changing effect keeps working even if Magus of the Moon itself loses abilities) removes Three Tree City's own printed abilities. So Three Tree City's own "as it enters" replacement effect is untouched and still applies: Azariah must choose a creature type as Three Tree City enters, at the same time it becomes a Mountain.

As for the follow-up you raised: since the choice does get made, there's no gap to fill later. But to answer the natural next question — if Magus of the Moon subsequently leaves the battlefield, Magus of the Moon's continuous "nonbasic lands are Mountains" effect ends immediately, so Three Tree City stops being a Mountain. The creature-type choice, however, was a one-time replacement effect resolved at the moment Three Tree City entered ([614.1c]) — it's not a continuous effect that has to be re-applied — so that chosen creature type stays fixed for Three Tree City's {2},{T} ability regardless of whether Magus of the Moon is still around.

(This assumes Three Tree City itself never leaves the battlefield during this sequence — if Three Tree City itself left and re-entered, rule [400.7i] would make it a new object and the creature-type choice would have to be made again.)

Card data from Scryfall (scryfall.com).

### CELL c0037

**Question**
Addison controls [Dryad of the Ilysian Grove] and casts [Blood Moon]. What are the characteristics of [Snow-Covered Island], [Study Hall], [Dryad Arbor], and [Mountain] after Blood Moon resolves?

**REFERENCE (correct)**
Snow-Covered Island and Mountain have all basic land subtypes: "Plains", "Island", "Swamp", "Mountain", and "Forest". Dryad of the Ilysian Grove doesn't change supertypes and Blood Moon affects nonbasic lands.

Study Hall has subtype Mountain. There are no dependencies between Dryad of the Ilysian Grove and Blood Moon, so we apply the type-changing effects in timestamp order.

Dryad Arbor is now a Creature Land - Dryad Mountain. Gaining a basic land type doesn't remove other card types or nonland subtypes.

**CANDIDATE**
Direct answer (Blood Moon has the later timestamp, so it applies after Dryad of the Ilysian Grove in layer 4; neither effect depends on the other, since 'nonbasic' is about the supertype basic, which neither effect changes):

- Snow-Covered Island — it's a basic land (supertype Basic), so Blood Moon doesn't touch it. Dryad of the Ilysian Grove gives it every basic land type: Basic Snow Land — Island Plains Swamp Mountain Forest. It has "{T}: Add {U}", "{T}: Add {W}", "{T}: Add {B}", "{T}: Add {R}", and "{T}: Add {G}" (intrinsic from each basic land type, 305.6). Colorless, no P/T. Snow is just a supertype with no function of its own [Snow-Covered Island ruling #0].
- Mountain — also basic, so likewise unaffected by Blood Moon: Basic Land — Mountain Plains Island Swamp Forest, with all five mana abilities.
- Study Hall — nonbasic, so Blood Moon overwrites it: its land subtype is set to just Mountain (it loses Plains/Island/Swamp/Forest that Dryad of the Ilysian Grove gave it). Per 305.7 it loses all abilities from its rules text, so it loses "{T}: Add {C}" and the "{1}, {T}: Add one mana of any color…" scry ability, and it has only "{T}: Add {R}" [Blood Moon ruling #2]. It's still a Land (card types don't change), still named Study Hall, still nonbasic [Blood Moon ruling #1].
- Dryad Arbor — nonbasic land, so Blood Moon applies: its land type Forest (and the extra basic types from Dryad of the Ilysian Grove) is replaced by Mountain. Setting a land's subtype doesn't touch card types or creature types (205.3c, 205.1b), so it remains a Land Creature — Mountain Dryad, still green (color indicator, [Dryad Arbor ruling #3]), still 1/1, still summoning-sick as normal. It loses the "{T}: Add {G}" it had from being a Forest and instead has "{T}: Add {R}". This matches [Dryad Arbor ruling #0] and [Dryad Arbor ruling #2]: changing its land type leaves it a green Dryad creature.

Why Blood Moon wins on the nonbasic lands: both effects are type-changing effects in layer 4, applied in timestamp order (613.6). Dryad of the Ilysian Grove adds types (305.7's "gains land types in addition" clause), then Blood Moon's "Nonbasic lands are Mountains" sets the subtype, wiping the added types. If Blood Moon had been on the battlefield first and Dryad of the Ilysian Grove entered afterward, the nonbasic lands would end up as every basic land type instead (though still without their original rules-text abilities, which Blood Moon's earlier-applied part already removed).

Multiplayer note: nothing here depends on the number of players — Blood Moon affects every nonbasic land on the battlefield regardless of controller, while Dryad of the Ilysian Grove only affects lands Addison controls.

Card data from Scryfall (scryfall.com).

### CELL c0038

**Question**
Ari casts [Memories Returning]. Does Noor have a chance to exile it with [Dawnhand Dissident] before Ari can cast Memories Returning again for its flashback cost?

**REFERENCE (correct)**
No. After Memories Returning resolves, Ari receives priority.. At this point, Memories Returning is in the graveyard, and they can choose to cast it again. When it's cast, it goes from the graveyard to the stack. Noor does not receive priority until after Memories Returning is on the stack, so Memories Returning can't be exiled with Dawnhand Dissident.

(Unless there's something else on the battlefield that would create a triggered ability when Memories Returning resolves. In that case, Ari wouldn't be able to cast Memories Returning until the trigger has left the stack, and Noor could exile it in response to the trigger.)

**CANDIDATE**
No. Once Memories Returning resolves and goes to Ari's graveyard, Ari (as the spell's caster) gets priority before Noor does, and the ruling for Memories Returning explicitly states that a card with flashback that lands in your graveyard during your turn can be recast "before any other player can take any actions" if it's otherwise legal to do so [Memories Returning ruling #2]. So Ari can immediately cast Memories Returning again for its flashback cost before Noor ever gets a chance to activate Dawnhand Dissident's second ability ("{T}, Blight 2: Exile target card from a graveyard") to exile Memories Returning out of the graveyard.

Mechanically: Memories Returning is a sorcery spell while it's cast and sits on the stack [112.1, 601.2a]; Dawnhand Dissident's ability targets a card in a graveyard, so it can't touch Memories Returning while it's still on the stack. Memories Returning only becomes exile-able once it finishes resolving and moves to Ari's graveyard. At that instant, priority passes again, and per Memories Returning ruling #2, Ari (the caster, on their own turn) gets to act—i.e., cast the flashback spell—before any other player, including Noor, can take an action such as activating Dawnhand Dissident. If Ari does recast it via flashback, Memories Returning is exiled instead of going back to the graveyard when it next leaves the stack, whether it resolves or is countered [702.34a, Memories Returning ruling #3], so Dawnhand Dissident's graveyard-exile ability would have nothing left to target there anyway.

This assumes the sequence in the question: Memories Returning is cast, allowed to resolve, and only then would Ari want to flashback it — the ruling covers exactly this timing. If instead Noor already had priority or a pending trigger before Memories Returning finished resolving (a different order of events), that wouldn't change this outcome, since Dawnhand Dissident still can't target a spell on the stack, only a card already in a graveyard.

Card data from Scryfall (scryfall.com).

