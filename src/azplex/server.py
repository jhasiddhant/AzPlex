# ============================================================================
# MCP SERVER - Tool definitions only
# ============================================================================
# All business logic is in separate modules:
#   - azure.py   : Azure resource management functions
#   - ado.py     : Azure DevOps functions
#   - fabric.py  : Microsoft Fabric functions  
#   - general.py : User identity and instructions
#   - utils.py   : Shared helpers and constants
# ============================================================================

from typing import Literal

from mcp.server.fastmcp import FastMCP

# Import function modules - handle both package and direct execution
try:
    from . import azure
    from . import ado
    from . import fabric
    from . import general
except ImportError:
    from azplex import azure
    from azplex import ado
    from azplex import fabric
    from azplex import general

# ============================================================================
# MCP SERVER INITIALIZATION
# ============================================================================

mcp = FastMCP("azplex")

@mcp.tool()
def get_current_user() -> str:
    """
    Gets the current Azure subscription, tenant, and user email.
    
    Returns:
        JSON with subscription name, subscriptionId, tenantId, and user_email
    """
    return general.get_current_user()


@mcp.tool()
def show_agent_instructions() -> str:
    """
    Returns the complete agent instructions and capabilities documentation.
    Use this to understand the agent's features, supported resources, and operational guidelines.
    """
    return general.show_agent_instructions()


@mcp.tool()
def azure_login(selected_subscription_id: str = None) -> str:
    """
    Login to Azure - for first-time users or switching accounts.
    Opens browser for authentication.
    
    Handles three scenarios automatically:
    1. No subscriptions: Logs in with --allow-no-subscriptions
    2. One subscription: Sets it as default automatically
    3. Multiple subscriptions: Returns list for user to choose, then call again with selected_subscription_id
    
    Args:
        selected_subscription_id: Optional. If user has multiple subscriptions, call this tool again 
                                  with the chosen subscription ID to set it as default.
    
    Returns:
        JSON with login status and subscription info. If action is "choose_subscription", 
        user must select one and call this tool again with selected_subscription_id.
    """
    return general.azure_login(selected_subscription_id)


@mcp.tool()
def azure_list_roles(
    role_type: str = None,
    user_principal_name: str = None,
    force_refresh: bool = True
) -> str:
    """
    Lists Azure roles for the current user - either active assignments or eligible PIM roles.
    
    USE THIS TOOL for ANY request about listing, showing, or viewing Azure roles/permissions.
    
    BEHAVIOR BASED ON USER REQUEST:
    
    1. User asks for "active roles", "current roles", "my assignments", "what roles do I have":
       → Use role_type="active"
       
    2. User asks for "PIM roles", "eligible roles", "roles I can activate":
       → Use role_type="eligible"
       
    3. User just says "list my roles" or "show permissions" WITHOUT specifying type:
       → ASK the user: "Would you like to see your active (currently assigned) roles 
         or eligible (PIM roles available for activation)?"
       → Do NOT guess - the user must specify which type they want
    
    Args:
        role_type: REQUIRED - Type of roles to list:
            - "active": Currently active/assigned RBAC roles (includes permanent assignments 
              AND temporarily activated PIM roles)
            - "eligible": Eligible PIM roles that can be activated (not yet active)
            - If not specified, returns a message to ask the user which type they want
        user_principal_name: Optional user email. Defaults to current logged-in user.
            Only applicable for role_type="active"
        force_refresh: Whether to force refresh the role cache. Default is True.
            Only applicable for role_type="active"
    
    Returns:
        For role_type="active": Table of current Azure role assignments
        For role_type="eligible": List of eligible PIM roles with max activation hours
    
    Examples:
        # User says "show my active roles"
        azure_list_roles(role_type="active")
        
        # User says "what PIM roles can I activate" or "list eligible roles"
        azure_list_roles(role_type="eligible")
        
        # User says "list my roles" (ambiguous - must ask)
        # First ask user which type, then call with their answer
    """
    return azure.list_roles(role_type, user_principal_name, force_refresh)


