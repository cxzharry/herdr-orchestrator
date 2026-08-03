# Meta-Harness Plan: Herdr Fast Path

Use the approved implementation plan at
`docs/superpowers/plans/2026-08-03-herdr-orchestrator-fast-path.md`.

Implementation parallelism: Parallel lanes.

Reason: delivery-mode persistence, reducer wave scheduling, and the live
worker/skill boundary have disjoint ownership. P5 integrates; P6 reviews; P7
and P9 evaluate concurrently after the exact candidate is accepted.
