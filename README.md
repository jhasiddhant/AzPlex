# AzPlex

**AzPlex** is an [MCP](https://modelcontextprotocol.io/) server for **Azure**, **Azure DevOps**, and **Microsoft Fabric**. It lets you deploy, manage, and orchestrate cloud resources using natural language in VS Code with GitHub Copilot Chat.

## Install

**Option A — VS Code Extension (recommended):**

Install the [AzPlex extension](https://marketplace.visualstudio.com/items?itemName=jhasiddhant.azplex) from the VS Code Marketplace. It bundles the MCP server automatically.

**Option B — pip:**

```bash
pip install azplex
```

Then add to your MCP config (`.vscode/mcp.json`):

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

## Prerequisites

- **Python 3.10+**
- **PowerShell Core (pwsh)** — [Install](https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell)
- **Azure CLI** — [Install](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli), authenticated via `az login`
- **GitHub Copilot Chat** extension in VS Code

## What It Does

**40 MCP tools** across Azure, Azure DevOps, and Microsoft Fabric — plus **50 Bicep resource types** for infrastructure deployment.

### Azure (24 tools)

| Category | Tools |
|----------|-------|
| **Auth & Account** | Login, list/set subscriptions, get current user, show agent instructions |
| **Resource Management** | Create resource groups, deploy 50 resource types via Bicep templates, query resources (Resource Graph & CLI), check existence, update tags, activity logs |
| **Security & Identity** | List RBAC roles (active/eligible), activate PIM roles (all or specific), assign PIM eligible roles, assign RBAC to SPNs/MIs |
| **Networking** | Private endpoints with auto DNS, manage PE connections (list/approve/reject), VNet integration & network ACL rules, NSP attachment |
| **Monitoring** | Diagnostic settings, App Insights attachment, data collection endpoints, data collection rules, DCE-to-DCR attachment |
| **Container Apps** | Create Container Apps Environment (VNet, zone-redundant, workload profiles), create Container Apps (auto-detect/create environment) |

### Azure DevOps (9 tools)

Create and manage projects, repositories, branches, pipelines, deploy YAML templates or custom YAML, and assign roles.

### Microsoft Fabric (7 tools)

List workspaces/permissions, create workspaces, assign roles, Git integration, deployment pipelines (Dev/UAT/Prod), managed private endpoints.

### Supported Bicep Resource Types (50)

Storage Account, Key Vault, Azure OpenAI, AI Search, AI Foundry, Cosmos DB, MongoDB Cluster, Container Registry, Function App (Flex/ASP), App Service, SQL Server, SQL Database, Redis Cache, VNet, Subnet, NSG, Private Endpoint, Private DNS Zone, DNS Zone VNet Link, API Management, Azure Firewall, Firewall Policy, NAT Gateway, VPN Gateway, Front Door, WAF Policy, DDoS Protection Plan, DNS Resolver, Log Analytics, Application Insights, Container Apps Environment, Container App, Container App Job, Service Bus, Data Factory, Synapse, Fabric Capacity, Automation Account, Speech Service, Logic App, UAMI, NSP, DCE, DCR, Public IP, Log Search Alert, Document Intelligence, Content Safety, Language Service, Log Search Alert.

## Usage Examples

```
login to azure
create storage account in my-rg
list resources in my-rg
activate all my PIM roles with justification "sprint deployment"
create private endpoint for my-storage blob in my-subnet
create azure devops project named MyProject with repo MainRepo
create fabric workspace named MyWorkspace in capacity <capacity-id>
```

## Architecture

![Architecture](docs/architecture.png)

## License

[MIT](LICENSE)
