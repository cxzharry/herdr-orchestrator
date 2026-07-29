# Persistent P1 Benchmark

This harness runs a deterministic scheduler scenario for the persistent-P1
control-plane design. It uses two active lanes, then evaluates a disjoint delta,
an overlapping delta, a capacity-blocked delta, and a plan-required delta.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 benchmarks/persistent-p1/run_benchmark.py --trials 3
```

The runner records median and p95 timing summaries only. It does not store
local socket paths, home directories, process IDs, sessions, raw prompts, or
temporary directories.
