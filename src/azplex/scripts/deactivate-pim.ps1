<#
.SYNOPSIS
    Deactivates active PIM roles for the current user.

.DESCRIPTION
    Deactivates currently active PIM role assignments. Supports two modes:
    1. DeactivateAll: Deactivates ALL active PIM roles
    2. Specific: Deactivates a specific role at a specific scope

.PARAMETER DeactivateAll
    When set, deactivates ALL active PIM roles.

.PARAMETER SubscriptionName
    Name of the subscription for specific role deactivation.

.PARAMETER ResourceGroupName
    Optional. Name of the resource group for RG-level scope.

.PARAMETER RoleName
    Name of the role to deactivate. Required when not using DeactivateAll.

.EXAMPLE
    .\deactivate-pim.ps1 -DeactivateAll

.EXAMPLE
    .\deactivate-pim.ps1 -SubscriptionName "MCAPSDE_DEV" -RoleName "Contributor"
#>

param(
    [Parameter(Mandatory = $false)]
    [switch]$DeactivateAll,

    [Parameter(Mandatory = $false)]
    [string]$SubscriptionName = "",

    [Parameter(Mandatory = $false)]
    [string]$ResourceGroupName = "",

    [Parameter(Mandatory = $false)]
    [string]$RoleName = ""
)

$ErrorActionPreference = "Stop"

# Load shared PIM utilities
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. "$scriptDir\pim-utils.ps1"

# Validate parameters
if (-not $DeactivateAll -and -not $SubscriptionName) {
    Write-Error "Either -DeactivateAll or -SubscriptionName must be provided"
    exit 1
}

