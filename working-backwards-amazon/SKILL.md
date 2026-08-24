---
name: working-backwards-amazon
description: Create, review, and finalize an Amazon-style Working Backwards feature package for substantial product work that needs customer-outcome discovery, scope decisions, or an implementation plan before coding. Use when the user wants to define, validate, or scope a new feature, workflow, major cross-cutting UX change, or product experiment whose behavior or tradeoffs are not already settled. Do not use for routine implementation tasks that do not need a plan, straightforward bug fixes, or purely visual/UI updates. Inspect the repository, interview the user, and save a readable PRESS-RELEASE.md plus an implementation-complete BUILD-SPEC.md in docs/working-backwards/FEATURE-SLUG/.
---

# Working Backwards Feature Package

Turn an early feature idea into two complementary documents:

- `PRESS-RELEASE.md` is the concise, human-reviewable decision document.
- `BUILD-SPEC.md` is the complete implementation contract an independent agent can execute.

Start from the customer outcome, not the proposed implementation. Read both `references/press-release-template.md` and `references/build-spec-template.md` completely before drafting or revising either document.

## Startup Version Gate

At the start of the workflow, before repository inspection or the broader interview, ask the user which software version this feature is planned for unless they already stated it explicitly. Do not infer the version from repository files, branches, tags, or release history.

Record the user's answer as `Planned software version` in the metadata of both `PRESS-RELEASE.md` and `BUILD-SPEC.md`. If the user says the version is undecided, record `TBD` and track it as an unresolved decision in both documents.

## Applicability Gate

Use this workflow only when the request requires product discovery or meaningful planning before implementation. Do not use it when the user is asking to:

- Complete a routine, already-defined task that does not need a plan
- Fix a straightforward bug with a clear expected behavior
- Make a purely visual or UI-only update without new product behavior, policy, data, or workflow decisions

For these excluded requests, handle the work directly using the repository's normal implementation and verification process. If a seemingly simple request reveals unresolved product behavior or material cross-cutting decisions, explain that change in scope before proposing this workflow.

## Core Rules

1. Inspect the repository before proposing detailed requirements.
2. Interview before drafting. Do not silently fill important gaps with assumptions.
3. Ask focused questions in small batches, normally 3-5 at a time.
4. Separate confirmed decisions, repository facts, recommendations, assumptions, and unresolved questions.
5. Challenge weak premises respectfully. Do not merely transcribe the requested solution.
6. Always produce both documents. Do not collapse them into one file.
7. Optimize `PRESS-RELEASE.md` for human reading and decision-making. Keep implementation detail in `BUILD-SPEC.md`.
8. Make each document independently understandable: include the feature identity, customer, problem, outcome, scope summary, and a link to its companion document in both.
9. Include valid Mermaid diagrams in `BUILD-SPEC.md`; include a diagram in `PRESS-RELEASE.md` only when it materially helps a reviewer.
10. Save drafts immediately after the readiness gate, then ask the user what to change or whether to approve execution.
11. Never label a package approved or implementation-ready while material decisions remain unresolved.

## Required Output Layout

Every feature discussion owns one folder:

```text
docs/working-backwards/<feature-slug>/
├── PRESS-RELEASE.md
└── BUILD-SPEC.md
```

Use uppercase filenames exactly as shown. Create a filesystem-safe feature slug in kebab case. Never place new feature packages directly in `docs/working-backwards/` as a single Markdown file.

If revising a legacy single-file PR/FAQ, read it completely, split its content between the two new documents, and preserve the original file unless the user explicitly asks to remove or replace it.

## Readability and Heading Architecture

The rendered document and its navigation outline must be easy to scan.

For `PRESS-RELEASE.md`:

- Use one `#` title containing the customer-facing feature name.
- Use exactly these four `##` sections, in this order:
  1. `Problem to Solve`
  2. `How We Measure Success`
  3. `The Launch Post`
  4. `Other Details`
