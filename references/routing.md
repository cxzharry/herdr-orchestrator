# Routing contract

## Entry and preflight

This runtime starts only from an approved spec and approved execution plan.
P1 validates their paths and digests, acceptance, locked base SHA, ownership,
dependencies, applicable review matrices, deployment topology, and required
evidence. Missing, stale, or contradictory inputs return BLOCKED upstream.
Do not brainstorm, redesign the product, or write a plan.

P1 is a persistent controller only. P1 never implements, tests, integrates,
reviews, commits, pushes, or deploys. On every turn or compaction, run
`next_controller_action.py`; do not continue from memory. A P1 turn is one
bounded scheduler tick: claim this chat's controller scope and socket-scoped P1
inbox, claim watcher event queue entries, reconcile ownership queue state,
dispatch all ready lanes without waiting, and return active, queued, blocked,
and newly dispatched work.

Confirm `HERDR_ENV=1`. Inspect the named workspace and current agents with the
bounded preflight below. Never infer an ID from visual pane order and do not
substitute a layout command:

```bash
test "${HERDR_ENV:-}" = 1 &&
test "$(git -C "$root" rev-parse HEAD)" = "$base_sha" &&
git -C "$root" diff --quiet -- &&
herdr workspace get "$workspace_id" &&
herdr agent list
```

Create one `herdr-run-manifest/v1` JSON containing the run identity and lane
list, then initialize the ledger in one command:

```bash
python3 <skill-root>/scripts/create_control_state.py \
  --manifest "$run_dir/lane-manifest.json" \
  --control-state "$run_dir/control-state.json"
```

The helper creates `receipts/` and `evidence/`. The ledger stores only material
transitions and no secrets. Each lane records its stable `lane_id`, generation,
role, live agent/pane/session, input identity, owned scope, state, and receipt
path. Do not handcraft control-state JSON.

## Dynamic live names

Live Herdr names are display handles, not stable identity. Stable identity is
controller scope, slot, lane, generation, pane, session, root, base, and owned
scope. Format every visible name as `p{slot}_{role}_{task}`. The default
controller visible name is `p1_orchestrator`; concurrent spaces append the
shortest deterministic suffix. Status stays in Herdr state, not the name.
Use `render_agent_status.py`; do not hand-format or poll broad status.

First tick: ensure P1 name -> migrate legacy live lanes -> process events.
Dispatch: register lane -> reserve name -> rename -> verify -> publish ->
prompt. Before each lane prompt, call `assign_agent_name.py` to
reserve/rename/verify the expected name, then prompt only the verified name.
Name selection must consider live Herdr names and pending registry reservations
in `runtime_registry.py`; do not rename another live agent.

Approved routing metadata supplies `display_role` and `display_slug`. If absent,
derive from role and lane ID; never guess product meaning. Legacy `hdr_pN`
names map only to slots. Legacy first-tick migration may rename working P1-P9
agents without resetting sessions and preserves `dispatch_agent_name`. Outside
that migration, do not rename a working lane merely to improve wording.
Repair only when live state drifts from the expected name; route
`LANE_NAME_DRIFT` to the same assignment helper.

## Launch invariant

After splitting a pane, inspect its process until an available shell is
reported; do not assume the pane is immediately ready. Parse the returned
opaque pane ID. Start every new Codex agent with native `--yolo`.
If `agent start` still returns `agent_pane_busy` after shell readiness, inspect
the same pane and retry once when only its shell remains; do not split another
pane.

Use medium effort for P2-P4:

```bash
herdr agent start "$agent_name" --kind codex --pane "$pane_id" -- \
  --yolo --model gpt-5.5 -c 'model_reasoning_effort="medium"'
```

Use high effort for P5-P8:

```bash
herdr agent start "$agent_name" --kind codex --pane "$pane_id" -- \
  --yolo --model gpt-5.5 -c 'model_reasoning_effort="high"'
```

Use medium effort for P9. If P1 itself must be replaced, use the same
`-- --yolo` launch boundary with `--model gpt-5.6-sol` and
`model_reasoning_effort="high"`.

