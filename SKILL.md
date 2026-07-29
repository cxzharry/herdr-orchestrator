---
name: herdr-orchestrator
description: Use when an implementation plan is approved and Herdr is the selected execution backend; do not use while brainstorming, drafting, or approving the plan.
---

# Herdr Orchestrator

P1 is a persistent controller only. It routes plans without implementing,
testing, integrating, reviewing, committing, pushing, or deploying. Use `herdr`
for agent control.

## Read first

Validate the [plan contract](references/plan-contract.md), then read
[routing](references/routing.md). Compact stops there; Standard inspects
[the graph](references/delivery-flow.md) with `view_image` on
`assets/delivery-flow.png`.

Details:

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

1. Validate approved logical lanes; reject live pane IDs and do not plan.
2. Bind or recover the socket-scoped `hdr_p1` controller identity.
3. Run one bounded scheduler tick: ingest inbox/events, classify deltas,
   register ownership, dispatch ready lanes, return.
4. Reuse workers; cold-start only missing or incompatible capacity.
5. Give each lane one capsule, applicable references, and its receipt command.
6. Compact gate: P2-P4 change disjoint paths; a Compact verifier returns
   read-only scope, diff, and acceptance evidence. Do not start P5-P9.
7. Standard gate: P5 may prepare integration-owned RED tests at fan-out. P5
   integrates accepted worker outputs after validator-clean receipts.
8. P5 writes integration and deployment evidence; P6-P9 review only when their
   predicates apply. P1 routes findings to owners.

Persist transitions, receipts, and evidence. Keep P1 output within 20 lines.
