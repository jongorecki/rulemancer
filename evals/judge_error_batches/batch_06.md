# Reference-grading batch batch_06

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
`evals/judge_error_out/batch_06.jsonl` -- nothing else, no prose, no markdown
fence:

    {"cell": "c0001", "verdict": "same", "reason": "<one sentence>"}

`verdict` must be exactly `same` or `different`. Write one line per cell, in
the order the cells appear.

---

### CELL c0096

**Question**
Addison has six cards in their graveyard and casts [Epicenter] targeting Nataly. In response, Nataly casts [Blossoming Calm]. Before it resolves, Addison casts [Dampen Thought] targeting themself. What happens?

**REFERENCE (correct)**
Neither player will sacrifice any lands. The text on Epicenter is a self-replacement effect and changes what the spell is doing. However, before the replacement effect would be applied the game checks to see if all the targets for the spell are still legal. Nataly is no longer a legal target, therefore the spell won't resolve.

**CANDIDATE**
Epicenter does nothing at all — it is removed from the stack and put into Addison's graveyard without resolving, so nobody sacrifices any land, and Nataly keeps hexproof and the 2 life.

Step by step (the stack resolves last-in, first-out):

1. **Dampen Thought** (cast last) resolves first. It targets Addison, who has no hexproof, so the target is legal: Addison mills four cards. Addison's graveyard goes from 6 to 10 cards, and Dampen Thought itself is put into that graveyard as the last part of its resolution (11 cards). Addison is now well past the seven-card threshold count [Dampen Thought ruling #4].

2. **Blossoming Calm** resolves next. Nataly gains hexproof until Nataly's next turn and gains 2 life. Because of rebound, Blossoming Calm is exiled as it resolves instead of going to the graveyard, and Nataly may cast it from exile for free at the beginning of Nataly's next upkeep (that recast is optional).

3. **Epicenter** tries to resolve last. On resolution the game rechecks target legality [608.2b]. Nataly now has hexproof, meaning Nataly can't be the target of spells or abilities Nataly's opponents control, so Nataly is an illegal target for Epicenter. Epicenter's only instance of the word "target" is now illegal, so the spell doesn't resolve; it is removed from the stack and put into its owner's graveyard, and **none** of its effects happen [608.2b]. Addison also can't move the target to another player — targets can't be changed unless a spell or ability explicitly says so [115.1a].

Why the threshold clause doesn't save it: "Each player sacrifices all lands they control instead" is a self-replacement effect that would modify Epicenter's own effect as it resolves [614.15], and later text modifying earlier text is only applied while following the spell's instructions during resolution [608.2c]. Since Epicenter never resolves, that replacement is never applied, even though Addison now has seven or more cards in the graveyard. Milling into threshold in response was a wasted effort here.

Note on terminology: the definition of hexproof isn't among the rules quoted in this context, but it is the keyword Blossoming Calm grants — a player with hexproof can't be targeted by opponents' spells and abilities; that characteristic change is exactly the kind of "other change to the game state" that makes a target illegal under [608.2b].

Timing assumption: I'm assuming the casting order stated in the question (Epicenter, then Blossoming Calm, then Dampen Thought, with nothing resolving in between). If instead Dampen Thought had resolved before Blossoming Calm was ever cast, nothing changes for Epicenter — hexproof still applies before Epicenter resolves. But if Blossoming Calm had resolved before Addison cast Epicenter, Addison simply couldn't choose Nataly as a target at all and would have to target a different (legal) player.

Multiplayer: the outcome is the same with two players or more — Epicenter never resolves, so no player sacrifices anything. The difference is only in what was lost: with more than two players, a resolving threshold Epicenter would have made *every* player, including Addison, sacrifice all their lands, and hexproof on Nataly alone doesn't protect anyone else — had Addison targeted some other, non-hexproof player, Epicenter would have resolved and the threshold clause would have wiped every player's lands.

Card data from Scryfall (scryfall.com).

### CELL c0097

