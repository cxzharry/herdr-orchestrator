# Herdr Orchestrator

`herdr-orchestrator` is a Codex delivery skill for executing an **approved
implementation plan** through directly controllable [Herdr](https://herdr.dev)
panes, from implementation through review, integration, verification, and
deployment.

It complements [Superpowers](https://github.com/obra/superpowers): use
Superpowers for brainstorming and plan writing, then hand the approved logical
plan to Herdr Orchestrator as the execution backend.

> This skill does not brainstorm, design the product, write the implementation
> plan, or approve its own work.

## What this skill helps with

The skill gives one controller, P1, direct control of a warm P2-P4 pool and
on-demand P5-P9 agents:

| Pane | Responsibility |
|---|---|
| P1 | Validate the approved plan, route work, and aggregate evidence |
| P2-P4 | Parallel implementation lanes |
| P5 | Additional worker, integration owner, and deployment owner |
| P6 | Independent integration reviewer |
| P7 | Functional QC when applicable |
| P8 | UI/design review when applicable |
| P9 | Persona/RBAC review when applicable |

It adds:

- logical lanes in the plan instead of fragile live pane IDs;
- bounded parallel implementation with path ownership and dependencies;
- warm P2-P4 reuse instead of starting every Codex process from scratch;
- direct interruption, redirection, and inspection of each Herdr agent;
- terminal receipts and independently rerun acceptance checks;
- conditional review gates instead of always starting all nine roles;
- recovery when P1 changes workspace or a worker pane moves or closes;
- socket-scoped, locked pool state so concurrent controllers cannot overwrite
  worker identity.

Every Codex worker created by the current runtime is launched with native
`--yolo`. Use this only in repositories and environments where bypassing
interactive approval is acceptable.

## When to use it

Use Herdr Orchestrator when all of the following are true:

1. A spec and implementation plan already exist.
2. The user has approved the plan.
3. The plan explicitly selects Herdr as its execution backend.
4. The work benefits from parallel implementation, independent review,
   recovery, or deployment evidence.

Do not use it:

- during brainstorming or plan approval;
- for an unapproved or contradictory plan;
- for a tiny task that one agent can finish faster inline;
- when multiple workers would need to edit the same tightly coupled paths;
- outside a Herdr-managed pane (`HERDR_ENV` must equal `1`).

## Compact and Standard delivery

The skill chooses one of two delivery gates.

### Compact

For approved, low-risk local work with one to three disjoint owned paths,
deterministic checks, no UI/browser/auth/schema/security/external-state scope,
and no deployment target.

```text
P1 -> warm P2/P3/P4 in parallel
   -> P1 reruns scope and deterministic checks
   -> verified local delivery
```

P5-P9 are not started.

### Standard

For UI/browser, integration, deployment, auth/RBAC, schema/migration,
security-sensitive, destructive, production-critical, or independently
reviewed work. P5-P9 are started only when their predicate is true.

Standard is intentionally more expensive: it buys integration and review
evidence, not raw latency.

## Quality and speed compared with Superpowers

Herdr Orchestrator is not automatically faster on every task. The winning
configuration is a **warm P2-P4 pool plus correct Compact/Standard routing**.
Cold-starting a full Standard topology for a small deterministic task is slower
than the Superpowers baseline.

Paired one-trial local benchmarks run on 2026-07-28 used the same task inputs
and shared acceptance checks:

| Scenario | Superpowers baseline | Herdr Orchestrator | Result |
|---|---:|---:|---|
| Three disjoint low-risk edits | 152s | 112s, Compact warm pool | 26.3% faster; both verified, zero rework |
| Multi-module canary deployment | 1009s | 841s, warm lanes + on-demand review | 16.65% faster; both passed acceptance |

In the multi-module canary, both modes passed the shared acceptance suite. A
separate locked deep-immutability probe failed on the baseline and passed on the
final Herdr flow. This is evidence of a quality improvement for that scenario,
not a claim that every Herdr run is universally better.

The same small benchmark also measured why routing matters:

| Herdr mode | Wall clock |
|---|---:|
| Standard, cold | 761s |
| Compact, cold | 299s |
| Compact, warm pool | 112s |

Cross-workspace recovery was also exercised for pool adoption, moved-pane
rebinding, closed-worker replacement, and delayed first-session binding. The
current repository has 45 source tests; 22 of them are the focused worker-pool
suite.

Inspectable result snapshots:

- [`benchmarks/2026-07-28-compact-runtime.json`](benchmarks/2026-07-28-compact-runtime.json)
- [`benchmarks/2026-07-28-multi-module.json`](benchmarks/2026-07-28-multi-module.json)

These are local single-run measurements, not a universal benchmark. They were
recorded with Herdr 0.7.5. The result snapshots expose the scenario inputs,
acceptance, timing, and quality outcomes used by this README; the compact
snapshot also records per-mode rework, while the multi-module snapshot marks
unrecorded baseline rework explicitly. The original workspace and machine
profile are not published. Treat the figures as directional rather than
independently reproducible. Runtime recovery and test counts were re-verified
at commit `d721108`.

Total-token superiority has **not** been proven because the Superpowers
baseline did not expose child-session usage. Static orchestration output was
smaller, but that is not equivalent to lower end-to-end token usage.

Quality improves through stronger controls rather than “more agents”:

- approved inputs and acceptance are locked before runtime binding;
- every lane has owned scope, generation, identity, checks, and a receipt;
- P5 integration and P6 review inspect the same artifact;
- stale, moved, closed, or replaced workers cannot silently satisfy a lane;
- a failed lane can be replaced without discarding unrelated worker progress.

## Requirements

- macOS or Linux;
- Herdr installed and running;
- the official `herdr` agent-control skill installed (the pinned installation
  below uses Herdr tag `v0.7.5`);
- Codex available inside a Herdr pane;
- Python 3.10 or newer;
- access to the model names used by the current roster:
  `gpt-5.6-sol` for P1 and `gpt-5.5` for P2-P9.

Install Herdr with Homebrew:

```bash
brew install herdr
```

Other installation methods are documented by the
[official Herdr install guide](https://herdr.dev/docs/install/). Review the
installer before running a remote installation script.

Before installing either skill, run a complete command and runtime preflight:

```bash
for command_name in git python3 herdr codex curl mktemp install; do
  command -v "$command_name" >/dev/null || {
    printf 'Missing required command: %s\n' "$command_name" >&2
    exit 1
  }
done
python3 -c 'import sys; assert sys.version_info >= (3, 10), sys.version'
if command -v shasum >/dev/null; then
  :
elif command -v sha256sum >/dev/null; then
  :
else
  printf 'Missing SHA-256 tool: install shasum or sha256sum\n' >&2
  exit 1
fi
```

Install Herdr's official agent-control skill from the pinned `v0.7.5` source
and verify its SHA-256 before installing it:

```bash
verify_sha256() {
  expected_sha256="$1"
  verified_file="$2"
  if command -v shasum >/dev/null; then
    printf '%s  %s\n' "$expected_sha256" "$verified_file" |
      shasum -a 256 -c -
  else
    printf '%s  %s\n' "$expected_sha256" "$verified_file" |
      sha256sum -c -
  fi
}
agent_skill_tmp="$(mktemp)"
trap 'rm -f "$agent_skill_tmp"' EXIT
curl -fsSL \
  https://raw.githubusercontent.com/ogulcancelik/herdr/v0.7.5/SKILL.md \
  -o "$agent_skill_tmp"
verify_sha256 \
  bc653fffc67918f2634aac201bc1a8a133eaa8264fb1ed7feb1a0a77ff238329 \
  "$agent_skill_tmp"
herdr_skill_root="${AGENTS_HOME:-$HOME/.agents}/skills/herdr"
mkdir -p "$herdr_skill_root"
install -m 0644 "$agent_skill_tmp" "$herdr_skill_root/SKILL.md"
verify_sha256 \
  bc653fffc67918f2634aac201bc1a8a133eaa8264fb1ed7feb1a0a77ff238329 \
  "$herdr_skill_root/SKILL.md"
```

The [official Herdr agent-skill guide](https://herdr.dev/docs/agent-skill/)
also documents an unpinned `npx skills` installation for users who prefer to
track the latest release.

The current launch validator requires the configured model names and
`--yolo`. If your Codex environment uses different model identifiers, update
these files together:

- `SKILL.md` — model roster;
- `references/routing.md` — launch commands;
- `scripts/manage_worker_pool.py` — launch arguments and invariant;
- `scripts/test_manage_worker_pool.py` — expected launch behavior.

Then rerun the full test command below. There is no separate model-access probe
in this repository; an unavailable model is a failed worker launch.

## Install the skill for Codex

```bash
skills_dir="${CODEX_HOME:-$HOME/.codex}/skills"
skill_root="${CODEX_HOME:-$HOME/.codex}/skills/herdr-orchestrator"
mkdir -p "$skills_dir"
git clone https://github.com/cxzharry/herdr-orchestrator.git "$skill_root"
```

For a reproducible runtime snapshot, check out the commit used for the latest
cross-workspace verification:

```bash
git -C "$skill_root" checkout d721108
```

That commit predates this README but contains the same runtime files. Omit the
checkout to use the latest `main`, then rely on the verification commands
instead of the historical benchmark.

Run verification **after** selecting latest `main` or the pinned commit:

```bash
cd "$skill_root"
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 scripts/verify_assets.py
```

Start or attach to Herdr. In a Herdr shell pane, verify the environment and
start P1 with the rostered model:

```bash
herdr
test "${HERDR_ENV:-}" = 1
codex --yolo --model gpt-5.6-sol \
  -c 'model_reasoning_effort="high"'
```

The controller creates missing worker panes. You do not need to pre-create
P2-P9. P2-P4 are retained as the warm pool. P5-P9 are started only when
applicable. No agent pane is auto-closed; close panes manually if you no longer
want them.

The full discovery command above currently runs 45 tests. The focused installed
worker-pool suite runs 22:

```bash
python3 -m unittest scripts.test_manage_worker_pool -v
```

## Use without modifying Superpowers

After the plan has been approved, give Codex an explicit handoff:

```text
The implementation plan at <absolute-plan-path> is approved and selects Herdr.
Use $herdr-orchestrator to execute it through the applicable review and
deployment gates. Do not brainstorm or rewrite the plan.
```

The approved plan must contain the `## Herdr Delivery Contract` described in
[`references/plan-contract.md`](references/plan-contract.md). If it does not,
the runtime must stop as `BLOCKED`; it must not invent the missing planning
decisions.

## Integrate with upstream Superpowers

### Where the integration belongs

Do **not** modify `using-superpowers` and do not add a startup hook.
`using-superpowers` decides whether a skill applies; it does not own the
post-plan execution choice.

The integration point is Superpowers'
`skills/writing-plans/SKILL.md`, after the complete plan is written and before
its normal execution handoff.

The behavior delta from upstream Superpowers is exactly:

1. When Herdr is selected, the plan header points to `herdr-orchestrator`
   instead of `subagent-driven-development` or `executing-plans`.
2. While writing the plan, the planner reads this repository's plan contract
   and writes logical lanes and review predicates. It must not write live
   agent, pane, session, or lease IDs.
3. The planner waits for explicit user approval.
4. After approval, it invokes `herdr-orchestrator` instead of offering the
   normal Superpowers execution choices.
5. When Herdr is not selected, original Superpowers behavior remains unchanged.

### Recommended: use an AGENTS.md overlay

This avoids editing plugin files that an upstream update may overwrite:

```markdown
## Herdr execution backend

When the user selects Herdr for delivery, the implementation plan must include
the installed `herdr-orchestrator` plan contract. Define logical lanes, owned
paths, dependencies, checks, P2-P9 applicability, deployment topology, and
evidence. Never bind live pane or session IDs during planning.

Wait for explicit plan approval. After approval, invoke
`herdr-orchestrator`; do not offer Superpowers'
`subagent-driven-development` or `executing-plans` choices for that plan.
Do not invoke Herdr Orchestrator during brainstorming or plan writing.
```

Place that block in the applicable project `AGENTS.md`, or in the user's global
Codex instructions if every project should support this handoff.

### Alternative: patch `writing-plans`

If you maintain a Superpowers fork, add the following behavior to
`skills/writing-plans/SKILL.md`.

After its normal plan-header template:

```markdown
When Herdr is the selected execution backend, replace the agentic-workers
blockquote with:

> **For Herdr delivery:** REQUIRED SUB-SKILL: Use
> `herdr-orchestrator` only after this plan is approved.
```

Before Superpowers' `## Execution Handoff` section:

```markdown
## Herdr Planning Handoff

When the user selected Herdr delivery, read the installed
`herdr-orchestrator` plan contract and add its `## Herdr Delivery Contract`
section before saving the plan. Define logical lanes, P2-P9 role
applicability, ownership, dependencies, acceptance, review matrices, deployment
topology, and evidence. Do not bind live agent, pane, session, or lease IDs
during planning.

Ask the user to approve the saved plan or request changes. Do not start
implementation while approval is pending. Once the user approves the plan,
invoke `herdr-orchestrator`; do not offer the Superpowers execution choices
below.
```

Finally, scope the original execution handoff:

```markdown
## Execution Handoff

When Herdr is not the selected backend, offer the normal Superpowers execution
choice after saving the plan.
```

Reapply or rebase this patch after upgrading Superpowers. The AGENTS.md overlay
is less maintenance-heavy.

## Agent operating guide

The agent running this skill should follow this sequence:

1. Confirm it is P1 in a Herdr-managed pane.
2. Read `SKILL.md`, validate `references/plan-contract.md`, then read
   `references/routing.md`.
3. Reject unapproved, stale, contradictory, or physically bound plans.
4. Select Compact or Standard from the locked risk predicates.
5. Reuse compatible warm P2-P4 workers before creating new panes.
6. Start every new Codex worker with `--yolo` and the rostered model/effort.
7. Dispatch only dependency-ready logical lanes with one bounded capsule each.
8. Accept terminal receipts and fresh checks, not chat summaries.
9. Run only the applicable integration, review, QC, design, persona, and
   deployment gates.
10. Report accepted identities, evidence, blockers, and the next transition;
    do not reopen planning.

Use the canonical path-aware invocation in
[Use without modifying Superpowers](#use-without-modifying-superpowers). Review
and deployment run only when the approved contract marks those gates
applicable.

## Recovery behavior

- P1 may move to another Herdr workspace and still reuse the pool.
- A worker moved with the same session is rebound to its new pane.
- A closed P2-P4 slot is recreated without replacing healthy siblings.
- If an active Standard lane in P5-P9 disappears, the receipt waiter reports it
  lost after three live checks. P1 preserves its shared-worktree evidence,
  supersedes only that generation, starts a replacement, and rejects any late
  receipt from the lost session.
- Same-contract busy workers are attached and observed, not double-dispatched.
- Another contract cannot hijack busy workers.
- A first prompt may create the Codex session; binding waits briefly and must
  reach `action=bound` before the lane is leased or its receipt is accepted.
- A failed replacement is renamed as an orphan and its pane is left open; the
  next prepare retries the missing slot.

## Repository map

- [`SKILL.md`](SKILL.md): trigger, roster, and top-level runtime contract.
- [`references/plan-contract.md`](references/plan-contract.md): required logical
  plan shape.
- [`references/routing.md`](references/routing.md): dispatch, pool, gate, and
  receipt rules.
- [`references/git-integration.md`](references/git-integration.md): Standard
  integration/isolation rules.
- [`references/review-deploy.md`](references/review-deploy.md): runtime,
  browser, persona, and deployment gates.
- [`references/high-assurance.md`](references/high-assurance.md): strict and
  production-critical additions.
- [`assets/delivery-flow.png`](assets/delivery-flow.png): nine-pane delivery
  graph.
- [`scripts/`](scripts): state, receipt, pool, validation, and test helpers.
