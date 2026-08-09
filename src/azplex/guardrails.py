# ============================================================================
# GUARDRAILS - Centralized mutation and execution policy
# ============================================================================

import re
from typing import List, Tuple

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
