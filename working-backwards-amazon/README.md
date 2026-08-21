# working-backwards-amazon

Amazon-style Working Backwards process for a feature that isn't settled yet: inspects the repo,
interviews you in rounds, then writes a reviewable press release plus an implementation-ready
build spec.

**Output:** `docs/working-backwards/<feature-slug>/PRESS-RELEASE.md` + `BUILD-SPEC.md`

---

## What problem it solves

Agents are eager to start coding. For a genuinely new feature that is the wrong first move — you end
up with a confident implementation of an under-specified idea, and the reasoning behind it lives only
in a chat log that nobody can review and the next agent session cannot read.

This skill forces the order of operations: **customer outcome → interview → repository grounding →
two written documents → then implementation.**

## Why two documents instead of one

They have different readers, so merging them makes both worse.

- **`PRESS-RELEASE.md`** is for a human deciding whether this is worth building. Four fixed sections
  (`Problem to Solve`, `How We Measure Success`, `The Launch Post`, `Other Details`), readable in
  5–10 minutes. Requirement inventories, API contracts, and test matrices are banned here.
- **`BUILD-SPEC.md`** is a contract for whoever implements it — usually another agent session with no
  memory of the conversation. Stable identifiers (`FR-001`, `BR-001`, `AC-001`), data and API
  contracts, Mermaid diagrams, cited repository paths, rollout, and observable acceptance criteria.

Each document is self-contained and links to the other, because in practice people open exactly one of
them and never scroll to find the rest.

## How it runs

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

## Design note: the applicability gate

The first version had one real failure mode in daily use: **it triggered on everything.** Ask for a bug
fix or a padding change and you'd get a full product-discovery interview for a ten-line diff.

The fix was not a better description alone — it was an explicit **Applicability Gate** section in the
skill body naming the excluded cases (routine defined tasks, straightforward bug fixes, purely visual
updates) and telling the agent what to do instead: just do the work. The `description` frontmatter was
tightened in parallel, since that is what the agent matches against before it ever reads the body.

The general lesson, which applies to most skills: **stating when *not* to fire is as load-bearing as
stating when to fire.** A skill that over-triggers gets disabled by its user, which makes it worth
exactly zero.

## When not to use it

Routine tasks with a defined outcome, straightforward bug fixes, and purely visual updates. The skill
enforces this itself, but it is worth knowing before you invoke it by name.

## Install

```bash
cp -R working-backwards-amazon ~/.claude/skills/
```

The `references/` folder ships the two document templates and must be copied along with `SKILL.md`.

## Credit

The Working Backwards agent-workflow framing is inspired by a
[post and video walkthrough](https://x.com/dexhorthy/status/2078592010852982977) by
[@dexhorthy](https://x.com/dexhorthy). The document architecture, interview rounds, readiness gate,
and applicability gate here are my own.
