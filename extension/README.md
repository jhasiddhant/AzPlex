# AzPlex — VS Code Extension

MCP server for **Azure**, **Azure DevOps**, and **Microsoft Fabric** — deploy, manage, and orchestrate cloud resources using natural language in GitHub Copilot Chat.

## Features

- **Azure Resource Management** — Deploy 40+ resource types via Bicep templates using natural language
- **Azure Security & Identity** — RBAC assignments, PIM activation, auto-resolve email/name to Object ID
- **Azure Networking** — Private endpoints with auto DNS, VNet integration, NSP attachment
- **Azure Monitoring** — Diagnostic settings, Application Insights, DCE/DCR
- **Azure DevOps** — Create projects, repos, branches, pipelines, assign roles
- **Microsoft Fabric** — Create workspaces, Git integration, deployment pipelines, managed private endpoints

## Prerequisites

- **Python 3.10+**
- **PowerShell Core (pwsh)** — [Install](https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell)
- **Azure CLI** — [Install](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli), authenticated via `az login`
- **GitHub Copilot Chat** extension

## Getting Started

1. Install this extension
2. The MCP server is registered automatically — no manual configuration needed
3. Open GitHub Copilot Chat and start using natural language:

```
create storage account in my-rg
list resources in my-rg
activate all my PIM roles
create devops project named MyProject
create fabric workspace named MyWorkspace
```

## Usage Examples

### Azure
```
login to azure
create resource group named my-rg in eastus
create key vault in my-rg
create function app in my-rg
create private endpoint for my-storage blob in my-subnet
assign Contributor role to user@example.com via PIM on my-rg
```

### Azure DevOps
```
list all devops projects in organization myorg
create project named MyProject with repo MainRepo
create branch feature/new-feature from main in MyRepo
```

### Microsoft Fabric
```
create fabric workspace named MyWorkspace in capacity <capacity-id>
attach fabric workspace to git repo MyRepo
create deployment pipeline Dev-to-Prod with workspaces DevWS,ProdWS
```

## Supported Azure Resource Types

Storage Account, Key Vault, Azure OpenAI, AI Search, AI Foundry, Cosmos DB, MongoDB Cluster, Container Registry, Function App (Flex/ASP), App Service, SQL Server/Database, Redis Cache, VNet, Subnet, NSG, Private Endpoint, DNS Zone, API Management, Azure Firewall, Firewall Policy, NAT Gateway, VPN Gateway, Front Door, WAF Policy, DDoS Protection, DNS Resolver, Log Analytics, Application Insights, Container Apps, Container App Job, Service Bus, Data Factory, Synapse, Fabric Capacity, Automation Account, Speech Service, Logic App, and more.

## Links

- [GitHub](https://github.com/jhasiddhant/azplex)
- [PyPI Package](https://pypi.org/project/azplex/)
- [Issues](https://github.com/jhasiddhant/azplex/issues)

## License

[MIT](https://github.com/jhasiddhant/azplex/blob/main/LICENSE)
