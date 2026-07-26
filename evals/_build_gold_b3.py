import json

ROWS = [
 ("rg899",
  [["702.89a"],["704.5g"],["616.1g"],["700.4","701.8a"]],
  "Anger's damage kills via the lethal-damage state-based action (704.5g), which is a destruction; umbra armor (702.89a) replaces that destruction, and because dying (700.4/701.8a: destroy = move to graveyard) is an event contained inside being destroyed, 616.1g forces the destruction-replacement to be chosen first, so the exile-instead replacement never gets an event.",
  "medium"),
 ("rg713",
  [["118.12"],["118.11","701.9c"]],
  "118.12 makes 'discard a card. If you do' a cost paid on resolution, and 118.11 says a cost whose actions are modified by another effect is still paid (701.9c likewise treats a discard redirected to a hidden zone as a discard that can pay a cost). Both halves are needed: the cost framing plus the rule that Library of Leng's redirection doesn't undo payment.",
  "medium"),
 ("rg608",
  [["603.10","603.10a"],["603.6c"],["113.6"]],
  "Triggers are checked against objects as they exist immediately after the event (603.10) unless they're one of the look-back exceptions in 603.10a; 603.6c states a 'from anywhere' trigger is never a leaves-the-battlefield ability, so Compost gets no look-back, and 113.6 says its ability doesn't function once it's in the graveyard.",
  "medium"),
 ("rg306",
  ["118.12a"],
  "118.12a converts 'you may draw a card unless that player pays {1}' into 'that player may pay {1}; if they don't, you may draw', which directly establishes that the paying player chooses first.",
  "high"),
 ("rg272",
  ["500.8","609.3"],
  "500.8 says added phases go directly after the specified phase, so with no main phase in progress there is nothing to add them after; 609.3's do-as-much-as-possible rule reaches the same result. Either chunk supports the answer, but neither states the empty case outright, so confidence is low.",
  "low"),
 ("rg559",
  ["723.4"],
  "723.4 is the only rule governing what a player controlling another player can see: only information that would currently be visible to the controlled player. A choice already made secretly isn't such information, so Albert can't see it.",
  "medium"),
 ("rg1095",
  [["614.12","614.12a","614.13a"],["614.16","616.1"]],
  "The as-enters replacement's choice is made before the permanent enters and the bounce it causes happens as part of that same entry event (614.12/614.12a/614.13a), so Primal Vigor is still on the battlefield; 614.16/616.1 then make Primal Vigor's counter-doubling apply to the counter placed by the Sphinx's own replacement effect.",
  "medium"),
 ("rg4256",
  [["701.15b"],["701.15a","702.26d","702.26f"]],
  "701.15b states the goad requirement (attack each combat, attack a player other than the goader if able); 701.15a fixes the duration as 'until the goading player's next turn', and 702.26d/702.26f establish that phasing neither changes zones nor ends a duration-based continuous effect, so goad is still in force when it phases in.",
  "medium"),
 ("rg247",
  ["106.7"],
  "106.7 defines 'could produce' and explicitly ends with 'If that permanent wouldn't produce any mana under these conditions... there's no type of mana it could produce' — Gaea's Cradle with no creatures, so Sylvok Explorer produces nothing.",
  "high"),
 ("rg1355",
  ["118.12a","113.6"],
  "118.12a rewrites 'discard a card unless you sacrifice a permanent' as 'you may sacrifice a permanent; if you don't, discard a card', putting the sacrifice first; 113.6 supplies the other half, that All-Seeing Arbiter's ability no longer functions once it has left the battlefield.",
  "medium"),
 ("rg3947",
  ["608.2b"],
  "608.2b is the whole answer: target legality is checked first on resolution, and a spell whose every target is illegal doesn't resolve at all, so neither the normal effect nor the threshold self-replacement happens.",
  "high"),
 ("rg1953",
  ["601.2f","602.2b"],
  "601.2f states that when multiple cost reductions apply the player may apply them in any order, which is what produces the {1}-or-{0} choice; 602.2b is required to know 601.2f governs an activated ability's activation cost.",
  "high"),
 ("rg549",
  ["106.7"],
  "106.7 defines 'could produce' as any type of mana an ability of that permanent would produce if it resolved at that time, ignoring whether costs could be paid — which covers Crumbling Vestige's triggered mana ability adding any color.",
  "high"),
 ("rg1718",
  [["727.1a"],["103.8a"],["614.10a","500.11"]],
  "727.1a makes Karn's controller the starting player of the new game, 103.8a makes that player skip their first draw step in a two-player game, and 614.10a/500.11 state that anything scheduled for a skipped step (Anvil's draw-step trigger) simply doesn't happen.",
  "high"),
 ("rg204",
  ["107.4e"],
  "107.4e states a hybrid mana symbol is a colored mana symbol and is all of its component colors, so {W/B} counts as one black mana symbol for Drought's additional cost.",
  "high"),
 ("rg1124",
  ["614.17b","614.17c"],
  "614.17b says a player can't choose to pay a cost that includes an event that can't happen (Solemnity stops the -1/-1 counter), and 614.17c says an event that can't happen can only be replaced by a self-replacement effect, which is why Vizier of Remedies can't rescue it.",
  "high"),
 ("rg528",
  ["616.1g"],
  "616.1g is exactly this case: entering the battlefield is an event contained within creating the token, so the token-doubling effect must be applied before any of the entering-the-battlefield replacements (its example uses Doubling Season plus an as-enters choice).",
  "high"),
 ("rg725",
  [["800.4g"],["603.3a","113.8"]],
  "800.4g states that when an object requires a departed player to make a choice other than paying a cost, the object's controller picks another player to make it; 603.3a/113.8 establish that Bailey, who controlled Pandemonium when it triggered, controls the ability and therefore makes that pick.",
  "high"),
 ("rg129",
  ["613.8a","613.8b"],
  "613.8a defines dependency (Life and Limb's effect changes what Blood Moon's effect applies to, but not vice versa) and 613.8b says the dependent effect waits until afterward, overriding timestamps. Both halves are needed to get the Mountain Saproling.",
  "high"),
 ("rg517",
  [["605.5a","605.1a"],["106.12","106.12b"]],
  "605.1a/605.5a establish that a targeted ability is not a mana ability, and 106.12/106.12b define 'tap for mana' as activating a mana ability with {T} — which is the condition Mana Reflection's replacement requires and Deathrite Shaman's ability fails.",
  "high"),
 ("rg5193",
  ["509.1c"],
  "509.1c is the blocking-requirement rule: the defending player must obey the maximum possible number of requirements without violating restrictions, so with one legal blocker Nico satisfies exactly one of the two 'block that creature' requirements and may choose which.",
  "high"),
 ("rg6556",
  [["727.2"],["702.139a","103.2b","727.1"]],
  "727.2 puts every card involved in the ended game (including the wished-for card) into the new game, so Goremonger is shuffled into the library; 702.139a/103.2b (and 727.1, which sends the restart through rule 103) require the companion condition to be met by the new starting deck, which it now isn't.",
  "medium"),
 ("rg851",
  [["303.4d"],["303.4g","303.4i","608.3e"]],
  "With Mycosynth Lattice plus March of the Machines the resolving Aura would be a creature, and 303.4d states an Aura that's also a creature can't enchant anything; 303.4g/303.4i (and 608.3e for the general case) then send it from the stack straight to its owner's graveyard instead of entering.",
  "medium"),
 ("rg807",
  [["613.6"],["613.7","613.7a","613.7b"],["613.1e","613.1f","613.1g"]],
  "613.6 is load-bearing: the threshold effect starts applying in layer 5 and keeps applying in layers 6 and 7 even though the ability generating it is removed. The layer assignments (613.1e-g) and timestamp order (613.7/613.7a/613.7b) are needed to see that Turn to Frog's later color change and ability removal win.",
  "medium"),
 ("rg475",
  ["729.2"],
  "729.2 says that as a subgame starts the players 'randomly determine which player goes first', so no player chooses to play second.",
  "high"),
 ("rg1454",
  ["404.3"],
  "404.3 states that when an effect or rule puts two or more cards into the same graveyard at once, their owner may arrange them in any order.",
  "high"),
 ("rg470",
  ["727.1","800.1","103.8a"],
  "727.1 restarts with only the players still in the game (two), 800.1 defines a multiplayer game as one that begins with more than two players so the new game isn't one, and 103.8a then makes the starting player skip their first draw step.",
  "medium"),
 ("rg282",
  ["514.2","704.5f","514.3a","603.7b"],
  "514.2 ends the +4/+4 in cleanup while leaving the -1/-1 counter, 704.5f puts the now-0-toughness Memnite into the graveyard, 514.3a is what lets state-based actions and waiting triggers happen during the cleanup step, and 603.7b is the delayed trigger firing the next time its event occurs.",
  "medium"),
 ("rg466",
  [["800.1"],["103.8c","800.7"]],
  "800.1 fixes multiplayer status at the game's start (more than two players), regardless of eliminations, and 103.8c/800.7 state that in multiplayer games other than Two-Headed Giant no player skips their first draw step.",
  "high"),
 ("rg289",
  [["602.1a"],["601.2f","602.2b"]],
  "602.1a defines the activation cost as everything before the colon ({X}, {T}), and 601.2f (via 602.2b) shows Suppression Field's {2} is a separate cost increase folded into the total cost, not into the activation cost Ice Cauldron notes.",
  "medium"),
 ("rg338",
  ["701.23f"],
  "701.23f states that when searching a zone is replaced with searching a portion of it, any other instructions referring to searching that zone still apply — so Panglacial Wurm's 'while you're searching your library' is satisfied.",
  "high"),
 ("rg811",
  ["613.7f","613.6","613.7"],
  "613.7f gives the permanent a new timestamp when it turns face up, putting Wayward Angel's ability after Turn to Frog; 613.7 supplies earlier-timestamp-first ordering, and 613.6 keeps the threshold effect applying in layers 6 and 7 even after Turn to Frog removes the ability in layer 6.",
  "medium"),
 ("rg60",
  [["702.26k","702.26b"],["800.4a"]],
  "800.4a removes every object Bobbie owns from the game, and 702.26k states outright that phased-out permanents owned by a departing player leave the game without causing zone-change abilities to trigger (702.26b's 'treated as though it does not exist' is the general form), so the exile effect's return condition never fires.",
  "medium"),
 ("rg1208",
  [["702.5a"],["303.4c","704.5m"]],
  "702.5a states that the enchant ability is what restricts what an Aura can enchant; once Opportunistic Dragon strips Favorable Destiny's abilities, 303.4c/704.5m (Aura attached to an illegal object as defined by its enchant ability) has no restriction to violate, so it stays attached.",
  "medium"),
 ("rg5768",
  [["603.2d"],["603.4"],["701.3b","609.3"]],
  "603.2d handles an effect making a triggered ability trigger an additional time (Panharmonicon sees the Aura as an artifact entering), 603.4 has each copy recheck the intervening 'if it's on the battlefield' on resolution, and 701.3b/609.3 make the second resolution a no-op since the Aura is already attached and the creature card has left the graveyard.",
  "low"),
 ("rg100",
  ["609.7a"],
  "609.7a states that if a permanent spell is chosen as the damage source, the effect applies to damage dealt by that spell and by the permanent it becomes — so Hallow's prevention still covers Keldon Champion's combat damage.",
  "high"),
 ("rg5863",
  [["702.62a","116.2f"],["608.2g"]],
  "702.62a/116.2f condition the suspend special action on being able to begin casting the card from hand, and 608.2g is what makes that true mid-resolution: Wildfire Eternal's ability specifically allows casting an instant or sorcery from hand during its resolution.",
  "medium"),
 ("rg6530",
  ["608.2i","508.6","508.1a"],
  "No rule counts creatures attacked with directly; 608.2i's look-back example is literally 'for each creature you attacked with this turn', and 508.1a/508.6 define attacking as declaring creatures as attackers — one creature declared twice is still one creature. Low confidence on the exact chunk.",
  "low"),
 ("rg1933",
  [["730.2i"],["702.140e","730.2a"],["303.4d","701.3b"],["704.5m"]],
  "730.2i transforms every double-faced component of the merged permanent; 702.140e/730.2a keep it a creature with the topmost card's characteristics plus all components' abilities; 303.4d/701.3b stop the attach because a creature can't enchant anything; and 704.5m is the state-based action that checks for the Aura subtype, which the merged permanent doesn't have, so it stays.",
  "medium"),
 ("rg659",
  ["107.3h","107.3g"],
  "107.3h fixes X at 0 when an effect tells a player to pay a mana cost of an object that isn't a spell on the stack, so only {0} can be paid; 107.3g fixes X at 0 for the card in exile, so the token copy enters with zero +1/+1 counters.",
  "medium"),
 ("rg72",
  [["616.1b"],["616.1","616.1c","614.12a"]],
  "616.1b forces the control-changing enters-the-battlefield replacement (Gather Specimens) to be chosen before any other, and 616.1/616.1c/614.12a then have the copy choice made afterward by the object's new controller, Nadia.",
  "medium"),
 ("rg5539",
  [["508.1c"],["508.1k","508.1a"]],
  "508.1c checks restrictions (Rhonas's 'can't attack unless') during the declaration, while 508.1k shows the chosen creatures don't become attacking creatures until after those checks (508.1a: all attackers chosen at once), so Gaea's Liege still has its non-attacking power at that moment.",
  "high"),
 ("rg279",
  ["702.90c","514.2","704.5f","514.3a"],
  "702.90c turns Baron Sengir's infect damage into -1/-1 counters that don't wear off, 514.2 ends the +5/+5 in cleanup, 704.5f then puts the 0-or-less-toughness Crocodile into the graveyard, and 514.3a is what allows those state-based actions and the resulting trigger during the cleanup step.",
  "medium"),
 ("rg5876",
  ["115.9c"],
  "115.9c is exactly on point: a 'targets only [something]' check counts the number of different objects or players chosen as targets, and one object targeted multiple times still counts as one.",
  "high"),
 ("rg1014",
  ["406.3a","614.4"],
  "406.3a states a card exiled face down has no characteristics, so Progenitus has no replacement ability there; 614.4 supplies the rest, that a replacement effect must exist before the event to affect it.",
  "high"),
 ("rg5785",
  [["508.1c"],["508.1k","508.1a"]],
  "508.1c checks Reverence's restriction during the declaration of attackers, and 508.1k/508.1a establish that the creature doesn't become an attacking creature until after that check, so Gaea's Liege is still power 3 (Aurora's Forests) when the restriction is evaluated.",
  "high"),
 ("rg238",
  [["508.1f"],["508.1g","508.1h","508.1i","508.1j"]],
  "508.1f taps the chosen attackers and states that tapping isn't a cost, and it comes before the cost steps 508.1g-j where Norn's Annex's 2 life is paid — so Vodalian Soldiers is already tapped by the time fateful hour would grant vigilance.",
  "high"),
 ("rg1555",
  [["614.12a","614.12"],["614.13a"]],
  "614.12/614.12a have the as-enters choices made before The Mimeoplasm enters (so Phyrexian Hulk is still in the graveyard), while 614.13a forbids choosing an object that's entering the battlefield at the same time.",
  "high"),
 ("rg842",
  [["500.7"],["614.10b","614.10"]],
  "500.7 adds the two extra turns directly after the current one, and 614.10/614.10b handle the skip: skipping is a replacement effect, and the accompanying action (untapping Time Vault) happens as the first thing in the next turn that actually occurs, which is why it can be tapped again in time to skip the second extra turn.",
  "medium"),
 ("rg625",
  [["702.16h","702.16g"],["702.16b"]],
  "702.16h (with 702.16g) states that 'protection from each [characteristic]' is shorthand for separate protection abilities, so losing protection from black leaves the others intact; 702.16b supplies the fact that protection is what was blocking targeting.",
  "high"),
]

