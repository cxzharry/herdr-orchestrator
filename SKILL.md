---
name: herdr-orchestrator
description: Use when an implementation plan is approved and Herdr is the selected execution backend; do not use while brainstorming, drafting, or approving the plan.
---

P1 controller only; never implements, tests, integrates, reviews, commits,
pushes/deploys.

Read [plan contract](references/plan-contract.md), then [routing](references/routing.md). Compact stops there. Standard inspects [graph](references/delivery-flow.md) with `view_image` on `assets/delivery-flow.png`. Predicate refs: [Git](references/git-integration.md), [Review/deploy](references/review-deploy.md), [High assurance](references/high-assurance.md).

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

Validate approved logical lanes; reject live pane IDs and do not plan. Bind/recover this chat's scoped P1. On every turn or compaction, run `next_controller_action.py`; P1 uses only Herdr-control helpers. Before prompting, derive `p{slot}_{role}_{task}`, reserve/rename/verify it. Default P1 is `p1_orchestrator`; use `render_agent_status.py` for status output.

Run one bounded scheduler tick: claim the same-workspace P1 inbox, watcher event queue, ownership queue, dispatch ready lanes without waiting, and return. P1 and every worker used by that P1 stay in the same Herdr workspace; another workspace on the same socket is a separate pool. Never adopt, dispatch, auto-move, prompt, receipt, event, or session-share across workspace boundaries. Worker moves out: mark lost and create/bind local replacement. Worker moves inside the same workspace: preserve lane/session.

Compact: P2-P4 change disjoint paths; verifier returns read-only scope, diff, acceptance. Do not start P5-P9. Standard: P5 may prepare integration-owned RED tests at fan-out, integrates after validator-clean receipts, and writes integration and deployment evidence; P6-P9 review only when predicates apply. P1 routes findings to owners. Keep P1 output within 20 lines.