Parse `argv`, pane, and session from Herdr's response, then match the Codex model
footer in the pane tail. Use `agent get` and the same tail when launch evidence
is incomplete. A wrong model, effort, missing `--yolo`, or mismatched identity
is a failed launch, not a usable lane.
Before dispatch, confirm the agent has a live session and its pane shows the
Codex input prompt. The only exception is a newly reserved pool worker whose
ledger proves the current name, pane, terminal, and `input_ready=true` while
`rebind_pending=true`: send its first capsule without a session, then run
`bind` to capture that session. The CLI bind waits up to five seconds for all
first sessions. If it still returns `action=pending`, the affected lane is not
leased: observe the session transition and rerun bind before accepting any
receipt. If the first submitted prompt does not appear, resend it once to the
same terminal identity.

Disable an external MCP server at launch only when its capability is explicitly
outside the lane contract, using scoped
`-c 'mcp_servers.<name>.enabled=false'`. Never change the global configuration.
Apply those scoped flags to every applicable P5-P9 launch as well as P2-P4;
do not omit them merely because a lane is on demand.

## Prompt and wait contract

Each lane receives one prompt capsule, not P1's conversation or the full plan.
Include only the locked input path plus digest, owned scope, prerequisites,
acceptance, terminal checks, applicable skill names, and receipt path. Load
only the conditional references whose predicates are explicitly true in the
approved plan. Do not load a reference because it might become relevant.

`INPUT IDENTITY` always gives the approved input's absolute path and digest.
`PREREQUISITES` explicitly marks each owned path as existing or intentionally
new; absence of an intentionally new path is not a blocker. After approved
inputs are locked, do not search memory, history, or prior runs for contract
shape.

Keep a dispatch capsule at or below 1,500 bytes unless exact acceptance text
alone exceeds that bound. Keep every P1 scenario explanation and operational
report at or below 20 lines unless a structured finding requires more. Report
only decisions, blockers, accepted identities, and the next
transition; never restate static rules or enumerate non-applicable evidence.

Use Herdr reads for bounded live progress and terminal receipts for completion.
Refer to large logs and screenshots by path and digest; include only the
relevant finding excerpt. Do not relay progress summaries between agents.

Submit independent lane prompts without `--wait`. A validator-clean terminal
receipt is the completion signal; a later chat final is not required. P1 does
not call await_receipts.py or any long synchronous receipt wait. Do not call
`herdr agent wait` after dispatch when a receipt path exists. Do not poll
workers sequentially, reread settled chat, or hold `agent prompt --wait` after
terminal receipts exist.

Each Standard delivery starts one run-scoped watcher process, not an agent and
not a daemon. The watcher observes receipt paths and live session identity,
then appends immutable events for terminal receipt, moved pane, lost lane, or
watcher failure into the watcher event queue. It sends only an async signal
containing the event ID when P1 is idle or done; when P1 is busy or blocked, the
event stays queued.

If the same session_id appears under a new pane_id after a pane move, the
watcher emits `LANE_MOVED`; P1 rebinds the same generation on the next
scheduler tick. A terminal receipt already on disk wins even if the agent was
then closed. If a requested session is absent for three live checks, the
watcher emits `LANE_LOST`. P1 marks only that generation SUPERSEDED, increments
the lane, starts a replacement with the locked input identity, and continues
unrelated lanes. Reject any late receipt from the lost session.

Do not inspect prior benchmark answers, unrelated run directories, superseded
receipts, or old conversations for response shape. Only current-contract
approved inputs and accepted receipts may influence routing.
Loading a false-predicate reference is a contract failure; correct it before
dispatch.

## Dispatch capsule

Dispatch only READY lanes. Independent lanes may start together; consumers of
schema, migration, API, or shared contracts wait for accepted producer inputs.

Every capsule has this exact shape:

```text
ROLE:
GOAL:
REQUIRED EVENT SKILLS:
CONTRACT / LANE / GENERATION:
INPUT IDENTITY:
OWNED SCOPE:
PREREQUISITES:
ACCEPTANCE:
TERMINAL CHECKS:
RECEIPT PATH:
DO NOT:
STOP / ESCALATE WHEN:
```

