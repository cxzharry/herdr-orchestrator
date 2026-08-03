# Meta-Harness Spec: Herdr Fast Path

Improve `herdr-orchestrator` so a deterministic one-function implementation
uses a contract-safe Compact route while Standard work overlaps independent
stages. The canonical approved design is
`docs/superpowers/specs/2026-08-03-herdr-orchestrator-fast-path-design.md` at
SHA-256 `b7a89af1d5e1a02a42726f54b9aa5978a60fd0648b05dd3f9ec113c7ce6fba52`.

The frozen Superpowers baseline remains read-only. P1 stays controller-only;
every implementation keeps P5 integration and P6 independent QC; runtime
actions remain inside one Herdr workspace and never close panes.
