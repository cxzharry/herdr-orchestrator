"""Pure validation for the deterministic Herdr delivery mode contract."""

from __future__ import annotations


COMPACT_ELIGIBILITY_FLAGS = {
    "local",
    "low_risk",
    "path_owned",
    "deterministic_acceptance",
}
STANDARD_TRIGGER_FLAGS = {
    "browser_or_visual",
    "auth_rbac_security_privacy_or_secrets",
    "schema_migration_or_destructive",
    "deployment_or_external_state",
    "nondeterministic_acceptance",
    "high_assurance",
    "broader_review",
    "runtime_recovery",
}
RISK_FLAGS = COMPACT_ELIGIBILITY_FLAGS | STANDARD_TRIGGER_FLAGS
REVIEW_SLOTS = {"P7", "P8", "P9"}


def _validate_flags(
    value: object,
    expected: set[str],
    label: str,
    members: str = "flags",
    require_all: bool = True,
) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    unknown = set(value) - expected
    if unknown:
        raise ValueError(f"unknown {label} {members}: {', '.join(sorted(unknown))}")
    missing = expected - set(value)
    if require_all and missing:
        raise ValueError(f"missing {label} {members}: {', '.join(sorted(missing))}")
    invalid = sorted(name for name, flag in value.items() if type(flag) is not bool)
    if invalid:
        raise ValueError(f"{label} {members} must be boolean: {', '.join(invalid)}")
    return value


def required_mode(risk: object) -> str:
    """Return the only mode allowed by the declared risk predicates."""
    flags = _validate_flags(risk, RISK_FLAGS, "risk", require_all=False)
    compact_eligible = all(
        flags.get(name, False) for name in COMPACT_ELIGIBILITY_FLAGS
    )
    has_standard_trigger = any(
        flags.get(name, False) for name in STANDARD_TRIGGER_FLAGS
    )
    return "Compact" if compact_eligible and not has_standard_trigger else "Standard"


def validate_mode(
    mode: object,
    risk: object,
    review_applicability: object,
    implementation_lane_count: object,
) -> None:
    """Reject a delivery mode that contradicts risk, reviews, or lane count."""
    if mode not in {"Compact", "Standard"}:
        raise ValueError("mode must be Compact or Standard")
    applicability = _validate_flags(
        review_applicability, REVIEW_SLOTS, "review", "slots"
    )
    if type(implementation_lane_count) is not int or implementation_lane_count < 1:
        raise ValueError("implementation_lane_count must be a positive integer")
    if mode == "Compact" and any(applicability.values()):
        raise ValueError("Compact cannot require P7, P8, or P9")

    required = required_mode(risk)
    if implementation_lane_count > 3:
        required = "Standard"
    if mode != required:
        raise ValueError(f"declared {mode} but contract requires {required}")
