#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


REQUIRED_FIELDS = {
    "schema_version",
    "contract_id",
    "lane_id",
    "generation",
    "role",
    "agent_name",
    "pane_id",
    "session_id",
    "status",
    "input_identity",
    "output_identity",
    "covered_acceptance",
    "checks",
    "finding_or_blocker",
    "resume_condition",
}
VALID_STATUSES = {"PASS", "FINDING", "BLOCKED"}
REVIEWER_ROLES = {
    "integration-reviewer",
    "qc",
    "designer",
    "persona",
}


def validate_receipt(receipt: dict, control_state: dict) -> list[str]:
    failures = []
    for field in sorted(REQUIRED_FIELDS - set(receipt)):
        failures.append(f"missing field: {field}")
    if failures:
        return failures

    if receipt["schema_version"] != "herdr-lane-receipt/v1":
        failures.append("unsupported schema_version")
    if receipt["status"] not in VALID_STATUSES:
        failures.append("status must be PASS, FINDING, or BLOCKED")
    if receipt["contract_id"] != control_state.get("contract_id"):
        failures.append("contract_id does not match control state")

    lane = control_state.get("lanes", {}).get(receipt["lane_id"])
    if lane is None:
        failures.append("lane_id is not present in control state")
        return failures

    expected_fields = {
        "generation": "generation does not match current lane",
        "role": "role does not match current lane",
        "pane_id": "pane_id does not match current lane",
        "session_id": "session_id does not match current lane",
        "input_identity": "input_identity does not match current lane",
    }
    for field, message in expected_fields.items():
        if receipt[field] != lane.get(field):
            failures.append(message)
    dispatch_name = lane.get("dispatch_agent_name", lane.get("agent_name"))
    if receipt["agent_name"] != dispatch_name:
        failures.append("agent_name does not match dispatch identity")
    optional_identity_fields = {
        "root": "root does not match current lane",
        "base_sha": "base_sha does not match current lane",
        "owned_scope": "owned_scope does not match current lane",
    }
    for field, message in optional_identity_fields.items():
        expected = lane.get(field, control_state.get(field))
        if field in receipt and receipt[field] != expected:
            failures.append(message)

    if receipt["status"] == "PASS":
        if receipt["finding_or_blocker"] is not None:
            failures.append("PASS cannot contain a finding or blocker")
        if not receipt["covered_acceptance"]:
            failures.append("PASS requires covered_acceptance")
        if not receipt["checks"]:
            failures.append("PASS requires checks")
        if not receipt["output_identity"]:
            failures.append("PASS requires output_identity")

    if receipt["status"] == "FINDING":
        finding = receipt["finding_or_blocker"]
        required = {
            "severity",
            "expected",
            "actual",
            "evidence_ref",
            "suspected_owner",
        }
        if not isinstance(finding, dict) or not required.issubset(finding):
            failures.append(
                "FINDING requires severity, expected, actual, evidence_ref, "
                "and suspected_owner"
            )

    if receipt["status"] == "BLOCKED":
        blocker = receipt["finding_or_blocker"]
        if not isinstance(blocker, dict) or not blocker.get("attempted_checks"):
            failures.append("BLOCKED requires attempted_checks")
        if not receipt["resume_condition"]:
            failures.append("BLOCKED requires resume_condition")

    if receipt["role"] in REVIEWER_ROLES:
        if receipt["output_identity"] != receipt["input_identity"]:
            failures.append(
                "reviewer output_identity must equal input_identity"
            )

    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--control-state", type=Path, required=True)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    state = json.loads(args.control_state.read_text(encoding="utf-8"))
    failures = validate_receipt(receipt, state)
    print(
        json.dumps(
            {"status": "pass" if not failures else "fail", "failures": failures},
            indent=2,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
