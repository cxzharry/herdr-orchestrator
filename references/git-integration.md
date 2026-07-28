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

## Publication and review

P5 is the only integration mutator. It reconciles accepted handoffs, final
base-to-integration paths, merge resolutions, and a clean tree before
publication.

P6 is read-only. It verifies the declared base, exact worker SHAs, allowed
parents, final paths/content, and P5-owned resolution patch. An unexplained
commit, parent, path, byte, staged change, or hook effect blocks PASS.

Every handoff names the base SHA, lane SHA, ownership, checks, and evidence.
Load `high-assurance.md` when nonce-bound mutation transcripts or strict
reproducibility are required.