`RECEIPT PATH` must contain the exact `write_lane_receipt.py` command for the
current lane. The worker supplies only output identity, covered acceptance, and
checks; the helper copies contract, generation, role, agent, pane, session, and
input identity from control-state. Never ask a worker to handcraft receipt JSON:

```bash
python3 <skill-root>/scripts/write_lane_receipt.py \
  --control-state "$run_dir/control-state.json" --lane "$lane_id" --status PASS \
  --output diff_sha256="$diff_sha256" \
  --acceptance "$covered_acceptance" --check "$check_command=PASS"
```

Name only event skills that apply now:

| Event | Skill |
|---|---|
| Implement behavior | `test-driven-development` |
| Unexpected failure | `systematic-debugging` |
| Isolated Git lane | `using-git-worktrees` |
| Owning lane receives a finding | `receiving-code-review` |
| Any terminal claim | `verification-before-completion` |
| Branch disposition not locked | `finishing-a-development-branch` |

Never invoke these inside Herdr:

- `brainstorming`
- `writing-plans`
- `dispatching-parallel-agents`
- `subagent-driven-development`
- `executing-plans`
- `requesting-code-review`

Herdr owns agent lifecycle, parallelism, and independent review. Do not create a
nested scheduler or reviewer inside a lane.

## Worker reuse policy

Prefer a compatible warm P2-P4 lane over starting another Codex process. A warm
lane is an idle Herdr agent whose launch response proves `--yolo`,
`gpt-5.5/medium`, scoped MCP settings, and a pane owned by this delivery pool.
P5-P9 remain on demand; keeping high-effort review lanes warm wastes context on
work that may not apply.

Worker reuse is not a delivery gate. Compact and Standard remain the only
delivery gates. Resolve the installed skill root, then prepare capacity with:

```bash
python3 <skill-root>/scripts/manage_worker_pool.py prepare --contract-id \
  "$contract_id" --cwd "$root" --count "$worker_count"
```

Use the returned agent, pane, session, and reset state directly. `action=reused`
means no split, start, reset, or model-check turn is needed. `action=reset`
returns replacement sessions already input-ready. `bind` remains only as a
compatibility check after an interrupted older pool operation:

```bash
python3 <skill-root>/scripts/manage_worker_pool.py bind --contract-id \
  "$contract_id"
```

The default ledger is
`~/.codex/herdr-pools/active-<socket-key>.json`: scoped by controller inside one
Herdr socket. Live `p2_worker_ready`-style names are display handles. P1's
workspace and pane are controller locations, not pool ownership. A P1 recreated
in another workspace must run `prepare` normally; the helper atomically adopts a
unique legacy workspace ledger, resolves workers by slot, terminal, and
session, and keeps their current panes. Never copy a ledger to the new
workspace or move healthy workers just to colocate them with P1.

`prepare` updates a moved worker's pane when its session is unchanged. It
recreates only a closed slot and preserves healthy siblings. It still refuses
busy workers from another contract or a mismatched session; those are active
ownership conflicts, not recovery cases. For the same contract, stable busy
workers return `status=busy, action=attached`. Resume tracking their current
lanes; do not dispatch a second capsule until they settle. The helper locks the
complete pool transaction, so a second P1 waits instead of overwriting newer
identity state. Closed-slot recovery records its pane reservation before
launch. A failed launch is renamed as an orphan without closing its pane; the
next prepare retries the slot instead of colliding with the partial worker.

After approved-input identity and gate eligibility pass, P1 may start the
required number of empty P2-P4 agents while it finishes lane-specific
validation. `status=ready` means startup/trust gates are cleared and every
worker is at its input prompt; do not repeat pane reads or press Enter. A first
launch may remain `rebind_pending` until its first capsule creates a session;
dispatch the first capsule before `bind`. An early `bind` returns
`action=pending` without failing; after fan-out, require `action=bound` before
leasing the lanes or accepting receipts.
Warming creates no product prompt and grants no scope. Every
assignment creates a `lease_id` bound to contract, lane, generation, agent,
pane, session, exact root/base, and owned paths. One live lease owns one lane;
never multiplex unrelated work through an occupied agent.

