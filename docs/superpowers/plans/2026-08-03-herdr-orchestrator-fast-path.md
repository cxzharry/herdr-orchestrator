# Herdr Orchestrator Deterministic Fast Path Implementation Plan

> **For Herdr delivery:** REQUIRED SUB-SKILL: Use
> `herdr-orchestrator` only after this plan is approved.

**Goal:** Make single-function work use a deterministic Compact route while
preserving P5 integration, P6 independent QC, same-workspace recovery, and all
existing quality contracts.

**Architecture:** Add one pure delivery-mode classifier, persist its locked
decision in the run ledger, emit complete prewarm/QC waves from the existing
controller reducer, and repair the worker command boundary to the installed
Herdr CLI. Keep P1 pure; workers, integration, review, and QC remain separate.

**Tech Stack:** Python 3.10 standard library, Herdr CLI 0.7.5, Codex CLI,
Markdown skills, `unittest`, Git worktrees, JSON receipts, and SHA-addressed
benchmark evidence.

---

## Locked Inputs

- Approved spec:
  `docs/superpowers/specs/2026-08-03-herdr-orchestrator-fast-path-design.md`
- Spec SHA-256:
  `b7a89af1d5e1a02a42726f54b9aa5978a60fd0648b05dd3f9ec113c7ce6fba52`
- Repository: `/Users/haido/herdr-orchestrator`
- Plan base: `1b988d99d24c5b501c34becc77243e96a836be9f`
- Delivery mode for this runtime change: `Standard`
- Frozen Superpowers baseline: Compact `152s`, multi-module `1009s`
- Best comparable Herdr result: Compact `143s`, multi-module `776s`
- Frozen baseline files are read-only and must not be rerun or replaced.

## File Map

| Path | Responsibility |
|---|---|
| `scripts/delivery_mode.py` | Pure mode and applicability validation |
| `scripts/test_delivery_mode.py` | Single-function Compact and risk-trigger regressions |
| `scripts/create_control_state.py` | Require and persist mode/risk/applicability |
| `scripts/test_create_control_state.py` | Reject missing or contradictory manifests |
| `scripts/controller_tick.py` | Emit full prewarm and concurrent QC waves |
| `scripts/test_controller_tick.py` | Compact P5/P6 overlap and Standard P7–P9 wave tests |
| `scripts/manage_worker_pool.py` | Current Herdr command boundary and local pane allocation |
| `scripts/test_manage_worker_pool.py` | Exact CLI shape, workspace, focus, and no-close regressions |
| `scripts/test_workflow_scenarios.py` | Public-helper one-lane Compact workflow |
| `SKILL.md` and `references/*.md` | Deterministic fast-path operating contract |
| `README.md` | Supported modes and benchmark policy |
| `scripts/verify_contract.py` | Release markers for the new contract |
| `benchmarks/scenarios/single-function-compact-v1.json` | Locked live micro-canary identity |
| `docs/meta-harness/2026-08-03-herdr-fast-path/**` | Locked rubric, iteration evidence, and outcome |
| `/Users/haido/.codex/skills/writing-plans/SKILL.md` | Codex planning integration |
| `/Users/haido/.agents/skills/writing-plans/SKILL.md` | Agents planning integration |
| `/Users/haido/.codex/skills/herdr-orchestrator` | Reviewed installed skill tree |

## Meta-Harness Strategy

Intent is `IMPROVE`, target composite is `8.5`, target minimum is `7`, and the
maximum is three iterations. Iteration 0 records current evidence: 85 tests in
0.15s, active-session-selector delivery in 4,393s, first implementation at
647–742s, serial post-implementation gates, missing manifest mode, and obsolete
agent-start syntax. Iteration 1 addresses deterministic routing and overlap.
Iteration 2 addresses live CLI/runtime friction found by canary. Iteration 3 is
used only when prior evidence misses target or a narrower latency improvement
remains without weakening a contract.

Implementation parallelism: Parallel lanes.

Reason: mode persistence, reducer wave scheduling, and worker/skill boundary
have disjoint production ownership and converge through public workflow tests.

### Parallelization Strategy

- Can parallelize: yes.
- Lane `mode_contract` (P2): `delivery_mode.py`, control-state creation, tests.
- Lane `controller_waves` (P3): controller reducer and tests.
- Lane `worker_skill_boundary` (P4): worker pool, skill/references, workflow and
  CLI-contract tests, benchmark scenario definition.
- Sequential dependencies: all three lanes require this plan; P5 integrates
  their commits; P6 reviews the exact integration candidate; P7 and P9 run
  concurrently only after P6 PASS.
- Per-lane verification: focused unittest modules named below.
- Final verification: full suite, validators, live isolated single-function
  canary, final Herdr Compact and multi-module candidates.
- Recommended Phase 3 Agent Split Gate input: `Spawn`, because ownership is
  disjoint and the controller must remain orchestration-only.

## Herdr Delivery Contract

