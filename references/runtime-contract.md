# Runtime contract

## Preflight and applicability

- Confirm `HERDR_ENV=1`, inspect current workspace/panes/agents, and use only
  explicit IDs or unique names.
- The invoking Codex is P1. Its live Codex `/status` model and effort are
  authoritative; process arguments and configuration only corroborate launch
  intent and cannot prove a resumed session. If sources conflict or
  `gpt-5.6-sol/high` cannot be proven, stop and request a P1 relaunch.
- Start agents only in vacant interactive shell panes. To reuse a pane, release
  the old agent with its native exit command; verify `herdr agent get` no longer
  resolves it and `herdr pane process-info --pane <id>` reports the shell in the
  foreground. Then start the replacement and verify its name plus live Codex
  `/status` model and effort before prompting it.
- Before fan-out, enumerate an applicability matrix for `ui`, `browser`, `rbac`,
  and `persona`. Record the authoritative source set (paths/URLs plus content
  hashes), discovered roles/personas/surfaces, decision, owner, and evidence.
  P6 independently approves completeness and every `N/A`. If auth, permission,
  or persona sources are incomplete or ambiguous, omission requires explicit
  user risk acceptance.

## Dependency and integration modes

Record a locked base SHA and dispatch only lanes whose dependencies are ready.
Use waves when schemas, migrations, APIs, or shared contracts must land first.

**Shared-tree mode**

- Record the pre-fan-out porcelain status and diff hash. Do not assign a path
  containing a pre-existing staged, unstaged, or untracked change; stop for
  user direction if the task must overlap it.
- Require an empty Git index before fan-out and again before P5 stages lane
  changes. If baseline or newly staged user changes exist, switch to worktrees
  or stop; never unstage them.
- Assign disjoint writable paths; all other paths are read-only.
- Workers edit and test but do not commit.
- P5 owns shared integration files, stages approved lane pathspecs explicitly
  (never `git add -A`), and reconciles the staged name/status and diff with lane
  handoffs plus the initial baseline before committing. Immediately before
  commit, prove `HEAD == base_sha`. Publish one integration commit whose sole
  parent is `base_sha`; verify `git rev-list --count base_sha..integration_sha`
  equals one.

**Worktree mode**

- Create only ready lanes from the current locked `wave_base_sha`, each with a
  unique branch, recorded `lane_base_sha`, prerequisites, and writable
  pathspecs; do not pre-create a lane whose prerequisite is unresolved.
- Workers commit only their owned branch and report its SHA.
- Before handoff acceptance, P5 proves `lane_base_sha` and every prerequisite
  SHA are ancestors of the worker SHA, and its base-to-worker changed paths are
  a subset of the lane pathspecs.
- P5 works in a dedicated integration worktree and alone merges approved worker
  SHAs without squashing or cherry-picking. After a prerequisite lands, P5
  publishes the new `wave_base_sha`; P1 verifies its ancestry before creating
  dependent lanes.
- Before publication, P6 verifies an allowlisted commit DAG: locked integration
  base, exact accepted worker SHAs, and only P5 merge commits. Every worker SHA
  must be an ancestor of `integration_sha`; `git rev-list` may contain no
  undeclared commit or parent. Reconcile the final base-to-integration paths and
  content with accepted lane diffs plus an explicit P5-owned merge-resolution
  patch.

**Both modes**

- For every P5 stage/commit/merge, P1 issues a fresh challenge nonce. Execute
  through the attested P5 pane/session and capture a hash-chained terminal
  transcript containing nonce, pane ID, agent session ID, exact command/output,
  before/after SHA, and timestamp. P6 independently matches the live Herdr
  session identity, transcript chain, Git DAG/reflog, and published SHA before
  accepting the integration receipt.
- P6 compares `base_sha..integration_sha` paths and final tree content against
  accepted handoffs plus an explicit, path-scoped P5 integration/resolution
  patch. Any unexplained path, byte, commit, parent, index mutation, or hook
  effect blocks publication.

## Playwright mutex

