# bug-finder

Adversarial three-agent bug review. A hunter finds bugs, a second model *paid to disprove them*
attacks the list, and an isolated referee rules on both.

**Output:** `bug-reports/01-bug-hunter.md`, `02-adversarial.md`, `03-referee.md`

---

## The problem it solves

Ask an agent to "find bugs in this codebase" and you get a long, confident list padded with false
positives. The list is worse than useless: someone has to read all of it to find the two real bugs,
and after one bad experience nobody runs it again.

The usual fix is to add "be rigorous, avoid false positives" to the prompt. That does very little.
This skill fixes it structurally instead — with **incentives and adversaries**, not adjectives.

## How it works

Three agents run in sequence, each writing a Markdown file to `bug-reports/`.

**1. Bug Hunter** scans the codebase and scores itself: `+1` low impact, `+5` some impact, `+10`
critical. It is told upfront that another agent will try to tear the list apart, so padding costs it
credibility.

**2. Adversarial reviewer** — run in a **different model** via Codex CLI — is paid to destroy the
hunter's work. It earns the bug's full point value for every finding it disproves, and **loses double**
for every real bug it wrongly dismisses. That asymmetry is the whole design: it only attacks findings
it is genuinely confident about, so surviving bugs have been through real opposition.

**3. Referee** starts in a **fresh session with zero context** from the first two — ideally a
separately spawned CLI process — reads both reports, independently verifies against the source, and
issues the final verdict plus a clean ranked list of confirmed bugs.

## Design notes

**Why a different model for the adversary.** Same-model self-review is weak: a model asked to check
its own reasoning tends to re-derive the same reasoning and approve it. Running the adversary through
Codex CLI means the challenge comes from a system with different training and different blind spots.
Independence is doing more work here than raw capability. It degrades gracefully — if `codex` isn't
installed, the step falls back to an isolated Task subagent.

**Why the referee must be context-isolated.** If the judge has watched the argument, it inherits the
framing of whoever spoke last. A fresh process is the only reliable way to get an independent read.
The skill prefers spawning a new CLI process, and explicitly warns against leaking the scoring rules
into the referee's prompt — a judge that knows the incentive structure starts modeling the players
instead of reading the code.

**Mandatory session splitting.** Every step must be split into 3–6 sequential subagents by directory
or feature area. Not for speed — explicitly sequential — but for **cost**. A single agent scanning a
whole repo carries every file it read into every subsequent read. Splitting means section A's file
contents are freed before section B starts. On a real codebase this is the difference between a run
you do weekly and one you do once.

**Two priority scans that came from production, not theory.** Both were added after specific misses:

- *Broken bug-reporting chains* — any path where an error reaches the user but never reaches the
  error tracker. Scored critical automatically, because it means production failures are invisible to
  the team while users silently suffer. Empty `catch {}`, console-only logging, and alerts without a
  capture call all qualify.
- *Error messages that mask missing logic* — strings like "switch back to X before retrying" or "you
  must select Y first". The code looks intentional and passes review, but the real bug is that the app
  knew what needed to happen and punted to the user anyway.

Neither is something a generic "find bugs" prompt surfaces. Both are the kind of thing you only learn
to grep for after shipping to users who never file bug reports.

## Focused variants

The full run is broad. For a targeted pass, invoke the skill with a narrowed scope — it keeps the same
three-agent structure while scanning for one class of defect:

- **Race conditions** — "Use bug-finder, but only race-condition issues: read/write ordering, async
  state updates, re-render timing, duplicate in-flight requests."
- **Performance** — same shape, scoped to hot paths, N+1 queries, and unnecessary re-renders.

Narrow runs are much cheaper and tend to produce a higher confirmed-bug rate than a full sweep.

## Before you run it

- Writes Markdown files to `./bug-reports/` in the project root.
- Shells out to `codex exec --full-auto` for step 2 and optionally spawns a `claude` process for step
  3. Both run against your working tree — read [`SKILL.md`](SKILL.md) before pointing it at anything
  sensitive.
- Sentry appears in the observability examples; substitute your own error tracker.
- It reports and ranks bugs. It does not fix them unless you ask.

## Install

Copy this folder into your agent's skills directory:

```bash
cp -R bug-finder ~/.claude/skills/
```

Then ask the agent to "run bug-finder".