@mcp.tool()
def azure_assign_role(
    mode: str,
    scope: str,
    object_ids: list = None,
    role_names: list = None,
    principal_type: str = None,
    principal_id: str = None,
    role_name: str = None,
    duration: str = None,
    justification: str = None
) -> str:
    """
    Assigns Azure roles - RBAC direct assignments or PIM eligible assignments.
    
    Two modes:
    
    MODE 1: mode="rbac" — Direct RBAC assignment (for SPNs/Managed Identities ONLY)
        [POLICY] Direct RBAC for Users/Groups is NOT RECOMMENDED — use mode="pim" instead.
        Supports bulk: multiple object_ids × multiple role_names.
        Args: scope, object_ids (list), role_names (list), principal_type ("ServicePrincipal" or "ManagedIdentity")
    
    MODE 2: mode="pim" — PIM eligible assignment (for Users/Groups/SPs)
        Creates an ELIGIBLE (not active) role assignment. Principal activates via PIM when needed.
        NOTE: PIM eligible roles can ONLY be assigned at Subscription or Resource Group level.
        CRITICAL: Ask user for justification and duration before calling.
        Args: scope, principal_id, role_name, duration (default: P365D), justification (REQUIRED)
    
    Args:
        mode: "rbac" or "pim" (required)
        scope: Azure resource scope (required). Examples:
            - /subscriptions/{sub-id}
            - /subscriptions/{sub-id}/resourceGroups/{rg-name}
            - /subscriptions/{sub-id}/resourceGroups/{rg}/providers/{type}/{name} (RBAC only)
        object_ids: List of Object IDs to assign roles to (RBAC mode)
        role_names: List of role names to assign (RBAC mode)
        principal_type: "ServicePrincipal" or "ManagedIdentity" (RBAC mode)
        principal_id: Object ID of user/group/SP (PIM mode)
        role_name: Single role name to assign (PIM mode)
        duration: ISO 8601 duration for PIM (default: P365D). Examples: P365D, P180D, P30D
        justification: Business justification (PIM mode, REQUIRED - must come from user)
    
    Returns:
        Assignment results with success/failure status
    """
    if mode == "rbac":
        return azure.assign_rbac_role(scope, object_ids, role_names, principal_type)
    elif mode == "pim":
        return azure.assign_pim_eligible_role(
            scope=scope,
            principal_id=principal_id,
            role_name=role_name,
            duration=duration or "P365D",
            justification=justification or "Platform deployment access"
        )
    else:
        return f"Invalid mode '{mode}'. Must be 'rbac' or 'pim'."


@mcp.tool()
def azure_activate_pim_roles(
    justification: str = None,
    activate_all: bool = False,
    subscription_name: str = None,
    resource_group_name: str = None,
    resource_name: str = None,
    role_name: str = None,
    duration_hours: int = 0
) -> str:
    """
    Activates eligible PIM roles for the current user.
    
    CRITICAL: Justification is MANDATORY — ask the user before calling.
    
    Two modes:
    1. activate_all=True: Activates ALL eligible PIM roles across all scopes
    2. Specific: Provide role_name + subscription_name (+ optional resource_group_name/resource_name)
    
    Args:
        justification: Business justification (REQUIRED - must come from user)
        activate_all: Set True to activate all eligible roles
        subscription_name: Subscription name for specific role mode
        resource_group_name: Resource group name for RG-level scope (optional)
        resource_name: Resource name for resource-level scope (optional)
        role_name: Specific role to activate (e.g., "Contributor")
        duration_hours: Duration in hours (0 = max allowed per role policy)
    
    Returns:
        Activation results with success/failure status per role
    """
    return azure.activate_pim_roles(
        justification=justification,
        activate_all=activate_all,
        subscription_name=subscription_name,
        resource_group_name=resource_group_name,
        resource_name=resource_name,
        role_name=role_name,
        duration_hours=duration_hours
    )


@mcp.tool()
def azure_schedule_pim_activation(
    justification: str,
    mode: str,
    scope: str = None,
    principal_id: str = None,
    role_definition_id: str = None,
    timestamps: list = None,
    daily_times: list = None,
    pattern: str = "daily",
    duration_hours: int = 8,
    horizon_days: int = 7,
    tz_name: str = None,
) -> str:
    """
    Schedules future or recurring PIM role activations.

    CRITICAL: Justification is MANDATORY — ask the user before calling. Confirm the
    plan (windows, duration, timezone) with the user before submitting.

    Two modes:
    1. mode="schedule_activate": one-shot future activations. Provide `timestamps`
       (ISO 8601). Naive timestamps use `tz_name`; all are normalized to UTC.
    2. mode="schedule_continuous": recurring activations. Provide `daily_times`
       (list of "HH:MM") and `pattern` ("daily" or "weekdays"). Expansion is bounded
       by `horizon_days` (max 30).

    Past, overlapping, duplicate, and beyond-horizon windows are rejected and reported.
    Submission requires scope, principal_id, and role_definition_id.

    Args:
        justification: Business justification (REQUIRED - must come from user).
        mode: "schedule_activate" or "schedule_continuous".
        scope: Azure scope for the activation (subscription or resource group).
        principal_id: Object ID of the principal to activate for.
        role_definition_id: Role definition ID or full role definition resource ID.
        timestamps: ISO 8601 timestamps for schedule_activate.
        daily_times: List of "HH:MM" slots for schedule_continuous.
        pattern: "daily" or "weekdays" for schedule_continuous.
        duration_hours: Activation duration in hours (1-24, default 8).
        horizon_days: Scheduling horizon in days (1-30, default 7).
        tz_name: IANA timezone for naive timestamps and recurring slots (e.g. "America/New_York").

    Returns:
        JSON with the scheduled windows, per-request results, and succeeded/failed/skipped counts.
    """
    return azure.schedule_pim_activation(
        justification=justification,
        mode=mode,
        scope=scope,
        principal_id=principal_id,
        role_definition_id=role_definition_id,
        timestamps=timestamps,
        daily_times=daily_times,
        pattern=pattern,
        duration_hours=duration_hours,
        horizon_days=horizon_days,
        tz_name=tz_name,
    )


