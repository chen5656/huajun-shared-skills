# Huajun's Shared Agent Skills

Agent skills I actually use in day-to-day product development with Claude Code, Codex, and Gemini CLI.

These are not demos. Each one is extracted from a working setup, and the design notes explain the
tradeoffs that survived contact with real use — including what I got wrong the first time.

Drop a skill folder into your agent's skills directory (for example `.claude/skills/` or
`.agents/skills/`) and the agent will load it when its `description` matches the task.

## A note on what these have in common

None of these skills is mainly a prompt. Each one exists because a capable model, left to
its own judgment, reliably does the wrong thing in a specific way — and the fix was
structural rather than a better-worded instruction:

| Skill | Failure mode it corrects | Mechanism |
| :--- | :--- | :--- |
| bug-finder | Models confirm their own reasoning | **Opposition** — a rival model paid to disprove the findings |
| working-backwards-amazon | Skills over-trigger and get disabled | **Boundaries** — an explicit gate naming when *not* to fire |
| i18n-translate | The expensive model helpfully does cheap work | **Routing** — a hard stop rule that forces the job onto a cheaper model |

The recurring lesson: designing an agent skill is mostly about constraints and division
of labor, not wording.

---

## Skills

| Skill | What it does | Output |
| :--- | :--- | :--- |
| [**bug-finder**](bug-finder/SKILL.md) | Adversarial three-agent bug review. A hunter finds bugs, a second model paid to disprove them attacks the list, an isolated referee rules on both. | `bug-reports/{01-bug-hunter,02-adversarial,03-referee}.md` |
| [**working-backwards-amazon**](working-backwards-amazon/SKILL.md) | Amazon-style Working Backwards process: inspects the repo, interviews you in rounds, then writes a reviewable press release plus an implementation-ready build spec. | `docs/working-backwards/<slug>/{PRESS-RELEASE.md,BUILD-SPEC.md}` |
| [**i18n-translate**](i18n-translate/SKILL.md) | Bulk Lingui catalog translation, routed to a cheap model on purpose: extract missing entries into batched JSON sessions, translate, audit for UI overflow, apply, compile, verify. | Updated `.po` / compiled catalogs, 0 missing entries |

---

## bug-finder

### The problem it solves

Ask an agent to "find bugs in this codebase" and you get a long, confident list padded with false
positives. The list is worse than useless: someone has to read all of it to find the two real bugs,
and after one bad experience nobody runs it again.

The usual fix is to add "be rigorous, avoid false positives" to the prompt. That does very little.
This skill fixes it structurally instead — with **incentives and adversaries**, not adjectives.

### How it works

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

### Design notes

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

### Focused variants

The full run is broad. For a targeted pass, invoke the skill with a narrowed scope — it keeps the same
three-agent structure while scanning for one class of defect:

- **Race conditions** — "Use bug-finder, but only race-condition issues: read/write ordering, async
  state updates, re-render timing, duplicate in-flight requests."
- **Performance** — same shape, scoped to hot paths, N+1 queries, and unnecessary re-renders.

Narrow runs are much cheaper and tend to produce a higher confirmed-bug rate than a full sweep.

### Before you run it

- Writes Markdown files to `./bug-reports/` in the project root.
- Shells out to `codex exec --full-auto` for step 2 and optionally spawns a `claude` process for step
  3. Both run against your working tree — read the SKILL file before pointing it at anything sensitive.
- Sentry appears in the observability examples; substitute your own error tracker.
- It reports and ranks bugs. It does not fix them unless you ask.

---

## working-backwards-amazon

### What problem it solves

Agents are eager to start coding. For a genuinely new feature that is the wrong first move — you end
up with a confident implementation of an under-specified idea, and the reasoning behind it lives only
in a chat log that nobody can review and the next agent session cannot read.

This skill forces the order of operations: **customer outcome → interview → repository grounding →
two written documents → then implementation.**

### Why two documents instead of one

They have different readers, so merging them makes both worse.

- **`PRESS-RELEASE.md`** is for a human deciding whether this is worth building. Four fixed sections
  (`Problem to Solve`, `How We Measure Success`, `The Launch Post`, `Other Details`), readable in
  5–10 minutes. Requirement inventories, API contracts, and test matrices are banned here.
- **`BUILD-SPEC.md`** is a contract for whoever implements it — usually another agent session with no
  memory of the conversation. Stable identifiers (`FR-001`, `BR-001`, `AC-001`), data and API
  contracts, Mermaid diagrams, cited repository paths, rollout, and observable acceptance criteria.

Each document is self-contained and links to the other, because in practice people open exactly one of
them and never scroll to find the rest.

