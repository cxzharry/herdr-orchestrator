# Herdr Orchestrator

`herdr-orchestrator` executes an approved implementation plan through a fixed
Herdr workspace. It uses one controller, one workspace ledger, fixed role names,
immutable receipts, and explicit Compact or Standard gates.

P1 is controller-only. It never implements, tests, integrates, reviews,
commits, pushes, or deploys. Workers and review owners perform delivery work;
P1 only claims the local controller role, forwards same-workspace requests,
runs bounded reducer ticks, and routes evidence.

## Runtime Shape

- `workspace-state.json` is the only mutable runtime ledger.
- `scripts/herdr_identity.py` is the only nested Herdr identity extractor.
- P2-P4 allocate panes from the current workspace with the run root and
  `--no-focus`, then start as fixed warm slots with
  `herdr agent start NAME --kind codex --pane ID -- --yolo`.
- The first prompt creates a worker session; the next reconcile binds it.
- A same-session move inside the same workspace updates pane evidence only.
- A foreign workspace session is never adopted.
- Three misses supersede only the affected lane generation.
- Task text is shown by `render_agent_status.py`, not encoded in role names.
- The watcher appends events and wakes P1; it never transitions lanes.
- Recovery never closes user panes.

## Roles

| Slot | Fixed role |
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

## Compact And Standard

Compact is for approved low-risk local work with one to three path-owned lanes
and deterministic checks. A single function or single file is first-class
Compact work. P5 integration and P6 independent QC are mandatory.

Standard is for integration, UI/browser, auth/RBAC, schema, security,
destructive, production, or independently reviewed work. P5 integrates accepted
worker outputs; P6 reviews; applicable P7, P8, and P9 lanes run concurrently
against the same immutable candidate.

The Superpowers baselines are frozen reference values. After each skill
change, only the Herdr candidate is rerun and stored under its Git SHA.
Herdr is released only when the candidate beats 152s on Compact and 1009s on
the multi-module scenario while passing the same quality gates.

## Checks

```bash
python3 -B -m unittest discover -s scripts -p 'test_*.py' -v
python3 -B scripts/verify_contract.py
python3 -B scripts/verify_assets.py
python3 -B scripts/render_assets.py --check assets/delivery-flow.png
python3 -B scripts/verify_complexity.py
python3 /Users/haido/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
```
