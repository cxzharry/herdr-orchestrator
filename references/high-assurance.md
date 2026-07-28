# High assurance

Read this reference only for security-sensitive, destructive,
production-critical, or explicitly strict work. These controls are not the
default fast path.

## Mutation provenance

For each P5 stage, commit, or merge, P1 issues a fresh nonce. Capture a
hash-chained terminal receipt with nonce, pane/session IDs, exact command and
output, before/after SHAs, and timestamp. P6 matches the live Herdr identity,
receipt chain, Git DAG/reflog, and published SHA before accepting it.

## Reproducibility

Build in two independent disposable worktrees and isolated environments. Bind
the full SHA, lockfile/toolchain, secret-redacted environment fingerprint,
external input digests, and output bytes in a source-to-artifact manifest.
Unexplained drift blocks publication. Record the actual running
PID/container/image or deployment digest, not a requested label.

## Authorization and evidence

Derive roles from authoritative IdP, database-role, policy-engine, and protected
route/API sources. Reconcile those enumerations against the locked role matrix;
an unexplained addition or omission blocks review. Reference secrets by name,
never copy their values into receipts.

Every command, permission result, trace, screenshot, finding, and verdict names
the same revision and artifact tuple. Runtime drift, orphaned processes,
unexpected sockets, or evidence from another tuple invalidates the affected
gate. P6 verifies teardown before final delivery.