@mcp.tool()
def azure_deactivate_pim_roles(
    deactivate_all: bool = False,
    subscription_name: str = None,
    resource_group_name: str = None,
    role_name: str = None
) -> str:
    """
    Deactivates active PIM roles for the current user.
    
    Supports two modes:
    1. deactivate_all=True: Deactivates ALL currently active PIM roles
    2. Specific: Deactivates a specific role at a specific scope
    
    Args:
        deactivate_all: Set True to deactivate all active PIM roles
        subscription_name: Subscription name for specific role deactivation
        resource_group_name: Resource group name for RG-level scope (optional)
        role_name: Specific role to deactivate (e.g., "Contributor")
    
    Returns:
        Deactivation results with success/failure status per role
    """
    return azure.deactivate_pim_roles(
        deactivate_all=deactivate_all,
        subscription_name=subscription_name,
        resource_group_name=resource_group_name,
        role_name=role_name
    )


@mcp.tool()
def azure_remove_role(
    mode: str,
    scope: str,
    object_ids: list = None,
    role_names: list = None,
    principal_id: str = None,
    role_name: str = None,
    justification: str = "Role removal"
) -> str:
    """
    Removes Azure role assignments - RBAC direct assignments or PIM eligible assignments.
    
    Two modes:
    1. mode="rbac": Remove direct RBAC role assignments (for SPNs/Managed Identities)
    2. mode="pim": Remove PIM eligible role assignments (for Users/Groups/SPs)
    
    Args:
        mode: "rbac" or "pim" (required)
        scope: Azure resource scope (required). Examples:
            - /subscriptions/{sub-id}
            - /subscriptions/{sub-id}/resourceGroups/{rg-name}
            - /subscriptions/{sub-id}/resourceGroups/{rg}/providers/{type}/{name}
        object_ids: List of Object IDs to remove roles from (RBAC mode)
        role_names: List of role names to remove (RBAC mode)
        principal_id: Object ID of the principal (PIM mode)
        role_name: Role name to remove (PIM mode)
        justification: Business justification (PIM mode, optional)
    
    Returns:
        Removal results with success/failure status
    """
    return azure.remove_role(
        mode=mode,
        scope=scope,
        object_ids=object_ids,
        role_names=role_names,
        principal_id=principal_id,
        role_name=role_name,
        justification=justification
    )


@mcp.tool()
def azure_get_resource_info(
    query_type: str,
    resource_name: str = None,
    resource_group: str = None,
    resource_type: str = None,
    resource_id: str = None,
    location: str = None,
    custom_query: str = None,
    days: int = None,
    max_events: int = 50,
    operation_type: str = None
) -> str:
    """
    Unified tool for querying Azure resources, resource groups, and their properties.
    
    Args:
        query_type: Type of query to perform. Options:
            - "list_rgs": List all resource groups in subscription
            - "list_resources": List resources (optionally filtered by resource_group or resource_type)
            - "get_resource": Get detailed info for a specific resource - name, type, location, tags, ID (requires resource_name)
            - "find_resource": Find which RG contains a resource (requires resource_name)
            - "check_type_in_rg": Check if resource type exists in RG (requires resource_group, resource_type)
            - "get_rg_info": Get resource group info (requires resource_group)
            - "get_identity": Get principalId (object ID) and clientId for any resource with managed identity.
                              For UAMIs: set resource_type="uami". Returns principalId, clientId, tenantId.
                              For other resources: returns system-assigned and/or user-assigned identity details.
            - "activity_log": Retrieve Azure Activity Log events for auditing/troubleshooting.
                              Uses: resource_group, resource_id, resource_name, days, max_events, operation_type.
                              days: 1-90 (default: 7). max_events: up to 500 (default: 50).
                              operation_type: "Write", "Delete", or "Action".
            - "custom": Run a custom Azure Resource Graph KQL query (requires custom_query). 
                        Example: "Resources | where type == 'Microsoft.Compute/virtualMachines'"
            - "cli_raw": Run a read-only Azure CLI command (requires custom_query).
                         Only read verbs (show, list, get, etc.) are permitted; mutating and
                         destructive commands are denied by guardrail policy.
                         Example: "az identity show --name my-uami -g my-rg"
        resource_name: Resource name (for get_resource, find_resource, get_identity, activity_log)
        resource_group: Resource group name (for filtering or specific queries)
        resource_type: Resource type filter (storage-account, key-vault, openai, uami, etc.)
        resource_id: Full resource ID (for activity_log filtering)
        location: Location filter
        custom_query: Azure Resource Graph KQL query (for query_type="custom") or CLI command (for query_type="cli_raw")
        days: Number of days to look back for activity_log (1-90, default: 7)
        max_events: Maximum events to return for activity_log (default: 50, max: 500)
        operation_type: Filter activity_log by operation type ("Write", "Delete", "Action")
    
    Returns:
        JSON with query results
    """
    if query_type == "activity_log":
        return azure.get_activity_log(resource_group, resource_id, resource_name, days, max_events, operation_type)
    return azure.query_resources(query_type, resource_name, resource_group, resource_type, location, custom_query)


