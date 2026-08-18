# Changelog

All notable changes to AzPlex are documented in this file.

## [1.0.1] - 2026-08-18

### Added
- **ADO work items** — `ado_manage_work_item` for create, show, update, WIQL query, and comment via authenticated Azure DevOps REST with safe JSON Patch.
- **Post-operation verification** — shared operation-result contract with read-after-write evidence gates and batch aggregation (succeeded/failed/skipped).
- **Centralized guardrails** — policy layer that classifies Azure CLI operations (read/mutate/destructive), restricts raw CLI to read-only, blocks shell-metacharacter injection, and redacts secrets.
- **Scheduled PIM** — `azure_schedule_pim_activation` for future one-shot and recurring (daily/weekday) activations with UTC normalization and bounded horizon.
- **ADLS Gen2 ACLs** — `azure_assign_adls_acl` for additive POSIX ACL grants with traversal, default ACLs, read-back verification, and guarded recursion.
- **Stronger validation** — enforce Bicep `@minLength/@maxLength/@minValue/@maxValue`, reusable validators, and ambiguity-aware identity resolution.

### Changed
- Native, self-contained MCP server (PyInstaller) — no user-side Python or package installation required.
- Automatic, version-triggered cache cleanup on extension update; executable-bit repair for reliable fresh installs.
- Removed the `Invoke-Expression` escape hatch and the unrestricted `cli-raw` mutation path.
