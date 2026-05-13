<#
.SYNOPSIS
    Removes Azure role assignments - RBAC direct assignments or PIM eligible assignments.

.DESCRIPTION
    Unified script to remove:
    1. RBAC: Direct role assignments (for SPNs/Managed Identities)
    2. PIM: Eligible role assignments (for Users/Groups/SPs)

.PARAMETER Mode
    "rbac" for direct RBAC removal, "pim" for PIM eligible removal.

.PARAMETER Scope
    Azure resource scope (required for both modes).

.PARAMETER ObjectIds
    Comma-separated Object IDs to remove roles from (RBAC mode).

.PARAMETER RoleNames
    Comma-separated role names to remove (RBAC mode).

.PARAMETER PrincipalId
    Object ID of the principal (PIM mode).

.PARAMETER RoleName
    Role name to remove (PIM mode).

.PARAMETER Justification
    Business justification (PIM mode, optional).

.EXAMPLE
    .\remove-role.ps1 -Mode rbac -Scope "/subscriptions/xxx/resourceGroups/rg" -ObjectIds "id1" -RoleNames "Contributor"

.EXAMPLE
    .\remove-role.ps1 -Mode pim -Scope "/subscriptions/xxx" -PrincipalId "id1" -RoleName "Contributor"
#>

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("rbac", "pim")]
    [string]$Mode,

    [Parameter(Mandatory = $true)]
    [string]$Scope,

    [Parameter(Mandatory = $false)]
    [string]$ObjectIds = "",

    [Parameter(Mandatory = $false)]
    [string]$RoleNames = "",

    [Parameter(Mandatory = $false)]
    [string]$PrincipalId = "",

    [Parameter(Mandatory = $false)]
    [string]$RoleName = "",

    [Parameter(Mandatory = $false)]
    [string]$Justification = "Role removal"
)

$ErrorActionPreference = "Stop"

if ($Mode -eq "rbac") {
    # ========================================================================
    # RBAC REMOVAL
    # ========================================================================
    if (-not $ObjectIds -or -not $RoleNames) {
        Write-Error "RBAC mode requires -ObjectIds and -RoleNames"
        exit 1
    }

    $ObjectIdList = $ObjectIds -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' }
    $RoleNameList = $RoleNames -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' }

    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "Removing RBAC Role Assignments" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "Scope      : $Scope" -ForegroundColor Yellow
    Write-Host "Object IDs : $($ObjectIdList -join ', ')" -ForegroundColor Yellow
    Write-Host "Roles      : $($RoleNameList -join ', ')" -ForegroundColor Yellow
    Write-Host "==========================================" -ForegroundColor Cyan

    $results = @()
    $successCount = 0
    $failCount = 0

    foreach ($objectId in $ObjectIdList) {
        foreach ($role in $RoleNameList) {
            Write-Host "`nRemoving '$role' from $objectId..." -ForegroundColor Yellow
            try {
                az role assignment delete --assignee $objectId --role $role --scope $Scope --yes 2>&1 | Out-Null
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "  SUCCESS" -ForegroundColor Green
                    $successCount++
                    $results += @{ ObjectId = $objectId; Role = $role; Status = "Removed" }
                } else {
                    Write-Host "  FAILED" -ForegroundColor Red
                    $failCount++
                    $results += @{ ObjectId = $objectId; Role = $role; Status = "Failed" }
                }
            }
            catch {
                Write-Host "  FAILED - $($_.Exception.Message)" -ForegroundColor Red
                $failCount++
                $results += @{ ObjectId = $objectId; Role = $role; Status = "Failed"; Error = $_.Exception.Message }
            }
        }
    }

    $output = @{
        mode = "rbac"
        summary = @{ total = ($ObjectIdList.Count * $RoleNameList.Count); successful = $successCount; failed = $failCount }
        roles = $results
    }
    Write-Host "`nJSON Output:" -ForegroundColor Cyan
    $output | ConvertTo-Json -Depth 5
}
elseif ($Mode -eq "pim") {
    # ========================================================================
    # PIM ELIGIBLE REMOVAL
    # ========================================================================
    if (-not $PrincipalId -or -not $RoleName) {
        Write-Error "PIM mode requires -PrincipalId and -RoleName"
        exit 1
    }

    # Load shared PIM utilities
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    . "$scriptDir\pim-utils.ps1"

    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "Removing PIM Eligible Role Assignment" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "Scope        : $Scope" -ForegroundColor Yellow
    Write-Host "Principal ID : $PrincipalId" -ForegroundColor Yellow
    Write-Host "Role         : $RoleName" -ForegroundColor Yellow
    Write-Host "==========================================" -ForegroundColor Cyan

    Write-Host "`nRetrieving access token..." -ForegroundColor Yellow
    $authContext = Get-PIMAuthContext

    # Resolve role definition ID
    Write-Host "Resolving role definition for '$RoleName'..." -ForegroundColor Yellow
    $roleDefResult = az role definition list --name "$RoleName" --scope "$Scope" --query "[0].id" -o tsv 2>$null
    if (-not $roleDefResult) {
        Write-Error "Could not find role definition for '$RoleName' at scope '$Scope'"
        exit 1
    }

    Write-Host "Role Definition ID: $roleDefResult" -ForegroundColor Gray

    try {
        $guid = [guid]::NewGuid().ToString()
        $body = @{
            properties = @{
                principalId      = $PrincipalId
                roleDefinitionId = $roleDefResult
                requestType      = "AdminRemove"
                justification    = $Justification
            }
        } | ConvertTo-Json -Depth 10

        $removeUrl = "https://management.azure.com$Scope/providers/Microsoft.Authorization/roleEligibilityScheduleRequests/$guid`?api-version=2020-10-01"
        $response = Invoke-RestMethod -Uri $removeUrl -Headers $authContext.Headers -Method Put -Body $body -ErrorAction Stop

        Write-Host "SUCCESS - PIM eligible role removed" -ForegroundColor Green
        $output = @{
            mode = "pim"
            summary = @{ total = 1; successful = 1; failed = 0 }
            roles = @(@{
                PrincipalId = $PrincipalId
                Role        = $RoleName
                Scope       = $Scope
                Status      = "Removed"
            })
        }
    }
    catch {
        $errMsg = $_.Exception.Message
        Write-Host "FAILED - $errMsg" -ForegroundColor Red
        $output = @{
            mode = "pim"
            summary = @{ total = 1; successful = 0; failed = 1 }
            roles = @(@{
                PrincipalId = $PrincipalId
                Role        = $RoleName
                Scope       = $Scope
                Status      = "Failed"
                Error       = $errMsg
            })
        }
    }

    Write-Host "`nJSON Output:" -ForegroundColor Cyan
    $output | ConvertTo-Json -Depth 5
}