Reuse rules:

- Within the same approved delivery contract, retain useful project context and
  send only the next bounded capsule. Do not reread static skills or references
  unless a new event makes them applicable.
- Before leasing a pool pane to a different contract, send `/new` without
  `--wait`. The first capsule must `cd` to the exact root, prove base and owned
  scope before mutation, and P1 must capture the new session identity after the
  lifecycle transition.
- Release a lease only after its accepted checkpoint persists outside chat and
  the agent is settled. A formatting-only chat failure does not invalidate
  verified Git work.
- If reset, identity, root, scope, or clean-state proof is missing; the lane is
  blocked; or prior context could affect acceptance, cold-start the lane in a
  new pool pane. Preserve the old pane until its useful work is checkpointed.

Pool reuse is an optimization, never an acceptance shortcut. Current generation,
live identity, scoped diff, and fresh checks remain mandatory. The pool removes
process startup and repeated static-context loading while preserving direct
interrupt, redirect, and lane-level recovery.

## Compact gate

Use the compact gate only when every condition is locked true:

- no deployment target and verified local delivery is accepted;
- approved low risk, clean shared tree, and one to three disjoint owned paths;
- deterministic local checks cover acceptance;
- no schema, migration, auth, security, RBAC, UI, browser, external-state,
  destructive, production-critical, or high-assurance scope;
- no integration mutation, packaging, conflict resolution, or independent
  reviewer is required by the approved plan.

If any condition is false or becomes false, use the standard gate.

The compact topology is:

```text
P1 scheduler tick -> ready P2/P3/P4 workers in parallel
   -> Compact verifier reads scope, diff, and deterministic evidence
   -> P1 records the verifier receipt and reports local delivery
```

The Compact verifier is read-only and owns the deterministic acceptance check.
P1 records only the verifier result and routing state. Do not start P5-P9.
Run the worker reuse policy before cold-starting missing capacity.
Use a smaller socket-scoped scheduler state containing controller, delta,
implementation lane, verifier lane, ownership queue, and receipt identities.
Live Herdr identity plus the scoped Git diff is the checkpoint.
If P1 restarts or a lane needs replacement, inspect that checkpoint and upgrade
to the standard gate before accepting more work.

Compact preflight is limited to `HERDR_ENV`, current pane/layout and agent list,
locked base SHA, clean index/tree, owned paths, and the exact acceptance
command. Do not run broad CLI help, workspace inventories, per-file hashes, or
unrelated source inspection after those facts are confirmed.

Because compact scope permits no external-state or UI work, disable the current
local external MCP servers for compact workers at launch:

```bash
-c 'mcp_servers.pencil.enabled=false' \
-c 'mcp_servers.notion.enabled=false' \
-c 'mcp_servers.figma.enabled=false' \
-c 'mcp_servers.atlassian.enabled=false' \
-c 'mcp_servers.openaiDeveloperDocs.enabled=false'
```

Each worker returns one compact terminal message of at most six physical lines,
72 columns per line, and 600 bytes total:

```text
COMPACT PASS <contract>/<lane>/g<generation>
INPUT <short digest>
PATHS <comma-separated owned paths>
DIFF <sha256>
CHECKS <command>=PASS[; ...]
BLOCKER: none
```

The Compact verifier obtains agent, pane, and session from live Herdr state and
returns a receipt only after matching that identity, owned paths, current
generation, input identity, exact diff, and fresh check output. P1 reports the
accepted compact identities after recording that receipt; no P5/P6 session is
required.

Read only the compact terminal tail:

```bash
herdr agent read "$agent_name" --source recent-unwrapped --lines 12
```

If `COMPACT PASS` is absent, keep the lane queued until the watcher or a later
scheduler tick reports a terminal signal. Do not load full terminal history or
raw logs unless a finding requires them.

Any blocker, finding, scope expansion, replacement, non-determinism, or failed
Compact verifier check upgrades the run to the standard gate. Preserve the
compact evidence, increment only affected generations, and require
validator-clean JSON receipts from that transition onward.

## Standard gate state and acceptance

