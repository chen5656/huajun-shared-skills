# Design notes

Why each guard exists. Every one of these was paid for by a real run.

## The core problem: mobile test failures are indistinguishable

Run a mobile black-box suite unattended and four completely different causes produce
near-identical output:

1. the dev server is not running, so the app never loads;
2. Maestro was not pinned to a device and drove a phone that happened to be plugged in;
3. a debug build was installed over the release build under test;
4. a selector is genuinely stale.

Only (4) is a test problem. Only (4) should change a line of YAML. But an agent reading
logs will happily "fix" forty selectors to explain away (1).

So the design principle is not *retry harder*. It is: **make the environment prove
itself before the tests run, and make the classifier admit when it cannot tell.**

## Preflight as the only privileged step

Exactly one command may boot devices, start servers, and install builds. Everything else
re-verifies a record it wrote and refuses to start otherwise. That converts the worst
failure mode — an hour of tests against nothing — into a five-second error with the fix
command in it.

The record expires. A readiness claim from before a reboot is not a readiness claim.

## Confidence as a first-class output

The triage rules carry `needs_screenshot`. When a rule matches but the log alone cannot
prove the class, the verdict is reported as *unconfident*.

This is the single most useful line in the whole system. The failure modes that cost the
most hours — a quota dialog, a permission sheet, an error overlay — are exactly the ones
whose log line reads like an ordinary assertion timeout. An agent that reports "stale
selector" with confidence there will send you chasing a regression that does not exist.

Related: the batch verdict. `40 failed` is a false headline when the cause is one dead
server. The report leads with the shape of the failure, not the count.

## The editing boundary, and the accessibility carve-out

The agent may edit tests freely, and in the app source it may edit **only non-visible
accessibility metadata** — labels, hints, roles, testIDs.

That carve-out is not a loophole; it is the most productive rule in the system. The
right fix for a selector that cannot address a control is usually not a cleverer
selector — it is that the control has no accessible identity. Giving a numeric field the
label `"L1 to L2 voltage input, volts"` makes a plain-string selector work *and* makes
the app usable with a screen reader. **Test addressability and accessibility are the same
property.** The suite becomes a slow, automatic accessibility audit as a side effect.

## Report, never fix

When a test exposes a real product bug, the agent writes it up and stops.

An agent with permission to fix business logic overnight removes the only human
checkpoint in an unattended loop, and does it at the exact moment nobody is watching.
The value of the loop is that a person reads a well-evidenced report in the morning —
not that code changed while they slept.

Same reasoning behind branch-and-PR: proposals, never pushes.

## Knowing what not to automate

A field the framework reports as on-screen while the keyboard covers it cannot be driven
reliably. The correct output is a **written limitation**, not a test that fails one night
in three.

A documented gap is engineering judgment. A flaky test is worse than no test, because it
trains the team to ignore red.

## Learning as data, not as memory

The knowledge base is a file in the target repo, structured, deduplicated, and reloaded
into context before every run — not something a model is expected to remember.

Scope tags (`platform` / `product` / `env`) give lessons a lifecycle: platform lessons
graduate into the engine, env lessons expire, product lessons stay put. Without that,
a knowledge base becomes an append-only log of stale observations that nobody reads.

## Commits in, work order out — and no silent invention

`plan` maps changed files to families to flows and produces three lists: covered,
uncovered, unmapped.

It stops there. It does not write tests by itself. A generated flow that asserts the
wrong thing is worse than an acknowledged gap, because it reports green forever. The
uncovered list is a proposal for a human or an agent to act on deliberately.

The `unmapped` list matters as much: it is the config admitting what it does not know,
which is how the coverage map stays honest as the product grows.

## Evidence or it did not happen

Every screenshot in the report, grouped by flow, no cherry-picking. A narrative written
for someone who was not there. And the rule that governs every status update:

> Never report "everything is fine" without evidence gathered in this same turn.
> "It is running normally" is a claim about the last minute, not the last hour.
> If you have not looked, say you have not looked.