### How it runs

1. **Repository inspection first** — routes, schemas, APIs, auth, entitlements, telemetry, tests, and
   adjacent features, *before* proposing requirements, so the questions are grounded in what exists.
   Without repo access it must say so and mark both drafts `Repository validation required` rather
   than pretending.
2. **Interview in rounds**, 3–5 questions at a time: customer and problem, experience and scope,
   business and policy, technical boundaries. It is instructed to challenge weak premises rather than
   transcribe whatever solution you walked in with.
3. **Readiness gate** — nothing is drafted while material decisions are open, and nothing is labeled
   approved just because you said "looks good."
4. **Drafts saved immediately**, paths reported, then it asks what to change. Approval flips both files
   to `Status: Approved` — and deliberately does *not* authorize writing code unless you separately
   ask.

### Design note: the applicability gate

The first version had one real failure mode in daily use: **it triggered on everything.** Ask for a bug
fix or a padding change and you'd get a full product-discovery interview for a ten-line diff.

The fix was not a better description alone — it was an explicit **Applicability Gate** section in the
skill body naming the excluded cases (routine defined tasks, straightforward bug fixes, purely visual
updates) and telling the agent what to do instead: just do the work. The `description` frontmatter was
tightened in parallel, since that is what the agent matches against before it ever reads the body.

The general lesson, which applies to most skills: **stating when *not* to fire is as load-bearing as
stating when to fire.** A skill that over-triggers gets disabled by its user, which makes it worth
exactly zero.

### Credit

The Working Backwards agent-workflow framing is inspired by a
[post and video walkthrough](https://x.com/dexhorthy/status/2078592010852982977) by
[@dexhorthy](https://x.com/dexhorthy). The document architecture, interview rounds, readiness gate,
and applicability gate here are my own.

---

## i18n-translate

### What problem it solves

Shipping a release with three locales means several hundred `msgstr` entries that need
translating, checking for placeholder damage, and checking that the Spanish version of a
button still fits on the button. It is real work with real failure modes — and almost
none of it needs frontier-model reasoning.

### The actual design decision: pay less for this

I run the translation worker on a cheap Gemini plan (`gemini-3.5-flash-low` in my setup),
launched as a separate non-interactive process by whichever agent is orchestrating the
release. That plan is inexpensive and the model is limited in what it can do well — but
this task is bounded, mechanical, and heavily validated downstream, so the fit is close to
ideal. Bulk translation is exactly the kind of work you should not be paying frontier
prices for.

The interesting part is what it takes to make that stick.

### Why the stop rule exists

Writing "use the cheap model for translation" in a deploy checklist does not work. The
orchestrating agent is capable, the task is right there, and being helpful is what it
does — so it translates the strings itself and the saving quietly evaporates. Nobody
notices, because the output is fine.

So the routing is enforced in the skill rather than requested: an agent reading this file
that was **not** launched as the worker is told, in the first section, that it may not run
extraction, the helpers, the translation, the audit, the apply, or the compile. Its only
move is to launch the worker and get on with the rest of the release.

It is stated as a role check rather than a model name, so the same file works whether your
worker is Gemini, a local model, or the same agent you started from. Naming a specific
model there was my first version and it was wrong — it broke the moment the setup changed.

### Why a Python helper instead of "translate this .po file"

`translate_helper.py` does the parts a language model should not be trusted with:

- **Batching.** Missing entries are extracted into `session_N.json` files of ~50 entries.
  A model handed a 700-entry catalog degrades badly toward the end; 50 at a time does not.
- **Structural safety.** Only `msgstr` is writable. Placeholders (`{0}`, `{count}`),
  plural keys, escapes, and leading/trailing whitespace are verified against the source
  before anything is written back, so a plausible-looking translation cannot silently
  break interpolation at runtime.
- **UI overflow audit.** Flags translations that grew past what tight surfaces — buttons,
  tabs, badges, fixed-height cards — can display. German and French routinely run 30%
  longer than English, and this is otherwise found by a user, in production, on a phone.
- **Verification that means something.** The run is only successful if `lingui:compile`
  passes *and* every locale reports 0 missing. A subset is a failure, not partial credit.

The division is the point: the cheap model does judgment about language, the deterministic
script does everything where being wrong is expensive.

### Requirements

- A project using [Lingui](https://lingui.dev) with `lingui:extract` / `lingui:compile`
  scripts and a `src/locales` catalog directory.
- Any agent CLI that can run a single prompt non-interactively and write files in the
  repo. The launch snippet in the skill is written generically — substitute your own.
- Python 3 for the helper. No third-party dependencies.

---

## License

MIT. Use them, fork them, change them.
