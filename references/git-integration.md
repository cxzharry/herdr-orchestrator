# Git integration

Read this reference only for multiple writers, integration, or isolation.

## Shared tree

- Record the pre-fan-out porcelain status and diff hash.
- Stop before assigning a path that overlaps an existing user change.
- Require an empty index before fan-out and before P5 stages lane changes;
  never unstage user work.
- Give workers disjoint writable paths. Workers edit and test without commits.
- P5 stages accepted pathspecs explicitly, never `git add -A`.
- Immediately before commit, prove `HEAD` equals the locked base. Publish one
  integration commit whose sole parent is that base.
- Bind each scoped diff digest to its lane generation. A replacement owner
  reconciles the preserved diff before P1 accepts a new receipt; late receipts
  from the superseded generation cannot authorize staging.

## Worktrees

- Create a lane only when its prerequisites are ready, from the locked wave
  base, with a unique branch and writable pathspecs.
- Workers commit only their owned branches and report full SHAs.
- P5 proves the lane base and prerequisite SHAs are ancestors of each handoff
  and that changed paths stay inside ownership.
- P5 alone merges accepted worker SHAs in a dedicated integration worktree.
  Do not squash or cherry-pick.
- After a prerequisite lands, P5 publishes the next wave base before P1 creates
  dependent lanes.
- Record branch, worktree path, base SHA, full lane SHA, clean/dirty state, and
  generation in `control-state.json`. Replacing an agent never deletes its
  worktree or branch before the new owner reconciles the checkpoint.

## Publication and review

P5 is the only integration mutator. It reconciles accepted handoffs, final
base-to-integration paths, merge resolutions, and a clean tree before
publication.

P6 is read-only. It verifies the declared base, exact worker SHAs, allowed
parents, final paths/content, and P5-owned resolution patch. An unexplained
commit, parent, path, byte, staged change, or hook effect blocks PASS.

Every accepted terminal receipt names the base SHA, lane SHA, ownership,
generation, checks, and evidence by path and digest. P5 integrates only
validator-clean current-generation receipts approved by P1.
Load `high-assurance.md` when nonce-bound mutation transcripts or strict
reproducibility are required.
