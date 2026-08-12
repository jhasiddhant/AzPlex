# ============================================================================
# GUARDRAILS - Centralized mutation and execution policy
# ============================================================================

import json
import re
import time
from typing import Callable, List, Optional, Tuple

# Operation classes
READ = "read"
MUTATE = "mutate"
DESTRUCTIVE = "destructive"

# Read-only Azure CLI verbs permitted through the raw escape hatch
READ_VERBS = frozenset({
    "show", "list", "get", "describe", "exists", "check", "check-name",
    "wait", "version", "export", "list-keys", "show-connection-string",
})

# Verbs that irreversibly remove or reset state
DESTRUCTIVE_VERBS = frozenset({
    "delete", "purge", "remove", "destroy", "deallocate", "reset",
    "regenerate", "revoke", "detach", "cancel", "flush", "clear", "prune",
})

# Verbs that change state without necessarily destroying it
MUTATE_VERBS = frozenset({
    "create", "update", "set", "add", "start", "stop", "restart",
    "enable", "disable", "assign", "import", "invoke", "run", "generate",
    "rotate", "renew", "approve", "reject", "move", "lock", "unlock",
    "login", "logout", "configure",
})

# Characters that indicate an attempt to chain or evaluate shell commands
_SHELL_METACHARACTERS = (";", "|", "&", "`", "$(", "${", ">", "<", "\n", "\r", "\\")

# Patterns whose captured values must be redacted from any surfaced output
_SECRET_PATTERNS = [
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(access[_-]?token[\"'\s:=]+)[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(password[\"'\s:=]+)\S+"),
    re.compile(r"(?i)(secret[\"'\s:=]+)\S+"),
    re.compile(r"(?i)(--password\s+)\S+"),
    re.compile(r"(?i)(connectionstring[\"'\s:=]+)\S+"),
    re.compile(r"(?i)(sig=)[A-Za-z0-9%._\-]+"),
]

_REDACTED = "***REDACTED***"


class PolicyDecision:
    """Structured allow/deny decision for an execution request."""

    def __init__(self, allowed: bool, operation_class: str, reason: str = ""):
        self.allowed = allowed
        self.operation_class = operation_class
        self.reason = reason

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "operation_class": self.operation_class,
            "reason": self.reason,
        }


def redact(text: str) -> str:
    """Removes token, password, secret, and SAS values from text."""
    if not text:
        return text
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(lambda m: f"{m.group(1)}{_REDACTED}", redacted)
    return redacted


def contains_shell_metacharacters(raw: str) -> bool:
    """Detects shell chaining/evaluation characters in raw command text."""
    return any(token in raw for token in _SHELL_METACHARACTERS)


def command_verb(args: List[str]) -> str:
    """Returns the Azure CLI verb — the last positional token before any flag."""
    positionals = []
    for token in args:
        if token.startswith("-"):
            break
        positionals.append(token)
    return positionals[-1].lower() if positionals else ""


def classify_az_command(args: List[str]) -> str:
    """Classifies an Azure CLI command as read, mutate, or destructive."""
    verb = command_verb(args)
    if verb in DESTRUCTIVE_VERBS:
        return DESTRUCTIVE
    if verb in MUTATE_VERBS:
        return MUTATE
    if verb in READ_VERBS:
        return READ
    # Unknown verbs are treated as mutations so they cannot slip through as read-only.
    return MUTATE


def evaluate_cli_raw(raw_command: str, parsed_args: Tuple[str, ...]) -> PolicyDecision:
    """
    Applies the raw Azure CLI policy: read-only, no shell evaluation.

    Denies chained/evaluated shell input and any non-read verb so destructive
    and mutating operations must go through approved typed tools instead.
    """
    if contains_shell_metacharacters(raw_command):
        return PolicyDecision(
            False,
            DESTRUCTIVE,
            "Shell metacharacters are not allowed in raw commands. Use a typed tool for this operation.",
        )

    if not parsed_args:
        return PolicyDecision(False, MUTATE, "No Azure CLI command was provided.")

    operation_class = classify_az_command(list(parsed_args))
    if operation_class != READ:
        return PolicyDecision(
            False,
            operation_class,
            f"Raw CLI is restricted to read-only operations; '{command_verb(list(parsed_args))}' is a {operation_class} verb. "
            "Use an approved typed tool (for example azure_modify_resource or azure_create_resource).",
        )

    return PolicyDecision(True, READ, "")


# ============================================================================
# POST-OPERATION VERIFICATION - Evidence gates for mutation tools
# ============================================================================

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