@mcp.tool()
def azure_list_subscriptions() -> str:
    """
    Lists all Azure subscriptions the current user has access to.
    Returns subscription name, ID, state, and whether it's the default.
    
    Returns:
        JSON with list of accessible subscriptions
    """
    return general.list_subscriptions()


@mcp.tool()
def azure_set_subscription(subscription_id: str = None, subscription_name: str = None) -> str:
    """
    Sets the active Azure subscription for subsequent commands.
    
    Args:
        subscription_id: Subscription ID (GUID) to switch to
        subscription_name: Subscription name to switch to (alternative to ID)
    
    Returns:
        Confirmation message with the new active subscription
    """
    return general.set_subscription(subscription_id, subscription_name)


@mcp.tool()
def azure_modify_resource(
    action: str,
    resource_name: str = None,
    resource_group: str = None,
    resource_type: str = None,
    resource_id: str = None,
    value: str = None,
    tags: str = None,
    tags_operation: str = "merge",
    attach_target: str = None,
    nsp_name: str = None,
    workspace_id: str = None,
    app_insights_name: str = None,
    app_insights_resource_group: str = None,
    target_app_name: str = None,
    target_resource_group: str = None,
    target_type: str = None,
    dcr_name: str = None,
    dcr_resource_group: str = None,
    dce_name: str = None,
    dce_resource_group: str = None,
    subscription_id: str = None,
    subnet_id: str = None
) -> str:
    """
    Unified tool to modify Azure resources. Does NOT create or delete resources.
    
    Args:
        action: Modification action (required). One of:
            - "tags": Add/update/replace tags on a resource
            - "start": Start a stopped resource (webapp, functionapp, containerapp)
            - "stop": Stop a running resource (webapp, functionapp, containerapp)
            - "restart": Restart a resource (webapp, functionapp, redis)
            - "scale": Change SKU/tier (webapp, sql-database, redis, acr, servicebus)
            - "set-public-access": Enable/disable public network access (storage-account, key-vault, openai, acr, sql-server, servicebus, cosmosdb)
            - "set-local-auth": Enable/disable local auth/API keys (storage-account, openai, servicebus)
            - "vnet-integrate": Add VNet integration or network ACL rules
            - "attach": Attach compliance/monitoring (nsp, diagnostic_settings, appinsights, dce_to_dcr)
        resource_name: Name of the Azure resource
        resource_group: Resource group containing the resource
        resource_type: Type of resource (webapp, functionapp, storage-account, key-vault, openai, sql-database, redis, acr, containerapp, servicebus, cosmosdb, etc.)
        resource_id: Full resource ID (for tags, attach)
        value: Action-specific value:
            - scale: SKU name (e.g., "S1", "P1v3", "Premium")
            - set-public-access: "true" or "false"
            - set-local-auth: "true" (enable) or "false" (disable)
        tags: Tag key-value pairs in format "key1=value1,key2=value2" (for action="tags")
        tags_operation: "merge" (default) or "replace" (for action="tags")
        attach_target: What to attach (for action="attach"): nsp, diagnostic_settings, appinsights, dce_to_dcr
        nsp_name: NSP name (for attach nsp)
        workspace_id: Log Analytics workspace resource ID (for attach diagnostic_settings)
        app_insights_name: App Insights name (for attach appinsights)
        app_insights_resource_group: RG of App Insights (for attach appinsights)
        target_app_name: Function App/Web App name (for attach appinsights)
        target_resource_group: RG of target app (for attach appinsights)
        target_type: "functionapp" or "webapp" (for attach appinsights)
        dcr_name: DCR name (for attach dce_to_dcr)
        dcr_resource_group: RG of DCR (for attach dce_to_dcr)
        dce_name: DCE name (for attach dce_to_dcr)
        dce_resource_group: RG of DCE (for attach dce_to_dcr)
        subscription_id: Subscription ID (for attach dce_to_dcr)
        subnet_id: Full subnet resource ID (for action="vnet-integrate")
    
    Returns:
        Modification result with status
    """
    return azure.modify_resource(
        action=action,
        resource_name=resource_name,
        resource_group=resource_group,
        resource_type=resource_type,
        resource_id=resource_id,
        value=value,
        tags=tags,
        tags_operation=tags_operation,
        attach_target=attach_target,
        nsp_name=nsp_name,
        workspace_id=workspace_id,
        app_insights_name=app_insights_name,
        app_insights_resource_group=app_insights_resource_group,
        target_app_name=target_app_name,
        target_resource_group=target_resource_group,
        target_type=target_type,
        dcr_name=dcr_name,
        dcr_resource_group=dcr_resource_group,
        dce_name=dce_name,
        dce_resource_group=dce_resource_group,
        subscription_id=subscription_id,
        subnet_id=subnet_id
    )


