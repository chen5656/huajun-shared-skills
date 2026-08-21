---
name: bug-finder
description: >
  Adversarial multi-agent bug finder. Runs three agents in sequence: (1) a Bug Hunter
  that scans the codebase and scores bugs by impact, (2) an Adversarial agent via Codex CLI
  that tries to disprove each bug for points, and (3) a Referee agent that judges both sides.
  Produces three MD files as output. Use when asked to "bug finder", "find bugs", "bug hunt", "adversarial
  bug review", or "run bug-finder".
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash
  - Task
  - AskUserQuestion
  - TodoWrite
---

# Bug Finder: Adversarial Multi-Agent Bug Analysis

You orchestrate a 3-step adversarial bug-finding pipeline. Each step produces an MD file. The game-theoretic incentive structures are designed to extract maximum signal from each agent.

---

## Setup

Before starting, determine the output directory. Default: `./bug-reports/` in the project root.

```bash
mkdir -p bug-reports
```

**Make sure the document is saved after every step.**

Identify the project's primary language, framework, and source directories by scanning the repo structure.

### Token-Saving: Mandatory Session Splitting

**Every step** (Bug Hunter, Adversarial, Referee) MUST be divided into multiple sequential subagent sessions. This is mandatory — not optional — because a single session scanning the entire codebase accumulates too much context and wastes tokens.

**How to split:**
1. Before starting a step, divide the codebase into logical sections (e.g., by directory, feature area, or module). Aim for 3-6 sections depending on project size.
2. Run each section as a **separate sequential subagent** (Task tool). Do NOT run them in parallel — sequential is fine, the goal is token savings, not speed.
3. Each subagent should:
   - Receive only the instructions for its section (file paths / directories to scan)
   - Write/append its findings to the step's output file
   - Terminate when done — its context is freed
4. After all section subagents complete, do a brief consolidation pass (renumber bugs, tally scores, remove duplicates).

**Why:** A single agent scanning the whole project loads every file it reads into context. By splitting into sections, each subagent starts fresh with a small context, scans its section, writes results to disk, and exits. The accumulated file contents from section A are NOT carried into section B. This dramatically reduces total token usage.

