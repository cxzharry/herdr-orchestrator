# Persistent P1 Benchmark

This harness runs a deterministic scheduler scenario for the persistent-P1
control-plane design. It uses two active lanes, then evaluates a disjoint delta,
an overlapping delta, a capacity-blocked delta, and a plan-required delta.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 benchmarks/persistent-p1/run_benchmark.py --trials 3
```

With an accepted primary-baseline report:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 benchmarks/persistent-p1/run_benchmark.py \
  --trials 3 \
  --baseline-report /path/to/herdr-b80be3e.json \
  --baseline-sha256 <expected-sha256>
```

The runner records median and p95 timing summaries only. It does not store
local socket paths, home directories, process IDs, sessions, raw prompts, or
temporary directories.

Baseline comparison is scenario-specific: it records the old blocking wait
probe from the accepted primary-baseline report beside the revised scheduler
tick timing. Superpowers remains `N/A` when the locked inputs do not support a
direct comparison.
