# Configuration

One file in the target repo: `autopilot.json` (or `config/autopilot.json`). The engine
searches upward from the cwd. Start from `config/autopilot.example.json`.

## Top level

| key | required | meaning |
|---|---|---|
| `project_id` | yes | free-form identifier used in artifacts |
| `platforms` | yes | see below; at least one enabled |
| `workspace` | for dev server / `plan` | the **app source** repo (where commits come from) |
| `app_source` | no | path an agent may read to confirm labels |
| `knowledge_dir` | no | default `knowledge` |
| `artifacts_dir` | no | default `artifacts` |
| `java_home_candidates` | no | Homebrew formulae to probe, in order |

## `platforms.ios`

| key | meaning |
|---|---|
| `app_id` | bundle id |
| `manifest` | path to the flow manifest |
| `device.udid` / `device.name` | the pinned simulator. Both are used: udid first, name as fallback. |
| `device.known_bad` | simulators proven broken. Configuring one is a hard error. |
| `dev_server.port` / `.start_command` | started only if the port is idle |
| `dev_server.forbidden_env` | env vars stripped before starting it (e.g. `CI`) |
| `build_command` | printed in errors; `{udid}` is substituted |
| `smoke_flow` | tiny flow that must pass for preflight to succeed |

## `platforms.android`

| key | meaning |
|---|---|
| `device.serial` | pinned serial. A mismatch is a stop condition, not a fallback. |
| `device.allow_emulator` | default `false`; emulators are filtered out of `adb devices` |
| `preferred_apk` | `release` or `debug`. **There is no fallback between variants** — a missing apk is a hard error that prints the build command. |
| `apk_paths` | one path per variant |
| `reverse_ports` | re-applied every preflight (`adb reverse` is per-connection state) |
| `restore_connectivity` | default `true`; runs after every flow, pass or fail |

## `run`

`per_flow_timeout_seconds` (default 600) — a hung flow is killed and recorded as failed
instead of blocking the batch. `exclude_tags` — manifest boolean flags that exclude a
flow from default batches (e.g. `real_api` for flows that spend a paid quota).

## `seed`

```json
"seed": { "command": "node scripts/seed.mjs --json --run-id {run_id}", "env_prefix": "SEED" }
```

Flows opt in via `"seed": true` or `{"count": 2, "fixture": "..."}` in the manifest. The
runner injects `SEED_MARKER` (and `_2`, `_3` …) plus any keys from a JSON line the
command prints on stdout. **A seeding failure fails the flow** rather than silently
running it against stale data.

Two rules worth stating explicitly, because both have produced silent false greens:

- Never give an injected variable a flow-level `env:` default — the default wins over
  `-e` and masks the injected value.
- Prefer a fresh record per run over one long-lived shared fixture.

## `coverage`

Glob → family mapping that `plan` uses to connect commits to flows. Deliberately
declarative: a wrong mapping is visible and fixable, rather than buried in a model's
reasoning.

## `pr`

`branch_prefix`, `base`, `remote`, `labels`. Unattended runs must never target the
default branch directly.
