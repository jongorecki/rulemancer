# Decisions

Every non-obvious choice, logged as it's made. 5-10 lines each: what,
alternatives rejected, why, what would change your mind. This is interview
prep — write it in the moment, not reconstructed later.

Template:

```
## YYYY-MM-DD — <short title>

**What:** <the choice>
**Alternatives considered:** <what else was on the table>
**Why:** <the reasoning>
**What would change my mind:** <the condition that would flip this later>
```

---

## 2026-07-21 — Project scaffold, no OpenCode yet

**What:** Starting the build with Claude Code only. Repo skeleton matches the
build plan's target layout, in this existing `mtg-rules-bot` folder rather
than a newly-created `mtg-rules-agent` one.
**Alternatives considered:** Setting up OpenCode + OpenRouter first, per the
original plan's "install OpenCode, configure both keys" step.
**Why:** Jon wants to defer OpenRouter/model-rotation setup until later and
start writing code now. Model rotation for review is a stretch goal, not a
day-1 blocker.
**What would change my mind:** Once OpenCode/OpenRouter is set up, revisit the
"whoever writes doesn't review" rule — Claude Code has been both author and
only reviewer so far, which the plan explicitly warns against.
