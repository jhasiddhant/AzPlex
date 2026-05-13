<#
.SYNOPSIS
    Modifies Azure resources - start/stop, enable/disable, scale SKU, update properties.

.DESCRIPTION
    Unified script for resource modifications via Azure CLI.
    Supports: start, stop, restart, scale, enable/disable public access, enable/disable local auth.

.PARAMETER Action
    The modification action: start, stop, restart, scale, set-public-access, set-local-auth, update-sku, cli-raw

.PARAMETER ResourceName
    Name of the Azure resource.

.PARAMETER ResourceGroup
    Resource group containing the resource.

.PARAMETER ResourceType
    Type of resource (functionapp, webapp, sql-server, sql-database, containerapp, cosmosdb, openai, storage-account, key-vault, redis, acr, etc.)

.PARAMETER Value
    Value for the action (e.g., SKU name for scale, "true"/"false" for enable/disable, raw CLI command for cli-raw).

.EXAMPLE
    .\modify-resource.ps1 -Action stop -ResourceName "myapp" -ResourceGroup "my-rg" -ResourceType "webapp"
    .\modify-resource.ps1 -Action scale -ResourceName "mydb" -ResourceGroup "my-rg" -ResourceType "sql-database" -Value "S1"
    .\modify-resource.ps1 -Action set-public-access -ResourceName "mystorage" -ResourceGroup "my-rg" -ResourceType "storage-account" -Value "false"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Action,

    [Parameter(Mandatory = $false)]
    [string]$ResourceName = "",

    [Parameter(Mandatory = $false)]
    [string]$ResourceGroup = "",

    [Parameter(Mandatory = $false)]
    [string]$ResourceType = "",

    [Parameter(Mandatory = $false)]
    [string]$Value = ""
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Modifying Azure Resource" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Action        : $Action" -ForegroundColor Yellow
Write-Host "Resource      : $ResourceName" -ForegroundColor Yellow
Write-Host "Resource Group: $ResourceGroup" -ForegroundColor Yellow
Write-Host "Resource Type : $ResourceType" -ForegroundColor Yellow
if ($Value) { Write-Host "Value         : $Value" -ForegroundColor Yellow }
Write-Host "==========================================" -ForegroundColor Cyan

$result = $null
$success = $false

