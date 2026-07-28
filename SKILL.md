---
name: herdr-orchestrator
description: Execute an approved implementation plan through directly controllable Herdr lanes to verified delivery.
---

# Herdr Orchestrator

P1 routes plans without implementing or self-approving. Use `herdr` for agent
control.

## Read first

Read [routing](references/routing.md) first and select a gate. For a compact
gate, stop there. For a standard gate, inspect
[the graph](references/delivery-flow.md) and call `view_image` on
`assets/delivery-flow.png`.

Load details only when applicable:

| Predicate | Reference |
|---|---|
| Standard-gate integration or isolation | [Git integration](references/git-integration.md) |
| Runtime, browser, RBAC, persona, or deployment | [Review and deployment](references/review-deploy.md) |
| Security-sensitive, destructive, production-critical, or explicitly strict | [High assurance](references/high-assurance.md) |

## Model roster

| Pane | Role | Model | Effort |
|---|---|---|---|
| P1 | Orchestrator | `gpt-5.6-sol` | `high` |
| P2 | Worker 1 | `gpt-5.5` | `medium` |
| P3 | Worker 2 | `gpt-5.5` | `medium` |
| P4 | Worker 3 | `gpt-5.5` | `medium` |
| P5 | Worker 4, then Integration Owner | `gpt-5.5` | `high` |
| P6 | Integration Reviewer | `gpt-5.5` | `high` |
| P7 | QC | `gpt-5.5` | `high` |
| P8 | Designer | `gpt-5.5` | `high` |
| P9 | Persona | `gpt-5.5` | `medium` |

## Runtime contract

1. Validate approved inputs; do not reopen discovery or planning.
2. Select the compact or standard gate defined in `routing.md`.
3. Reuse workers; cold-start only missing or incompatible capacity.
4. Dispatch only ready lanes with `--yolo` and roster model/effort.
5. Give each lane one capsule, applicable references, and its receipt command.
6. Compact gate: workers change disjoint paths; non-mutating P1 reruns locked
   checks and verifies local delivery. Do not start P5-P9.
7. Standard gate: start P5 at fan-out, read any locked executable acceptance
   harness, then prepare RED integration work. Accept current receipts before
   it consumes worker bytes. P5 smokes and P6 reviews the same artifact.
8. Deliver only after applicable gates pass.

Use live state for progress. Persist only material transitions, terminal
receipts, and evidence references. P1 output is at most 20 physical lines:
decisions, blockers, identities, and next transition.
