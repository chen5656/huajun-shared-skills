# Huajun's Shared Agent Skills

Agent skills I actually use in day-to-day product development with Claude Code, Codex, and Gemini CLI.

These are not demos. Each one is extracted from a working setup, and each skill folder has its own
README explaining the tradeoffs that survived contact with real use — including what I got wrong the
first time.

**Pick the ones you need.** They are independent; there is nothing to install as a set.

---

## The skills

### [bug-finder](bug-finder/) — adversarial bug review

A hunter scans the repo and scores its findings; a **different model**, paid points for every finding
it disproves and penalized double for wrongly dismissing a real one, attacks the list; a
**context-isolated referee** rules on both.

**Why this and not a "find bugs" prompt.** Ordinary bug prompts return long, confident lists padded
with false positives, and the padding is what kills adoption. This one doesn't ask the model to be
rigorous — it makes padding cost something. What survives has been through real opposition.

**Choose it when** you want a list short enough to actually read. **Skip it if** you want fixes, not a
report, or if you can't run a second model CLI.

→ [Full details](bug-finder/README.md)

---

### [working-backwards-amazon](working-backwards-amazon/) — feature discovery before code

Amazon-style Working Backwards: inspects your repo first, interviews you in rounds, then writes a
5-minute **press release** for the human deciding, plus an implementation-complete **build spec** for
the agent building it.

**Why this and not a generic "write a PRD" skill.** Two documents, not one, because they have
different readers and merging them makes both worse. And it ships an explicit **applicability gate** —
the excluded cases are named in the skill body, so it doesn't fire on a ten-line bug fix. Most PRD
skills over-trigger, get annoying, and get disabled.

**Choose it when** the feature's behavior and tradeoffs are genuinely unsettled. **Skip it for**
routine tasks, bug fixes, and visual tweaks — it will refuse anyway.

→ [Full details](working-backwards-amazon/README.md)

---

### [i18n-translate](i18n-translate/) — Lingui catalogs, on a cheap model

Extract missing entries into ~50-entry batches, translate, audit for UI overflow, apply, compile,
verify 0 missing per locale.

**Why this and not asking your agent to translate the `.po` files.** Two reasons. A hard **stop rule**
forces the job onto a cheap worker model — an orchestrating agent reading the skill is told it may not
do the work itself, because capable agents helpfully do cheap work and the saving evaporates silently.
And a **deterministic Python helper** owns everything where being wrong is expensive: batching,
placeholder and plural safety, whitespace, and the overflow audit that catches a French or Spanish string
too long for its button.

**Choose it when** you ship multi-locale Lingui releases regularly. **Skip it if** you're not on
Lingui — the helper is `.po`-specific.

→ [Full details](i18n-translate/README.md)

---

### maestro-autopilot — unattended mobile black-box testing

Runs [Maestro](https://maestro.mobile.dev) flows unattended and still produces a result you can trust:
pins the device, mandatory preflight, four-class failure triage, repairs only inside a declared
boundary, learns durable lessons, proposes changes via PR. Ships zero knowledge of any app — your
screen map stays in your own repo.

*Maintained as a separate repository, not vendored here.*

---

## What these have in common

None of these is mainly a prompt. Each exists because a capable model, left to its own judgment,
reliably does the wrong thing in a specific way — and the fix was structural, not better wording:

| Skill | Failure mode it corrects | Mechanism |
| :--- | :--- | :--- |
| bug-finder | Models confirm their own reasoning | **Opposition** — a rival model paid to disprove the findings |
| working-backwards-amazon | Skills over-trigger and get disabled | **Boundaries** — an explicit gate naming when *not* to fire |
| i18n-translate | The expensive model helpfully does cheap work | **Routing** — a hard stop rule that forces the job onto a cheaper model |
| maestro-autopilot | Unattended runs report confidently and wrongly | **Proof** — device pinning, preflight gates, evidence-backed triage |

The recurring lesson: designing an agent skill is mostly about constraints and division of labor, not
wording.

---

## Install

Each skill is a self-contained folder. Copy the ones you want into your agent's skills directory —
`~/.claude/skills/` for user-wide, `.claude/skills/` in a project, or `.agents/skills/` for other
agents. The agent loads a skill when its `description` matches your task; you can also invoke it by
name.

```bash
git clone https://github.com/chen5656/huajun-shared-skills.git
cp -R huajun-shared-skills/bug-finder ~/.claude/skills/
```

Copy the **whole folder**, not just `SKILL.md` — `i18n-translate` needs its Python helper and
`working-backwards-amazon` needs its `references/` templates.

Two skills expect other CLIs on your PATH: `bug-finder` shells out to `codex` (and optionally
`claude`), and `i18n-translate` launches a worker via whichever agent CLI you point it at. Both
degrade or are configurable — see each skill's README.

## License

MIT. Use them, fork them, change them.