- Put all subdivisions under those blocks at `###` or deeper.
- Use meaningful, feature-specific `###` headings that communicate the point, not labels such as “Paragraph 1” or “More.”
- Keep paragraphs short, normally 1-4 sentences.
- Prefer prose for the story, bullets for choices or scope, and tables only for compact comparisons.
- Keep requirement inventories, API contracts, repository path lists, exhaustive edge cases, test matrices, and long decision logs out of this file.
- Target a document a product reviewer can read in roughly 5-10 minutes.

For `BUILD-SPEC.md`:

- Use one `#` title and stable, descriptive `##` sections from the build-spec template.
- Use tables for repeated mappings, permissions, requirements, rules, events, and acceptance criteria when this improves scanning.
- Keep identifiers stable (`FR-001`, `BR-001`, `AC-001`, and so on).
- Put details in the section where an implementer will look for them; avoid duplicating the same requirement across many sections.
- Cite repository paths and symbols instead of copying large code blocks.

## Workflow

### 1. Establish the feature identity

Determine:

- Planned software version
- Working feature name and slug
- Repository root and affected product
- Primary customer and role
- Triggering customer problem
- Desired customer outcome
- Why the feature matters now

Confirm the slug only if it differs materially from the user's wording.

### 2. Inspect the complete available codebase

Before the substantive interview, inspect all relevant repository areas, including:

- README files, product documentation, and existing Working Backwards documents
- Product routes, screens, components, and user flows
- Domain models, schemas, migrations, and storage
- APIs, actions, jobs, events, queues, and integrations
- Authentication, authorization, organizations, roles, and entitlements
- Billing, subscriptions, feature flags, and usage limits
- Analytics, telemetry, logging, and error handling
- Tests, fixtures, mocks, CI, deployment, and environment configuration
- Localization, accessibility, offline behavior, and platform-specific code
- Adjacent or competing features already in the repository

Search broadly before reading individual files deeply. Follow references across frontend, backend, shared packages, and infrastructure. Summarize only repository facts that materially constrain the feature and cite paths and symbols.

If repository access is unavailable, say so and include a clearly marked `Repository validation required` block in both drafts. Do not pretend the codebase was inspected.

### 3. Interview in progressive rounds

Adapt questions to information already supplied by the user or repository. Do not repeat answered questions.

#### Round A: Customer and problem

Clarify the target user, job-to-be-done, current workaround, frequency, severity, evidence, triggering moment, and desired outcome.

#### Round B: Experience and scope

Clarify the entry point, happy path, states, recovery, platforms, role differences, dependencies, in-scope behavior, and explicit non-goals.

#### Round C: Business and policy

Clarify entitlement, permissions, data lifecycle, privacy, rollout, operations, success metrics, and guardrails.

#### Round D: Technical boundaries

Ground questions in repository findings: reuse, data and API changes, offline and retry behavior, compatibility, observability, tests, performance, security, accessibility, and localization.

Offer a labeled recommendation when the user may not know an implementation detail. Request a decision only when it materially changes product behavior or scope.

### 4. Run the readiness gate

Before drafting, verify that the following are sufficiently resolved:

- Customer, problem, desired outcome, and value proposition
- Happy path and major failure/recovery paths
- Scope and non-goals
- Roles, permissions, ownership, and data lifecycle
- Billing or entitlement impact
- Technical integration points
- Success measures and guardrails
- Rollout and migration
- Planned software version, or an explicit `TBD` decision

If a major item is unresolved, ask the next focused question batch. Minor uncertainty may remain as an explicit assumption or open question.

### 5. Draft and save both files

Use the two reference templates as the exact structural baselines. Remove only sections that are genuinely irrelevant; never leave empty placeholders.

Create the feature folder and save both files immediately with `Status: Draft`. A draft is a review artifact, so it does not require prior approval to save. Preserve unrelated files and inspect any same-named package before updating it.

