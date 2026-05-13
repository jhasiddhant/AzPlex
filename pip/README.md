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

### Azure (44 tools)

- **Resource Management** — Deploy 40+ resource types via Bicep templates (Storage, Key Vault, OpenAI, Cosmos DB, Function Apps, Container Apps, SQL, Redis, VNet, Firewall, Front Door, and many more)
- **Security & Identity** — RBAC role assignments, PIM activation/assignment, auto-resolve email/name to Object ID
- **Networking** — Private endpoints with auto DNS, VNet integration, NSP attachment
- **Monitoring** — Diagnostic settings, Application Insights, Data Collection Endpoints/Rules

### Azure DevOps (9 tools)

- List/create projects and repositories
- Create branches, deploy YAML pipelines
- Assign security group roles

### Microsoft Fabric (8 tools)

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
