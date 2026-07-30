# Review And Deployment

Review and deployment are Standard-only.

P5 integrates accepted worker artifacts into a forward commit. P6 reviews the
integrated diff and runtime state ownership. P7, P8, and P9 run only when the
approved plan marks their predicates applicable.

Deployment evidence is required only when the plan has a deployment target.
Local-only work records local checks and stops. Public release must advance
normally; do not force-push, reset, or rebase.

Reviewers validate the current tuple:

- contract id
- lane id
- generation
- session id
- input identity
- output artifact

Old tuple-bound PASS receipts do not prove a changed candidate. Recovery is
fix-forward or rollback through P5. P1 routes findings but performs no product
command and no delivery mutation.