```yaml
herdr_delivery:
  backend: herdr
  repository_root: /Users/haido/herdr-orchestrator
  base_sha: 1b988d99d24c5b501c34becc77243e96a836be9f
  mode: Standard
  approved_spec:
    path: docs/superpowers/specs/2026-08-03-herdr-orchestrator-fast-path-design.md
    sha256: b7a89af1d5e1a02a42726f54b9aa5978a60fd0648b05dd3f9ec113c7ce6fba52
  lanes:
    - lane_id: mode_contract
      generation: 1
      eligible_slots: [P2]
      owned_paths:
        - scripts/delivery_mode.py
        - scripts/test_delivery_mode.py
        - scripts/create_control_state.py
        - scripts/test_create_control_state.py
      acceptance:
        - python3 -B -m unittest scripts.test_delivery_mode scripts.test_create_control_state -v
    - lane_id: controller_waves
      generation: 1
      eligible_slots: [P3]
      owned_paths:
        - scripts/controller_tick.py
        - scripts/test_controller_tick.py
      acceptance:
        - python3 -B -m unittest scripts.test_controller_tick -v
    - lane_id: worker_skill_boundary
      generation: 1
      eligible_slots: [P4]
      owned_paths:
        - scripts/manage_worker_pool.py
        - scripts/test_manage_worker_pool.py
        - scripts/test_workflow_scenarios.py
        - scripts/test_p1_contract.py
        - scripts/verify_contract.py
        - SKILL.md
        - README.md
        - references/routing.md
        - references/plan-contract.md
        - references/review-deploy.md
        - references/high-assurance.md
        - references/delivery-flow.md
        - benchmarks/scenarios/single-function-compact-v1.json
      acceptance:
        - python3 -B -m unittest scripts.test_manage_worker_pool scripts.test_workflow_scenarios scripts.test_p1_contract -v
        - python3 -B scripts/verify_contract.py
  reviews:
    P5:
      applicable: true
      role: integration-and-delivery
    P6:
      applicable: true
      role: independent-runtime-review
    P7:
      applicable: true
      role: functional-and-performance-qc
    P8:
      applicable: false
      reason: no visual artifact changes
    P9:
      applicable: true
      role: controller-persona-and-fast-path-review
  deployment:
    topology: local-skill-install-plus-public-github-main
    source_install: /Users/haido/.codex/skills/herdr-orchestrator
    related_integrations:
      - /Users/haido/.codex/skills/writing-plans/SKILL.md
      - /Users/haido/.agents/skills/writing-plans/SKILL.md
    public_update: non-force-forward-push
  required_evidence:
    - implementation receipts for all three lanes
    - P5 integration receipt
    - P6 independent review receipt
    - concurrent P7 and P9 receipts
    - meta-harness iteration feedback and outcome
    - live single-function cold and warm timings
    - SHA-addressed Compact and multi-module candidate result
```

Runtime IDs are bound after plan approval. Every dispatch stays inside the
current Herdr workspace. No runtime action closes a pane.

---

### Task 1: Lock the Meta-Harness Baseline

**Owner:** P1 records orchestration evidence only.

**Files:**

- Create: `docs/meta-harness/2026-08-03-herdr-fast-path/spec.md`
- Create: `docs/meta-harness/2026-08-03-herdr-fast-path/plan.md`
- Create: `docs/meta-harness/2026-08-03-herdr-fast-path/rubric.json`
- Create: `docs/meta-harness/2026-08-03-herdr-fast-path/state/state-0.json`

- [ ] Record the five locked criteria: route correctness, live latency,
  overlap, CLI/recovery compatibility, and frozen-quality compatibility.
- [ ] Record exact baseline commands and receipt timeline evidence.
- [ ] Lock the rubric before implementation and never change its weights.
- [ ] Commit only the plan and meta-harness baseline artifacts.

### Task 2: Add a Deterministic Mode Contract

**Owner:** P2 `mode_contract`.

**Files:**

- Create: `scripts/delivery_mode.py`
- Create: `scripts/test_delivery_mode.py`
- Modify: `scripts/create_control_state.py`
- Modify: `scripts/test_create_control_state.py`

- [ ] Write RED tests proving one deterministic local lane is Compact; each
  Standard trigger produces Standard; unknown flags fail; Compact with P7–P9
  applicability fails; and missing manifest mode fails.
- [ ] Run:
  `python3 -B -m unittest scripts.test_delivery_mode scripts.test_create_control_state -v`
  and require the expected missing-contract failures.
- [ ] Implement `required_mode(risk)` and `validate_mode(mode, risk,
  review_applicability, implementation_lane_count)` without side effects.
- [ ] Require manifest keys `mode`, `risk`, and `review_applicability`; persist
  them in `state["run"]` and reject contradictions before creating directories.
- [ ] Rerun the focused tests and commit `feat: make Herdr delivery mode deterministic`.

### Task 3: Emit Complete Concurrent Waves

**Owner:** P3 `controller_waves`.

**Files:**

- Modify: `scripts/controller_tick.py`
- Modify: `scripts/test_controller_tick.py`

