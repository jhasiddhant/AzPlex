# ============================================================================
# VERIFICATION - Post-operation evidence gates for mutation tools
# ============================================================================

import json
import time
from typing import Callable, Optional, Tuple

# Command execution outcome
COMMAND_SUCCEEDED = "succeeded"
COMMAND_FAILED = "failed"

# Read-after-write verification outcome
VERIFIED = "verified"
UNVERIFIED = "unverified"
VERIFICATION_FAILED = "verification_failed"
VERIFICATION_SKIPPED = "skipped"

# Markers that indicate a mutation command did not succeed
_FAILURE_MARKERS = (
    "[exit code:",
    "creation failed",
    "deployment failed",
    "assignment failed",
    "error:",
    "error details:",
    "unauthorized",
    "forbidden",
    "not found",
)


def command_failed(output: str) -> bool:
    """Detects whether a script/CLI text output represents a failed command."""
    if not output or not output.strip():
        return True
    lowered = output.lower()
    return any(marker in lowered for marker in _FAILURE_MARKERS)


class OperationResult:
    """Shared contract describing a mutation's execution and verification state."""

    def __init__(self, operation: str):
        self.operation = operation
        self.command_status = COMMAND_SUCCEEDED
        self.verification_status = VERIFICATION_SKIPPED
        self.evidence = {}
        self.warnings = []
        self.failures = []

    @property
    def success(self) -> bool:
        """A success claim requires both a successful command and positive verification."""
        return self.command_status == COMMAND_SUCCEEDED and self.verification_status == VERIFIED

    def to_dict(self) -> dict:
        return {
            "operation": self.operation,
            "success": self.success,
            "command_status": self.command_status,
            "verification_status": self.verification_status,
            "evidence": self.evidence,
            "warnings": self.warnings,
            "failures": self.failures,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


def verify_with_retry(
    check: Callable[[], Tuple[bool, object]],
    *,
    max_attempts: int = 3,
    delay: float = 2.0,
    timeout: float = 30.0,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> Tuple[str, object]:
    """
    Runs a read-back check with bounded retries for eventual consistency.

    The check returns (found, evidence). Retries stop at the first positive
    result, when attempts are exhausted, or when the timeout budget is spent.
    Returns (verification_status, evidence_or_error).
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    start = clock()
    last_evidence = None
    for attempt in range(1, max_attempts + 1):
        try:
            found, evidence = check()
        except Exception as error:  # a failing read-back is a verification failure, not a crash
            return VERIFICATION_FAILED, f"{type(error).__name__}: {error}"

        last_evidence = evidence
        if found:
            return VERIFIED, evidence

        if attempt == max_attempts:
            break
        if clock() - start + delay > timeout:
            break
        sleep(delay)

    return VERIFICATION_FAILED, last_evidence


def run_verified_operation(
    operation: str,
    execute: Callable[[], str],
    verify: Optional[Callable[[], Tuple[bool, object]]] = None,
    **retry_options,
) -> OperationResult:
    """
    Executes a mutation, then gates the success claim on read-back evidence.

    If the command fails, verification is skipped. If no verifier is supplied,
    the result stays unverified rather than claiming success.
    """
    result = OperationResult(operation)
    output = execute()
    result.evidence["command_output"] = output.strip() if isinstance(output, str) else output

    if command_failed(output):
        result.command_status = COMMAND_FAILED
        result.verification_status = VERIFICATION_SKIPPED
        result.failures.append("Command reported failure; verification skipped.")
        return result

    if verify is None:
        result.verification_status = UNVERIFIED
        result.warnings.append("No read-back verifier was provided; success is not confirmed.")
        return result

    status, evidence = verify_with_retry(verify, **retry_options)
    result.verification_status = status
    result.evidence["verification"] = evidence
    if status != VERIFIED:
        result.failures.append("Read-back verification did not confirm the expected state.")
    return result


class BatchResult:
    """Aggregates per-item results, treating any partial failure as an overall failure."""

    def __init__(self, operation: str):
        self.operation = operation
        self.items = []

    def add(self, item: OperationResult) -> None:
        self.items.append(item)

    @property
    def succeeded(self) -> int:
        return sum(1 for item in self.items if item.success)

    @property
    def failed(self) -> int:
        return sum(1 for item in self.items if item.command_status == COMMAND_FAILED or item.verification_status == VERIFICATION_FAILED)

    @property
    def skipped(self) -> int:
        return sum(1 for item in self.items if item.verification_status in (VERIFICATION_SKIPPED, UNVERIFIED) and item.command_status != COMMAND_FAILED)

    @property
    def success(self) -> bool:
        return bool(self.items) and all(item.success for item in self.items)

    def to_dict(self) -> dict:
        return {
            "operation": self.operation,
            "success": self.success,
            "counts": {
                "total": len(self.items),
                "succeeded": self.succeeded,
                "failed": self.failed,
                "skipped": self.skipped,
            },
            "items": [item.to_dict() for item in self.items],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
