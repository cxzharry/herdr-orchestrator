# Herdr plan contract

Use this contract while writing a plan whose selected execution backend is
Herdr, and validate it again after the user approves the plan.

## Logical delivery topology

Add a `## Herdr Delivery Contract` section to the plan. It must lock:

- approved spec path and digest, repository root, base SHA, and plan acceptance;
- logical `lane_id`, role, owned paths, prerequisites, dependency wave,
  acceptance, and terminal checks for every implementation lane;
- eligible role slots: implementation lanes use P2-P4; P5 owns integration and
  deployment; P6 owns integration review; P7-P9 are explicitly applicable or
  not applicable with a reason;
- deployment topology, blocking severity, review matrices, and required
  evidence.

The plan describes logical capacity, not live runtime identity. Never record an
`agent_name`, `pane_id`, `session_id`, or `lease_id` in the approved plan.
Those values can change after reuse, reset, move, close, or recovery.

Use this minimal shape:

```yaml
herdr_delivery:
  backend: herdr
  lanes:
    - lane_id: frontend
      role: implementation
      eligible_slots: [P2, P3, P4]
      owned_paths: [app/**, components/**]
      prerequisites: []
      acceptance: [npm test, npm run build]
  reviews:
    P5: {applicable: true, role: integration-owner}
    P6: {applicable: true, role: integration-reviewer}
    P7: {applicable: false, reason: no functional matrix}
    P8: {applicable: true, reason: UI scope}
    P9: {applicable: false, reason: no persona matrix}
  deployment:
    topology: no-deployment-target
    verification: isolated-local-runtime
```

## Approval and runtime binding

The plan is not executable until the user approves it. After approval, bind
each logical lane to a compatible live agent, pane, and session in
`control-state.json`. A plan change invalidates its prior approval; a runtime
identity change does not change the plan.