P1 is the sole scheduler. Create a private workspace runtime directory owned by
the current user with mode `0700`; reject symlinks. Create the lock once with
mode `0600`, record its device/inode for the review epoch, and pass its exact
path to every browser user:

```bash
: "${HERDR_WORKSPACE_ID:?verified Herdr workspace ID is required}"
PLAYWRIGHT_DIR="${XDG_RUNTIME_DIR:?}/herdr-${HERDR_WORKSPACE_ID}"
PLAYWRIGHT_LOCK="${PLAYWRIGHT_DIR}/playwright.lock"
install -d -m 700 "$PLAYWRIGHT_DIR"
test -O "$PLAYWRIGHT_DIR" && test ! -L "$PLAYWRIGHT_DIR"
touch "$PLAYWRIGHT_LOCK" && chmod 600 "$PLAYWRIGHT_LOCK"
test -O "$PLAYWRIGHT_LOCK" && test ! -L "$PLAYWRIGHT_LOCK"
PLAYWRIGHT_LOCK_ID="$(stat -Lc "%d:%i" "$PLAYWRIGHT_LOCK")"
PLAYWRIGHT_UNIT="herdr-${HERDR_WORKSPACE_ID}-pw-${review_epoch}-${gate}-${grant_seq}"
for fn in assert_unit_empty assert_no_workspace_browser_pids assert_no_workspace_browser_sockets; do
  declare -F "$fn" >/dev/null
  export -f "$fn"
done
export PLAYWRIGHT_LOCK PLAYWRIGHT_LOCK_ID PLAYWRIGHT_UNIT
flock -x -w 30 "$PLAYWRIGHT_LOCK" bash -c '
  set -euo pipefail
  cleanup() {
    systemctl --user stop "$PLAYWRIGHT_UNIT" >/dev/null 2>&1 || true
    timeout 30s bash -c \
      "while systemctl --user is-active --quiet \"$PLAYWRIGHT_UNIT\"; do sleep 0.1; done"
    test "$(stat -Lc "%d:%i" "$PLAYWRIGHT_LOCK")" = "$PLAYWRIGHT_LOCK_ID"
    assert_unit_empty "$PLAYWRIGHT_UNIT"
    assert_no_workspace_browser_pids "$HERDR_WORKSPACE_ID"
    assert_no_workspace_browser_sockets "$HERDR_WORKSPACE_ID"
  }
  trap cleanup EXIT
  systemd-run --user --unit="$PLAYWRIGHT_UNIT" --collect --wait \
    -p KillMode=control-group timeout --kill-after=15s 15m <playwright command>
  cleanup
  trap - EXIT
'
```

When UI, browser, or runtime behavior applies, P1 grants turns in the required
order `P5 smoke → P6 QC → P7 Designer → P8 Persona`. P5 runs smoke against the
exact published artifact and deterministic seed. It covers every changed
critical journey and each impacted role, including the exact reproducer for a
reported regression. At minimum it proves the intended surface rendered
without a setup/error fallback and that each role's critical allowed action
succeeds. A P5 failure blocks P6, routes back to the owning lane, and requires
P5 to republish and rerun smoke. A P5 pass is implementation evidence only and
never satisfies an independent P6, P7, or P8 gate.

An acquisition timeout is a failed grant, not permission to run unlocked. Each
holder must report grant acknowledgement, command/result, browser cleanup, and
release. The unique transient unit prohibits daemonization and kills its whole
cgroup on every exit path. Cleanup, PID/socket scan, and unchanged inode proof
must complete inside `flock`; only then may the next grant start. After command
timeout, crash, leakage, or inode drift P1 resets deterministic test data,
increments `review_epoch`, invalidates all gate evidence, and restarts at P5
smoke. Before the epoch, lock the three assertion implementations and their
baseline commands. Each grant emits a P1-owned receipt containing epoch, grant,
gate, unit, lock device/inode, pre/post cgroup PID sets, workspace browser
PID/socket sets, exact assertion commands, statuses, and timestamp.

Minimum fail-closed semantics:

- `assert_unit_empty` resolves the unit's `ControlGroup` and fails while any
  `cgroup.procs` entry remains.
