# AzPlex

MCP server for **Azure**, **Azure DevOps**, and **Microsoft Fabric** — deploy, manage, and orchestrate from one interface.

[![PyPI](https://img.shields.io/pypi/v/azplex)](https://pypi.org/project/azplex/)
[![Python](https://img.shields.io/pypi/pyversions/azplex)](https://pypi.org/project/azplex/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/jhasiddhant/azplex/blob/main/LICENSE)

## Quick Start

```bash
pip install azplex
```

Add to your VS Code MCP config (`.vscode/mcp.json`):

```json
{
  "servers": {
    "azplex": {
      "type": "stdio",
      "command": "python3",
      "args": ["-m", "azplex.server"]
    }
  }
}
```

Or use `uvx`:

```json
{
  "servers": {
    "azplex": {
      "type": "stdio",
      "command": "uvx",
      "args": ["azplex"]
    }
  }
}
```

## Prerequisites

- Python 3.10+
- [PowerShell Core (pwsh)](https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell)
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) — authenticated via `az login`

## Features

### Azure (17 tools)

- **Auth & Account** — Login, list/set subscriptions, get current user
- **Resource Info** — Unified query tool: list resources/RGs, find resources, get managed identity, activity logs, Resource Graph KQL, read-only CLI
- **Resource Management** — Create resource groups, deploy 50 resource types via Bicep, modify resources (tags, start/stop/restart, scale, public access, local auth, VNet integration, attach NSP/diagnostics/AppInsights/DCE)
- **Security & Identity** — List RBAC roles (active/eligible), assign/remove roles (RBAC or PIM), activate/deactivate PIM roles, schedule future/recurring PIM activation, grant additive ADLS Gen2 POSIX ACLs
- **Networking** — Manage PE connections (list/approve/reject)

### Azure DevOps (8 tools)

- List/create projects and repositories
- Create, show, update, query, and comment on work items
- Create branches, deploy YAML pipelines
- Assign security group roles

### Microsoft Fabric (7 tools)

- List workspaces, permissions, and managed private endpoints
- Create workspaces and assign roles
- Git integration with Azure DevOps
- Deployment pipelines (Dev→Prod, Dev→UAT→Prod)
- Managed private endpoints

## Usage

Use natural language in GitHub Copilot Chat or any MCP-compatible client:

```
create storage account in my-rg
list resources in my-rg
activate all my PIM roles
create devops project named MyProject
create fabric workspace named MyWorkspace
```

## Links

- [GitHub](https://github.com/jhasiddhant/azplex)
- [VS Code Extension](https://marketplace.visualstudio.com/items?itemName=jhasiddhant.azplex)
- [Issues](https://github.com/jhasiddhant/azplex/issues)

## License

[MIT](https://github.com/jhasiddhant/azplex/blob/main/LICENSE)
