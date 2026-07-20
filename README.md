# Huajun's Shared Skills for AI Agents

Skills shared by Huajun for improving daily work efficiency with AI Agents (Claude Code, Codex, etc.).

These skills can be imported or registered in your agent environment (e.g., in `.agents/skills/` or referenced in a `skills.json` configuration) to extend the capabilities of your AI pair programmers.

---

## 🛠️ Skill Menu

| Skill Name | Description | Key Deliverable | Link |
| :--- | :--- | :--- | :--- |
| **working-backwards-amazon** | Create a human-reviewable Working Backwards release narrative and an implementation-ready build contract. | `docs/working-backwards/<feature-slug>/{PRESS-RELEASE.md,BUILD-SPEC.md}` | [Detail](#-working-backwards-amazon) |

---

## 🔍 Skill Details

### 📝 working-backwards-amazon

Use this skill when you want to define, validate, scope, or prepare the implementation of a new feature, product capability, workflow, major UX change, or product experiment.

* **Path**: [`working-backwards-amazon/SKILL.md`](file:///Users/huajun/Code/huajun-shared-skills/working-backwards-amazon/SKILL.md)
* **Goal**: Start from the customer outcome, then produce two linked documents: a concise `PRESS-RELEASE.md` for human review and a comprehensive `BUILD-SPEC.md` that another agent can implement without relying on chat history.
* **Inspiration**: Concept inspired by a [post and video walkthrough](https://x.com/dexhorthy/status/2078592010852982977) by [@dexhorthy](https://x.com/dexhorthy).

Each feature discussion is saved as its own folder:

```text
docs/working-backwards/<feature-slug>/
├── PRESS-RELEASE.md
└── BUILD-SPEC.md
```

#### Core Rules & Workflow:

1. **Repository Inspection First**: Inspects the entire codebase (frontend, backend, schemas, APIs) to understand physical constraints and dependencies before proposing requirements.
2. **Iterative User Interview**: Conducts structured interview rounds covering:
   - **Round A**: Customer identity, problem severity, jobs-to-be-done, and what success looks like.
   - **Round B**: Scope, end-to-end happy path, error cases, platform/device targets.
   - **Round C**: Business impact, pricing/entitlements, telemetry/analytics, and launch operations.
   - **Round D**: Repository-grounded technical boundaries, compatibility, observability, quality, and testing.
3. **Readable Human Review**: `PRESS-RELEASE.md` uses four scan-friendly blocks—`Problem to Solve`, `How We Measure Success`, `The Launch Post`, and `Other Details`—and keeps engineering inventories out of the review narrative.
4. **Independent Implementation Contract**: `BUILD-SPEC.md` contains confirmed decisions, requirements, rules, states, data and API contracts, repository references, Mermaid diagrams, tests, rollout, and observable acceptance criteria.
5. **Drafts Saved Early**: Once the readiness gate passes, both files are saved immediately with `Status: Draft`. The agent reports their paths and asks what to change or whether the package is approved for implementation.
6. **Consistent Approval and Handoff**: Approval updates both documents to `Status: Approved`. Approval does not itself authorize code changes unless the user also asks the agent to implement the feature.