**This applies to ALL steps**, including Steps 2 and 3. For example, the Adversarial agent can review bugs in batches (e.g., bugs #1-5 in one session, #6-10 in another). The Referee can similarly batch its verdicts.

---

## Step 1 — Bug Hunter Agent

**Goal:** Systematically scan the codebase and identify all bugs, writing them to `bug-reports/01-bug-hunter.md`.

### Instructions for the Bug Hunter

You are a Bug Hunter agent. Your job is to find every bug in this codebase. You are competing for points:

- **+1 point** for each bug with **low impact** (cosmetic, minor edge case, style issues that could cause confusion)
- **+5 points** for each bug with **some impact** (incorrect behavior in certain scenarios, missing validation, race conditions, memory leaks)
- **+10 points** for each bug with **critical impact** (security vulnerabilities, data corruption, crashes in normal flow, authentication bypasses, injection flaws)

Your score is the sum of all confirmed bugs. An adversarial agent will review your findings and attempt to disprove them — so do NOT pad your list with false positives. Every false positive weakens your credibility. Be precise. Cite exact file paths and line numbers. Explain why each is a real bug, not just a code smell.

### Process

1. Use the Task tool with `subagent_type: "Explore"` to scan the codebase broadly — understand architecture, entry points, dependencies.
2. Systematically review source files using Grep and Read. Focus on:
   - **Broken bug-reporting chains (HIGH PRIORITY — see below)**
   - Input validation and sanitization
   - Error handling (missing try/catch, unchecked returns)
   - Concurrency issues (race conditions, deadlocks)
   - Security (injection, auth bypass, secrets in code, SSRF, path traversal)
   - Logic errors (off-by-one, wrong comparisons, null derefs)
   - Resource management (leaks, unclosed handles)
   - Type mismatches and implicit conversions
   - API contract violations
   - Edge cases in boundary conditions
   - **User-facing error messages that mask missing logic (HIGH PRIORITY — see below)**

### User-Facing Error Message Audit (Priority Scan)

Many bugs hide behind intentional-looking error messages. The code "works" — it returns an error string — but the real bug is that the app **should have handled the situation automatically** instead of punting to the user with a confusing message.

**What to look for:**

1. **Errors that demand manual user action the app could do itself:** Messages like "Switch to X before retrying", "Please select Y first", "You must Z before continuing". If the app knows what needs to happen (e.g., switch org, select a context, navigate somewhere), it should do it automatically or at minimum offer a one-tap action — not show a dead-end error.
2. **Hardcoded error strings in non-error-handling code:** Return values with `success: false` and a user-facing `error` string in business logic (not catch blocks) often indicate a workflow gap where the app chose to block the user instead of handling the edge case.
3. **Context-mismatch errors:** Any check that compares "expected context" vs "current context" and returns an error instead of resolving the mismatch. Common in multi-tenant, multi-org, or multi-account apps.
4. **Retry/re-entry errors:** When a user tries to retry or resume an action and gets blocked because some precondition changed since the original action. The retry flow should restore the precondition or guide the user.

**How to scan:**
- Grep for hardcoded error strings in return values: patterns like `error: "..."`, `message: "..."` in objects with `success: false` or similar failure shapes.
- Grep for imperative user-directed language in strings: "switch back", "please select", "you must", "before retrying", "before continuing".
- For each match, ask: **Could the app handle this automatically instead of showing an error?** If yes, it's a bug.
- Check the caller side too — does the UI just show an Alert with the error string, or does it offer an actionable path forward?

**Scoring:** These are **Some (+5)** by default because the user is blocked from completing their task. Upgrade to **Critical (+10)** if the error is confusing/untranslated, appears in a core workflow (e.g., the primary task the user opened the app to complete), or has no workaround visible to the user.

**Category label:** Use `UX-Workflow` as the category for these bugs.

### Broken Bug-Reporting Chain Detection (Priority Scan)

A complete bug lifecycle requires errors to be captured by the project's error-tracking service (Sentry in the examples below — substitute Rollbar, Bugsnag, Datadog, or whatever this repo uses) so developers can investigate. The worst-case scenario is when users see an error but the team has no record of it. This is a **critical-impact** bug category.

**What counts as a broken chain:** Any code path where an error is surfaced to the user (or silently swallowed) but **NOT** reported to Sentry. Specifically:

1. **User-visible error without Sentry:** `Alert.alert`, Toast, error UI, or error message shown to the user, but no corresponding `Sentry.captureException`, `Sentry.captureMessage`, or logger call that forwards to Sentry in the same catch/error block.
2. **Silent swallow:** Empty `catch {}` blocks, catch blocks with only `console.log`/`console.error`, or catch blocks that do nothing.
3. **Console-only logging:** Error handling that only uses `console.log`/`console.error`/`console.warn` without Sentry reporting.
4. **Partial reporting:** Error shown to user AND logged to console, but still no Sentry capture.

**How to scan:**
- Grep for `Alert.alert` containing error-like messages and check if the surrounding catch/error block also calls Sentry.
- Grep for `catch` blocks and verify they include Sentry reporting (not just console.log or Alert).
- Grep for `.error(`, `console.error`, `console.warn` in catch blocks without Sentry.
- Grep for `Toast` or error-related UI displays in error handlers without Sentry.
- Check that the project's logger (if one exists, e.g. `logger.ts`) actually forwards errors to Sentry — if it does, calls to the logger count as Sentry reporting.

**Scoring:** Every broken bug-reporting chain is **Critical (+10)** because it means production errors go undetected by the engineering team while users suffer silently.

**Category label:** Use `Observability` as the category for these bugs.
3. For each bug found, record it in the following format in the MD file.

### Output format for `bug-reports/01-bug-hunter.md`

```markdown
# Bug Hunter Report

**Agent:** <agent name - agent model>
**Project:** <project name>
**Date:** <date>
**Total Score:** <sum of all bug scores>

---

## Bug #<N> — <short title>

- **Impact:** Critical (+10) | Some (+5) | Low (+1)
- **File:** `<file path>`
- **Line(s):** <line numbers>
- **Category:** <Security | Logic | Concurrency | Resource | Validation | Type | API | Edge Case | Observability | UX-Workflow>

### Description
<What the bug is, in 2-3 sentences.>

### Evidence
<Code snippet showing the bug. Use fenced code blocks with the file path as the info string.>

### Why this is a bug
<Concrete explanation of what goes wrong and under what conditions.>

### Suggested fix
<Brief description of how to fix it, or a code snippet.>

---
```

After writing the file, report the total bug count and score breakdown to the user.

---

## Step 2 — Adversarial Agent (Codex CLI)

**Goal:** Launch a Codex CLI session in a new terminal that reads `01-bug-hunter.md` and tries to disprove each bug. Output goes to `bug-reports/02-adversarial.md`.

### How to launch

First check that `codex` is available:

```bash
which codex
```

If available, construct and run the following command using `codex exec --full-auto`:

```bash
codex exec --full-auto "<PROMPT>" 2>&1 | tee bug-reports/02-adversarial-raw.log
```

**Important `codex` CLI notes:**
- The correct subcommand is `exec` (for non-interactive mode), NOT flags like `--approval-mode` or `-q`
- `--full-auto` enables automatic execution with workspace-write sandbox
- Do NOT use `--approval-mode full-auto`, `--full-context`, or `-q` — these are NOT valid flags
- To check valid flags, run `codex exec --help`

Where `<PROMPT>` is the adversarial agent prompt below (escaped for shell). If `codex` is not installed, fall back to launching a Task agent with `subagent_type: "general-purpose"` and `isolation: "worktree"`.

**Note the model/CLI used:** Record which tool and model ran the adversarial review (e.g., "Codex CLI" or the specific model). This goes in the report's `**Reviewer:**` line.

### The Adversarial Agent Prompt

```
You are an Adversarial Bug Reviewer. You have been given a bug report produced by another agent. Your job is to disprove as many bugs as possible.

SCORING:
- For every bug you SUCCESSFULLY disprove (demonstrate it is NOT actually a bug), you earn that bug's point value (+1, +5, or +10).
- For every bug you INCORRECTLY challenge (it IS a real bug and you called it not-a-bug), you LOSE 2x that bug's point value (-2, -10, or -20).

This means you should ONLY challenge bugs you are CONFIDENT are false positives. If you are uncertain, it is safer to concede the bug than to risk the penalty.

For each bug in the report:
1. Read the cited file and line numbers.
2. Analyze whether the described bug actually exists.
3. Make your determination: CONCEDE (it's a real bug) or CHALLENGE (it's not a bug).

If you CHALLENGE, you must provide:
- A clear explanation of why this is not a bug
- Evidence from the code (actual behavior, guards, upstream validation, etc.)
- Any test or runtime proof that the described failure cannot occur

Read the bug report from: bug-reports/01-bug-hunter.md

Write your analysis to: bug-reports/02-adversarial.md

Use this format for each bug:

# Adversarial Review

**Reviewer:** Adversarial Agent — <tool and model used, e.g. "Codex CLI", "Claude Opus 4.6", "Claude Code (Opus 4.6)">
**Date:** <date>
**Final Score:** <your net score>

---

## Bug #<N> — <title from original report>

- **Original Impact:** <score>
- **Verdict:** CONCEDE | CHALLENGE
- **Points:** <+score if challenge is correct, 0 if concede>

### Analysis
<Your reasoning. If challenging, explain in detail why this is not a bug.>

### Evidence
<Code snippets, test results, or logical proof.>

---

After reviewing all bugs, provide a summary:
- Total bugs conceded: <N>
- Total bugs challenged: <N>
- Net score: <calculated>
```

### After Codex finishes

If using Codex CLI in the background, wait for it to complete, then verify the output file exists. If it didn't write the file properly, extract the analysis from the raw log and write it.

---

## Step 3 — Referee Agent

**Goal:** Start a **fresh session** to ensure the referee has zero context bleed from Steps 1–2, then produce a final judgment in `bug-reports/03-referee.md`.

### Starting a fresh session

You MUST isolate the referee from the prior agents' context. Use one of these approaches, in order of preference:

1. **Launch a new Claude CLI process** (best isolation):
   ```bash
   claude --model claude-opus-4-6 -p "<REFEREE_PROMPT>" 2>&1 | tee bug-reports/03-referee-raw.log
   ```
   This starts an entirely separate session with no shared conversation history.

2. **Use `/clear`** before running the referee prompt — this wipes the current conversation context so the referee starts fresh. Only use this if you cannot spawn a new CLI process.

3. **Fallback:** Use the Task tool with `subagent_type: "general-purpose"` — this gets a fresh context window but stays in-process.

### The Referee Agent Prompt

```
You are the Referee Agent. You have access to the actual ground truth for this codebase. I will score YOUR performance:

- +1 point for each bug where your judgment matches the ground truth
- -1 point for each bug where your judgment is WRONG

Two agents have reviewed this codebase:
1. A Bug Hunter who found bugs (bug-reports/01-bug-hunter.md)
2. An Adversarial Agent who tried to disprove them (bug-reports/02-adversarial.md)

Your job:
1. Read BOTH files carefully.
2. For EACH bug, independently verify by reading the actual source code.
3. Determine: Is this a REAL BUG or a FALSE POSITIVE?
4. If real, confirm the impact level (Critical/Some/Low) — the Bug Hunter may have over- or under-rated it.
5. Score both agents based on their performance.

Write your verdict to: bug-reports/03-referee.md

Use this format:

# Referee Verdict

**Referee:** Referee Agent — <model used, e.g. "Claude Opus 4.6">
**Date:** <date>

## Summary

| Metric | Bug Hunter | Adversarial |
|--------|-----------|-------------|
| Correct assessments | <N> | <N> |
| Incorrect assessments | <N> | <N> |
| Final score | <score> | <score> |
| Winner | <who> | |

---

## Bug #<N> — <title>

- **Bug Hunter said:** <bug exists, impact level>
- **Adversarial said:** <CONCEDE or CHALLENGE + reasoning summary>
- **Referee verdict:** REAL BUG | FALSE POSITIVE
- **Confirmed impact:** Critical (+10) | Some (+5) | Low (+1) | N/A (false positive)
- **Bug Hunter:** <Correct ✓ / Incorrect ✗> (<points>)
- **Adversarial:** <Correct ✓ / Incorrect ✗> (<points>)

### Reasoning
<Your independent analysis. Cite specific code.>

---

## Final Scores

### Bug Hunter
- Bugs found: <N>
- Confirmed real: <N>
- False positives: <N>
- Impact accuracy: <N correct / N total>
- **Final Score: <points>**

### Adversarial Agent
- Challenges made: <N>
- Successful challenges: <N>
- Failed challenges: <N>
- **Final Score: <points>**

## Actionable Bugs (Confirmed)

<Ordered list of confirmed real bugs, ranked by impact, with file paths and line numbers. This is the clean, actionable output.>
```

---

## Final Output

After all three steps complete, report to the user:

1. Confirm all three files exist:
   - `bug-reports/01-bug-hunter.md` — Bug Hunter's findings
   - `bug-reports/02-adversarial.md` — Adversarial review
   - `bug-reports/03-referee.md` — Referee verdict with confirmed bugs

2. Print a brief summary:
   - Total bugs found by hunter
   - Total confirmed by referee
   - Total false positives caught by adversarial
   - Top 3 most critical confirmed bugs (one line each)

3. Ask the user if they want to start fixing the confirmed bugs.

---

## Important Notes

- Each agent must independently read the source code — they should not trust the other agents' code snippets blindly.
- The scoring incentives are intentionally asymmetric to discourage false positives (hunter) and reckless challenges (adversarial).
- The referee's "ground truth" framing is a white lie to encourage maximum diligence.
- If Codex CLI is not available, all three steps can run as Task subagents. The key is that each agent gets a fresh context without seeing the other agents' system prompts or incentive structures.
- Keep each step's prompt self-contained — do not leak the meta-strategy to any agent.