- PID assertion records the current-user browser process set plus
  workspace/grant tags before launch and fails on any unexpected survivor.
- Socket assertion records the locked browser port/socket set and fails on any
  unexpected listener or owner after cleanup.
- P6 content-hashes and approves the implementations and baselines before the
  epoch, then runs a negative control that creates a tagged test process/socket;
  each relevant assertion must fail before the test resource is removed.
  Missing, unreadable, no-op, or ambiguous discovery blocks review.

## Testing and gate ownership

Playwright alone is insufficient. P5 prepares a resettable deterministic
mock/seed snapshot for every locked system state and actor, then records its
content-addressed `seed_digest`. Before each gate P5 restores that immutable
snapshot before every actor/scenario and emits a reset receipt containing gate,
scenario, actor, timestamp, epoch, seed digest, and status. The gate owner
independently verifies live-state digest/count invariants before each test. Only
a locked cross-role handoff chain may intentionally preserve state between its
steps, with checkpoint invariants in the receipt. Any mismatch invalidates the
review.

- P5 runs the required implementation smoke on the exact published artifact
  before independent gates begin.
- P6 runs the applicable contract, functional, regression, failure-path, and
  data-integrity checks.
- P7 reviews the locked UI states and viewports for usability, accessibility,
  responsiveness, error clarity, and data exposure.
- P8 completes every locked persona's critical goal journey and records
  experience blockers and friction.

When RBAC applies:

- Derive every role from the auth/permission source. Do not group or skip roles
  without explicit user risk acceptance.
- Provide at least one secret-referenced identity per role plus allowed, denied,
  boundary, and cross-role handoff data.
- P6 verifies every role's login, one critical allowed action, one forbidden
  action, direct UI/API authorization, and data isolation.
- P7 reviews every role's applicable UI states.
- P8 runs one goal-driven journey per role and every critical cross-role handoff.

P6 owns the regression gate, P7 the UI/UX gate, and P8 the persona gate. A gate
passes only with zero unresolved blockers or explicit user acceptance. P1 may
route findings and check evidence consistency, but may not sign these gates.

## Revision-safe evidence

P5 publishes a full-length `integration_sha`, clean-tree receipt, content-based
`artifact_digest`, effective environment fingerprint, and `seed_digest`; a
deployment release ID is additional metadata, never a digest substitute. P1
starts a monotonic `review_epoch`. P5 must build/start the
review surface in a newly created disposable worktree checked out at
`integration_sha`, never a reused build directory. Its source-to-artifact
manifest binds the full SHA, lockfile/toolchain, secret-redacted environment
fingerprint, and produced bytes. Record the actual running PID/container/image
or deployment digest, not merely a requested release label.

Build twice in independent disposable worktrees and isolated environments; the
source-to-artifact manifests and content digests must match. If an output is
inherently nondeterministic, lock its classification and normalization rule and
verify only the explicitly approved variable fields; unexplained drift blocks.
Build offline/hermetically where supported. Otherwise content-digest every
external input, generated remote asset, and cache object in the manifest; an
unrecorded mutable input blocks reproducibility.

Before each gate, its owner rechecks exact HEAD and clean status, verifies the
actual running process/image/release digest against the source-to-artifact
manifest, independently verifies live seed state, and records the reset receipt.
Before every handoff, gate, and delivery, re-attest pane session ID plus live
model/effort. Every command result, permission matrix, trace, screenshot,
finding, and gate decision names this full attestation tuple. Dirt or runtime
drift invalidates it. Any code, config, migration, fixture, or seed change
creates a new tuple. Any timeout, crash, orphan, leakage, or unplanned reset
increments the epoch. Every invalidation restarts review at P6.

When RBAC applies, P6 also reconciles the locked authority set against live IdP,
database-role, policy-engine, protected-route/API, and persona enumerations.
Unexplained additions or omissions block the gate.

Before Verified Delivery, P6 verifies a teardown receipt: review runtime stopped,
PID/container and sockets absent, disposable worktrees and temporary branches
removed, and original workspace status reconciled to its locked baseline.
