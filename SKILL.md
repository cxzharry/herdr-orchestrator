---
name: herdr-orchestrator
description: Use when coordinating multi-lane Git-backed product delivery in Herdr with integration plus applicable QC, UI/UX, persona, Playwright, RBAC, mock-data, or worktree gates.
---

# Herdr Orchestrator

Run a bounded delivery loop. P1 owns contract, routing, and evidence consistency;
it never implements worker-owned changes or self-approves.

**REQUIRED SUB-SKILL:** Use `herdr` for live pane and agent control.

## Required sources

Before planning:

1. Inspect [the graph](references/delivery-flow.md) and call `view_image` on
   `assets/delivery-flow.png`.
2. Read [the runtime contract](references/runtime-contract.md) completely.

Treat the Excalidraw graph as visual topology and the runtime contract as
operational authority.

## Model roster

| Pane | Role | Model | Effort |
|---|---|---|---|
| P1 | Orchestrator | `gpt-5.6-sol` | `high` |
| P2–P4 | Workers 1–3 | `gpt-5.5` | `medium` |
| P5 | Worker 4 + Integration Owner | `gpt-5.6-sol` | `high` |
| P6 | QC + Integration Reviewer | `gpt-5.6-sol` | `high` |
| P7 | Designer | `gpt-5.5` | `high` |
| P8 | Persona | `gpt-5.5` | `medium` |

Do not change models without user direction. Start vacant panes with:

```bash
herdr agent start <name> --kind codex --pane <pane-id> -- \
  -m <model> -c 'model_reasoning_effort="<effort>"'
```

Before its first prompt, every pane must report the rostered model and effort
through live Codex `/status`; launch arguments alone are not evidence.

## Run

1. Verify `HERDR_ENV=1`. Treat the invoking Codex as P1; prove its actual model
   and effort match the roster before fan-out, or stop for relaunch.
2. Lock an authority-backed applicability matrix for UI, browser, RBAC, and
   persona; P6 independently confirms it. Never mark a gate `N/A` for convenience.
3. Lock source, acceptance criteria, base SHA, ownership, dependencies, checks,
   test data, role matrix, gate owners, and required evidence.
4. Dispatch only ready lanes in dependency waves. Never force P2–P5 to start
   together when an interface or migration is unresolved.
5. Follow the selected shared-tree or worktree protocol. P5 alone publishes the
   attested integration artifact and seed; P1 publishes the review epoch.
6. P1 schedules the browser mutex. When UI, browser, or runtime behavior
   applies, P5 must pass implementation smoke on the published artifact before
   independent review runs `P6 QC → P7 Designer → P8 Persona`. P5 smoke never
   substitutes for a P6 gate.
7. Any code, config, or seed mutation invalidates P5–P8 evidence. P5
   republishes, then the applicable browser flow restarts at P5 smoke.
8. Deliver only when every applicable gate owner passes, all evidence names the
   same attestation tuple, and no blocker remains without explicit user acceptance.

Full topology is eight agent panes, never nine. A reused pane must release its
old agent and restart with the new role's model, effort, and name.
