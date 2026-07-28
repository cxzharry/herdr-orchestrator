# Routing contract

## Preflight

Confirm `HERDR_ENV=1`, inspect the workspace/panes/agents, and use explicit IDs.
P1 proves `gpt-5.6-sol/high` through live Codex `/status`; launch arguments only
show intent. Before prompting any new role, verify its live model and effort.

P1 completes the full brainstorming workflow on every run, including written
spec review, then uses `superpowers:writing-plans`. Herdr is already the
user-selected execution mode, so do not ask whether to use another executor.
Lock authoritative sources, acceptance criteria, base SHA, ownership,
dependencies, checks, mock/seed data, system roles, deployment topology, and
applicability for UI, browser, RBAC, persona, and high assurance.

## Dispatch

Dispatch only dependency-ready lanes. Independent lanes may start together;
schema, migration, API, or shared-contract consumers wait for their producer.

Every lane brief has this exact shape:

```text
ROLE:
GOAL:
REQUIRED SKILLS:
INPUTS / BASE SHA / ARTIFACT DIGEST:
WRITABLE PATHS:
PREREQUISITES:
DONE EVIDENCE:
DO NOT:
STOP / ESCALATE WHEN:
```

Name skills in invocation order and attach observable conditions. Do not load
conditional skills before their condition occurs.

| Role or event | Skill route |
|---|---|
| P1 design | `superpowers:brainstorming` |
| P1 after design approval | `superpowers:writing-plans` |
| P2-P5 behavior change | `superpowers:test-driven-development` |
| Implementation failure | `superpowers:systematic-debugging` |
| P5 isolated Git lanes | `superpowers:using-git-worktrees` |
| Owning lane receives a finding | `superpowers:receiving-code-review` |
| Any handoff, PASS, publish, or completion claim | `superpowers:verification-before-completion` |
| Branch disposition not locked | `superpowers:finishing-a-development-branch` |

Never invoke these inside Herdr:

- `dispatching-parallel-agents`
- `subagent-driven-development`
- `executing-plans`
- `requesting-code-review`

They create a nested scheduler or reviewer. P1 and the fixed Herdr panes replace
those procedures.

## Phase transitions

P5 must restart before every role change. At any integration wave boundary, P5
may restart as Integration Owner and publish a prerequisite `wave_base_sha`.
When dependent Worker 4 work remains, P5 exits the integration role and must
restart as Worker 4 from the published wave base. After the final Worker 4
handoff, P5 restarts as Integration Owner for final publication. Each clean
session receives only the locked contract and accepted handoffs.

After final publication, P5 smoke and P6 review run concurrently. P6 is
read-only and returns a bounded PASS or finding package, preventing P5 from
self-approving integration.

P7-P9 may prepare as soon as the artifact exists. After deployment they run
applicable reviews concurrently and send receipts to P1 without waiting for
each other. A downstream action starts when its own prerequisites pass; side
work does not create a global barrier.

Reviewers never fix production code. P1 routes findings to an owning lane. The
same blocker twice without new evidence triggers reassignment or user
escalation, not another unbounded retry.
