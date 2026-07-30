#!/usr/bin/env python3
import argparse
import importlib
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    sys.path.insert(0, str(root))

    canary = importlib.import_module("dataset_promotion.canary")
    quality = importlib.import_module("dataset_promotion.canary_quality")
    schema = importlib.import_module("dataset_promotion.canary_schema")
    provenance = importlib.import_module("dataset_promotion.canary_provenance")
    deployment = importlib.import_module("dataset_promotion.deployment")

    policy = canary.CanaryPolicy(
        sample_percent=10,
        required_fields=("id", "score"),
        allowed_additive_fields=("segment",),
        metric_minimums={"accuracy": 0.9, "coverage": 0.85},
    )
    schema_result = schema.evaluate_canary_schema(
        {"id": "string", "score": "number"},
        {"id": "string", "score": "number", "segment": "string"},
        policy,
    )
    if not schema_result.passed:
        raise SystemExit(f"schema equality acceptance failed: {schema_result.reasons}")

    quality_result = quality.evaluate_canary_quality(
        {"accuracy": 0.9, "coverage": 0.85},
        policy,
    )
    if not quality_result.passed:
        raise SystemExit(f"inclusive threshold failed: {quality_result.reasons}")

    evidence = provenance.build_canary_evidence(
        "canary-2026-07-28",
        "integration-source",
        policy,
        [{"id": "row-1", "score": 0.91, "segment": "control"}],
    )
    for field in ("policy_digest", "dataset_digest"):
        if len(evidence[field]) != 64:
            raise SystemExit(f"invalid {field}")

    target = root / "deployments" / "canary-2026-07-28"
    receipt = deployment.verify_deployment(target)
    if receipt["release_id"] != "canary-2026-07-28":
        raise SystemExit("wrong deployed release")
    persisted = json.loads((target / "receipt.json").read_text(encoding="utf-8"))
    if persisted != receipt:
        raise SystemExit("receipt mismatch")
    print(
        json.dumps(
            {
                "status": "pass",
                "release_id": receipt["release_id"],
                "manifest_digest": receipt["manifest_digest"],
                "quality_generation": 2,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
