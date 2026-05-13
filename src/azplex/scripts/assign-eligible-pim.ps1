param(
    [Parameter(Mandatory=$true)]
    [string]$Scope,
    
    [Parameter(Mandatory=$true)]
    [string]$PrincipalID,
    
    [Parameter(Mandatory=$true)]
    [string]$RoleName,
    
    [Parameter(Mandatory=$false)]
    [string]$Duration = "P365D",
    
    [Parameter(Mandatory=$false)]
    [string]$Justification = "Platform deployment access"
)

$ErrorActionPreference = "Stop"

# Resolve role definition ID from role name
$roleDef = Get-AzRoleDefinition -Name $RoleName -ErrorAction Stop
if (-not $roleDef) { Write-Error "Role '$RoleName' not found."; exit 1 }
$roleDefId = "$Scope/providers/Microsoft.Authorization/roleDefinitions/$($roleDef.Id)"

# Check if role is already directly assigned
$existing = Get-AzRoleAssignment -Scope $Scope -PrincipalId $PrincipalID -RoleDefinitionName $RoleName -ErrorAction SilentlyContinue
if ($existing) { Write-Output "SKIP: Role '$RoleName' is already directly assigned to '$PrincipalID' at scope '$Scope'."; exit 0 }

# Check for existing PIM eligible assignment
try {
    $eligibleMatch = Get-AzRoleEligibilitySchedule -Scope $Scope -Filter "principalId eq '$PrincipalID'" -ErrorAction SilentlyContinue |
        Where-Object { $_.RoleDefinitionDisplayName -eq $RoleName }
    if ($eligibleMatch) { Write-Output "SKIP: PIM eligible '$RoleName' already exists for '$PrincipalID' at scope '$Scope'."; exit 0 }
} catch { }

# Assign PIM eligible role using native Az PowerShell
New-AzRoleEligibilityScheduleRequest `
    -Name ([guid]::NewGuid().ToString()) `
    -Scope $Scope `
    -PrincipalId $PrincipalID `
    -RoleDefinitionId $roleDefId `
    -RequestType "AdminAssign" `
    -ScheduleInfoStartDateTime (Get-Date).ToUniversalTime() `
    -ExpirationDuration $Duration `
    -ExpirationType "AfterDuration" `
    -Justification $Justification

Write-Output "SUCCESS: Assigned PIM eligible role '$RoleName' to '$PrincipalID' at scope '$Scope' for duration '$Duration'."
