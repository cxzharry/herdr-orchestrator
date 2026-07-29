# P1 Self-Promotion and Worker Forwarding Design

**Status:** Approved direction, pending written-spec review

**Scope:** Change Herdr Orchestrator controller identity and request routing.
Keep product brainstorming and plan authoring outside `herdr-orchestrator`.

## Goal

The agent the user is currently chatting with becomes P1 when it starts an
approved Herdr Orchestrator delivery. The user does not need to pre-create or
pre-name a P1 pane.

If the user is instead chatting with P2-P9, that worker must keep its current
lane and forward the orchestration request to the live P1 without stealing the
controller role or discarding work.

## Terminology

- `hdr_p1`: the one live Herdr controller for the current Herdr session.
- `hdr_p2`-`hdr_p4`: reusable implementation workers.
- P5-P9: on-demand integration or review roles.
- Self-promotion: the current unnamed chat agent renames itself `hdr_p1` and
  becomes the controller for an approved delivery.
- Forwarding: a non-controller persists a request for `hdr_p1` and, when safe,
  signals P1 to handle it.

The `p1` segment in a pane ID such as `w5:p1` is not a role. Controller
identity comes from the live Herdr agent name and session identity.

## Role Resolution

At orchestration entry, resolve the current agent by
`HERDR_PANE_ID` through Herdr:

| Current identity | Existing live `hdr_p1` | Result |
|---|---|---|
| `hdr_p1` | self | Continue as P1 |
| `hdr_p2`-`hdr_p9` | present | Forward; never promote |
| `hdr_p2`-`hdr_p9` | absent | Return `BLOCKED_NO_CONTROLLER`; never promote |
| unnamed agent | absent | Self-promote to `hdr_p1` |
| unnamed agent | present | Forward to the existing P1 |
| any other named agent | absent | Return `BLOCKED_ROLE_CONFLICT` |
| any other named agent | present | Forward without changing its name |

Only an unnamed agent may self-promote automatically. A named worker cannot
escape or replace its active lane by receiving a broad user request.

## Self-Promotion Flow

For an unnamed current agent with no live `hdr_p1`:

1. Confirm `HERDR_ENV=1` and resolve the current pane and Codex session.
2. Confirm the approved plan contract and repository preflight still pass.
3. Run `herdr agent rename "$HERDR_PANE_ID" hdr_p1`.
4. Re-read `hdr_p1` and require the same pane, terminal, and Codex session.
5. Record that identity as the controller in the run manifest.
6. Enter the existing Compact or Standard orchestration flow.

The rename occurs only after the approved-input gate passes. A missing,
unapproved, stale, or contradictory plan remains `BLOCKED`; self-promotion
must not turn Herdr Orchestrator into a planning skill.

The `hdr_p1` name follows the live agent when its pane moves. When that Codex
process exits, Herdr clears the name and a later eligible chat agent may
self-promote.

## Worker Forwarding

P2-P9 must never call `herdr agent rename ... hdr_p1`.

When a worker receives a request outside its owned lane:

1. Preserve the worker's active context and lane state.
2. Resolve the unique live `hdr_p1`.
3. Create one bounded request envelope containing:
   - request ID and creation time;
   - source agent, pane, session, and current lane;
   - repository root;
   - the exact user request and referenced local artifact paths.
4. Persist the envelope atomically in a socket-scoped controller inbox.
5. If P1 is `idle` or `done`, signal it to drain that request.
6. If P1 is `working` or `blocked`, leave the request queued until P1 reaches
   a safe routing boundary.
7. Reply to the user with `FORWARDED` or `QUEUED`, including the request ID.

Do not inject a new prompt into a working P1. In Codex, that can steer the
active turn and risks replacing or mixing the work already in progress.

P1 drains its inbox at safe boundaries:

- before dispatching a new dependency wave;
- after accepting a terminal receipt wave;
- before claiming final delivery.

Requests are processed once. Acceptance records the request ID; replaying an
accepted or already-active request is rejected.

## Controller Conflict

Herdr agent names are unique. If another live `hdr_p1` exists:

- an unnamed agent forwards rather than promoting;
- a worker forwards rather than promoting;
- no agent interrupts, renames, or takes over the existing P1 automatically.

If `hdr_p1` is stale or unavailable, recovery must prove the old Codex session
is gone before a replacement self-promotes. A merely busy or moved P1 is still
the controller.

## Components

### Skill entry

Update `SKILL.md` and `references/routing.md` so role resolution is the first
runtime action after approved-plan validation.

### Controller identity

Extend the Standard run manifest with the live P1 agent, pane, terminal, and
session identity. Compact delivery validates the same live identity without
creating Standard receipt state.

### Request router

Add one small helper responsible for:

- resolving current/P1 identities from Herdr JSON;
- atomically creating socket-scoped inbox envelopes;
- listing, claiming, and accepting queued requests;
- refusing automatic promotion by P2-P9.

It must not execute product work, modify plans, or become a background daemon.

## Failure Handling

- Outside Herdr: `BLOCKED_NOT_IN_HERDR`.
- Worker receives orchestration request with no P1: `BLOCKED_NO_CONTROLLER`.
- Named non-worker attempts promotion: `BLOCKED_ROLE_CONFLICT`.
- P1 identity changes while claiming a request: release the claim and recover
  the controller before dispatch.
- Duplicate request: return the existing request status.
- Malformed or oversized envelope: reject it without prompting P1.

Forwarding failure never releases or supersedes the worker's current lane.

## Tests

Unit tests must cover:

1. Unnamed agent plus no P1 self-promotes and retains the same Codex session.
2. Existing `hdr_p1` continues without renaming.
3. `hdr_p2`-`hdr_p9` never self-promote.
4. Worker plus live P1 creates one request envelope.
5. Working P1 is not prompted; the request remains queued.
6. Idle P1 is signalled once.
7. Unnamed agent plus live P1 forwards instead of promoting.
8. Moved P1 remains controller through stable name and session.
9. Closed P1 permits a later unnamed agent to self-promote.
10. Duplicate forwarding is idempotent.
11. Concurrent promotion attempts produce only one `hdr_p1`.
12. Existing worker-pool, move, close, receipt, and asset tests still pass.

Add one live canary in an isolated Herdr test session:

1. Start an unnamed controller candidate and named P2.
2. Promote the candidate to `hdr_p1`.
3. Give P2 a broad orchestration request while P1 is working.
4. Verify P2 remains P2, its lane stays intact, and the request is queued.
5. Let P1 reach a safe boundary and verify it claims the exact request once.

## Non-Goals

- Pre-creating a permanent P1 pane.
- Treating pane ID `p1` as the P1 role.
- Allowing workers to become P1 automatically.
- Adding a daemon, scheduler service, or background polling process.
- Moving brainstorming or plan writing into `herdr-orchestrator`.
- Automatically taking over a live controller.