@mcp.tool()
def azure_create_resource(resource_type: str, resource_group: str = None, parameters: str = None) -> str:
    """Interactive Azure resource creation using Bicep templates.
    
    When called without resource_group or parameters, returns the required/optional
    parameters for the specified resource type (acts as a requirements lookup).
    When called with all parameters, deploys the resource.
    
    IMPORTANT: For resources with hosting variants, always use the BASE type first:
    - For function apps: use 'function-app' (NOT 'function-app-flex' or 'function-app-appserviceplan')
    This returns the available hosting options for the user to choose from.
    Only use the specific variant AFTER the user has explicitly chosen one.
    
    Args:
        resource_type: Type of resource to create (e.g. storage-account, key-vault, function-app, etc.)
        resource_group: Azure resource group name (omit to get parameter requirements)
        parameters: JSON string of resource-specific parameters (omit to get parameter requirements)
    
    Returns:
        Parameter requirements if resource_group/parameters not provided, or deployment status with resource details
    """
    return azure.create_resource(resource_type, resource_group, parameters)


@mcp.tool()
def azure_manage_pe_connection(
    action: str = None,
    resource_id: str = None,
    connection_id: str = None,
    connection_name: str = None,
    description: str = None
) -> str:
    """
    Manages private endpoint connections on Azure resources - list, approve, or reject.
    
    This unified tool handles all PE connection operations:
    - 'list': Show all PE connections (pending/approved/rejected) on a resource
    - 'approve': Approve a pending PE connection
    - 'reject': Reject a PE connection request
    
    Workflow:
    1. Call with action='list' and resource_id to see all connections
    2. Copy the connection_id of the target connection
    3. Call with action='approve' or 'reject' and the connection_id
    
    Args:
        action: Action to perform - 'list', 'approve', or 'reject' (required)
        resource_id: Full resource ID of the target resource (required for 'list')
        connection_id: Full PE connection ID (for approve/reject - preferred)
        connection_name: PE connection name (alternative to connection_id, use with resource_id)
        description: Approval/rejection reason (optional)
    
    Returns:
        List of connections or action result
    
    Examples:
        # List connections on a storage account
        azure_manage_pe_connection(action='list', resource_id='/subscriptions/.../storageAccounts/mysa')
        
        # Approve a pending connection
        azure_manage_pe_connection(action='approve', connection_id='<id from list>')
        
        # Reject with custom reason
        azure_manage_pe_connection(action='reject', connection_id='<id>', description='Not authorized')
    """
    return azure.manage_private_endpoint_connection(
        action=action,
        resource_id=resource_id,
        connection_id=connection_id,
        connection_name=connection_name,
        description=description
    )


@mcp.tool()
def azure_create_resource_group(resource_group_name: str, region: str, project_name: str) -> str:
    """Creates an Azure resource group with project tagging."""
    return azure.create_resource_group(resource_group_name, region, project_name)


@mcp.tool()
def fabric_list(
    target: str,
    user_principal_name: str = None,
    workspace_id: str = None
) -> str:
    """
    Unified tool to list Microsoft Fabric resources.

    Args:
        target: What to list. One of: 'permissions', 'workspaces', 'managed_private_endpoints'
        user_principal_name: Optional user email (for target='permissions'). Defaults to current user.
        workspace_id: Fabric workspace ID - GUID (required for target='managed_private_endpoints')

    Returns:
        List of requested Fabric resources
    """
    if target == "permissions":
        return fabric.list_permissions(user_principal_name)
    elif target == "workspaces":
        return fabric.list_workspaces()
    elif target == "managed_private_endpoints":
        return fabric.list_managed_private_endpoints(workspace_id)
    else:
        return f"Invalid target '{target}'. Must be one of: permissions, workspaces, managed_private_endpoints"


@mcp.tool()
def fabric_create_managed_private_endpoint(
    workspace_id: str,
    endpoint_name: str,
    target_resource_id: str,
    group_id: str
) -> str:
    """
    Creates a Managed Private Endpoint in Microsoft Fabric for secure outbound connectivity to Azure resources.
    
    This allows Fabric notebooks and Spark jobs to securely connect to Azure resources (Storage, Key Vault, SQL, etc.)
    via private networking. After creation, the endpoint requires APPROVAL on the target Azure resource.
    
    Args:
        workspace_id: Fabric workspace ID (GUID). Get from workspace URL or fabric_list_workspaces.
        endpoint_name: Name for the managed private endpoint (e.g., "adls-mydata", "kv-secrets")
        target_resource_id: Full Azure resource ID to connect to
        group_id: Sub-resource type (e.g., "blob", "dfs", "vault", "sqlServer")
    
    Returns:
        Creation status with endpoint details and approval instructions
    """
    return fabric.create_managed_private_endpoint(workspace_id, endpoint_name, target_resource_id, group_id)


