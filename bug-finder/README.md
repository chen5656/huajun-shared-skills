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
three-agent structure while scanning for one class of defect. No changes to the skill are needed; the
scope lives entirely in how you phrase the invocation.

Narrow runs are much cheaper and tend to produce a higher confirmed-bug rate than a full sweep.

### Correctness scopes

- **Race conditions (server/shared state)** — "Use bug-finder, but only race-condition issues:
  read/write ordering, check-then-act gaps, non-atomic updates, retries that double-apply."
- **Client-side race conditions** — the browser-specific half, worth its own run: async state updates
  landing after unmount or after a newer render, **duplicate in-flight requests** for the same key,
  **stale data usage** (a closure or ref holding a value from two states ago), **out-of-order
  responses** where a slow request overwrites a fast newer one, **concurrent user actions** (double
  submit, rapid tab switching, typing during a save), and **event handling overlaps** — two handlers
  that both fire and both mutate the same state.
  > "Use bug-finder scoped to client-side races: for every async call, ask what happens if it resolves
  > after a newer one, after navigation, or twice."
- **UI flicker / layout jank** — a class of bug users complain about and stack traces never show:
  content that renders, then re-renders with different data; loading states that flash for 40ms;
  layout shifting as images or fonts settle; a value that briefly shows the previous item's data
  during a transition.
  > "Use bug-finder for visible flicker: any state that renders an intermediate value on the way to
  > the final one."
- **Performance** — hot paths, N+1 queries, unnecessary re-renders.
- **Over-fetching** — queries and endpoints that pull more than the caller needs: `SELECT *` behind a
  two-field view, a list endpoint returning full nested objects for a dropdown, a fetch inside a loop,
  refetching data already in cache, or subscribing to a whole store to read one key.

### Structural / hygiene scopes

These read less like bug hunts and more like standing cleanup crews. Same three-agent structure — the
adversary keeps the list honest, which matters more here, because refactor suggestions are exactly
where an agent pads.

- **"Changed the wrapper, not the callers"** — a signature, default, unit, or return shape changed in
  one place while some call sites still assume the old contract. Common after a hurried refactor and
  invisible to type checks when the types are loose (`any`, untyped JSON, string enums, optional
  params silently defaulted).
  > "Use bug-finder to find contract drift: for each recently changed function/component/API, check
  > every call site actually matches the new behavior, not just the new types."
- **Dup unifier** — scans for similar-yet-slightly-divergent abstractions: two date formatters that
  disagree on timezone, three "retry" helpers with different backoff, copy-pasted validation that
  diverged in one branch. The interesting output isn't "these are duplicates" but "these are
  duplicates **that no longer agree**" — which is a live bug, not a style issue.
  > "Use bug-finder as a duplicate unifier: find near-identical implementations and report where their
  > behavior has diverged."
- **Dead-code remover** — two passes worth asking for separately: *statically unreachable* code
  (unexported and unreferenced, branches behind an always-false condition, unused exports) and
  *suspected dead* code (a feature flag that's been on for a year, an endpoint with no caller in the
  repo, a component only referenced by its own test). The second list needs human judgment — ask for
  it separately and labelled as suspicion, not fact.
- **Abstraction police** — leaky abstractions: a repository layer that returns raw driver rows, a UI
  component that knows the database column names, an error type that only makes sense to one caller,
  a "generic" helper with a special case for one call site.
  > "Use bug-finder as abstraction police: find places where an abstraction's implementation details
  > leak into its callers, or where a caller must know something the interface promised to hide."

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