try {
    switch ($Action) {
        # ================================================================
        # START / STOP / RESTART
        # ================================================================
        "start" {
            switch ($ResourceType) {
                "webapp"       { $result = az webapp start --name $ResourceName -g $ResourceGroup 2>&1 }
                "functionapp"  { $result = az functionapp start --name $ResourceName -g $ResourceGroup 2>&1 }
                "containerapp" { $result = az containerapp start --name $ResourceName -g $ResourceGroup 2>&1 }
                "sql-server"   { Write-Host "SQL Server is always-on. Use sql-database to manage." -ForegroundColor Yellow; exit 0 }
                "sql-database" { $result = az sql db update --name $ResourceName -g $ResourceGroup --server $Value --status "Online" 2>&1 }
                default        { Write-Error "Start not supported for resource type: $ResourceType" }
            }
        }

        "stop" {
            switch ($ResourceType) {
                "webapp"       { $result = az webapp stop --name $ResourceName -g $ResourceGroup 2>&1 }
                "functionapp"  { $result = az functionapp stop --name $ResourceName -g $ResourceGroup 2>&1 }
                "containerapp" { $result = az containerapp stop --name $ResourceName -g $ResourceGroup 2>&1 }
                default        { Write-Error "Stop not supported for resource type: $ResourceType" }
            }
        }

        "restart" {
            switch ($ResourceType) {
                "webapp"       { $result = az webapp restart --name $ResourceName -g $ResourceGroup 2>&1 }
                "functionapp"  { $result = az functionapp restart --name $ResourceName -g $ResourceGroup 2>&1 }
                "redis"        { $result = az redis force-reboot --name $ResourceName -g $ResourceGroup --reboot-type AllNodes 2>&1 }
                default        { Write-Error "Restart not supported for resource type: $ResourceType" }
            }
        }

        # ================================================================
        # SCALE / UPDATE SKU
        # ================================================================
        "scale" {
            if (-not $Value) { Write-Error "Value (SKU/tier) is required for scale action" }
            switch ($ResourceType) {
                "webapp"       { $result = az appservice plan update -g $ResourceGroup --name $ResourceName --sku $Value 2>&1 }
                "functionapp"  { $result = az appservice plan update -g $ResourceGroup --name $ResourceName --sku $Value 2>&1 }
                "sql-database" {
                    # Value format: "S1" or "GP_Gen5_2" etc.
                    $parts = $Value -split "/"
                    $serverName = $parts[0]
                    $sku = if ($parts.Count -gt 1) { $parts[1] } else { $Value }
                    $result = az sql db update --name $ResourceName -g $ResourceGroup --server $serverName --service-objective $sku 2>&1
                }
                "redis"        { $result = az redis update --name $ResourceName -g $ResourceGroup --sku $Value 2>&1 }
                "acr"          { $result = az acr update --name $ResourceName -g $ResourceGroup --sku $Value 2>&1 }
                "servicebus"   { $result = az servicebus namespace update --name $ResourceName -g $ResourceGroup --sku $Value 2>&1 }
                default        { Write-Error "Scale not supported for resource type: $ResourceType" }
            }
        }

        # ================================================================
        # ENABLE / DISABLE PUBLIC NETWORK ACCESS
        # ================================================================
        "set-public-access" {
            if (-not $Value) { Write-Error "Value ('true' or 'false') is required" }
            $enabled = if ($Value -eq "true") { "Enabled" } else { "Disabled" }
            switch ($ResourceType) {
                "storage-account" { $result = az storage account update --name $ResourceName -g $ResourceGroup --public-network-access $enabled 2>&1 }
                "key-vault"       { $result = az keyvault update --name $ResourceName -g $ResourceGroup --public-network-access $enabled 2>&1 }
                "openai"          { $result = az cognitiveservices account update --name $ResourceName -g $ResourceGroup --public-network-access $enabled 2>&1 }
                "acr"             { $result = az acr update --name $ResourceName -g $ResourceGroup --public-network-access $enabled 2>&1 }
                "sql-server"      { $result = az sql server update --name $ResourceName -g $ResourceGroup --public-network-access $enabled 2>&1 }
                "servicebus"      { $result = az servicebus namespace update --name $ResourceName -g $ResourceGroup --public-network-access $enabled 2>&1 }
                "cosmosdb"        { $result = az cosmosdb update --name $ResourceName -g $ResourceGroup --public-network-access $enabled 2>&1 }
                default           { Write-Error "set-public-access not supported for resource type: $ResourceType" }
            }
        }

        # ================================================================
        # ENABLE / DISABLE LOCAL AUTH (API KEYS)
        # ================================================================
        "set-local-auth" {
            if (-not $Value) { Write-Error "Value ('true' or 'false') is required" }
            $disable = if ($Value -eq "false") { "true" } else { "false" }
            switch ($ResourceType) {
                "storage-account" { $result = az storage account update --name $ResourceName -g $ResourceGroup --allow-shared-key-access $Value 2>&1 }
                "openai"          { $result = az cognitiveservices account update --name $ResourceName -g $ResourceGroup --custom-domain $ResourceName --api-properties "{`"disableLocalAuth`":$disable}" 2>&1 }
                "servicebus"      { $result = az servicebus namespace update --name $ResourceName -g $ResourceGroup --disable-local-auth $disable 2>&1 }
                default           { Write-Error "set-local-auth not supported for resource type: $ResourceType" }
            }
        }

        # ================================================================
        # RAW CLI COMMAND (for anything not covered above)
        # ================================================================
        "cli-raw" {
            if (-not $Value) { Write-Error "Value (CLI command) is required for cli-raw action" }
            $result = Invoke-Expression $Value 2>&1
        }

        default {
            Write-Error "Unknown action: $Action. Supported: start, stop, restart, scale, set-public-access, set-local-auth, cli-raw"
        }
    }

    if ($LASTEXITCODE -eq 0 -or $null -eq $LASTEXITCODE) {
        $success = $true
    }
}
catch {
    $result = $_.Exception.Message
    $success = $false
}

if ($success) {
    Write-Host "`nSUCCESS" -ForegroundColor Green
} else {
    Write-Host "`nFAILED" -ForegroundColor Red
}

$output = @{
    action       = $Action
    resourceName = $ResourceName
    resourceGroup = $ResourceGroup
    resourceType = $ResourceType
    status       = if ($success) { "Success" } else { "Failed" }
    output       = if ($result) { "$result" } else { "Completed" }
}

Write-Host "`nJSON Output:" -ForegroundColor Cyan
$output | ConvertTo-Json -Depth 5