@mcp.tool()
def fabric_create_workspace(capacity_id: str = None, workspace_name: str = None, 
                           description: str = "") -> str:
    """
    Creates a Microsoft Fabric workspace in a capacity.
    
    Workflow:
    1. Validates capacity ID and workspace name
    2. Creates workspace using Fabric REST API
    3. Associates workspace with specified capacity
    
    Args:
        capacity_id: Full resource ID of the Fabric capacity (e.g., /subscriptions/.../resourceGroups/.../providers/Microsoft.Fabric/capacities/...)
        workspace_name: Name for the new workspace
        description: Optional description for the workspace
    
    Returns:
        Workspace creation status with workspace ID and details
    """
    return fabric.create_workspace(capacity_id, workspace_name, description)


@mcp.tool()
def fabric_attach_workspace_to_git(workspace_id: str = None, organization: str = None,
                                   project_name: str = None, repo_name: str = None,
                                   branch_name: str = None, directory_name: str = "/") -> str:
    """
    Attaches a Microsoft Fabric workspace to an Azure DevOps Git repository.
    
    Workflow:
    1. Validates workspace ID and Git connection details
    2. Connects workspace to specified Azure DevOps repository
    3. Enables Git integration for workspace items
    
    Args:
        workspace_id: Fabric workspace ID (GUID)
        organization: Azure DevOps organization URL or name
        project_name: Azure DevOps project name
        repo_name: Azure DevOps repository name
        branch_name: Git branch name (e.g., 'main')
        directory_name: Directory path in repository (defaults to '/')
    
    Returns:
        Git connection status with workspace and repository details
    """
    return fabric.attach_workspace_to_git(workspace_id, organization, project_name, repo_name, branch_name, directory_name)


@mcp.tool()
def fabric_assign_role(
    workspace_identifier: str,
    role_name: str,
    principal_id: str,
    principal_type: str
) -> str:
    """
    Assigns a role to a user, group, service principal, or managed identity in a Microsoft Fabric workspace.
    
    Use this tool when a user wants to grant access to a Fabric workspace.
    
    Args:
        workspace_identifier: Workspace name or workspace ID (GUID). Can use either.
        role_name: Role to assign. Must be one of: Admin, Contributor, Member, Viewer
            - Admin: Full control including managing permissions and deleting workspace
            - Contributor: Can create, edit, delete items but cannot manage permissions
            - Member: Can view and interact with items
            - Viewer: Read-only access to workspace items
        principal_id: Object ID (Principal ID) of the identity to grant access to.
            For Users: User's Object ID from Entra ID
            For Groups: Group's Object ID from Entra ID  
            For Service Principals: Application's Object ID (not Application ID)
            For Managed Identities: Principal ID of the managed identity
        principal_type: Type of principal. Must be one of:
            - User: For individual user accounts
            - Group: For Entra ID security groups or Microsoft 365 groups
            - ServicePrincipal: For app registrations / service principals
            - ServicePrincipalProfile: For managed identities
    
    Returns:
        Role assignment status with details
    """
    return fabric.assign_role(workspace_identifier, role_name, principal_id, principal_type)


@mcp.tool()
def fabric_create_deployment_pipeline(
    pipeline_name: str,
    pipeline_type: str,
    workspace_names: str,
    description: str = ""
) -> str:
    """
    Creates Microsoft Fabric deployment pipeline(s) and assigns workspaces.
    
    IMPORTANT: User MUST choose a pipeline_type. Three options available:
    - "Dev-to-Prod": 1 pipeline (Development -> Production), 2 workspaces
    - "UAT-to-Prod": 1 pipeline (UAT -> Production), 2 workspaces
    - "Dev-to-UAT-to-Prod": 2 pipelines (Dev->UAT + UAT->Prod), 3 workspaces
    
    Args:
        pipeline_name: Name for the pipeline (prefix for Dev-to-UAT-to-Prod)
        pipeline_type: REQUIRED - Must be one of: "Dev-to-Prod", "UAT-to-Prod", or "Dev-to-UAT-to-Prod"
        workspace_names: Comma-separated workspace names matching the type.
            Dev-to-Prod: "DevWS,ProdWS" (2 names)
            UAT-to-Prod: "UATWS,ProdWS" (2 names)
            Dev-to-UAT-to-Prod: "DevWS,UATWS,ProdWS" (3 names)
        description: Optional description for the pipeline(s)
    
    Returns:
        Pipeline creation and workspace assignment results
    """
    return fabric.create_deployment_pipeline(pipeline_name, pipeline_type, workspace_names, description)


