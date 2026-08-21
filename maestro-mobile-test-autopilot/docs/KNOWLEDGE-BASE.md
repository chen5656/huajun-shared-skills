# The knowledge base

This is the part that makes the loop improve rather than repeat.

## Why it lives in the target repo

Because it is the only place product knowledge is allowed. Keeping it out of the engine
is what lets the engine be public while your screen map, data model, and billing
behaviour stay private.

## `LESSONS.md`

One entry per durable fact learned from a real run. Loaded into the agent's context
before every run via `autopilot.py context`.

```
## [kb-014] Container label collapses subtree

- **Scope:** platform
- **Learned:** 2026-08-21
- **Symptom:** assertVisible fails on text that is plainly on screen
- **Cause:** an explicit accessibilityLabel on a pressable removes child text from the tree
- **Rule:** put a testID on the inner text node and select {id, text}
```

**Scope** decides where a lesson belongs long-term:

- `platform` — true of Maestro/iOS/Android themselves. Candidates for upstreaming into
  the engine's SKILL.md.
- `product` — true of this app only. Stays here forever.
- `env` — true of this machine or account. The most perishable; re-verify these.

### The two rules that keep it useful

**Durable facts only.** "X was renamed to Y on 2026-08-10" is worthless in a month.
"An accessibility label on a container collapses its subtree" is true forever. When the
product changes, **edit the entry in place** — do not append a correction.

**Duplicate ids are refused.** A knowledge base full of near-duplicates stops being
read, which is exactly as useful as not having one.

## `BUGS.md`

Product bugs found by tests. Written by the agent, fixed by a human. This is the
checkpoint that keeps an overnight agent from quietly rewriting your product.

## `TRIAGE.json`

Project-specific failure patterns, merged ahead of the built-in rules:

```json
{ "rules": [
  { "id": "quota-exhausted", "klass": "environment",
    "pattern": "Monthly token limit reached",
    "explain": "The test account's paid quota is spent.",
    "fix": "Not a bug and not fixable in YAML. Budget reruns.",
    "needs_screenshot": true }
] }
```

`needs_screenshot: true` marks a class the log cannot prove. The classifier then reports
it as *unconfident* rather than asserting it — the honest answer when a quota dialog and
an ordinary assertion timeout produce the same log line.