if (-not $DeactivateAll -and -not $RoleName) {
    Write-Error "When not using -DeactivateAll, -RoleName must be specified"
    exit 1
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deactivating PIM Roles" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
if ($DeactivateAll) {
    Write-Host "Mode          : Deactivate ALL active roles" -ForegroundColor Magenta
} else {
    Write-Host "Mode          : Specific role deactivation" -ForegroundColor Magenta
    Write-Host "Role          : $RoleName" -ForegroundColor Gray
    Write-Host "Subscription  : $SubscriptionName" -ForegroundColor Gray
    if ($ResourceGroupName) {
        Write-Host "Resource Group: $ResourceGroupName" -ForegroundColor Gray
    }
}
Write-Host "==========================================" -ForegroundColor Cyan

# Authenticate
Write-Host "`nRetrieving user info and access token..." -ForegroundColor Yellow
try {
    $authContext = Get-PIMAuthContext
    Write-Host "User        : $($authContext.UserName)" -ForegroundColor Gray
}
catch {
    Write-Host "Authentication failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Get active role assignments (PIM-activated only, not permanent)
Write-Host "`nFetching active PIM role assignments..." -ForegroundColor Yellow

$activeUrl = "https://management.azure.com/providers/Microsoft.Authorization/roleAssignmentScheduleInstances?api-version=2020-10-01&`$filter=asTarget()"
$activeResponse = Invoke-RestMethod -Uri $activeUrl -Headers $authContext.Headers -Method Get -ErrorAction Stop

$activeRoles = @()
foreach ($item in $activeResponse.value) {
    $props = $item.properties
    # Only include PIM-activated roles (memberType=Direct, assignmentType=Activated)
    if ($props.assignmentType -ne "Activated") { continue }

    $roleDefId = $props.roleDefinitionId
    $scope = $props.scope
    $roleName_ = Get-RoleDefinitionName -RoleDefId $roleDefId -Headers $authContext.Headers

    $roleObj = [PSCustomObject]@{
        RoleName         = $roleName_
        RoleDefinitionId = $roleDefId
        Scope            = $scope
        PrincipalId      = $props.principalId
    }

    # Add scope details
    $subscriptionId = ""
    $subName = ""
    $rgName = ""
    if ($scope -match "/subscriptions/([^/]+)") {
        $subscriptionId = $Matches[1]
        $subName = Get-SubscriptionName -SubscriptionId $subscriptionId
        if ($scope -match "/resourceGroups/([^/]+)") {
            $rgName = $Matches[1]
        }
    }
    $roleObj | Add-Member -NotePropertyName "Subscription" -NotePropertyValue $subName
    $roleObj | Add-Member -NotePropertyName "SubscriptionId" -NotePropertyValue $subscriptionId
    $roleObj | Add-Member -NotePropertyName "ResourceGroup" -NotePropertyValue $rgName

    $activeRoles += $roleObj
}

Write-Host "Found $($activeRoles.Count) active PIM role(s)" -ForegroundColor Green

# Filter if specific mode
if (-not $DeactivateAll) {
    $filtered = $activeRoles | Where-Object {
        ($_.Subscription -eq $SubscriptionName -or $_.Subscription -like "*$SubscriptionName*" -or $_.SubscriptionId -eq $SubscriptionName) -and
        $_.RoleName -eq $RoleName
    }
    if ($ResourceGroupName) {
        $filtered = $filtered | Where-Object { $_.ResourceGroup -eq $ResourceGroupName }
    }
    $activeRoles = $filtered
}

if ($activeRoles.Count -eq 0) {
    Write-Host "No active PIM roles found matching the criteria." -ForegroundColor Yellow
    $output = @{
        summary = @{ total = 0; successful = 0; failed = 0 }
        message = if ($DeactivateAll) { "No active PIM roles to deactivate" } else { "No active role '$RoleName' found at specified scope" }
    }
    Write-Host "`nJSON Output:" -ForegroundColor Cyan
    $output | ConvertTo-Json -Depth 5
    exit 0
}

# Deactivate each role
$results = @()
$successCount = 0
$failCount = 0

foreach ($role in $activeRoles) {
    $rn = $role.RoleName
    $scope = $role.Scope
    $roleDefId = $role.RoleDefinitionId
    $principalId = if ($authContext.PrincipalId) { $authContext.PrincipalId } else { $role.PrincipalId }

    Write-Host "`n------------------------------------------" -ForegroundColor Gray
    Write-Host "Deactivating: $rn" -ForegroundColor Yellow
    Write-Host "  Scope: $scope" -ForegroundColor Gray

    try {
        $guid = [guid]::NewGuid().ToString()
        $body = @{
            properties = @{
                principalId      = $principalId
                roleDefinitionId = $roleDefId
                requestType      = "SelfDeactivate"
            }
        } | ConvertTo-Json -Depth 10

        $deactivateUrl = "https://management.azure.com$scope/providers/Microsoft.Authorization/roleAssignmentScheduleRequests/$guid`?api-version=2020-10-01"
        Invoke-RestMethod -Uri $deactivateUrl -Headers $authContext.Headers -Method Put -Body $body -ErrorAction Stop | Out-Null

        Write-Host "  SUCCESS - Deactivated" -ForegroundColor Green
        $successCount++
        $results += [PSCustomObject]@{
            RoleName = $rn
            Scope    = $scope
            Status   = "Deactivated"
        }
    }
    catch {
        $errMsg = $_.Exception.Message
        Write-Host "  FAILED - $errMsg" -ForegroundColor Red
        $failCount++
        $results += [PSCustomObject]@{
            RoleName = $rn
            Scope    = $scope
            Status   = "Failed"
            Error    = $errMsg
        }
    }
}

# Output summary
Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host "Deactivation Summary" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Total  : $($activeRoles.Count)" -ForegroundColor White
Write-Host "Success: $successCount" -ForegroundColor Green
Write-Host "Failed : $failCount" -ForegroundColor $(if ($failCount -gt 0) { "Red" } else { "Green" })

$output = @{
    summary = @{
        total      = $activeRoles.Count
        successful = $successCount
        failed     = $failCount
    }
    roles = $results
}

Write-Host "`nJSON Output:" -ForegroundColor Cyan
$output | ConvertTo-Json -Depth 5