@mcp.tool()
def fabric_add_deployment_pipeline_role(
    pipeline_id: str,
    user_email: str,
    role: str = "Admin",
    principal_type: str = "User"
) -> str:
    """
    Adds a role assignment to a deployment pipeline.
    
    Accepts user email and automatically resolves it to the Entra ID Object ID.
    
    Args:
        pipeline_id: The deployment pipeline ID (GUID)
        user_email: The user's email address (auto-resolved to Object ID)
        role: Role to assign - currently only "Admin" is supported
        principal_type: Type of principal - "User", "Group", "ServicePrincipal", or "ServicePrincipalProfile"
    
    Returns:
        JSON with role assignment result
    """
    return fabric.add_deployment_pipeline_role(pipeline_id, user_email, role, principal_type)


@mcp.tool()
def ado_create_project(organization: str = None, project_name: str = None, repo_name: str = None, description: str = None) -> str:
    """
    Creates an Azure DevOps project using AZ CLI via the PS1 script and sets the initial repo name.

    Behavior: Runs creation, then confirms the project via read-back before claiming success.
    Returns a structured operation result with command status, verification status, and evidence.
    Required: organization (URL or org name), project_name, repo_name; description optional.
    """
    return ado.create_project(organization, project_name, repo_name, description)


@mcp.tool()
def ado_create_repo(organization: str = None, project_name: str = None, repo_name: str = None) -> str:
    """
    Creates a new Azure DevOps Git repository via the PS1 script.

    Behavior: Runs creation, then confirms the repository via read-back before claiming success.
    Returns a structured operation result with command status, verification status, and evidence.
    Required: organization (URL or org name), project_name, repo_name.
    """
    return ado.create_repo(organization, project_name, repo_name)


@mcp.tool()
def ado_list(target: str, organization: str = None, project_name: str = None) -> str:
    """
    Lists Azure DevOps resources - projects or repositories.

    Args:
        target: What to list. One of: 'projects', 'repos'
        organization: Azure DevOps organization URL or name (required)
        project_name: Project name (required for target='repos')

    Returns:
        List of projects or repositories with their details
    """
    if target == "projects":
        return ado.list_projects(organization)
    elif target == "repos":
        return ado.list_repos(organization, project_name)
    else:
        return f"Invalid target '{target}'. Must be one of: projects, repos"


@mcp.tool()
def ado_manage_work_item(
    action: Literal["create", "show", "update", "query", "comment"],
    organization: str,
    project_name: str,
    work_item_id: int = None,
    work_item_type: str = None,
    title: str = None,
    description: str = None,
    assigned_to: str = None,
    state: str = None,
    iteration_path: str = None,
    area_path: str = None,
    priority: int = None,
    story_points: float = None,
    start_date: str = None,
    target_date: str = None,
    tags: list[str] = None,
    parent_id: int = None,
    comment: str = None,
    wiql: str = None,
    top: int = 50,
) -> str:
    """
    Creates, shows, updates, queries, or comments on Azure DevOps work items.

    Required for every action: action, organization, project_name.
    Action-specific requirements:
    - create: work_item_type and title
    - show: work_item_id
    - update: work_item_id and at least one supported field or parent_id
    - comment: work_item_id and comment
    - query: optional WIQL; defaults to recently changed project work items

    Args:
        action: One of "create", "show", "update", "query", or "comment".
        organization: Azure DevOps organization URL or organization name.
        project_name: Azure DevOps project name.
        work_item_id: Positive work-item ID for show, update, or comment.
        work_item_type: Type for create, such as "User Story", "Bug", or "Task".
        title: Work-item title. Required for create.
        description: Work-item description.
        assigned_to: Assignee identity recognized by Azure DevOps.
        state: Workflow state supported by the selected work-item type.
        iteration_path: Iteration path.
        area_path: Area path.
        priority: Integer priority.
        story_points: Story-point estimate.
        start_date: Start date in an Azure DevOps-supported ISO 8601 format.
        target_date: Target date in an Azure DevOps-supported ISO 8601 format.
        tags: Tags to store as a semicolon-delimited Azure DevOps field.
        parent_id: Positive parent work-item ID for create or update.
        comment: Comment text for the comment action.
        wiql: WIQL SELECT query for the query action.
        top: Maximum WIQL results, from 1 to 200. Defaults to 50.

    Returns:
        Structured JSON with success, action, and normalized data or an actionable error.
    """
    return ado.manage_work_item(
        action=action,
        organization=organization,
        project_name=project_name,
        work_item_id=work_item_id,
        work_item_type=work_item_type,
        title=title,
        description=description,
        assigned_to=assigned_to,
        state=state,
        iteration_path=iteration_path,
        area_path=area_path,
        priority=priority,
        story_points=story_points,
        start_date=start_date,
        target_date=target_date,
        tags=tags,
        parent_id=parent_id,
        comment=comment,
        wiql=wiql,
        top=top,
    )


