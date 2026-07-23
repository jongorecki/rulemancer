# Grading-feedback backlog (harvested from verdict note fields)

Auto-harvested from evals/verdicts_*.json + Downloads/answer_verdicts*.json. These are Jon's grading notes that are about IMPROVING THE SYSTEM, not verdict rationale. Re-run the harvester after each grading export (the v3ab pass is not yet exported as of 2026-07-23).


## Display: rule/ruling TEXT not shown in grading UI (citations/IDs present) (13)

- **c008**: missing scryfall rulings text
- **c018**: missing scryfall rulings text, but answer is correct
- **c003**: missing scryfall rulings text but correct answer
- **c011**: missing rulings and CR rules text, but multiple citations come up in the "cited by the answer" section, including the gold rule
- **c015**: missing scryfall rulings text
- **c018**: this ruling contradicts itself but makes the right assertion. "This choice is made when Clone is on the stack" is wrong but it states in other places that the choice of what it copies is made as it enters. also missing scryfall rulings text.
- **c002**: missing scryfall rulings text but correct answer
- **c009**: missing scryfall rulings text, no CR rulings, but correct decision
- **q001**: missing CR text, but citations are there. This is something we really need to look at. it happens a lot from both scryfall and occasionally the CR. could this be related to token limits? with some of these bots the tokens are so cheap that it won't really matter at any meaningful scale.
- **q011**: CR text missing but citations are there. there is no ruling saying that you can have negative counters on any entity, so you can't have negative counters on any entity. these are not to be confused with -1/-1 counters.
- **q014**: [802.2] is important here as well. most of this answer is correct except this:

Who is the defending player at the beginning of combat (multiplayer): as the beginning of combat step starts, the active player chooses one of their opponents to be the defending player unless the multiplayer variant/opt
- **q031**: missing text from CR but citations are present. also noticed double brackets here for some reason.
- **c011**: missing scryfall ruling text

## Data / formatting bugs (double brackets, blanks, truncation, wrong card) (1)

- **q031**: missing text from CR but citations are present. also noticed double brackets here for some reason.

## Retrieval / gold gaps (a rule that should be surfaced isn't) (4)

- **q016**: Answer is knowable and is 'no': paying a cost is part of casting/activating, so no one has priority then and it can't be responded to. Bot declines because 117.3c/601.2h rank 189/109 -- not retrieved. Fix = query rewriting (#3).
- **q014**: most is correct, but this part is not, and the rule it cites does not support it:

 In other multiplayer variants, the active player may choose a defending player as a turn-based action at the start of the beginning of combat step [507.1], and that player (along with any other defending players dict
- **q014**: 802.2 is a great rule to surface and probably needs to be added to all of the multiplayer combat gold rules.
- **q014**: [802.2] is important here as well. most of this answer is correct except this:

Who is the defending player at the beginning of combat (multiplayer): as the beginning of combat step starts, the active player chooses one of their opponents to be the defending player unless the multiplayer variant/opt

## Feature: clarify-then-escalate signals (4)

- **q026**: mana abilities are not spells, they're abilities. this is just a weird way to word this. other than that, its correct. the question asks who gets priority after the the spell is cast, which would be whoever cast the spell, which this does say. the clarification at the end (therefore, the answer is:)
- **c004**: correct but we're assuming timing here that could be incorrect. if the damage was marked on it AFTER the lightning bolt was cast targeting Grizzly Bears, lightning bolt could still be on the stack but no longer have a valid target. this ruling is assuming that its happening before the cast of the sp
- **q016**: it got close. does it make sense for us to both be able to ask clarifying questions from the user, and to ask one round of clarifying questions of the rules, or something to that effect? I know that's an extra round trip and an extra query, but if it would solve our issue, it might be fine.
- **q026**: This is hands down the best answer out of the last few. its very clear on both answering the question as well as the somewhat related question of "who gets priority after the spell resolves" which has a different answer than "who gets priority after the spell is cast" but both questions could be inf
