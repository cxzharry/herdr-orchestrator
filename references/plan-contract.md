# Plan Contract

Herdr Orchestrator starts only from an approved spec and approved execution
plan. Missing, stale, contradictory, or unapproved inputs are blockers.

The plan must define logical lanes with:

- `contract_id`
- `lane_id`
- `generation`
- owned paths
- prerequisites
- acceptance checks
- terminal receipt command

Runtime identity is recorded after approval in `workspace-state.json`; the plan
does not depend on live pane IDs. Valid receipt identity is contract, lane,
generation, session, input identity, and output artifact.

Compact uses one to three path-owned lanes; a single function or single file is
first-class. Implementation lanes use P2-P4. P5 integration and P6 independent
QC are mandatory in both modes. P7-P9 are explicitly applicable or not
applicable; Standard starts all applicable lanes concurrently.