@mcp.tool()
def ado_create_branch(organization: str = None, project_name: str = None, 
                        repo_name: str = None, branch_name: str = None, 
                        base_branch: str = None) -> str:
    """
    Creates a new branch in an Azure DevOps repository from a base branch.

    Behavior: Creates branch from specified base branch (defaults to 'main').
    Branch name can be simple (e.g., 'dev') or folder-based (e.g., 'feature/myfeature').
    Required: organization, project_name, repo_name, branch_name, base_branch (defaults to 'main').
    """
    return ado.create_branch(organization, project_name, repo_name, branch_name, base_branch)


# ============================================================================
# AZURE DEVOPS TOOLS - Pipelines
# ============================================================================

@mcp.tool()
def ado_deploy_pipeline_yaml(organization: str = None, project_name: str = None, 
                        repo_name: str = None, pipeline_type: str = None,
                        branch: str = None, folder_path: str = None,
                        custom_yaml_content: str = None, yaml_file_name: str = None) -> str:
    """
    Deploys pipeline YAML to an Azure DevOps repository - from templates OR custom YAML content.
    
    Workflow:
    1. If custom_yaml_content provided → deploys custom YAML directly
    2. If pipeline_type matches PIPELINE_TEMPLATE_MAP entry → uses that template
    3. Otherwise → prompts for custom YAML content
    4. Clones repo, copies YAML to specified folder, commits and pushes
    
    Args:
        organization: Azure DevOps organization URL (required)
        project_name: Existing project name (required)
        repo_name: Existing repository name (required)
        pipeline_type: Template key from PIPELINE_TEMPLATE_MAP OR identifier for custom YAML (required)
        branch: Branch to deploy to (defaults to 'main')
        folder_path: Folder in repo to deploy YAML (defaults to 'pipelines')
        custom_yaml_content: Custom YAML content to deploy (optional - overrides template)
        yaml_file_name: Custom filename for YAML (optional - defaults to pipeline_type.yml)
    
    Returns:
        Deployment status and YAML location
    """
    return ado.deploy_pipeline_yaml(organization, project_name, repo_name, pipeline_type, branch, folder_path, custom_yaml_content, yaml_file_name)


@mcp.tool()
def ado_create_pipeline(organization: str = None, project_name: str = None,
                          repo_name: str = None, pipeline_name: str = None,
                          branch: str = None, pipeline_type: str = None,
                          yaml_path: str = None) -> str:
    """
    Creates an Azure DevOps pipeline from YAML file in repository.
    
    Template Management (Similar to Bicep TEMPLATE_MAP):
    - Pipeline templates are defined in PIPELINE_TEMPLATE_MAP
    - Keywords: '1ES', 'prod', 'production' → selects 1ES template
    - Auto-constructs yaml_path as: pipelines/{template_file}.yml
    - OR use yaml_path parameter to specify a custom YAML file path
    
    Workflow:
    1. Auto-detects pipeline type from pipeline_name keywords (if yaml_path not provided)
    2. Constructs yaml_path from PIPELINE_TEMPLATE_MAP (if yaml_path not provided)
    3. Checks if YAML exists in repository
    4. Creates pipeline referencing the YAML
    
    Note: YAML file must already exist in repository (use ado_deploy_pipeline_yaml first)
    
    Args:
        organization: Azure DevOps organization URL
        project_name: Existing project name
        repo_name: Existing repository name
        pipeline_name: Name for pipeline (keywords '1ES'/'prod' select production template)
        branch: Branch containing YAML (defaults to 'main')
        pipeline_type: Optional explicit template type from PIPELINE_TEMPLATE_MAP
        yaml_path: Optional custom YAML file path in repository (e.g., 'pipelines/sourcebranchvalidation.yml')
    
    Returns:
        Pipeline creation status and URL
    """
    return ado.create_pipeline(organization, project_name, repo_name, pipeline_name, branch, pipeline_type, yaml_path)


@mcp.tool()
def ado_assign_role(
    organization: str = None,
    project_name: str = None,
    role_name: str = None,
    principal_id: str = None
) -> str:
    """
    Assigns a role (security group membership) to a principal in an Azure DevOps project.
    
    Common built-in roles:
    - Project Administrators: Full control over project settings and security
    - Build Administrators: Manage build pipelines and definitions
    - Release Administrators: Manage release pipelines and deployments
    - Contributors: Create and modify code, work items, and pipelines
    - Readers: View-only access to project resources
    - Endpoint Administrators: Manage service connections
    - Endpoint Creators: Create service connections
    
    Custom roles/groups are also supported - provide the exact group name.
    
    If the role does not exist, the tool will return an error listing available groups.
    
    Args:
        organization: Azure DevOps organization URL or name
        project_name: Name of the Azure DevOps project
        role_name: Name of the security group/role to assign
        principal_id: Object ID (GUID) of the user, group, service principal, or managed identity from Azure AD/Entra ID
    
    Returns:
        Role assignment result with status and details
    """
    return ado.assign_role(organization, project_name, role_name, principal_id)


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
