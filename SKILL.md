---
name: herdr-orchestrator
description: Use when coordinating Git-backed product delivery in Herdr across implementation, integration, deployment, QC, UI/UX, persona, Playwright, RBAC, mock-data, or worktree lanes.
---

# Herdr Orchestrator

Run an event-driven delivery loop. P1 owns routing and evidence consistency; it
never implements worker changes or self-approves.

**REQUIRED SUB-SKILL:** Use `herdr` for live pane and agent control.

## Read first

Inspect [the graph](references/delivery-flow.md), call `view_image` on
`assets/delivery-flow.png`, then read [routing](references/routing.md).

Load details only when applicable:

| Predicate | Reference |
|---|---|
| Multiple writers, integration, or isolation | [Git integration](references/git-integration.md) |
| Runtime, browser, RBAC, persona, or deployment | [Review and deployment](references/review-deploy.md) |
| Security-sensitive, destructive, production-critical, or explicitly strict | [High assurance](references/high-assurance.md) |

## Model roster

| Pane | Role | Model | Effort |
|---|---|---|---|
| P1 | Orchestrator | `gpt-5.6-sol` | `high` |
| P2 | Worker 1 | `gpt-5.5` | `medium` |
| P3 | Worker 2 | `gpt-5.5` | `medium` |
| P4 | Worker 3 | `gpt-5.5` | `medium` |
| P5 | Worker 4, then Integration Owner | `gpt-5.6-sol` | `high` |
| P6 | Integration Reviewer | `gpt-5.6-sol` | `high` |
| P7 | QC | `gpt-5.6-sol` | `high` |
| P8 | Designer | `gpt-5.5` | `high` |
| P9 | Persona | `gpt-5.5` | `medium` |

## Run

1. P1 completes brainstorming and planning, then locks applicability,
   dependencies, ownership, checks, deployment topology, and evidence.
2. Dispatch only ready P2-P5 lanes with the brief in `routing.md`.
3. P5 exits its worker session, restarts as Integration Owner, and publishes one
   immutable artifact.
4. Run P5 smoke and P6 Integration Review concurrently. Both must pass before
   P1 authorizes P5 to deploy.
5. P7, P8, and P9 prepare early and run applicable reviews concurrently. Each
   reports to P1 immediately.
6. Promote or deliver only when every applicable blocking gate passes against
   the same artifact.
