# Git Integration

Use Git worktrees for code-changing lanes. Each accepted lane must produce a
clean commit and a validator-clean receipt before P5 consumes it.

For a replacement candidate, P5 merges accepted lane commits into the
replacement worktree, runs full checks, then applies the reviewed tracked-tree
delta to the integration worktree with normal Git plumbing. Do not reset,
rebase, force-push, or delete worktrees.

The integration commit must descend from the current mainline base named by the
approved plan. Current-only deletions are explicit and limited to superseded
runtime paths listed in the plan.
