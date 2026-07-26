# Reference-grading batch batch_08

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
`evals/judge_error_out/batch_08.jsonl` -- nothing else, no prose, no markdown
fence:

    {"cell": "c0001", "verdict": "same", "reason": "<one sentence>"}

`verdict` must be exactly `same` or `different`. Write one line per cell, in
the order the cells appear.

---

### CELL c0134

**Question**
Autumn controls [Painter's Servant] naming "blue" and [Sword of Body and Mind]. Nico casts [Gift of Tusks] targeting the Painter's Servant. After it resolves, what happens if Autumn tries to equip Painter's Servant with Sword of Body and Mind?

**REFERENCE (correct)**
It becomes equipped and then becomes unequipped.

Gift of Tusks makes Painter's Servant lose all abilities, but this happens after color-changing effects have applied, so all cards are still blue. Nothing prevents the Sword of Body and Mind from becoming attached to Painter's Servant. Once Sword of Body and Mind is equipped to the Painter's Servant, it has protection from blue (the effect removing its abilities is applied before the effect giving it protection from blue, and so can't be equipped by anything blue. It becomes unattached as a state-based action.

**CANDIDATE**
The equip works, and Sword of Body and Mind stays attached.

Why: Gift of Tusks makes Painter's Servant lose all abilities and become a green Elephant with base power and toughness 3/3. Losing all abilities removes Painter's Servant's color-changing ability, so nothing is making other objects blue anymore [113.10]. (Even while that ability worked, Gift of Tusks' own color-setting effect would apply on top of it for Painter's Servant itself [Painter's Servant ruling #4].)

Equip {2} means "{2}: Attach this permanent to target creature you control. Activate only as a sorcery" [702.6a]. Painter's Servant is still a creature Autumn controls, so it's a legal target, and Sword of Body and Mind can legally be attached to a creature [301.5c]. The {2} is two generic mana, payable with any color or with colorless mana.

On resolution, Sword of Body and Mind attaches (receiving a new timestamp) [701.3c] and grants +2/+2 and protection from green and from blue. Protection would make an Equipment fall off as a state-based action only if that Equipment itself has the stated quality [702.16d, 704.1]. Sword of Body and Mind is a colorless artifact — it is neither green nor blue, because Painter's Servant's ability is gone. So it stays on, and Painter's Servant is a 5/5 green Elephant with protection from green and from blue until end of turn.

Contrast: if Painter's Servant still had its ability naming blue, Sword of Body and Mind would be blue and would immediately become unattached as a state-based action while remaining on the battlefield [702.16d].

Timing note: this assumes Autumn activates equip after Gift of Tusks has fully resolved, as stated. If Autumn had already attached Sword of Body and Mind before Gift of Tusks resolved, the Sword would have been blue (from Painter's Servant) and would have fallen off as soon as protection from blue applied; after Gift of Tusks resolves it could then be re-equipped as described.

This analysis doesn't depend on player count — it's the same with two players or more.

Card data from Scryfall (scryfall.com).

### CELL c0135

**Question**
Autumn casts [Time Stretch]. Can they choose to skip both extra turns with [Time Vault]?

**REFERENCE (correct)**
Yes. As their turn ends, they can apply Time Vault's replacement effect, which means the next turn gets skipped and Time Vault gets untapped as part of the next turn that actually happens. Then, since it's still tapped as Autumn's turn is ending, they can choose to skip the next turn again.

**CANDIDATE**
No. With one Time Vault, Autumn can skip only one of the two extra turns Time Stretch gives them.

Why: Time Vault's own text reads "If you would begin your turn while this artifact is tapped, you may skip that turn instead. If you do, untap this artifact." The skip is a replacement effect — "skip [something]" means "instead of doing [something], do nothing" ([614.10], [614.1b]) — but it only offers the choice if Time Vault is tapped at the moment the turn would begin, and using it untaps Time Vault ([Time Vault ruling #1]). That self-untap is exactly why the card no longer chains: [Time Vault ruling #2] states that with this wording you no longer end up skipping multiple turns even if you find a way to activate the ability multiple times.

Step by step, assuming Time Stretch resolves during Autumn's turn and Autumn targets themselves, and that Time Vault is tapped when the first extra turn would begin:

1. Time Stretch's two extra turns are added after the current turn, one at a time ([500.7]).
2. As extra turn #1 would begin, Time Vault is tapped, so Autumn may skip that turn. Doing so untaps Time Vault, and it untaps before anything else happens in the next turn ([Time Vault ruling #1]).
3. Extra turn #2 then begins with Time Vault untapped, so no skip is available. Once that turn has started it can no longer be skipped anyway; any skip effect would have to wait for the next occurrence ([614.10]).

Autumn could, during extra turn #2, activate Time Vault's "{T}: Take an extra turn after this one" — but that tap creates yet another extra turn, and skipping that later turn just untaps Time Vault again. So the count of turns actually taken doesn't shrink; Autumn never gets to skip both Time Stretch turns off a single Time Vault. Two untapped Time Vaults (or another way to tap it before turn #2 begins without granting a turn) would be needed to skip both.

If Time Vault happens to be untapped when the first extra turn begins, Autumn skips neither of the Time Stretch turns.

Note also that a skipped turn produces no priority, so nothing can be done during it; and if a skip effect tells you to take an action, that action is the first thing that happens in the next turn to actually occur ([614.10b]) — which is how Time Vault's untap lands.

This is the same in a two-player game and at a multiplayer table; the only multiplayer wrinkle in the provided rules is that when several players are given extra turns, those turns are added one at a time in APNAP order ([500.7]), which doesn't change Autumn's ability to skip only one.

Card data from Scryfall (scryfall.com).

### CELL c0136

**Question**
Amelia attacks with [Wildfire Eternal], which isn't blocked. As the trigger resolves, can they choose to suspend [Shivan Meteor]?

**REFERENCE (correct)**
Yes. The suspend special action can be taken whenever Shivan Meteor could be cast from Amelia's hand. Normally that's only when Amelia has priority on their turn with an empty stack, but in this case the effect of Wildfire Eternal is letting that happen while the ability resolves.

(They still have to pay the suspend cost, and afterwards they can choose to cast a different spell from hand without paying its mana cost.)

**CANDIDATE**
No. Amelia cannot suspend Shivan Meteor during the resolution of Wildfire Eternal's triggered ability. Exiling a card with suspend is a special action, and a player may take that special action only when they have priority — no player receives priority in the middle of a spell or ability resolving [116.2f, 608.2g, Shivan Meteor ruling #3].

Why: "Suspend N—[cost]" is a static ability of a card in hand that lets you pay the suspend cost and exile the card with N time counters on it; that action doesn't use the stack and isn't casting the card [702.62a, Shivan Meteor ruling #3, Shivan Meteor ruling #12]. Wildfire Eternal's trigger says "you may cast an instant or sorcery spell from your hand without paying its mana cost" — an effect that specifically instructs a player to cast a spell during resolution. That permission covers casting only; it does not grant priority or permission to take special actions [608.2g].

What Amelia can do instead: as Wildfire Eternal's trigger resolves (during the declare blockers step, before combat damage), Amelia may cast Shivan Meteor itself from hand for free, paying neither {3}{R}{R} nor the {1}{R}{R} suspend cost, choosing a target creature for its 13 damage at that time [Wildfire Eternal ruling #1, Shivan Meteor ruling #11]. Note that "without paying its mana cost" also means Amelia couldn't substitute an alternative cost even if one existed [Shivan Meteor ruling #6]. If Amelia wants to suspend Shivan Meteor for {1}{R}{R} instead, she must do it at a time she holds priority — for example, before the trigger goes on the stack or after it finishes resolving, at any point she could begin casting Shivan Meteor from hand [116.2f, 702.62a, Shivan Meteor ruling #12]. Since Shivan Meteor is a sorcery, that means a main phase of her own turn with an empty stack, not during combat.

This answer is the same in a two-player game and at a multiplayer table; nothing here depends on the number of opponents (Wildfire Eternal's afflict and "attacks and isn't blocked" ability only care about the one defending player it's attacking).

Card data from Scryfall (scryfall.com).

### CELL c0137

**Question**
Ann has a [Sphere of Resistance], a Plains and a Swamp. Can Ann cast [Prismatic Ending] targeting [Drake Familiar]?

**REFERENCE (correct)**
Yes Ann can cast Prismatic Ending targeting Drake Familiar. Ann can target Drake Familiar regardless of whether the final spell will exile it or not, as any card is targetable with Prismatic Ending, and it's only exiled if the conditions are met. Then Ann chooses the value of X, in this case they can select 0, then add Sphere of Resistance's tax resulting in a required mana payment of two. If Ann chooses to use two different colors of mana, when the spell resolves it will see that two colors were spent and exile the target if it's mana value is two or less.

**CANDIDATE**
Yes — and it will actually exile Drake Familiar.

Costs: Prismatic Ending's mana cost is {X}{W}. Sphere of Resistance says "Spells cost {1} more to cast," and that increase applies to Ann too (Sphere of Resistance ruling). Cost increases are added when the total cost is determined [601.2f]. Ann announces X as part of casting [601.2b]; with only two lands she must choose X=0, giving a total cost of {1}{W} (one generic plus one white).

Paying it: Ann taps Plains for {W} to pay the {W} symbol, and taps Swamp for {B} to pay the {1} generic (generic mana can be paid with mana of any color). She has therefore spent two colors of mana — white and black — to cast Prismatic Ending. Note this isn't the forbidden "paying extra mana just to add colors" case (Prismatic Ending ruling #3): the {1} from Sphere of Resistance is mandatory, and she's simply choosing which color pays it.

Targeting and resolution: targets are chosen when the spell is cast [115.1a], and Drake Familiar is a nonland permanent, so it's a legal target. The mana value comparison is not a targeting condition — it's checked only on resolution (Prismatic Ending ruling #1). Drake Familiar's mana value is 2 ({1}{U}), and 2 colors of mana were spent, so 2 ≤ 2 and Drake Familiar is exiled. (Compare Prismatic Ending ruling #2's example structure: more colors spent means a higher mana value can be exiled.)

Caveat on payment choice: if Ann instead paid the generic {1} with a second white source (she can't here — she has only one Plains), only one color would have been spent, Drake Familiar's mana value 2 would exceed it, and the spell would resolve doing nothing.

Player count: this doesn't change with the number of players. Sphere of Resistance's increase applies to every player's spells, and nothing here depends on who the opponents are, so the answer is the same in a two-player game or a multiplayer game.

Card data from Scryfall (scryfall.com).

### CELL c0138

**Question**
Amaris controls a [The Flame of Keld] with 2 lore counters on it and [Soul-Scar Mage]. Amaris puts the third lore counter on The Flame of Keld and resolves its final chapter ability. Amaris then casts [Shock], targeting Nico's [River Kaijin]. How many -1/-1 counters are placed on the River Kaijin?

**REFERENCE (correct)**
There are two replacement effects trying to apply to the damage being dealt, so Nico chooses which one to apply first. If they apply The Flame of Keld's effect first, Soul-Scar Mage's effect will then apply afterwards, and 4 -1/-1 counters will be placed on the River Kaijin. If they apply the Soul-Scar Mage's effect first, the The Flame of Keld's effect will no longer be applicable and the River Kaijin will only receive 2 -1/-1 counters.

**CANDIDATE**
Nico's River Kaijin ends up with 2 -1/-1 counters on it (assuming Nico, as the controller of River Kaijin, chooses to apply Soul-Scar Mage's replacement effect before The Flame of Keld's chapter III effect, which is the order that benefits Nico).

Here's why there's a choice at all: Shock deals 2 damage, and it is a noncombat, red source controlled by Amaris. Two of Amaris's replacement effects are trying to modify that same damage event: (1) Soul-Scar Mage's ability, "If a source you control would deal noncombat damage to a creature an opponent controls, put that many -1/-1 counters on that creature instead," and (2) The Flame of Keld's chapter III ability, "If a red source you control would deal damage to a permanent or player this turn, it deals that much damage plus 2 to that permanent or player instead."

Per [Soul-Scar Mage ruling #0], when multiple prevention and/or replacement effects are trying to apply to the same damage, it is the controller of the creature that would be dealt the damage — here, Nico, who controls River Kaijin — who chooses the order in which they apply, not Amaris.

- If Nico applies Soul-Scar Mage's effect first, the 2 damage from Shock is replaced entirely with 2 -1/-1 counters on River Kaijin. Since this is no longer a damage event, The Flame of Keld's chapter III effect (which only modifies damage) has nothing left to act on, so it does not add 2 more. Result: 2 -1/-1 counters.
- If Nico instead let The Flame of Keld apply first, the 2 damage would become 4 damage, and then Soul-Scar Mage would replace that 4 damage with 4 -1/-1 counters instead. Result: 4 -1/-1 counters.

Since Nico controls the order and it is strictly better for Nico to take fewer counters, Nico will choose the first order, resulting in 2 -1/-1 counters being placed on River Kaijin. Note that Soul-Scar Mage's ability is a replacement effect, not damage prevention [Soul-Scar Mage ruling #1], and a replacement effect only gets one opportunity to apply to a given event [614.5], so once the damage is converted to counters it can't also be boosted by The Flame of Keld afterward.

Card data from Scryfall (scryfall.com).

### CELL c0139

**Question**
Aubrey controls [Mycosynth Lattice]. Natalia controls [Watchwolf] enchanted with [Favorable Destiny]. Aubrey casts [Opportunistic Dragon] and takes control of Favorable Destiny. What will happen after Opportunistic Dragon's ability resolves?

**REFERENCE (correct)**
Favorable Destiny will continue to be attached to Watchwolf indefinitely. The "enchant" keyword is a restriction on what an Aura can enchant- without it Favorable Destiny is legally able to enchant anything.

**CANDIDATE**
Favorable Destiny is put into Natalia's graveyard as a state-based action, and Aubrey never gets any use out of it.

Here's the chain:

1. **Mycosynth Lattice** says "All permanents are artifacts in addition to their other types," so Favorable Destiny is an artifact Enchantment — Aura while it's on the battlefield. That makes it a legal choice for Opportunistic Dragon's trigger, which chooses "target Human or artifact an opponent controls."

2. When Opportunistic Dragon's ability resolves, Aubrey gains control of Favorable Destiny, **it loses all abilities**, and it can't attack or block. Losing all abilities includes losing its enchant keyword ability ("Enchant creature"), which is a static ability that defines what that Aura is allowed to be attached to [702.5a].

3. Favorable Destiny doesn't move — it stays physically attached to Watchwolf — but with no enchant ability there is nothing it can legally be attached to. An Aura attached to an illegal object is put into its owner's graveyard as a state-based action [303.4c] [704.5m]. This is the same principle as the Mycosynth Lattice ruling about Auras that become creatures via March of the Machines: an Aura that can't enchant anything becomes unattached and is then put into its owner's graveyard by state-based actions [Mycosynth Lattice ruling #4].

4. State-based actions are checked the next time a player would receive priority after Opportunistic Dragon's ability finishes resolving, so Favorable Destiny hits the graveyard immediately, before anyone can respond. It goes to its **owner's** graveyard (Natalia's, assuming she owns the card), not to Aubrey's, even though Aubrey controlled it for that instant.

Side note: Favorable Destiny's bonus was already dead weight — Mycosynth Lattice's second ability makes everything colorless, so Watchwolf isn't white and wouldn't have gotten +1/+2 anyway. But the abilities are gone regardless.

Assumed timing: Opportunistic Dragon is still on the battlefield when its trigger resolves. If Opportunistic Dragon had left the battlefield before the trigger resolved, Aubrey would gain nothing — Natalia would keep Favorable Destiny, it wouldn't lose its abilities, and it would stay attached to Watchwolf.

Player count doesn't change any of this: Opportunistic Dragon only requires that the chosen permanent be controlled by an opponent, so the result is the same at a two-player table or a multiplayer one (Aubrey just gets to pick which opponent's artifact to take).

Card data from Scryfall (scryfall.com).

### CELL c0140

**Question**
Nathaniel controls [Rest in Peace] and [Dauthi Voidwalker], and Armani casts [Read the Bones]. What happens to it?

**REFERENCE (correct)**
Armani gets to choose which replacement effect applies to it. After applying that effect, it's no longer moving to the graveyard, so the other effect doesn't apply. It'll end up in exile either way, but Armani gets to choose whether it has a void counter on it.

**CANDIDATE**
Read the Bones resolves normally (Armani scries 2, draws two cards, loses 2 life), and then, instead of going to Armani's graveyard, Read the Bones is exiled. Armani — as the card's owner, since a spell on the stack heading to the graveyard has no controller once it finishes resolving — chooses which of the two replacement effects applies (616.1, 616.1f, 400.6).

Both Rest in Peace ("If a card or token would be put into a graveyard from anywhere, exile it instead") and Dauthi Voidwalker ("If a card would be put into an opponent's graveyard from anywhere, instead exile it with a void counter on it") are replacement effects trying to modify the same event — Read the Bones being put into Armani's graveyard (614.1). Neither is a self-replacement effect and neither changes control of a permanent entering the battlefield, so no effect is forced to be chosen first; the choice is free (614.15, 616.1a, 616.1b, 616.1e).

- If Armani picks Rest in Peace, Read the Bones is exiled with no counter, and the process repeats — but the graveyard event no longer happens, so Dauthi Voidwalker's effect does nothing (614.7, 616.1f).
- If Armani picks Dauthi Voidwalker, Read the Bones is exiled with a void counter on it, and Nathaniel can later tap and sacrifice Dauthi Voidwalker to cast Read the Bones without paying its mana cost that turn (subject to normal timing rules for sorceries).

So Armani will essentially always choose Rest in Peace, denying Nathaniel the void counter. Note Dauthi Voidwalker only applies because Armani is Nathaniel's opponent; Rest in Peace applies to everyone's cards.

Multiplayer note: this works the same at any number of players. If several players' cards were being put into graveyards simultaneously and multiple owners had to choose, those choices are made in APNAP order (101.4, 616.1).

Card data from Scryfall (scryfall.com).

### CELL c0141

**Question**
Amber controls a [Spellbinder] that exiled [Guardian Angel]. Nico controls a [Meddling Mage] that named "Guardian Angel". As Spellbinder's second ability resolves, what happens?

**REFERENCE (correct)**
Amber copies the Guardian Angel in exile. Amber can't cast the copy, so it remains in exile. It ceases to exist as soon as Spellbinder's ability finishes resolving.

**CANDIDATE**
Amber may still create the copy, but she can't cast it — Nico's Meddling Mage stops it.

Why: Spellbinder's triggered ability says "you may copy the exiled card. If you do, you may cast the copy without paying its mana cost." Per [Spellbinder ruling #0], the copy of Guardian Angel is created in the exile zone (where the imprinted card is), and casting it from there is casting a copy of an object under [707.12]/[707.12a] — it follows the normal rules for casting spells, including the legality check.

That legality check is [601.3]: a player can begin to cast a spell only if no rule or effect prohibits it. Meddling Mage reads "Spells with the chosen name can't be cast," and Nico chose "Guardian Angel," so Amber is prohibited from beginning to cast the Guardian Angel copy. Nothing about Guardian Angel's cost gives Amber a choice that would change its name ([601.3a] only helps when a proposal choice could remove the prohibition — X in {X}{W} doesn't change the name).

So the copy of Guardian Angel is simply never cast; it stays in exile as a copy with no spell to become and ceases to exist. Amber gets no damage prevention and doesn't get to use the "pay {1} to prevent 1 more damage" part either, since that only comes from Guardian Angel resolving. Note Meddling Mage only stops casting: if a Guardian Angel spell were already on the stack when Meddling Mage entered, it would resolve normally ([Meddling Mage ruling #1]) — but that isn't the case here.

This works the same whether it's just Amber and Nico or a larger multiplayer table: Meddling Mage's restriction applies to all players, so Amber is blocked in either case.

Card data from Scryfall (scryfall.com).

### CELL c0142

**Question**
Nico controls [Thespian's Stage] that's currently a copy of [Temple of Triumph]. Alayna casts [Alpine Moon] and names "Temple of Triumph" as it resolves. Alayna then activates a second Thespian's Stage targeting Temple of Triumph. What does each Thespian's Stage look like?

**REFERENCE (correct)**
Both Thespian's Stages are lands named "Temple of Triumph" and have "{T}: Add one mana of any color." and no other abilities. Because Thespian's Stage gains its ability as part of the copying process, the ability applies in the copy layer, which is earlier than the adding and removing abilities layer.

**CANDIDATE**
Direct answer: Nico's Thespian's Stage is a land named Temple of Triumph with no land types and no abilities except "{T}: Add one mana of any color" (Alpine Moon shuts it off from producing {R}/{W} and strips the copy ability). Alayna's Thespian's Stage becomes a copy of Temple of Triumph that still has the Thespian's Stage copy ability, and Alpine Moon does NOT affect it, because Alpine Moon only hits lands Alayna's opponents control.

Why:

1) Nico's Stage. Its last ability made it a copy of Temple of Triumph, "except it has this ability." The exception is part of its copiable values (707.9b), so its copiable name is Temple of Triumph and its abilities are Temple of Triumph's plus the copy ability; it lost the original "{T}: Add {C}" ability (Thespian's Stage ruling #0). Because its name is Temple of Triumph and Nico is Alayna's opponent, Alpine Moon applies: in layer 4 it loses all land types (Temple of Triumph had none printed anyway), and in layer 6 it loses all abilities — including "enters tapped," the scry trigger, "{T}: Add {R} or {W}," and the Thespian's Stage copy ability — then gains "{T}: Add one mana of any color." It keeps the land card type and any supertypes (Alpine Moon ruling #1). It also stays tapped or untapped as it already was (Thespian's Stage ruling #2). Practically, Nico can no longer activate the copy ability, since Alpine Moon removed it.

2) Alayna's Stage. Copy effects copy copiable values only; Alpine Moon's ability-removal is a continuous non-copy effect and is not copied (707.3, 707.9b). So whichever "Temple of Triumph" she targets — a real Temple of Triumph, or Nico's Stage whose copiable name is Temple of Triumph — she gets Temple of Triumph's characteristics plus "except it has this ability." If she copied Nico's Stage, the copiable values already include the Thespian's Stage ability, and her own exception grants it again; either way she has it once meaningfully. She does not enter the battlefield, so "enters tapped" and the scry trigger do nothing (Thespian's Stage ruling #1), and it doesn't untap (ruling #2). Since Alayna controls it and Alpine Moon only affects "lands your opponents control," her land keeps its abilities and taps for {R} or {W} and can re-copy later.

Self-reference note: the granted copy ability on either permanent refers to "this land" / that specific object, so activating it affects the permanent it's on, not any other object named Temple of Triumph (201.5, 201.5b, 707.11).

Multiplayer: the same analysis holds at any table size — Alpine Moon hits every opponent of Alayna's who controls a land named Temple of Triumph, and never her own lands. With more players, a third player's Stage copying Temple of Triumph would also be shut off by Alayna's Alpine Moon.

Timing note: I assumed Alpine Moon resolved (naming Temple of Triumph) before Alayna activated her Stage. If she had copied first and Alpine Moon resolved after, the result is identical, since Alpine Moon's effect applies continuously to any qualifying opponent-controlled land regardless of order.

Card data from Scryfall (scryfall.com).

### CELL c0143

**Question**
Alex controls a [Life and Limb], a [Blood Moon], and a 1/1 Green Saproling Creature token, that entered the battlefield in that order. What is the Saproling?

**REFERENCE (correct)**
It's a 1/1 green Land Creature - Mountain Saproling with "{T}: Add {R}.". Applying Life and Limb's effect would allow Blood Moon's effect to apply to the Saproling and applying Blood Moon's effect first would not affect how Life and Limb's effect is applied or what it does, so Blood Moon's effect is dependent on Life and Limb's effect and waits to apply until afterwards. Since Life and Limb's effect makes the Saproling a nonbasic land, Blood Moon then applies and turns it into a Mountain with "{T}: Add {R}." and no other abilities.

**CANDIDATE**
Alex's Saproling token is a 1/1 green Saproling creature that is also a nonbasic land with the land type Mountain, and it has "{T}: Add {R}" instead of "{T}: Add {G}."

Step by step:

1. Life and Limb says "All Forests and all Saprolings are 1/1 green Saproling creatures and Forest lands in addition to their other types." The token is a Saproling, so Life and Limb makes it a creature land: card types creature and land, subtypes Saproling and Forest, with Forest correlating to the land type and Saproling to the creature type [Life and Limb ruling #3]. As a land it enters/exists as a land permanent, and land-enters triggers see it [Life and Limb ruling #1].

2. Tokens created this way have only the characteristics the creating effect gave them, so it has no "basic" supertype [111.3]. A land without the basic supertype is a nonbasic land [Basic] [Nonbasic Land] [205.4b].

3. Because it is a nonbasic land, Blood Moon's "Nonbasic lands are Mountains" applies. It loses its other land types (Forest) and their abilities, gains the land type Mountain, and gains "{T}: Add {R}" [Blood Moon ruling #2] [305.6]. Blood Moon entered after Life and Limb, so its later effect governs which basic land type sticks; Life and Limb keeps applying to it as a Saproling, but the Forest type it grants is overwritten by Mountain.

4. Losing the Forest land type doesn't stop Life and Limb from applying, because the token is still a Saproling — so it remains a 1/1 green Saproling creature, and it's affected by summoning sickness (it can't attack or use {T} abilities, including the mana ability, until it has been under Alex's control since their most recent turn began).

Note the token is still a Saproling creature and a land at the same time; changing its subtypes doesn't add or remove supertypes [205.4b], so it never becomes basic. This answer doesn't depend on the number of players — both enchantments affect the permanents globally regardless of whether it's a two-player or multiplayer game.

One assumption: I'm reading the order given (Life and Limb, then Blood Moon, then the token) as the order the permanents entered. Even if Blood Moon had entered before Life and Limb, the token would still be a nonbasic land Saproling creature; only which basic land type/mana ability sticks (Mountain vs. Forest) turns on that relative timestamp, and the layer rules governing that comparison weren't included in the context.

Card data from Scryfall (scryfall.com).

### CELL c0144

**Question**
Ashley controls [Frogtosser Banneret]. Will it affect the cost of [Knowledge Exploitation]?

**REFERENCE (correct)**
Yes. Knowledge Exploitation is a Rogue.

**CANDIDATE**
Yes. Knowledge Exploitation is a Kindred Sorcery — Rogue, so it's a Rogue spell, and Frogtosser Banneret reduces its total cost by {1}.

Why: kindred is a card type that lets a noncreature card have creature types (its subtypes are drawn from the same list as creature subtypes) [308.1] [308.2]. Knowledge Exploitation's type line "Kindred Sorcery — Rogue" therefore makes it a Rogue spell on the stack even though it isn't a creature spell, which is exactly what Frogtosser Banneret's ability keys off of.

Resulting costs (only the generic portion shrinks; the colored symbols are untouched):
- Normal cost {5}{U}{U} becomes {4}{U}{U}.
- Prowl cost {3}{U} becomes {2}{U}. Frogtosser Banneret reduces the total cost regardless of whether you paid an alternative cost such as prowl [Frogtosser Banneret ruling #2].

Note that Knowledge Exploitation is only a Rogue, not also a Goblin, so it gets the single {1} reduction, not {2} [Frogtosser Banneret ruling #1].

One caution about the free spell: when Knowledge Exploitation resolves and you cast the found instant or sorcery from the opponent's library without paying its mana cost, Frogtosser Banneret's reduction is irrelevant there unless that card is itself a Goblin or Rogue spell — and even then you're paying no mana cost, so there's nothing to reduce [Knowledge Exploitation ruling #2].

This works the same at any player count; the only multiplayer wrinkle is that Knowledge Exploitation targets one opponent of your choice, and prowl requires that you dealt combat damage to a player this turn with a Rogue.

Card data from Scryfall (scryfall.com).

### CELL c0145

**Question**
Angelique has [Copy Enchantment] enter the battlefield as a copy of [Estrid's Invocation], which is a copy of [Hardened-Scale Armor]. At the beginning of their next upkeep, which permanents may Angelique exile?

**REFERENCE (correct)**
Since both cards will have the ability, either Copy Enchantment and Estrid's Invocation may be exiled.

The copy effect of Estrid's Invocation includes the copy gaining an ability as part of the copying process. This is also a copiable value, and Copy Enchantment will also have this ability.

**CANDIDATE**
Angelique may not exile anything — Copy Enchantment does not have an exile-at-upkeep ability at all in this scenario, because it never actually became a copy of Estrid's Invocation's modified copy; it becomes a copy of Hardened-Scale Armor instead.

Here's why: per [Copy Enchantment ruling #6], "If the chosen permanent is copying something else (for example, if the chosen permanent is another Copy Enchantment), then your Copy Enchantment enters the battlefield as whatever the chosen permanent copied." Estrid's Invocation was copying Hardened-Scale Armor, so when Copy Enchantment enters as a copy of Estrid's Invocation, it skips past Estrid's Invocation's own copiable values and instead becomes a copy of what Estrid's Invocation itself copied — Hardened-Scale Armor. This is confirmed from the other side by [Estrid's Invocation ruling #9], which states the identical principle: "If the chosen enchantment is copying something else...then Estrid's Invocation enters the battlefield as whatever the chosen enchantment copied." The same logic applies to Copy Enchantment copying an object with this property.

Crucially, the "except it has 'At the beginning of your upkeep, you may exile this enchantment...'" clause is part of Estrid's Invocation's own copy effect, not part of the copiable values that Estrid's Invocation itself acquired when it copied Hardened-Scale Armor (see [Copy Enchantment ruling #0] and [Estrid's Invocation ruling #8], both stating that copying only picks up what was printed on the original permanent, not non-copy modifications layered on afterward). So that upkeep-exile ability is not passed along when Copy Enchantment copies through Estrid's Invocation to Hardened-Scale Armor.

As a result, Copy Enchantment enters the battlefield as a plain copy of Hardened-Scale Armor — an Aura enchanting a creature that grants +3/+3, with no upkeep trigger whatsoever. Since Copy Enchantment has no "exile this enchantment" ability, there is nothing for Angelique to exile at the beginning of their next upkeep; no trigger even occurs.

Card data from Scryfall (scryfall.com).

### CELL c0146

**Question**
Axel controls [Vastwood Gorger] and attacks Nico's [Teferi, Who Slows the Sunset]. Before damage is dealt, Nico activates [Barrin, Master Wizard], sacrificing Teferi, Who Slows the Sunset. Does Vastwood Gorger deal damage? If so, to what?

**REFERENCE (correct)**
No, Vastwood Gorger does not deal any combat damage. When combat damage would be assigned, a creature that is not currently attacking anything does not deal combat damage.

**CANDIDATE**
Vastwood Gorger deals no combat damage at all. Sacrificing Teferi, Who Slows the Sunset removes it from the battlefield, which removes it from combat under rule [506.4c]. Since Vastwood Gorger was attacking Teferi specifically (a planeswalker, not a player), removing Teferi from combat does not remove Vastwood Gorger from combat — it remains an attacking creature, but it is no longer attacking any player, planeswalker, or battle, per [506.4c]. Vastwood Gorger has no trample or trample-over-planeswalkers ability (it's a vanilla 5/6 per its printed text), so the exception in [702.19e] for trample-over-planeswalkers creatures does not apply, and [702.19f] confirms that without that ability none of its damage can ever be redirected to the defending player even though the planeswalker it was attacking is gone. Under the combat damage assignment rules in [510.1b], an unblocked creature that isn't currently attacking anything (for example because what it was attacking left the battlefield) assigns no combat damage. So Vastwood Gorger simply deals zero damage this combat; it doesn't hit Nico, and it isn't redirected anywhere.

Note on timing: this assumes Barrin's activated ability resolves and Teferi is sacrificed before the combat damage step (i.e., 'before damage is dealt' as stated), so the removal-from-combat rules apply before damage assignment. If instead Teferi had already been removed after damage was already assigned/dealt, the outcome wouldn't change here since no damage was assigned yet in the scenario described.

Card data from Scryfall (scryfall.com).

### CELL c0147

**Question**
Addison casts [Virulent Wound], targeting Natalee's [Memnite]. In response, Natalee casts [Resounding Roar] on the Memnite. What happens at the end of the turn?

**REFERENCE (correct)**
The effect from Resounding Roar wears off, but the -1/-1 counter remains. Memnite dies. The delayed triggered ability created by Virulent Wound is not a continuous effect, so it still exists during the cleanup step, and will trigger due to Memnite dying. Natalee gets a poison counter.

**CANDIDATE**
Memnite dies during the cleanup step of that turn, and Natalee gets a poison counter from Virulent Wound's delayed triggered ability.

How it plays out:

1. Resounding Roar was cast in response, so it resolves first: Memnite (a 1/1) gets +3/+3 until end of turn, making it 4/4.
2. Virulent Wound then resolves, putting a -1/-1 counter on Memnite (now 3/3) and creating a delayed triggered ability: "When that creature dies this turn, its controller gets a poison counter" [610.2, 603.7b].
3. Memnite survives the rest of the turn as a 3/3.
4. In the cleanup step, all "until end of turn" effects end simultaneously with damage removal [514.2]. Resounding Roar's +3/+3 wears off, but the -1/-1 counter is a counter, not a duration effect, so it stays. Memnite is now 1/1 with a -1/-1 counter, i.e. 0/0.
5. Normally no player gets priority in the cleanup step, but because a state-based action is now waiting, the game checks state-based actions [514.3a]: a creature with toughness 0 or less is put into its owner's graveyard [704.5f]. Memnite dies.
6. That death happens during the cleanup step, which is still the same turn Virulent Wound resolved, so the delayed trigger triggers and is put on the stack, and players receive priority [514.3a, 603.7b]. It resolves and Natalee gets a poison counter. Since players got priority, another cleanup step then begins after the stack empties and all players pass [514.3a].

This matches the Virulent Wound ruling: the controller misses the poison counter only if the creature isn't put into a graveyard on the turn Virulent Wound resolved — here it is, just barely, in that turn's cleanup step [Virulent Wound ruling #1].

Timing note: I'm assuming Resounding Roar was cast (for {1}{G}, +3/+3), not cycled. If it had been cycled instead, the trigger would give +6/+6 until end of turn — the result at end of turn is the same, since that bonus also ends in cleanup and Memnite still becomes 0/0 [Resounding Roar]. Also, if Virulent Wound had somehow resolved first and Resounding Roar second, nothing changes: the counter and the pump don't interact, and the same cleanup-step death occurs.

Only Addison and Natalee are named here, and the rules provided don't include any multiplayer-specific rules; nothing about this interaction depends on the number of players, since it's just Natalee's own creature dying and Natalee getting the poison counter.

Card data from Scryfall (scryfall.com).

### CELL c0148

**Question**
Atlas casts [Piracy] and would like to tap all of Nicole's lands but not cast any spells. Can Atlas do this?

**REFERENCE (correct)**
Yes. Piracy creates a restriction on what Atlas must spend the mana on, but does not prevent them from not spending the mana.

**CANDIDATE**
Yes. Piracy lets Atlas tap lands Atlas doesn't control for mana, and nothing in Piracy or the mana rules forces Atlas to actually spend that mana. Atlas can tap every one of Nicole's lands and simply let the mana sit unused.

Why:

- Piracy reads "Until end of turn, you may tap lands you don't control for mana. Spend this mana only to cast spells." That second sentence is a spending *restriction*, not a requirement to spend. Rule [106.6] describes exactly this kind of effect: some effects that produce mana restrict how that mana can be spent. A restriction limits what the mana may legally pay for; it never obligates the player to find something to pay for.
- The mana Atlas produces from Nicole's lands goes into Atlas's mana pool, where it can be spent immediately or stay there as unspent mana ([106.4]). Since Atlas casts nothing, it stays unspent.
- Atlas's mana pool empties at the end of each step and phase, and Atlas is said to lose that mana ([106.4]). There is no penalty stated in the provided rules for losing unspent mana.

So the practical effect is that Nicole's lands are tapped (and unavailable to her until they untap), and Atlas gains nothing but the tapping. Note that the mana can only be spent to cast spells — not, for example, to activate abilities — but again, Atlas isn't required to spend it at all.

Timing note: Atlas must do the tapping while Piracy's effect is still active, i.e., during this turn, and at a time Atlas has priority (or while casting a spell/activating an ability). Tapping all of Nicole's lands at, say, the end step still works; the mana simply drains when that step ends.

Multiplayer: Piracy says "lands you don't control," so with more than two players Atlas may tap any opponent's lands, not just Nicole's — the answer above is otherwise identical. The rules provided here contain no multiplayer-specific text, so nothing changes between a two-player and a multiplayer game for this interaction.

Card data from Scryfall (scryfall.com).

### CELL c0149

**Question**
April casts [Spontaneous Flight] targeting their [Mist Dragon]. After that resolves April then activates its 'lose flying' ability. They cast another Spontaneous Flight targeting Mist Dragon. After that resolves they then use [Hex Parasite] to remove one flying counter. Does Mist Dragon have flying?

**REFERENCE (correct)**
Yes. Keyword counters and ability-removing effects all apply in layer 6 in timestamp order. However when April put the second flying counter on Mist Dragon all flying counters on Mist Dragon had their timestamps updated to match the most recent counter. Meaning that the remaining flying counter on Mist Dragon has a newer timestamp than the activation of the ability that causes it to lose flying.

**CANDIDATE**
Yes — Mist Dragon has flying (and, assuming all of this happened in one turn, it's an 8/8 until end of turn).

Why: a flying counter grants the flying ability, so it's an ability-adding effect that works in layer 6 like any other, and the last-applied effect in that layer wins ([113.10c], [613.9], [613.7a]).

Timeline in layer 6:
1. First Spontaneous Flight resolves: Mist Dragon gets +2/+2 (layer 7c) and a flying counter — Mist Dragon has flying.
2. April activates Mist Dragon's "{0}: This creature loses flying" ability. That effect has a later timestamp, removes all instances of flying ([113.10b]), so Mist Dragon doesn't have flying — even though the counter is still physically there.
3. Second Spontaneous Flight resolves: another +2/+2 and a second flying counter. That counter's flying-granting effect has the latest timestamp, so it beats the earlier "loses flying" effect and Mist Dragon has flying again.
4. Hex Parasite removes one flying counter. One flying counter still remains on Mist Dragon, and its flying-granting effect still postdates the "loses flying" activation, so Mist Dragon still has flying.

Running the layers gives: layer 6 → loses flying (ts 2), then counter grants flying (ts 3) → Mist Dragon has flying; layer 7c → +2/+2 and +2/+2 → 8/8.

Ambiguity worth naming: the two flying counters are identical objects, so the game doesn't really distinguish "the old one" from "the new one"; either way one flying counter survives and it is a counter that was on Mist Dragon at a time after the lose-flying effect applied, so the result is the same. If instead April had activated "{0}: This creature loses flying" *after* Hex Parasite removed the counter, that later effect would win and Mist Dragon would not have flying (it could then be turned back on with "{0}: This creature gains flying").

Also note Hex Parasite gets +1/+0 until end of turn for the one counter actually removed ([Hex Parasite ruling #0]). Multiple simultaneous sources of flying would just be redundant ([702.9c]). Nothing here depends on the number of players.

Card data from Scryfall (scryfall.com).

### CELL c0150

**Question**
Aya controls a [Skullbriar, the Walking Grave] with 3 +1/+1 counters on it. Nico casts [Duplicant] and has it exile Skullbriar, the Walking Grave. What are Duplicant's power and toughness after the imprint ability resolves?

**REFERENCE (correct)**
Duplicant is a 1/1. Duplicant has a non-characteristic defining ability that sets its power and toughness. This is applied in layer 7b, at which point Skullbriar, the Walking Grave's power and toughness is still 1/1 because power and toughness changes from counters are not applied until layer 7c.

**CANDIDATE**
Duplicant is a 4/4 (and an Artifact Creature — Shapeshifter Zombie Elemental).

Why: Skullbriar, the Walking Grave's third ability says "Counters remain on Skullbriar as it moves to any zone other than a player's hand or library." Exile is neither hand nor library, so all three +1/+1 counters stay on the Skullbriar, the Walking Grave card in exile (Skullbriar, the Walking Grave ruling #5, ruling #1 — the ability works because Skullbriar, the Walking Grave had it in the zone it left, the battlefield). Skullbriar, the Walking Grave's own text overrides the general expectation that counters fall off on a zone change.

A +1/+1 counter on a creature card in a zone other than the battlefield still adds to that card's power and toughness ([122.1a]), and Skullbriar, the Walking Grave ruling #2 confirms exactly this (a Skullbriar, the Walking Grave with one counter in the command zone is 2/2). So the exiled Skullbriar, the Walking Grave card is 1/1 base plus three counters = 4/4.

Duplicant's static ability then gives Duplicant "the power, toughness, and creature types of the last creature card exiled with it," so Duplicant's base 2/4 is overwritten in layer 7b ([613.1g], [613.4a] for the layer-7 sublayer framework) with 4/4, and it gains Zombie and Elemental while staying a Shapeshifter. Duplicant ruling #0 notes Duplicant's base power/toughness change to the imprinted card's, and any counters or effects on Duplicant itself would still apply on top (there are none here).

Note the limit in Duplicant ruling #2: characteristic-defining abilities that define a * apply in exile, but abilities that add or subtract power/toughness don't. Counters are not such an ability — they're markers that modify the card's power and toughness directly ([122.1a]), so they do count.

One timing note: this assumes the counters were on Skullbriar, the Walking Grave when it was exiled. If Skullbriar, the Walking Grave had somehow lost its counter-retention ability before leaving the battlefield (e.g., an effect stripping its abilities, per Skullbriar, the Walking Grave ruling #1), the counters would vanish and Duplicant would be 1/1 instead.

Player count doesn't matter here — nothing in this interaction depends on the number of players; the same result holds in a two-player or multiplayer game.

Card data from Scryfall (scryfall.com).

### CELL c0151

**Question**
Archer attacks with a [The Scarab God] that was turned face-down by [Ixidron] and Nia blocks with [Scathe Zombies]. Does The Scarab God trigger?

**REFERENCE (correct)**
No. By default, triggered abilities are checked immediately after the event in question to see if they should trigger. However, "leaves-the-battlefield" triggers check the game state immediately before the event instead. At that point, The Scarab God had no abilities.

**CANDIDATE**
No. The face-down The Scarab God has no abilities while it's face down, so nothing triggers when it dies in combat.

What happens: Ixidron's own text ("As this creature enters, turn all other nontoken creatures face down. (They're 2/2 creatures.)") made The Scarab God a face-down 2/2 with no name, no mana cost, and no rules text. When Archer attacks with the face-down The Scarab God and Nia blocks with Scathe Zombies, combat damage is assigned and then dealt simultaneously as a turn-based action that doesn't use the stack [510.2, 703.4m, 120.4b]. Each is a 2/2 dealing 2 damage to the other, so both the face-down The Scarab God and Scathe Zombies are destroyed by lethal damage. Since the dying permanent is a face-down creature with no rules text, its "When The Scarab God dies, return it to its owner's hand at the beginning of the next end step" ability simply isn't on the object to trigger — a triggered ability needs to exist on the object to see its trigger condition [603.1]. Likewise the upkeep ability doesn't exist while it's face down. Any abilities that did trigger on combat damage would go on the stack before the active player receives priority in the combat damage step [510.3a, 120.4b].

Note also that even turning it face up later wouldn't retroactively fix anything: copiable values only revert when the permanent is actually turned face up [708.8]. And this is independent of player count — the same result applies in a two-player game or a multiplayer game, since it depends only on the face-down permanent's characteristics.

Timing caveat: I'm assuming The Scarab God was still face down at the time combat damage was dealt. If it were somehow turned face up before damage (before it died), its copiable values including the dies ability would be restored [708.8], and then its dies trigger would go on the stack after combat damage [510.3a] — and note it would be a 5/5, surviving Scathe Zombies' 2 damage entirely.

Card data from Scryfall (scryfall.com).

### CELL c0152

**Question**
Alfonso has 20 life and has cast a [Channel] previously this turn. Nancy casts [Word of Command], choosing [Squire] from Alfonso's hand. Can Nancy have Alfonso pay 20 life to add 20 colorless mana while casting the Squire, causing Alfonso to lose the game?

**REFERENCE (correct)**
Yes. There is no restriction on how much mana Alfonso can add while casting Squire. While Word of Command does prevent Alfonso from activating mana abilities that aren't used to cast Squire, paying 1 life to add {C} due to Channel is not a mana ability, it is a special action.

**CANDIDATE**
No. Word of Command's own text says that while the controlled player is playing the chosen card, "the player can activate mana abilities only if they're from lands that player controls and only if mana they produce is spent to activate other mana abilities of lands the player controls and/or to play that card." Channel's ability is a mana ability, but it is not a mana ability of a land Alfonso controls — it's a floating effect created by the Channel spell. So Nancy cannot have Alfonso activate it at all during the Word of Command-forced casting of Squire, and cannot drain Alfonso's life this way. This card text controls over the general rule (723.5a) that a controlling player may use all of the controlled player's resources to pay costs.

Secondary points, assuming the timing given (Channel resolved earlier this turn, then Word of Command resolves and Nancy picks Squire from Alfonso's hand):

- Even if Channel were usable, Squire costs {1}{W}. Channel's {C} is colorless mana specifically and can pay the {1} generic portion, but it can never pay the {W}. So Alfonso would still need a white source, and only 1 generic mana is actually needed for the spell.
- Life payment limits: a player may pay life only if their life total is at least the amount paid (119.4/118.3), so 20 life from a 20-life total is technically a legal payment — but per Channel ruling #0, once a life total is 0 you can't pay any more life even if you haven't lost yet. A player at 0 or less life loses the game as a state-based action the next time a player would receive priority (119.6, 104.3b) — during Word of Command's resolution no one receives priority, so the loss would be checked afterward.
- Note also that Word of Command only compels Alfonso to play the chosen card if able; it does not compel him to activate mana abilities beyond what Nancy directs, and the mana produced must be spent on lands' mana abilities or on playing Squire, so pointless extra mana isn't sanctioned.

If instead Channel were cast after Word of Command started resolving, that's impossible — Alfonso is only being made to play Squire, and Nancy can't have him cast a different card (Word of Command ruling #3 limits it to the chosen card in hand).

This analysis involves just Nancy and Alfonso; the provided rules include a Two-Headed Giant note (810.9b) that if a cost lets both teammates pay life simultaneously, the total can't exceed the team's shared life total, but nothing here changes with more opponents at the table.

Card data from Scryfall (scryfall.com).

