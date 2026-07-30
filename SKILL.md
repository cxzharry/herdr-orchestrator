---
name: herdr-orchestrator
description: Use when an implementation plan is approved and Herdr is the selected execution backend; do not use while brainstorming, drafting, or approving the plan.
---

# Herdr Orchestrator

Use only when an approved spec and approved execution plan select Herdr and
`HERDR_ENV=1`.

P1 is controller-only. It never implements, tests, integrates, reviews,
commits, pushes, or deploys. A reducer return is internal: respond finally only
after terminal delivery or a real user blocker.

## Routing Kernel

If the same Herdr workspace lacks a live P1, the current ordinary chat claims
`p1_orchestrator`. Chats to P2-P9 forward immutable envelopes to local P1 in
`workspace-state.json`, then signal P1. Never infer role from pane position.

Run one controller tick:

```bash
python3 -B scripts/controller_tick.py
```

Compact applies only to approved low-risk work with disjoint P2-P4 paths,
deterministic checks, no browser/auth/schema/security/deploy scope, and no
required independent review. Otherwise use Standard.

## Fixed Roles

| Slot | Role |
|---|---|
| P1 | `p1_orchestrator` |
| P2 | `p2_impl` |
| P3 | `p3_impl` |
| P4 | `p4_impl` |
| P5 | `p5_integration` |
| P6 | `p6_review` |
| P7 | `p7_qc` |
| P8 | `p8_design` |
| P9 | `p9_persona` |

Compact details: [routing](references/routing.md),
[plan contract](references/plan-contract.md).
Standard details: [git integration](references/git-integration.md),
[review/deploy](references/review-deploy.md),
[high assurance](references/high-assurance.md), and
[delivery graph](references/delivery-flow.md).