Draft `PRESS-RELEASE.md` first so the customer story constrains the implementation. Then draft `BUILD-SPEC.md` so every promise and policy in the press release has implementable requirements and acceptance coverage.

### 6. Keep the press release decision-focused

`PRESS-RELEASE.md` must contain only the information needed to understand and approve the feature:

- The customer, moment, pain, current workaround, and consequence
- Observable success and explicit guardrails; never invent baselines or targets
- A concise launch narrative: headline, subheading, dateline, solution, benefits, illustrative quotes, how it works, and call to action
- Key experience choices, scope/non-goals, important risks, alternatives, and unresolved decisions
- A short handoff pointing to `BUILD-SPEC.md`

Do not turn the press release into a requirements database. If a detail mainly helps an engineer implement or test the feature, put it in `BUILD-SPEC.md`.

### 7. Make the build spec independently executable

`BUILD-SPEC.md` must let a capable engineer or agent implement the feature using only the repository and this file. Include, when applicable:

- Context summary and links to the press release
- Planned software version
- Confirmed decisions, assumptions, and open questions
- Personas, role matrix, end-to-end flows, and lifecycle
- UI surfaces and all interaction states
- Functional requirements and business rules with stable IDs
- Data entities, ownership, retention, deletion, migration, and audit behavior
- API, event, job, and integration contracts
- Permissions and entitlement matrix
- Loading, empty, error, offline, retry, timeout, conflict, and partial-success behavior
- Analytics events and success metrics
- Security, privacy, accessibility, localization, performance, and reliability requirements
- Rollout, flags, migration, rollback, and support plan
- Test strategy and verifiable acceptance criteria
- Repository impact with paths and symbols

The build spec must not depend on unwritten conversation context. Any implementation agent should be able to distinguish confirmed behavior from recommendations and unresolved decisions.

### 8. Add diagrams

Normally include at least two diagrams in `BUILD-SPEC.md`:

- A customer journey, sequence, or state diagram
- A system, data-flow, or architecture diagram

Use conservative Mermaid syntax supported by common GitHub renderers. Ensure diagrams agree with requirements and acceptance criteria.

### 9. Review with the user

After saving the draft package, report both exact paths and a concise summary of:

- Decisions encoded
- Assumptions made
- Open questions
- Repository conflicts or risks

Then ask: **What would you like to change, or do you approve this package for implementation?**

Apply revisions to both files wherever necessary for consistency. Do not discard prior confirmed decisions. Continue until the user explicitly approves, says it is final, or authorizes implementation.

### 10. Approve and hand off

On approval:

1. Run the final quality audit.
2. Change both files to `Status: Approved` and update their dates.
3. Confirm there are no material open questions, or record any explicitly accepted deferrals.
4. Report the two paths and major repository areas likely to change.
5. If the user also asks this agent to implement, proceed from `BUILD-SPEC.md`. Approval alone does not imply implementation unless the user's wording authorizes it.

## Final Quality Audit

Before approval, verify:

- The press release uses the four required `##` blocks and its outline is readable.
- The customer problem is clearer than the feature mechanics.
- The headline and subheading describe customer value.
- The press release contains only review-critical content and links to the build spec.
- Both files agree on scope, terminology, roles, policies, and success.
- Every functional requirement is testable and every acceptance criterion is observable.
- Failure and recovery behavior is defined.
- Diagrams match the prose.
- Repository reuse and required changes are identified.
- No contradictory decisions remain.
- Open questions are resolved or explicitly accepted as deferred.

## Revision of an Existing Package

When either target file already exists:

1. Read both documents in full, plus any legacy single-file PR/FAQ.
2. Inspect current repository code related to the feature.
3. Identify divergence between documents and code.
4. Ask only questions needed for the requested revision.
5. Update all linked requirements, diagrams, acceptance criteria, and decision logs consistently.
6. Preserve concise decision history.
7. Save the revised drafts immediately and request changes or approval.