**Question**
Nico controls [Urza's Saga] with two lore counters on it. Alexzander uses [Jinx] to change its land type. What happens?

**REFERENCE (correct)**
In layer 4, Urza's Saga will have its land type overwritten as well as lose all of its chapter abilities. It will gain the abilities to tap for {C} and to create Construct tokens in layer 6, as those abilities are granted by a continuous effect that was generated when the previous chapter abilities resolved..

Since Urza's Saga no longer has any chapter abilities, it will remain at 2 lore counters and will not receive any more in future turns. It is not sacrificed.

**CANDIDATE**
Urza's Saga becomes (say) a Mountain, loses its chapter abilities, and — per the card's own ruling — is immediately sacrificed as a state-based action. Nico keeps nothing from it except whatever abilities other effects had already granted it (which disappear with the permanent).

Why:

1. Jinx sets the land's subtype to a basic land type. Under rule [305.7], setting a land's subtype means the land loses its old land type (Urza's Saga) and loses all abilities generated from its rules text and old land types, gaining the basic type's mana ability instead. So the three chapter abilities (I, II, III) — which are keyword abilities printed in its text box, rule [107.15a] / [714.2b] — are gone.
2. Jinx changes only land subtypes. It doesn't change card types or supertypes ([305.7], [205.4b]), so the permanent is still an enchantment with the enchantment subtype Saga, and it still has its two lore counters.
3. [Urza's Saga ruling #1] directly covers this: if Urza's Saga loses all of its chapter abilities but is still a Saga, it is immediately sacrificed. That ruling is authoritative for this interaction.
   Note the tension worth knowing: the current wording of the state-based action, rules [704.5s] and [714.4], only sacrifices "a Saga permanent with one or more chapter abilities" whose lore counters meet or exceed its final chapter number. Read strictly, a Saga with zero chapter abilities has no final chapter number and wouldn't be sacrificed. Follow the card ruling as given here; at a sanctioned event confirm with a judge which wording applies.
4. Abilities granted by other effects are not removed by [305.7]. So the "{T}: Add {C}" and the "{2}, {T}: Create a 0/0 Construct" abilities Urza's Saga gained from its own resolved chapter I and II triggers ([Urza's Saga ruling #5]) technically survive the type change — but only until the sacrifice, which happens immediately as a state-based action before anyone gets priority. If Nico had priority in response to Jinx, activating those abilities first is the way to get value; after Jinx resolves it's too late.

Chapter III never triggers, since no lore counter is added by Jinx and the Saga is gone before Nico's next precombat main phase turn-based action ([505.4], [703.4f], [714.3c]).

Player count doesn't matter here: this works identically at a two-player table and in multiplayer, since Jinx targets a single land and the sacrifice is performed by that permanent's controller, Nico.

Card data from Scryfall (scryfall.com).

### CELL c0098

**Question**
Adriel controls [Wandering Ones] equipped with [Fleetfeather Sandals]. On Nico's turn, they enchant it with [Tightening Coils]. On Adriel's next turn, they activate Fleetfeather Sandals's equip ability, targeting Wandering Ones. After that resolves, does it have flying?

**REFERENCE (correct)**
No. Tightening Coils has the most recent timestamp, so its effect is applied last. Activating Fleetfeather Sandals's equip ability targeting Wandering Ones doesn't change its timestamp.

**CANDIDATE**
Yes — after the equip ability resolves, Wandering Ones has flying (and haste).

Why: Both Fleetfeather Sandals' "Equipped creature has flying and haste" and Tightening Coils' "loses flying" are ability-adding/removing effects applied in layer 6, so they're ordered by timestamp, and the most recent one prevails (CR 113.10c, 613.1). Fleetfeather Sandals was attached first, so originally Tightening Coils' later timestamp won and Wandering Ones lost flying. But CR 613.7e says an Equipment receives a new timestamp each time it becomes attached to an object — and re-activating equip targeting the same creature still makes it become attached anew, so Fleetfeather Sandals (and the continuous effect from its static ability, CR 613.7a) now has a timestamp later than Tightening Coils. Applying layer 6 in order: Tightening Coils removes flying, then Fleetfeather Sandals grants flying and haste. Net result: Wandering Ones has flying and haste. This matches Tightening Coils ruling #0: if an effect gives the enchanted creature flying after Tightening Coils became attached, the creature has flying.

Tightening Coils' -6/-0 is a layer 7c effect and is unaffected by the re-equip, so Wandering Ones is a -5/1 flier (power is treated as 0 for damage purposes; it doesn't die, since only 0-or-less toughness is lethal).

Note: only Adriel, as controller of Fleetfeather Sandals, can activate its equip ability (CR 301.5d), and equip only targets a creature Adriel controls — that's satisfied here. Nothing about this changes with more than two players; it's purely a timestamp/layers question between Adriel's and Nico's permanents.

Card data from Scryfall (scryfall.com).

### CELL c0099

**Question**
Aya controls a [Skullbriar, the Walking Grave] with 3 +1/+1 counters on it. Nico casts [Duplicant] and has it exile Skullbriar, the Walking Grave. What are Duplicant's power and toughness after the imprint ability resolves?

**REFERENCE (correct)**
Duplicant is a 1/1. Duplicant has a non-characteristic defining ability that sets its power and toughness. This is applied in layer 7b, at which point Skullbriar, the Walking Grave's power and toughness is still 1/1 because power and toughness changes from counters are not applied until layer 7c.

**CANDIDATE**
Duplicant is a 4/4 Zombie Elemental Shapeshifter (assuming nothing else is modifying it).

Why: Skullbriar, the Walking Grave's last ability says "Counters remain on Skullbriar as it moves to any zone other than a player's hand or library." Skullbriar, the Walking Grave has that ability on the battlefield, so when Nico's Duplicant exiles it, the three +1/+1 counters go to exile with it [Skullbriar, the Walking Grave ruling #1]. A +1/+1 counter on a creature card in a zone other than the battlefield still adds to that object's power and toughness [122.1a], which is exactly why a Skullbriar, the Walking Grave with a counter in the command zone is 2/2 [Skullbriar, the Walking Grave ruling #2]. So the exiled Skullbriar, the Walking Grave card is 1/1 base + three counters = 4/4 in exile.

Duplicant's static ability then sets its power and toughness (in layer 7b, effects that set P/T to a specific value [613.4b]) to the exiled card's power and toughness, and gives it that card's creature types (Zombie Elemental) while remaining a Shapeshifter. That's a base-P/T change [Duplicant ruling #0], and it updates continuously if the exiled card's P/T changes [Duplicant ruling #3]. Note the exception Duplicant ruling #2 mentions — abilities that add or subtract power/toughness (like Death's Shadow's) don't apply in exile — but counters are not abilities; they are markers that modify characteristics directly [122.1a], so they do count here.

Any +1/+1 counters or pump effects on Duplicant itself would still apply on top of the 4/4 [Duplicant ruling #0]; the question states none.

This works the same at a two-player or multiplayer table; nothing here depends on the number of players. Timing note: I'm assuming the counters were on Skullbriar, the Walking Grave before it was exiled. If the counters were somehow added after it hit exile, they wouldn't be there (nothing places counters on exiled cards), and Duplicant would be 1/1.

Card data from Scryfall (scryfall.com).

### CELL c0100

**Question**
Adriel controls [Oko, Thief of Crowns], [Gilded Goose], and a Food token. Adriel uses Oko, Thief of Crowns's +1 ability to make the Food token into a 3/3 Elk. Can Adriel then sacrifice it to Gilded Goose?

**REFERENCE (correct)**
No. Oko, Thief of Crowns's ability is a type-changing effect which will overwrite any previous types and subtypes the object had. When Gilded Goose asks Adriel to sacrifice a Food, it is saying that Adriel needs to sacrifice a permanent with the subtype "Food".

**CANDIDATE**
No. Once Oko, Thief of Crowns's +1 ability resolves on the Food token, that token is no longer a Food, so Gilded Goose's "{T}, Sacrifice a Food: Add one mana of any color" ability can't be activated by sacrificing it.

Why:

1. Oko, Thief of Crowns's +1 makes the target lose all abilities and become a green Elk creature with base power and toughness 3/3. Per the Oko, Thief of Crowns ruling, this overwrites all colors and creature types and the permanent "loses any other card types it has (such as artifact)" [Oko, Thief of Crowns ruling #5]. So the token is now just a creature, not an artifact.

2. Food is an artifact type (an artifact subtype), never a creature type [Oko, Thief of Crowns ruling #13] [Gilded Goose ruling #2]. Rule 205.1a says that when an object's card type is removed, subtypes correlated with that card type remain only if they're also subtypes of a card type the object currently has; otherwise they're removed for as long as that card type is gone. Since the token is no longer an artifact and Food isn't a creature type, the Food subtype falls off. Its new creature type is Elk.

3. Gilded Goose's cost says "Sacrifice a Food." Under rule 109.2, a description using a subtype without the words "card," "spell," or "source" means a permanent of that subtype on the battlefield — i.e., a permanent that is currently a Food. The 3/3 Elk isn't one, so it can't pay that cost.

Also note the token lost all abilities, so it no longer has its own "{2}, {T}, Sacrifice this token: You gain 3 life" ability either.

Timing: I'm assuming Adriel resolved the +1 first and is asking about sacrificing afterward. If instead Adriel sacrifices the token to Gilded Goose first (or in response, while Oko, Thief of Crowns's ability is still on the stack), it's still a Food at that moment and the sacrifice works fine — and Oko, Thief of Crowns's ability would then be countered for having an illegal target if that token was its only target.

This interaction doesn't depend on player count; it plays out the same in a two-player game or at a multiplayer table.

Card data from Scryfall (scryfall.com).

### CELL c0101

**Question**
Nico controls [Urza's Saga] with two lore counters on it. Alexzander uses [Jinx] to change its land type. What happens?

**REFERENCE (correct)**
In layer 4, Urza's Saga will have its land type overwritten as well as lose all of its chapter abilities. It will gain the abilities to tap for {C} and to create Construct tokens in layer 6, as those abilities are granted by a continuous effect that was generated when the previous chapter abilities resolved..

Since Urza's Saga no longer has any chapter abilities, it will remain at 2 lore counters and will not receive any more in future turns. It is not sacrificed.

**CANDIDATE**
Urza's Saga is put into Nico's graveyard as a state-based action almost immediately after Jinx resolves.

Why:

1. Jinx says "Target land becomes the basic land type of your choice until end of turn." That's a type-changing effect applied in layer 4 ([613.1d], [Type-Changing Effect]). Setting a land's subtype replaces its existing land types, so Urza's Saga loses the Urza's land type and gains the chosen basic land type plus that type's intrinsic mana ability, and it loses all abilities generated from its rules text ([305.7], [205.1a]).
2. Setting a land subtype does not change card types or supertypes ([305.7], [205.4b]). Urza's Saga is still an Enchantment Land, and "Saga" is an enchantment subtype, not a land subtype — Jinx only replaces subtypes from the land-type set ([205.1a]). So Urza's Saga is still a Saga, but with no chapter abilities.
3. A Saga with no chapter abilities is sacrificed immediately — this is exactly the situation covered by [Urza's Saga ruling #1] ("If Urza's Saga loses all of its chapter abilities but is still a Saga, perhaps due to a card like Blood Moon, it will immediately be sacrificed"). Having two lore counters doesn't protect it. See also [Urza's Saga ruling #4], confirming it remains a Saga even though it's a land.

A note on abilities it had already gained: chapter I's "{T}: Add {C}" (and chapter II's token ability if it had resolved) were granted by a separate effect, and [305.7] says setting a land's subtype doesn't remove abilities granted to the land by other effects; [Urza's Saga ruling #5] says it keeps those for as long as it's on the battlefield. But since it's sacrificed right away, that matters only if Nico can respond — Jinx's target change happens on resolution, so Nico can tap Urza's Saga for {C} (colorless mana specifically, not generic) or activate the Construct-token ability in response to Jinx while it's still on the stack.

Timing assumption: I'm assuming chapter II has already resolved (two lore counters) and Jinx resolves before Nico's next draw step. If instead a third lore counter were added first, chapter III would trigger and Urza's Saga would be sacrificed after that chapter resolves ([Urza's Saga ruling #4]) — Jinx afterward would find nothing.

Multiplayer: nothing here depends on the number of players; the result is the same whether it's a two-player game or a larger table.

Card data from Scryfall (scryfall.com).

### CELL c0102

**Question**
In a game of commander, Natasha has shuffled their commander into their library. Adan casts [Praetor's Grasp] targeting Natasha and finds Natasha's commander. Can Natasha choose to put it into the command zone?

**REFERENCE (correct)**
Yes. Despite being face-down, it's still Natasha's commander, and they can choose to have it move to the command zone as a state-based action.

**CANDIDATE**
Yes. Once Praetor's Grasp resolves and Natasha's commander is in the exile zone, the Commander state-based action applies: if a commander is in a graveyard or in exile and it was put there since the last time state-based actions were checked, its owner may put it into the command zone (704.6d, 903.9a). Natasha is the owner, so Natasha gets that choice.

Details that matter here:

- Being face down doesn't matter. A commander that's been turned face down is still a commander, and the commander designation is an attribute of the card itself that it keeps in every zone (903.3). So the exiled face-down card is still Natasha's commander and still eligible for the command-zone state-based action.
- The choice is Natasha's alone, and it's a one-shot window. The state-based action only applies while the object was put into exile "since the last time state-based actions were checked" (704.6d, 903.9a). If Natasha declines at that check, the commander stays in exile.
- If Natasha declines, Adan keeps the benefit of Praetor's Grasp: "You may play that card for as long as it remains exiled," paying its costs and obeying normal timing rules (Praetor's Grasp ruling #1). If Natasha takes the command-zone option, the card leaves exile and Adan can no longer play it.
- One practical wrinkle the provided material doesn't resolve: a Praetor's Grasp ruling says other players, including the card's owner, can't look at the card while it remains exiled (Praetor's Grasp ruling #2). Nothing in the rules given here explains how Natasha is meant to be informed that the exiled card is the commander; the state-based action itself is unambiguous, but the information-handling procedure isn't covered by the context provided.

Player count: Commander games are commonly multiplayer, and nothing in the rules cited changes with the number of players — the commander's owner (Natasha) makes the choice whether the table is two players or more. Praetor's Grasp targets one opponent regardless.

Card data from Scryfall (scryfall.com).

### CELL c0103

**Question**
Nico controls [Thespian's Stage] that's currently a copy of [Temple of Triumph]. Alayna casts [Alpine Moon] and names "Temple of Triumph" as it resolves. Alayna then activates a second Thespian's Stage targeting Temple of Triumph. What does each Thespian's Stage look like?

**REFERENCE (correct)**
Both Thespian's Stages are lands named "Temple of Triumph" and have "{T}: Add one mana of any color." and no other abilities. Because Thespian's Stage gains its ability as part of the copying process, the ability applies in the copy layer, which is earlier than the adding and removing abilities layer.

**CANDIDATE**
Nico's Thespian's Stage is hit by Alpine Moon; Alayna's own Thespian's Stage is not.

Nico's permanent (Thespian's Stage copying Temple of Triumph): its copiable values are those of Temple of Triumph, including its name, plus the granted "{2}, {T}: This land becomes a copy of target land, except it has this ability" (707.3, 707.9b; Thespian's Stage ruling #0 — it no longer has the Stage's mana ability "{T}: Add {C}"). Because its name is now literally "Temple of Triumph" — the chosen name — and Nico is an opponent of Alayna, Alpine Moon applies. Applying the layers (613.1c): in layer 4 it loses all land types (Temple of Triumph has none printed anyway, so no visible change), and in layer 6 it loses all abilities — including the "enters tapped" and "scry 1" abilities, the {R}/{W} mana ability, and the copy ability it kept as an exception — and then gains "{T}: Add one mana of any color." Result: a land named Temple of Triumph with no land types and exactly one ability, "{T}: Add one mana of any color." It keeps the land card type and any supertypes (Alpine Moon ruling #1), and it stays tapped or untapped as it already was (Thespian's Stage ruling #2). Notably it can no longer activate the copy ability, since Alpine Moon strips it.

Alayna's second Thespian's Stage: it copies Temple of Triumph (whether it targeted a real one or Nico's permanent — the copiable values are the same, and if it targeted Nico's permanent the Alpine Moon effect is not copied, since only copiable values are copied per 707.3). So it becomes a land named Temple of Triumph with "{T}: Add {R} or {W}", the enters-tapped and scry abilities (which do nothing now — it was already on the battlefield, per Thespian's Stage ruling #1), plus "{2}, {T}: This land becomes a copy of target land, except it has this ability." Alpine Moon only affects lands Alayna's *opponents* control, and Alayna controls this one, so it is untouched, and it doesn't become untapped from copying (Thespian's Stage ruling #2).

Multiplayer note: Alpine Moon says "lands your opponents control," so at a table of more than two players every opponent's land named Temple of Triumph — including copies like Nico's — is affected the same way; Alayna's own are always exempt.

Timing assumption: Alpine Moon's name choice was made as it entered and Nico's Stage was already a copy of Temple of Triumph. If Nico instead copies Temple of Triumph *after* Alpine Moon is on the battlefield, the answer is the same — Alpine Moon is a continuous effect that applies to whatever qualifying lands exist at any moment.

Card data from Scryfall (scryfall.com).

### CELL c0104

**Question**
Alijah controls [Badlands] and [Conversion]. Alijah then casts [Magus of the Moon]. After that resolves, what color(s) of mana can Badlands tap for?

**REFERENCE (correct)**
Only {R}. Both Magus of the Moon and Conversion only apply in layer 4. The effects are applied in timestamp order, resulting in Conversion applying first to make Badlands a Plains, then Magus of the Moon applies making it a Mountain.

**CANDIDATE**
Badlands taps only for {W} (white).

Why: both Magus of the Moon ("Nonbasic lands are Mountains") and Conversion ("All Mountains are Plains") are type-changing continuous effects applied in layer 4. Conversion has the earlier timestamp, but it depends on Magus of the Moon: applying Magus of the Moon changes what Conversion applies to (it makes the nonbasic Badlands a Mountain), so Magus of the Moon is applied first.

Step 1 — Magus of the Moon: Badlands loses its Swamp and Mountain types and becomes just a Mountain, losing its old abilities and gaining "{T}: Add {R}" [Magus of the Moon ruling #4], [305.7].
Step 2 — Conversion: Badlands is now a Mountain, so it becomes a Plains. Under 305.7 it again loses the land type it had and the abilities from it, and gains the intrinsic Plains ability "{T}: Add {W}" [305.6].

So Badlands ends up as a nonbasic land with subtype Plains only, tapping for {W}. It can no longer produce {B} or {R} — its printed dual mana abilities ([Badlands ruling #3]) are gone, since the type-setting effects strip abilities generated from its old land types [Badlands ruling #1]. Note neither effect changes its name or supertypes [Magus of the Moon ruling #1], [Conversion ruling #1], and there was never a window to tap it for red in between — this is a single continuous-effect calculation, not a sequence of events [Conversion ruling #0].

This analysis doesn't depend on player count: the effects are global and apply the same way in a two-player or multiplayer game.

Card data from Scryfall (scryfall.com).

### CELL c0105

**Question**
Alannah controls [Ore-Rich Stalactite], [Life and Limb], [March of the Machines], and [Xenograft] naming "Saproling", that entered the battlefield in that order. What is the Ore-Rich Stalactite?

**REFERENCE (correct)**
It's a 2/2 colorless Artifact Creature - Saproling.

In layer 4, Life and Limb's effect is not dependent on March of the Machines or Xenograft, so Life and Limb is applied first, then March of the Machines, then Xenograft. Since Life and Limb didn't apply to Ore-Rich Stalactite in layer 4, it doesn't apply to it in later layers either.

**CANDIDATE**
Alannah's Ore-Rich Stalactite ends up as a green 1/1 Saproling Artifact Creature — Forest Land that still has its own printed abilities.

How it gets there (all type changes happen in layer 4, per [613.1d], and each effect adds types rather than replacing them, per [205.1b]):

1. Ore-Rich Stalactite starts as a colorless noncreature Artifact.
2. March of the Machines makes each noncreature artifact an artifact creature with power and toughness equal to its mana value — so Ore-Rich Stalactite becomes an artifact creature (layer 4 type change; the P/T setting happens later in layer 7b, see [613.6]).
3. Xenograft (naming Saproling) makes each creature Alannah controls that type in addition to its other types, so Ore-Rich Stalactite is now a Saproling artifact creature ([205.1b]).
4. Life and Limb makes all Saprolings 1/1 green Saproling creatures and Forest lands in addition to their other types. Even though Life and Limb entered first, it can only apply to Ore-Rich Stalactite once Xenograft has made it a Saproling; I'm assuming the standard dependency treatment, under which Life and Limb is applied after Xenograft. (The dependency rule itself isn't in the provided context, so that ordering is an assumption; if you instead applied strict timestamp order in layer 4, Life and Limb would never see Ore-Rich Stalactite as a Saproling and it would just be a 2/2 Saproling artifact creature with no land types and no green color.)

Resulting characteristics under the dependency reading:
- Card types: Artifact, Creature, Land ([205.1b], [205.2b], [300.2]).
- Subtypes: Saproling (creature type) and Forest (land type), each correlated to its own card type ([205.3c], [205.3i], [305.5]).
- Supertypes: none — it is not "basic"; type changes never add supertypes ([205.4b], [305.7]).
- Color: green, from Life and Limb (layer 5).
- Power/toughness: 1/1. Both March of the Machines and Life and Limb are setting effects in layer 7b, and Life and Limb applies last, overwriting the mana-value-based 2/2 ([613.6]).
- Abilities: it keeps "{T}: Add {R}. Spend this mana only to cast an instant or sorcery spell." and its Craft ability, because gaining a land type in addition to its own types doesn't remove rules text ([305.7]). It also gains the intrinsic Forest ability "{T}: Add {G}" ([305.6]). Note it's a creature now, so summoning sickness applies to those {T} abilities.

This analysis doesn't depend on the number of players; it's the same at a two-player or multiplayer table, since all four permanents are Alannah's and Xenograft only looks at creatures she controls.

Card data from Scryfall (scryfall.com).

### CELL c0106

**Question**
Amos controls [March of the Machines] and [Mycosynth Lattice] and casts [Lust for War] targeting their [Gilded Sentinel]. What will happen when Lust for War resolves?

**REFERENCE (correct)**
Lust for War cannot legally enchant anything, so it will be put directly into its owners graveyard.

**CANDIDATE**
Lust for War will resolve and enter the battlefield attached to Gilded Sentinel, but it will immediately fall off and go to Amos's graveyard — it never gets to do anything.

Step by step:

1. While Lust for War is still a spell on the stack, Mycosynth Lattice doesn't affect it. Mycosynth Lattice only makes permanents artifacts, and spells on the stack aren't permanents (Mycosynth Lattice ruling #2).
2. Gilded Sentinel is a legal object for Lust for War's "Enchant creature" ability, so Lust for War resolves and enters the battlefield attached to Gilded Sentinel ([303.4d]).
3. The instant Lust for War is on the battlefield, Mycosynth Lattice makes it an artifact in addition to being an enchantment — Aura. March of the Machines then sees a noncreature artifact and turns it into an artifact creature with power and toughness equal to its mana value. Lust for War's mana value is 3 ({2}{R}), so it becomes a 3/3 artifact creature that is still an enchantment — Aura (March of the Machines ruling #2).
4. An Aura that's also a creature can't enchant anything. The next time state-based actions are checked, Lust for War becomes unattached from Gilded Sentinel, and then as a second state-based action it's put into its owner's graveyard ([303.4d], Mycosynth Lattice ruling #4).

So Gilded Sentinel is never actually enchanted for any meaningful length of time: neither the "deals 3 damage when tapped" trigger nor the "attacks each combat if able" requirement will ever apply. Note that Lust for War dies because it's an Aura that's a creature, not because of a toughness problem — as a 3/3 it isn't destroyed for lethal damage or 0 toughness.

One timing note: this assumes Gilded Sentinel is still a legal target when Lust for War resolves. If Gilded Sentinel had left the battlefield or otherwise become an illegal target first, Lust for War would simply fail to resolve and be put into the graveyard as a countered spell instead — the same end zone, just for a different reason.

Player count doesn't matter here. Nothing in this interaction involves choosing an opponent or a defending player, so the result is identical in a two-player game and at a multiplayer table.

Card data from Scryfall (scryfall.com).

### CELL c0107

**Question**
Aubrey controls [Mycosynth Lattice]. Natalia controls [Watchwolf] enchanted with [Favorable Destiny]. Aubrey casts [Opportunistic Dragon] and takes control of Favorable Destiny. What will happen after Opportunistic Dragon's ability resolves?

**REFERENCE (correct)**
Favorable Destiny will continue to be attached to Watchwolf indefinitely. The "enchant" keyword is a restriction on what an Aura can enchant- without it Favorable Destiny is legally able to enchant anything.

**CANDIDATE**
Favorable Destiny is put into Natalia's graveyard almost immediately. When Opportunistic Dragon's triggered ability resolves, Aubrey gains control of Favorable Destiny, Favorable Destiny loses all abilities, and it can't attack or block. Losing all abilities means Favorable Destiny loses its "Enchant creature" ability — and what an Aura may legally be attached to is defined solely by its enchant ability [303.4c, 702.5a]. With no enchant ability, Favorable Destiny is attached to an illegal object, so the next time state-based actions are checked (before any player receives priority) Favorable Destiny is put into its owner's graveyard [704.5m]. Its owner is Natalia, so it goes to Natalia's graveyard even though Aubrey controls it at that moment [110.2b].

Why Favorable Destiny was a legal target at all: Mycosynth Lattice makes all permanents artifacts in addition to their other types, so the enchantment Favorable Destiny is an artifact on the battlefield and qualifies as "target Human or artifact an opponent controls" [Mycosynth Lattice ruling #2]. This mirrors the published Mycosynth Lattice ruling about Auras that stop being able to enchant anything: they become unattached and are put into their owner's graveyard as a state-based action [Mycosynth Lattice ruling #4].

Other consequences:
- Gaining control of Favorable Destiny does not move it and does not give Aubrey control of Watchwolf; an Aura's controller is separate from the enchanted permanent's controller [303.4e].
- While Favorable Destiny exists with no abilities, it grants nothing: Watchwolf loses the +1/+2 (which wasn't applying anyway, since Mycosynth Lattice makes Watchwolf colorless rather than white) and loses the conditional shroud. Watchwolf stays under Natalia's control and is unaffected once Favorable Destiny hits the graveyard.
- Note the shroud clause never protected Favorable Destiny itself — it only would have applied to Watchwolf.

Timing assumption: I'm assuming Opportunistic Dragon is still on the battlefield when its trigger resolves. If Opportunistic Dragon leaves the battlefield before the ability resolves, Aubrey never gains control of Favorable Destiny, it doesn't lose any abilities, and it simply stays attached to Watchwolf [Opportunistic Dragon ruling #4].

Multiplayer: nothing changes. Opportunistic Dragon's trigger just requires the targeted artifact to be controlled by any one opponent of Aubrey, so with more than two players the same sequence occurs, and Favorable Destiny still goes to its own owner's graveyard [110.2b].

Card data from Scryfall (scryfall.com).

### CELL c0108

**Question**
Armani controls [Soul Echo] with 0 counters on it and Nico controls [Spirit of the Hearth]. Will Armani have to sacrifice Soul Echo at the beginning of their upkeep?

**REFERENCE (correct)**
No. Since the ability has no legal targets, it would trigger at the beginning of the upkeep but would not be put on the stack.

**CANDIDATE**
Yes — Armani will have to sacrifice Soul Echo. Soul Echo's triggered ability reads: "At the beginning of your upkeep, sacrifice this enchantment if there are no echo counters on it. Otherwise, target opponent may choose that for each 1 damage that would be dealt to you until your next upkeep, you remove an echo counter from this enchantment instead." Because Soul Echo has 0 echo counters when Armani's upkeep begins, the first branch of the ability applies: Armani simply sacrifices Soul Echo. The 'target opponent' language only comes into play in the 'Otherwise' branch, which is used when Soul Echo *does* have one or more echo counters on it. Since that branch never triggers here, no target is chosen at all, so Spirit of the Hearth's hexproof (which only stops Nico from being the target of a spell or ability an opponent controls) is completely irrelevant to this particular upkeep trigger. Nico's hexproof would matter only in a scenario where Soul Echo still had counters and Armani's ability needed to choose Nico as the 'target opponent' for the damage-redirection effect — in that case, if Nico is the only opponent, the ability would have no legal target to choose and that branch couldn't be used to redirect damage. But that's not the situation here, since Soul Echo already has 0 counters and the sacrifice instruction doesn't require a target. This holds whether Armani and Nico are the only two players or there are more players at the table (the outcome doesn't change with additional opponents, since the sacrifice branch never involves choosing any opponent as a target). Card text always overrides general targeting expectations when it conditions targeting on a specific branch of a conditional trigger, which is what's happening here.

Card data from Scryfall (scryfall.com).

### CELL c0109

**Question**
Natalie controls [High Fae Trickster]. Allen activates the crew ability of [Capenna Express]. Before it resolves Natalie casts [One with the Stars] targeting Capenna Express. What happens when the crew ability resolves?

**REFERENCE (correct)**
Capenna Express will become an artifact creature as normal. One with the Stars and Capenna Express's abilities both apply in layer 4 and attempt to change its type. Capenna Express's ability will have the newer timestamp, and it resolved most recently. ([613.7], [613.7b], [702.122a])

**CANDIDATE**
Natalie can't cast One with the Stars targeting Capenna Express at that moment — the crew ability is still on the stack, so Capenna Express is still just a noncreature artifact Vehicle and is not a legal target for an Aura that reads "Enchant creature or enchantment." The attempted cast is illegal and is rewound; Allen's crew ability then resolves normally and Capenna Express becomes an artifact creature (a 6/6) until end of turn.

Details:
- Crew is an activated ability: "Tap any number of other untapped creatures you control with total power N or greater: This permanent becomes an artifact creature until end of turn" [702.122a]. The creatures are tapped as a cost when Allen activates it; the type change happens only on resolution. Until then Capenna Express has no power or toughness and isn't a creature [208.3a].
- Because Capenna Express is neither a creature nor an enchantment while the crew ability is on the stack, it can't be chosen as the target of One with the Stars. Target legality is checked both on casting and again on resolution [608.2b].
- High Fae Trickster's "You may cast spells as though they had flash" lets Natalie cast One with the Stars at instant speed, but it doesn't change what the Aura can legally enchant.
- If instead Natalie waits until after the crew ability resolves, Capenna Express is then an artifact creature and is a legal target. One with the Stars would make it an enchantment that loses all other card types, and per One with the Stars ruling #1 it stays an enchantment even after the crew effect would have expired at end of turn.

Nothing here depends on the number of players; the answer is the same in a two-player game or at a multiplayer table.

Card data from Scryfall (scryfall.com).

### CELL c0110

**Question**
Ahmad controls [Conspiracy] (naming "Ferret"), [Kormus Bell], [Urborg, Tomb of Yawgmoth], and a [Vastwood Zendikon] enchanting Urborg, Tomb of Yawgmoth that entered the battlefield in that order. Is Urborg, Tomb of Yawgmoth a creature? If so, what are its creature types?

**REFERENCE (correct)**
It is an Elemental Ferret creature. Conspiracy has the earliest timestamp, but it's dependent on Vastwood Zendikon, and waits to apply until after Vastwood Zendikon is applied. Kormus Bell is dependent on Urborg, Tomb of Yawgmoth, so Urborg, Tomb of Yawgmoth is applied first, then Kormus Bell. At this point Conspiracy is no longer be dependent on Vastwood Zendikon, so Conspiracy is applied, and then Vastwood Zendikon. Since Vastwood Zendikon says that Urborg, Tomb of Yawgmoth is still a land, it retains its prior creature type of "Ferret" when it becomes an Elemental.

**CANDIDATE**
Yes — Urborg, Tomb of Yawgmoth is a creature, and its only creature type is Ferret. Its full type line ends up: Legendary Land Creature — Swamp Ferret (a green 6/4).

How the layers get there (CR 613.1d, layer 4 for type changes; CR 613.6 for effects split across layers):

1. Urborg, Tomb of Yawgmoth's own ability makes each land a Swamp in addition to its other land types, so Urborg, Tomb of Yawgmoth itself is a Swamp (Urborg, Tomb of Yawgmoth ruling #0; CR 305.7 — gaining a land type in addition keeps existing types and rules text).
2. Kormus Bell then applies: "All Swamps are 1/1 black creatures that are still lands." Because Urborg, Tomb of Yawgmoth is a Swamp, Kormus Bell makes it a land creature (CR 205.1b, 205.2b; Kormus Bell ruling #0). Kormus Bell's effect depends on Urborg, Tomb of Yawgmoth's, since Urborg, Tomb of Yawgmoth changes what Kormus Bell applies to (CR 613.9).
3. Vastwood Zendikon makes the enchanted land a 6/4 green Elemental creature that's still a land (Vastwood Zendikon ruling #5).
4. Conspiracy (naming Ferret) says creatures you control are the chosen type. Even though Conspiracy has the earliest timestamp, it's applied last in layer 4 here: whether Urborg, Tomb of Yawgmoth is a creature — i.e., whether Conspiracy applies to it at all — is determined by Kormus Bell and Vastwood Zendikon, so Conspiracy's effect depends on theirs (CR 613.9). Conspiracy sets the creature type, and affected creatures lose all their other creature types (Conspiracy ruling #4), so Elemental from Vastwood Zendikon is gone and Ferret is the only creature type. Conspiracy can also grant a creature type to animated lands that would otherwise have none (Conspiracy ruling #1).

What is unchanged: the Swamp subtype is a land type, not a creature type, so Conspiracy doesn't touch it; Urborg, Tomb of Yawgmoth keeps Swamp and the {T}: Add {B} ability that comes with it (CR 205.3c, 305.7). The Legendary supertype survives all of this (CR 205.4b). Colors and P/T are set in later layers by timestamp: layer 5 gives black (Kormus Bell) then green (Vastwood Zendikon), so it's green; layer 7b sets 1/1 then 6/4, so it's 6/4.

This analysis is player-count independent — nothing here depends on how many opponents are at the table; Conspiracy and Kormus Bell only care about creatures Ahmad controls and Swamps anywhere, respectively.

Card data from Scryfall (scryfall.com).

### CELL c0111

**Question**
Nico controls [Drought]. How many Swamps would Ava have to sacrifice in order to cast [Beckon Apparition]?

**REFERENCE (correct)**
1. Hybrid mana symbols are the colors of their constituent mana symbols.

**CANDIDATE**
Ava must sacrifice exactly one Swamp.

Beckon Apparition's mana cost is a single hybrid symbol, {W/B}. A hybrid symbol is a colored mana symbol that is *all* of its component colors, so {W/B} is both a white mana symbol and a black mana symbol [107.4e]. Drought counts black mana symbols in the spell's mana cost, and its ruling is explicit that a hybrid symbol which is partly black counts as a black mana symbol regardless of which half you actually pay [Drought ruling #2]. Beckon Apparition's cost contains one such symbol, so Drought adds one additional cost of "Sacrifice a Swamp."

Two practical notes:

- It doesn't matter that Ava pays the {W/B} with white mana; the symbol is still black for Drought's purposes [107.4e][Drought ruling #2].
- Drought's second ability says "Spells cost an additional..." without limiting it to its controller, so it applies to Ava's spells even though Nico controls Drought. If Ava controls no Swamp, she can't pay the additional cost and therefore can't cast Beckon Apparition at all.

The total cost is thus {W/B} (payable with one white or one black mana) plus sacrificing one Swamp. This is the same whether the game is two-player or multiplayer — Drought's wording doesn't single out any particular player, so every player's black-symbol spells are taxed identically.

Card data from Scryfall (scryfall.com).

### CELL c0112

**Question**
Nathanael controls [Grizzly Bears] and [Muraganda Petroglyphs]. They cast and resolve [Crowd's Favor], targeting Grizzly Bears. Amia then casts [Archetype of Courage]. After it resolves, what are the power and toughness of Grizzly Bears?

**REFERENCE (correct)**
5/4. In layer 6, Archetype of Courage makes Crowd's Favor unable to grant first strike to Grizzly Bears. Archetype of Courage isn't granting any abilities to Grizzly Bears itself, so in layer 7 Grizzly Bears has no abilities and gets +2/+2 from Muraganda Petroglyphs and +1/+0 from Crowd's Favor.

**CANDIDATE**
Grizzly Bears ends up 5/4.

Why: the layer system (CR 613.1) is applied continuously and automatically, and all its results are instantaneous (CR 613.5), so you re-evaluate after Archetype of Courage resolves.

- Layer 6 (abilities): Crowd's Favor granted Grizzly Bears first strike. Archetype of Courage, controlled by Amia (Nathanael's opponent), has a later timestamp and says creatures your opponents control lose first strike and can't have or gain first strike (CR 613.7). So Grizzly Bears loses first strike and now has no abilities at all.
- Layer 7c (modifications, CR 613.4c): Muraganda Petroglyphs checks the state after layer 6. Grizzly Bears now has no abilities, so it gets +2/+2 — 4/4. Note that a granted ability is a real ability for this check, while a mere quality or characteristic-setting effect is not (CR 113.12); once the granted first strike is stripped, Grizzly Bears qualifies again.
- Also in layer 7c: Crowd's Favor's +1/+0 keeps applying — its power/toughness effect doesn't go away just because the granted ability was removed. Base 2/2 → +2/+2 → +1/+0 = 5/4.

So Grizzly Bears is a 5/4 with no first strike (and it can't gain first strike while Archetype of Courage is on the battlefield).

Timing assumption: Crowd's Favor fully resolved before Archetype of Courage was cast, as stated. Had Archetype of Courage been on the battlefield first, Grizzly Bears would never have gained first strike at all, and the result would be the same 5/4.

Player count: this works identically in a two-player game or a multiplayer game — Archetype of Courage affects creatures controlled by each of its controller's opponents, so any number of opponents' creatures are stripped of first strike the same way.

Card data from Scryfall (scryfall.com).

### CELL c0113

**Question**
Alex controls a [Life and Limb], a [Blood Moon], and a 1/1 Green Saproling Creature token, that entered the battlefield in that order. What is the Saproling?

**REFERENCE (correct)**
It's a 1/1 green Land Creature - Mountain Saproling with "{T}: Add {R}.". Applying Life and Limb's effect would allow Blood Moon's effect to apply to the Saproling and applying Blood Moon's effect first would not affect how Life and Limb's effect is applied or what it does, so Blood Moon's effect is dependent on Life and Limb's effect and waits to apply until afterwards. Since Life and Limb's effect makes the Saproling a nonbasic land, Blood Moon then applies and turns it into a Mountain with "{T}: Add {R}." and no other abilities.

**CANDIDATE**
Alex's Saproling token is a 1/1 green Saproling Mountain — a creature land — with the mana ability "{T}: Add {R}," and it's subject to summoning sickness.

How it gets there, by layer and timestamp:

1. The token starts as a 1/1 green Saproling creature token, with no other characteristics (rule 111.3).
2. Life and Limb ("All Forests and all Saprolings are 1/1 green Saproling creatures and Forest lands in addition to their other types") applies in layer 4 for types/subtypes, layer 5 for color, and layer 7b for the 1/1. Because it says "in addition to their other types," the token keeps creature and gains the land card type, and gains the Forest land subtype alongside its Saproling creature subtype (rule 205.1b; Life and Limb ruling #3 — Forest stays a land type, Saproling stays a creature type). Life and Limb ruling #1 confirms Saprolings are on the battlefield as land creatures.
3. Blood Moon ("Nonbasic lands are Mountains") also applies in layer 4, with a later timestamp than Life and Limb (rule 613.6 — each part of an effect applies in its own layer, and within layer 4 timestamps decide). The token is now a land and is not basic, so Blood Moon applies to it: setting a land's subtype to a basic land type removes its old land types and the abilities from its rules text, and grants the new type's mana ability (rule 305.7; Blood Moon ruling #2). So the Forest subtype and "{T}: Add {G}" go away and it becomes a Mountain with "{T}: Add {R}."
4. Setting the land subtype does not add or remove card types or creature types (rule 305.7), so it is still a Saproling creature, and it is still a land. Life and Limb's color and power/toughness parts (layers 5 and 7b) continue to apply to it — note that Life and Limb also applies to it as a Saproling, not just as a Forest, so nothing about Blood Moon shuts Life and Limb off (rule 613.6).

Final state: a green 1/1 Saproling Mountain creature land token with "{T}: Add {R}", affected by summoning sickness (so it can't tap for that mana until Alex has controlled it since their most recent turn began).

Order assumption: I'm assuming the timestamps are as stated — Life and Limb, then Blood Moon, then the token. If Blood Moon had the earlier timestamp than Life and Limb, the result would be the same for this token anyway, because Blood Moon can only ever apply to it after Life and Limb has made it a land (a dependency), so Blood Moon's Mountain-setting still ends up applied last.

This analysis doesn't depend on player count; it's identical in a two-player or multiplayer game.

Card data from Scryfall (scryfall.com).

### CELL c0114

**Question**
Apollo controls [Realmwright] naming "Island", [Arcane Adaptation] naming "Saproling", and [Life and Limb], which entered the battlefield in that order. What are the types and subtypes of Realmwright?

**REFERENCE (correct)**
Realmwright is a 1/1 green Land Creature - Vedalken Wizard Saproling Forest.

All three cards have effects in layer 4, the type changing layer. The game first looks at Realmwright's effect since it's first in timestamp order, sees that it's not dependent on Arcane Adaptation nor on Life and Limb, and applies it. Next the game looks at Arcane Adaptation's effect, sees that it's not dependent on Life and Limb, and applies it, followed by Life and Limb last.

Life and Limb lets it keep its original creature types, but not its original colors.

**CANDIDATE**
Realmwright ends up as a **Land Creature — Vedalken Wizard Saproling Forest Island**, a 1/1 that's both blue and green.

How it gets there (all in layer 4, type-changing effects, CR 613.1d):

1. **Arcane Adaptation** (naming Saproling) makes Realmwright a Saproling in addition to its other types — it's now a Vedalken Wizard Saproling (CR 205.1b).
2. **Life and Limb** then applies, because Realmwright is now a Saproling: it becomes a 1/1 green Saproling creature and a Forest land in addition to its other types. This is a dependency, not just timestamps — applying Arcane Adaptation changes what Life and Limb applies to, so Life and Limb is applied after it (CR 613.8, 613.8a). Realmwright now has card types Creature and Land, with Forest correlated to Land and Saproling/Vedalken/Wizard correlated to Creature (CR 205.3c, Life and Limb ruling #3).
3. **Realmwright's own** "Lands you control are the chosen type in addition to their other types" now applies, even though Realmwright entered first: Life and Limb changing Realmwright into a land changes what Realmwright's effect applies to, so Realmwright's effect depends on Life and Limb and is applied last (CR 613.8, 613.8a). It gains the land type Island as well.

Other consequences: because it gained the land types Forest and Island in addition to its own types, it keeps its rules text and gains the mana abilities of both — "{T}: Add {G}" and "{T}: Add {U}" (CR 305.7). Its color is blue (printed) plus green from Life and Limb's layer‑5 effect, and Life and Limb sets its power/toughness to 1/1 in layer 7b. It has no supertypes; nothing here grants or removes any (CR 205.4b). Being a land creature, it's subject to summoning sickness for tapping.

Note the order they entered doesn't ultimately matter here, since dependency overrides timestamps (CR 613.7, 613.8). This analysis is about Apollo's own permanents only, so it reads the same in a two-player or multiplayer game — each "you control" effect only affects Apollo's permanents.

Card data from Scryfall (scryfall.com).