Standard preflight is one bounded pass: `HERDR_ENV`, exact root/base, clean
index/tree, approved input identity, explicit owned paths, current workspace
agents, and applicable references. Do not run broad Herdr inventories, CLI
help, optional binary probes, or reread helper source. Use the commands already
given in this contract.

Once Standard and integration applicability are locked, start a fresh P5
Integration Owner at the same fan-out boundary as P2-P4. P5 may write only its
owned RED integration tests, fixtures, and contract scaffold while upstream
workers run. It must not accept or publish worker bytes until current receipts
are validator-clean. This overlaps preparation without weakening the
dependency gate.

When the approved input names an executable acceptance harness, P5 must read
that exact harness before writing RED tests or scaffold. Treat its public
arguments, output keys, digest formats, and artifact shape as locked acceptance,
not as a later smoke discovery. P5 still must not inspect prior run outputs.

Use only:

```text
PLANNED -> READY -> ACTIVE -> CANDIDATE -> ACCEPTED
                     |           |
                     v           v
                  BLOCKED     REJECTED

Any generation -> SUPERSEDED when its input identity changes
```

Progress is observable through Herdr and does not create a receipt. A lane
writes one terminal PASS, FINDING, or BLOCKED receipt only through
`write_lane_receipt.py`. Before acceptance, run:

```bash
python3 scripts/validate_lane_receipt.py "$receipt_path" \
  --control-state "$run_dir/control-state.json"
```

P1 additionally checks semantic evidence, owned scope, commands, and acceptance
coverage. Accept only the current contract, generation, agent, pane, session,
and input identity.

Never hand-edit lane generations in JSON. Change exactly one lane atomically:

```bash
python3 <skill-root>/scripts/set_lane_state.py \
  --control-state "$run_dir/control-state.json" \
  --lane "$lane_id" --generation "$generation" --state ACTIVE \
  --receipt-path "$receipt_path"
```

When an on-demand P5-P9 session first becomes live, write its lane capsule JSON
and register it without hand-editing control-state:

```bash
python3 <skill-root>/scripts/register_lane.py \
  --control-state "$run_dir/control-state.json" \
  --lane-json "$run_dir/$lane_id.json"
```

If a public contract says immutable or frozen, terminal acceptance must probe
attribute mutation plus every nested or constructor-supplied collection
surface. A decorator alone is not evidence of deep immutability.

## Direct control and recovery

P1 addresses a lane by its recorded agent_name, pane_id, and session_id.
Aggregate reads are for overview. At a dependency boundary, reconcile only the
lane blocking that transition; unrelated lanes continue.

For a stalled lane:

1. Inspect the named agent, pane process, Git state, and evidence.
2. If responsive and input identity is unchanged, send one bounded redirect to
   the same generation.
3. If replacement is required, preserve its work and evidence, mark it
   SUPERSEDED, increment generation, and start a clean agent from the latest
   accepted checkpoint.
4. The recovered owner reconciles dirty or ambiguous work before acceptance.
5. Reject every late old-generation receipt even when its content looks valid.

The same blocker twice without new evidence triggers reassignment or user
escalation. Never restart unrelated panes or silently discard useful work.

## Integration and review

P5 is the only integration mutator and deploy owner. Start it directly as
Integration Owner when that role is applicable. If an existing P5 Worker 4
session would change roles, P5 must restart first; a prompt claiming a role
change is not a clean authority boundary. Each new session receives only the
locked contract and accepted receipt identities.

After publication, P5 smoke and P6 review run concurrently against the same
artifact generation and tuple. P6-P9 are read-only and return PASS, FINDING, or
BLOCKED. P1 routes findings to the owning worker.

P7-P9 prepare early but start only when their approved matrices apply. A new
artifact invalidates old tuple-bound evidence; rerun the locked smoke, P6, and
only impacted applicable matrices.

The standard single-worker path is exactly:

```text
P1 -> P2 -> P5 Integration Owner
             -> P5 smoke || P6 Integration Reviewer
             -> deploy or verified local delivery
             -> applicable P7/P8/P9 only
```

Do not substitute P7 for P5 or P6. Do not start P3, P4, P7, P8, or P9 when
their approved scope is absent.