- [ ] Write RED tests proving both Compact and Standard emit P5/P6 PREWARM in
  the first implementation tick, including from COLD slots.
- [ ] Write a RED test where accepted integration and P6 review cause all
  applicable READY P7/P8/P9 lanes to emit in one tick; non-applicable lanes
  must not emit.
- [ ] Run `python3 -B -m unittest scripts.test_controller_tick -v` and capture
  the expected failures.
- [ ] Add only the minimum state predicates and action emission needed; do not
  execute actions or product commands in the reducer.
- [ ] Rerun focused tests and commit `perf: overlap Herdr delivery waves`.

### Task 4: Repair the Live Herdr Boundary and Skill Contract

**Owner:** P4 `worker_skill_boundary`.

**Files:** the P4 owned paths in the delivery contract.

- [ ] Write RED tests requiring this argument order:
  `herdr agent start <name> --kind codex --pane <id> -- --yolo ...`.
- [ ] Add tests proving the adapter uses explicit current-workspace pane IDs,
  `--no-focus`, the run root cwd, and never issues pane close/move.
- [ ] Add a public-helper Compact scenario with one implementation lane, P5
  integration, and P6 independent QC.
- [ ] Rewrite Compact contract wording from “disjoint P2–P4” to “one to three
  path-owned lanes”; require P5/P6; require Standard P7–P9 concurrency.
- [ ] Add the locked single-function scenario JSON with deterministic command,
  fixture digest fields, start/stop definitions, and no baseline mutation.
- [ ] Run the three focused test modules and contract validator, then commit
  `perf: add the one-lane Herdr fast path`.

### Task 5: Integrate and Evaluate Iteration 1

**Owner:** P5 integrates; P6 reviews.

- [ ] P5 validates all three current-generation receipts and integrates only
  their commits into a clean worktree based on the locked SHA.
- [ ] P5 runs focused tests, full unittest discovery, contract, complexity,
  assets, quick validation, and `git diff --check`.
- [ ] P6 reviews exact candidate SHA/tree for P1 product work, missing P5/P6,
  cross-workspace adoption, automatic pane closure, fake-only CLI coverage,
  mode fallthrough, or serialized applicable QC.
- [ ] A finding returns to exactly one owning lane and increments only that
  lane generation. A PASS writes the candidate-bound P6 receipt.
- [ ] Write `feedback/iter-1.json` and `state/state-1.json` with evidence.

### Task 6: Run the Live Single-Function Canary

**Owner:** P7 functional/performance QC. P1 only routes it.

- [ ] Create an isolated test worktree and panes in the current Herdr workspace;
  do not address other workspaces or existing user panes.
- [ ] Cold run: implement one deterministic function through Compact, measure
  dispatch, implementation receipt, integration receipt, P6 receipt, and total
  delivery timestamps.
- [ ] Warm run: reuse only valid same-workspace agents and repeat from a clean
  fixture at the same base.
- [ ] Require acceptance exit 0, clean scope, P5 integration, P6 independent
  PASS, no rework, exact `--yolo`, and no pane close command.
- [ ] If the live command boundary fails, return one P4 finding with the exact
  CLI output. If latency is dominated by a serialized phase, return one P3
  finding with phase timestamps.

### Task 7: Evaluate and Iterate to the Locked Target

**Owners:** owning P2/P3/P4 lane, then P5/P6/P7/P9.

- [ ] Score iteration evidence against the locked rubric; empty evidence is an
  invalid score.
- [ ] Apply one targeted concern per iteration. Do not bundle unrelated
  refactors or weaken quality gates.
- [ ] Stop on SUCCESS at composite at least 8.5 and every criterion at least 7;
  use iteration 3 only if a targeted improvement remains.
- [ ] P7 and P9 evaluate concurrently on the same immutable candidate after P6
  PASS. P9 verifies P1 remains responsive and a single-function plan follows
  the Compact path without user intervention.

### Task 8: Final Performance, Install, and Delivery

**Owner:** P7 measures; P5 validates and delivers.

- [ ] Do not rerun or modify Superpowers. Verify frozen file digests.
- [ ] Rerun only the final Herdr Compact candidate and require `<152s`, shared
  acceptance PASS, and clean scope.
- [ ] Rerun only the final Herdr multi-module candidate and require `<1009s`,
  shared acceptance PASS, deployment verification PASS, and deep immutability.
- [ ] Record a new SHA-addressed result with raw timings, rework, scenario
  identity, and warnings against `143s`/`776s` best prior Herdr results.
- [ ] P5 updates both external `writing-plans` copies identically with the
  required mode/risk/applicability planning block and verifies `cmp -s`.
- [ ] P5 installs the reviewed repository tree to
  `/Users/haido/.codex/skills/herdr-orchestrator` with exact tracked-tree parity.
- [ ] Run full release checks at final HEAD, fast-forward main, push without
  force, and verify `HEAD == main == origin/main`.
- [ ] Write the meta-harness outcome and trace. Report measured cold/warm
  single-function timings and frozen-scenario comparisons without universal
  speed claims.