out = []
for rid, spec, rat, conf in ROWS:
    rec = {"id": rid}
    if spec and isinstance(spec[0], list):
        flat = []
        for g in spec:
            for x in g:
                if x not in flat:
                    flat.append(x)
        if all(len(g) == 1 for g in spec):
            rec["gold"] = flat
            rec["match"] = "all"
        else:
            rec["gold"] = flat
            rec["match"] = "groups"
            rec["gold_groups"] = spec
    else:
        rec["gold"] = list(spec)
        rec["match"] = "all" if len(spec) > 1 else "any"
    rec["rationale"] = rat
    rec["confidence"] = conf
    rec["proposed_by"] = "claude-opus-5 (subscription subagent)"
    rec["batch"] = "rulesguru150-b3"
    out.append(rec)

# order check against input
ids_in = [json.loads(l)["id"] for l in open("evals/_mine_batch3.jsonl", encoding="utf-8") if l.strip()]
assert [r["id"] for r in out] == ids_in, (len(out), len(ids_in))

inv = {x.strip() for x in open("evals/_chunk_inventory.txt", encoding="utf-8") if x.strip()}
bad = []
for r in out:
    for x in r["gold"]:
        if x not in inv:
            bad.append((r["id"], x))
    if r["match"] == "groups":
        flat = [x for g in r["gold_groups"] for x in g]
        assert sorted(set(flat)) == sorted(set(r["gold"])), r["id"]
    else:
        assert "gold_groups" not in r
assert not bad, bad

with open("evals/gold_proposals_batch3.jsonl", "w", encoding="utf-8") as f:
    for r in out:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

from collections import Counter
print("ROWS", len(out))
print("match", Counter(r["match"] for r in out))
print("conf", Counter(r["confidence"] for r in out))
n = sum(len(r["gold"]) for r in out)
print("gold ids total", n, "mean", round(n / len(out), 2))
