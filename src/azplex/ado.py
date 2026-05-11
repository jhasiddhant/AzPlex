# ============================================================================
# ADO FUNCTIONS - Azure DevOps logic
# ============================================================================

import os
import json
from typing import Optional

try:
    from .utils import (
        run_powershell_script, get_script_path,
        detect_pipeline_type, PIPELINE_TEMPLATE_MAP
    )
except ImportError:
    from utils import (
        run_powershell_script, get_script_path,
        detect_pipeline_type, PIPELINE_TEMPLATE_MAP
    )


# ============================================================================
# Azure DevOps - Helpers
# ============================================================================

def _normalize_org_url(organization: str) -> str:
    """Normalize ADO organization to full URL format."""
    if organization and not organization.strip().lower().startswith("http"):
        return f"https://dev.azure.com/{organization.strip()}"
    return organization


# ============================================================================
# Azure DevOps - Projects & Repos
# ============================================================================

def create_project(organization: str = None, project_name: str = None, repo_name: str = None, description: str = None) -> str:
    """Creates an Azure DevOps project using AZ CLI via the PS1 script and sets the initial repo name."""
    organization = _normalize_org_url(organization)

    missing = []
    if not organization or not organization.strip():
        missing.append("organization (existing org URL where you're admin, e.g., https://dev.azure.com/<org>)")
    if not project_name or not project_name.strip():
        missing.append("project_name (name to keep/create)")
    if not repo_name or not repo_name.strip():
        missing.append("repo_name (initial repo name)")
    if missing:
        return (
            "ADO Project Creation\n\n"
            "Please provide:\n"
            + "\n".join([f"  - {m}" for m in missing]) +
            "\n\nOnly required inputs: organization, project_name, repo_name."
        )

    project_script = get_script_path("create-devops-project.ps1")
    if not os.path.exists(project_script):
        return "Error: create-devops-project.ps1 not found"

    proj_params = {
        "Organization": organization,
        "ProjectName": project_name,
        "RepoName": repo_name
    }
    if description:
        proj_params["Description"] = description

    try:
        proj_out = run_powershell_script(project_script, proj_params)
        return proj_out.strip()
    except Exception as e:
        return f"Project creation failed\n\nError: {str(e)}\nError Type: {type(e).__name__}\n\nScript: {project_script}\nParameters: {proj_params}"


def create_repo(organization: str = None, project_name: str = None, repo_name: str = None) -> str:
    """Creates a new Azure DevOps Git repository via the PS1 script."""
    organization = _normalize_org_url(organization)

    missing = []
    if not organization or not organization.strip():
        missing.append("organization (existing org URL where you're project admin)")
    if not project_name or not project_name.strip():
        missing.append("project_name (existing project)")
    if not repo_name or not repo_name.strip():
        missing.append("repo_name (new repo name to keep/create)")
    if missing:
        return (
            "ADO Repo Creation\n\n"
            "Please provide:\n"
            + "\n".join([f"  - {m}" for m in missing]) +
            "\n\nOnly required inputs: organization, project_name, repo_name."
        )

    repo_script = get_script_path("create-devops-repo.ps1")
    if not os.path.exists(repo_script):
        return "Error: create-devops-repo.ps1 not found"

    params = {
        "Organization": organization,
        "ProjectName": project_name,
        "RepoName": repo_name
    }

    try:
        out = run_powershell_script(repo_script, params)
        return out.strip()
    except Exception as e:
        return f"Repository creation failed\n\nError: {str(e)}\nError Type: {type(e).__name__}\n\nScript: {repo_script}\nParameters: {params}"


def list_projects(organization: str = None) -> str:
    """Lists all Azure DevOps projects in an organization."""
    organization = _normalize_org_url(organization)

    if not organization or not organization.strip():
        return (
            "ADO List Projects\n\n"
            "Please provide:\n"
            "  - organization (org URL to list projects from)\n\n"
            "Only required input: organization."
        )

    list_projects_script = get_script_path("list-devops-projects.ps1")
    if not os.path.exists(list_projects_script):
        return "Error: list-devops-projects.ps1 not found"

    params = {
        "Organization": organization
    }

    try:
        out = run_powershell_script(list_projects_script, params)
        return out.strip()
    except Exception as e:
        return f"List projects failed\n\nError: {str(e)}\nError Type: {type(e).__name__}\n\nScript: {list_projects_script}\n\nCommon causes:\n- Not authenticated: Run 'az login'\n- Missing Azure DevOps extension: Run 'az extension add --name azure-devops'\n- Invalid organization URL\n- No access to organization"


def list_repos(organization: str = None, project_name: str = None) -> str:
    """Lists all Azure DevOps repositories in a project."""
    organization = _normalize_org_url(organization)

    missing = []
    if not organization or not organization.strip():
        missing.append("organization (org URL)")
    if not project_name or not project_name.strip():
        missing.append("project_name (project to list repos from)")
    if missing:
        return (
            "ADO List Repositories\n\n"
            "Please provide:\n"
            + "\n".join([f"  - {m}" for m in missing]) +
            "\n\nOnly required inputs: organization, project_name."
        )

    list_repos_script = get_script_path("list-devops-repos.ps1")
    if not os.path.exists(list_repos_script):
        return "Error: list-devops-repos.ps1 not found"

    params = {
        "Organization": organization,
        "ProjectName": project_name
    }

    try:
        out = run_powershell_script(list_repos_script, params)
        return out.strip()
    except Exception as e:
        return f"List repositories failed\n\nError: {str(e)}\nError Type: {type(e).__name__}\n\nScript: {list_repos_script}\nParameters: {params}\n\nCommon causes:\n- Project does not exist\n- No access to project\n- Authentication issue"


def create_branch(organization: str = None, project_name: str = None, 
                  repo_name: str = None, branch_name: str = None, 
                  base_branch: str = None) -> str:
    """Creates a new branch in an Azure DevOps repository from a base branch."""
    organization = _normalize_org_url(organization)

    missing = []
    if not organization or not organization.strip():
        missing.append("organization (org URL)")
    if not project_name or not project_name.strip():
        missing.append("project_name (existing project)")
    if not repo_name or not repo_name.strip():
        missing.append("repo_name (existing repo)")
    if not branch_name or not branch_name.strip():
        missing.append("branch_name (new branch name, e.g., 'dev' or 'feature/myfeature')")
    if not base_branch or not base_branch.strip():
        missing.append("base_branch (branch to create from, usually 'main')")
    if missing:
        return (
            "ADO Create Branch\n\n"
            "Please provide:\n"
            + "\n".join([f"  - {m}" for m in missing]) +
            "\n\nOnly required inputs: organization, project_name, repo_name, branch_name, base_branch."
        )

    branch_script = get_script_path("create-devops-branch.ps1")
    if not os.path.exists(branch_script):
        return "Error: create-devops-branch.ps1 not found"

    params = {
        "Organization": organization,
        "ProjectName": project_name,
        "RepoName": repo_name,
        "BranchName": branch_name,
        "BaseBranch": base_branch
    }

    try:
        out = run_powershell_script(branch_script, params)
        return out.strip()
    except Exception as e:
        return f"Branch creation failed\n\nError: {str(e)}\nError Type: {type(e).__name__}\n\nScript: {branch_script}\nParameters: {params}\n\nCommon causes:\n- Base branch does not exist\n- Branch already exists\n- No write access to repository"


# ============================================================================
# Azure DevOps - Pipelines
# ============================================================================

def deploy_pipeline_yaml(organization: str = None, project_name: str = None, 
                         repo_name: str = None, pipeline_type: str = None,
                         branch: str = None, folder_path: str = None,
                         custom_yaml_content: str = None, yaml_file_name: str = None) -> str:
    """Deploys a pipeline YAML template or custom YAML content to an Azure DevOps repository."""
    organization = _normalize_org_url(organization)

    missing = []
    if not organization or not organization.strip():
        missing.append("organization (org URL)")
    if not project_name or not project_name.strip():
        missing.append("project_name (existing project)")
    if not repo_name or not repo_name.strip():
        missing.append("repo_name (existing repo)")
    if not pipeline_type or not pipeline_type.strip():
        missing.append("pipeline_type (template key like 'codeql', 'codeql-1es', or name for custom)")
    if not branch or not branch.strip():
        missing.append("branch (target branch, usually 'main')")
    if missing:
        templates_list = ', '.join(sorted(PIPELINE_TEMPLATE_MAP.keys())) if PIPELINE_TEMPLATE_MAP else "(none)"
        return (
            "Deploy Pipeline YAML\n\n"
            "Please provide:\n"
            + "\n".join([f"  - {m}" for m in missing]) +
            f"\n\nAvailable templates: {templates_list}"
            "\n\nOptional: folder_path (defaults to 'pipelines'), custom_yaml_content, yaml_file_name"
        )

    if not folder_path:
        folder_path = "pipelines"

    deploy_script = get_script_path("deploy-pipeline-yaml.ps1")
    if not os.path.exists(deploy_script):
        return "Error: deploy-pipeline-yaml.ps1 not found"

    if custom_yaml_content:
        yaml_name = yaml_file_name or f"{pipeline_type}.yml"
        if not yaml_name.endswith('.yml') and not yaml_name.endswith('.yaml'):
            yaml_name = f"{yaml_name}.yml"
        
        params = {
            "Organization": organization,
            "ProjectName": project_name,
            "RepoName": repo_name,
            "TemplateName": yaml_name.replace('.yml', '').replace('.yaml', ''),
            "Branch": branch,
            "FolderPath": folder_path,
            "CustomYamlContent": custom_yaml_content,
            "YamlFileName": yaml_name
        }
    else:
        detected_type = detect_pipeline_type(pipeline_type, pipeline_type)
        
        if detected_type in PIPELINE_TEMPLATE_MAP:
            template_basename = os.path.basename(PIPELINE_TEMPLATE_MAP[detected_type])
            params = {
                "Organization": organization,
                "ProjectName": project_name,
                "RepoName": repo_name,
                "TemplateName": template_basename.replace(".yml", ""),
                "Branch": branch,
                "FolderPath": folder_path
            }
        else:
            return (
                f"Pipeline template '{pipeline_type}' not found in agent/templates.\n\n"
                f"Available templates: {', '.join(PIPELINE_TEMPLATE_MAP.keys())}\n\n"
                "To deploy custom YAML, provide the custom_yaml_content parameter with your YAML content."
            )

    try:
        out = run_powershell_script(deploy_script, params)
        return out.strip()
    except Exception as e:
        return f"YAML deployment failed\n\nError: {str(e)}\nError Type: {type(e).__name__}\n\nScript: {deploy_script}\nParameters: {params}\n\nCommon causes:\n- Repository not initialized\n- Branch does not exist\n- No write access\n- Git authentication failed"


def create_pipeline(organization: str = None, project_name: str = None,
                    repo_name: str = None, pipeline_name: str = None,
                    branch: str = None, pipeline_type: str = None,
                    yaml_path: str = None) -> str:
    """Creates an Azure DevOps pipeline from YAML file in repository."""
    organization = _normalize_org_url(organization)

    if pipeline_name and not pipeline_type:
        pipeline_type = detect_pipeline_type(pipeline_name, "")
    elif not pipeline_type:
        pipeline_type = "codeql"

    missing = []
    if not organization or not organization.strip():
        missing.append("organization (org URL)")
    if not project_name or not project_name.strip():
        missing.append("project_name (existing project)")
    if not repo_name or not repo_name.strip():
        missing.append("repo_name (existing repo)")
    if not pipeline_name or not pipeline_name.strip():
        missing.append("pipeline_name (include '1ES' or 'prod' for production pipelines)")
    if not branch or not branch.strip():
        missing.append("branch (branch with YAML, usually 'main')")
    
    if missing:
        suggestion = f"\n\nDetected pipeline type: {pipeline_type}"
        if "1es" in pipeline_type or "prod" in pipeline_type:
            suggestion += "\nThis is a PRODUCTION pipeline (1ES template with pool parameters required)"
        else:
            suggestion += "\nThis is a standard pipeline template"
        
        templates_list = ', '.join(sorted(PIPELINE_TEMPLATE_MAP.keys())) if PIPELINE_TEMPLATE_MAP else "(none discovered)"
        
        return (
            "Create Azure DevOps Pipeline\n\n"
            "Please provide:\n"
            + "\n".join([f"  - {m}" for m in missing]) +
            suggestion +
            f"\n\nAvailable templates (auto-discovered): {templates_list}"
        )

    if pipeline_type in PIPELINE_TEMPLATE_MAP:
        template_basename = os.path.basename(PIPELINE_TEMPLATE_MAP[pipeline_type])
    elif PIPELINE_TEMPLATE_MAP:
        first_key = sorted(PIPELINE_TEMPLATE_MAP.keys())[0]
        template_basename = os.path.basename(PIPELINE_TEMPLATE_MAP[first_key])
    else:
        template_basename = "pipeline.yml"
    
    if yaml_path and yaml_path.strip():
        final_yaml_path = yaml_path.strip()
    else:
        final_yaml_path = f"pipelines/{template_basename}"

    pipeline_script = get_script_path("create-devops-pipeline.ps1")
    if not os.path.exists(pipeline_script):
        return "Error: create-devops-pipeline.ps1 not found"

    params = {
        "Organization": organization,
        "ProjectName": project_name,
        "RepoName": repo_name,
        "PipelineName": pipeline_name,
        "Branch": branch,
        "YamlPath": final_yaml_path
    }

    try:
        out = run_powershell_script(pipeline_script, params)
        return out.strip()
    except Exception as e:
        return f"Pipeline creation failed\n\nError: {str(e)}\nError Type: {type(e).__name__}\n\nScript: {pipeline_script}\nParameters: {params}\n\nCommon causes:\n- YAML file does not exist in repository\n- No 'Build Administrators' permission\n- Invalid YAML path\n- Branch does not exist"


# ============================================================================
# Azure DevOps - Role Assignment
# ============================================================================

def assign_role(
    organization: str,
    project_name: str,
    role_name: str,
    principal_id: str
) -> str:
    """Assigns a role (security group membership) to a principal in an Azure DevOps project.
    
    Common built-in roles:
    - Project Administrators: Full control over project settings and security
    - Build Administrators: Manage build pipelines and definitions
    - Release Administrators: Manage release pipelines and deployments
    - Contributors: Create and modify code, work items, and pipelines
    - Readers: View-only access to project resources
    - Endpoint Administrators: Manage service connections
    - Endpoint Creators: Create service connections
    
    Custom roles/groups are also supported - provide the exact group name.
    
    Args:
        organization: Azure DevOps organization URL or name (e.g., 'https://dev.azure.com/myorg' or 'myorg')
        project_name: Name of the Azure DevOps project
        role_name: Name of the security group/role to assign
        principal_id: Object ID (GUID) of the user, group, service principal, or managed identity from Azure AD/Entra ID
    
    Returns:
        Role assignment result with status and details
    """
    # Validate required parameters
    missing = []
    if not organization:
        missing.append("organization (Azure DevOps org URL or name)")
    if not project_name:
        missing.append("project_name (name of the ADO project)")
    if not role_name:
        missing.append("role_name (e.g., 'Project Administrators', 'Contributors', 'Readers')")
    if not principal_id:
        missing.append("principal_id (Object ID / GUID of the user, group, service principal, or managed identity)")
    
    if missing:
        return "Missing required parameters:\n" + "\n".join([f"  - {m}" for m in missing])
    
    # Normalize organization URL
    organization = _normalize_org_url(organization)
    
    script_path = get_script_path("assign-ado-role.ps1")
    if not os.path.exists(script_path):
        return "Error: assign-ado-role.ps1 not found"
    
    params = {
        "Organization": organization,
        "ProjectName": project_name,
        "RoleName": role_name,
        "PrincipalId": principal_id
    }
    
    try:
        return run_powershell_script(script_path, params)
    except Exception as e:
        return f"ADO role assignment failed\n\nError: {str(e)}\nError Type: {type(e).__name__}\n\nScript: {script_path}\nParameters: {params}\n\nCommon causes:\n- Not authenticated: Run 'az login'\n- No Project Administrator or Collection Administrator access\n- Invalid organization URL or project name\n- Invalid principal ID (Object ID)\n- Role/group does not exist in the project"


# ============================================================================
# Azure DevOps - Delete Operations
# ============================================================================

def delete_repo(organization: str = None, project_name: str = None, repo_name: str = None) -> str:
    """Deletes an Azure DevOps Git repository."""
    organization = _normalize_org_url(organization)
    
    missing = []
    if not organization or not organization.strip():
        missing.append("organization (org URL)")
    if not project_name or not project_name.strip():
        missing.append("project_name (existing project)")
    if not repo_name or not repo_name.strip():
        missing.append("repo_name (repo to delete)")
    if missing:
        return "Delete ADO Repo - Missing:\n" + "\n".join([f"  - {m}" for m in missing])
    
    from .utils import run_command
    
    # Get repo ID first
    get_cmd = ["az", "repos", "show", "--repository", repo_name,
               "--org", organization, "--project", project_name, "--query", "id", "-o", "tsv"]
    repo_id = run_command(get_cmd).strip()
    
    if "error" in repo_id.lower() or not repo_id:
        return f"Error: Could not find repo '{repo_name}' in project '{project_name}'. Verify the name and your access."
    
    # Delete the repo
    del_cmd = ["az", "repos", "delete", "--id", repo_id,
               "--org", organization, "--project", project_name, "--yes"]
    result = run_command(del_cmd)
    
    if "error" in result.lower():
        return f"Delete failed:\n{result}"
    
    return f"Successfully deleted repository: {repo_name}"


# ============================================================================
# Azure DevOps - Pipeline Triggers
# ============================================================================

def trigger_pipeline(organization: str = None, project_name: str = None,
                     pipeline_name: str = None, pipeline_id: str = None,
                     branch: str = "main") -> str:
    """Triggers/runs an existing Azure DevOps pipeline."""
    organization = _normalize_org_url(organization)
    
    missing = []
    if not organization or not organization.strip():
        missing.append("organization (org URL)")
    if not project_name or not project_name.strip():
        missing.append("project_name (existing project)")
    if not pipeline_name and not pipeline_id:
        missing.append("pipeline_name or pipeline_id (pipeline to trigger)")
    if missing:
        return "Trigger Pipeline - Missing:\n" + "\n".join([f"  - {m}" for m in missing])
    
    from .utils import run_command
    
    cmd = ["az", "pipelines", "run",
           "--org", organization, "--project", project_name,
           "--branch", branch]
    
    if pipeline_id:
        cmd.extend(["--id", str(pipeline_id)])
    else:
        cmd.extend(["--name", pipeline_name])
    
    cmd.extend(["-o", "json"])
    result = run_command(cmd)
    
    if "error" in result.lower():
        return f"Pipeline trigger failed:\n{result}"
    
    try:
        data = json.loads(result)
        run_id = data.get("id", "N/A")
        status = data.get("status", "N/A")
        web_url = data.get("_links", {}).get("web", {}).get("href", "")
        
        output = [f"Pipeline triggered successfully!",
                  f"  Run ID: {run_id}",
                  f"  Status: {status}"]
        if web_url:
            output.append(f"  URL: {web_url}")
        return "\n".join(output)
    except (json.JSONDecodeError, ValueError):
        return f"Pipeline triggered. Output:\n{result}"


# ============================================================================
# Azure DevOps - Work Items
# ============================================================================

# Field name mapping for convenience
_WORK_ITEM_FIELDS = {
    "title": "System.Title",
    "state": "System.State",
    "status": "System.State",
    "assigned_to": "System.AssignedTo",
    "assigned": "System.AssignedTo",
    "area_path": "System.AreaPath",
    "area": "System.AreaPath",
    "iteration_path": "System.IterationPath",
    "iteration": "System.IterationPath",
    "description": "System.Description",
    "priority": "Microsoft.VSTS.Common.Priority",
    "severity": "Microsoft.VSTS.Common.Severity",
    "activity": "Microsoft.VSTS.Common.Activity",
    "completed_work": "Microsoft.VSTS.Scheduling.CompletedWork",
    "remaining_work": "Microsoft.VSTS.Scheduling.RemainingWork",
    "original_estimate": "Microsoft.VSTS.Scheduling.OriginalEstimate",
    "start_date": "Microsoft.VSTS.Scheduling.StartDate",
    "target_date": "Microsoft.VSTS.Scheduling.TargetDate",
    "tags": "System.Tags",
    "reason": "System.Reason",
    "value_area": "Microsoft.VSTS.Common.ValueArea",
    "story_points": "Microsoft.VSTS.Scheduling.StoryPoints",
    "effort": "Microsoft.VSTS.Scheduling.Effort",
}


def manage_work_item(
    organization: str = None,
    project_name: str = None,
    action: str = None,
    work_item_id: int = None,
    work_item_type: str = None,
    title: str = None,
    fields: str = None,
    comment: str = None
) -> str:
    """Manage Azure DevOps work items - create, read, update, or add comments."""
    organization = _normalize_org_url(organization)

    VALID_ACTIONS = ["create", "read", "update", "add-comment"]

    if not action:
        return f"Error: action is required. Valid actions: {', '.join(VALID_ACTIONS)}"
    action = action.lower().strip()
    if action not in VALID_ACTIONS:
        return f"Error: Invalid action '{action}'. Valid actions: {', '.join(VALID_ACTIONS)}"

    missing = []
    if not organization or not organization.strip():
        missing.append("organization (org URL or name)")
    if not project_name or not project_name.strip():
        missing.append("project_name")
    if missing:
        return f"Work Item ({action}) - Missing:\n" + "\n".join([f"  - {m}" for m in missing])

    from .utils import run_command

    # ---- CREATE ----
    if action == "create":
        if not work_item_type:
            return "Error: work_item_type is required for create (e.g., 'Task', 'Bug', 'User Story', 'Epic', 'Feature')"
        if not title:
            return "Error: title is required for create"

        cmd = ["az", "boards", "work-item", "create",
               "--type", work_item_type,
               "--title", title,
               "--org", organization,
               "--project", project_name,
               "-o", "json"]

        # Parse additional fields
        if fields:
            for field_entry in fields.split(","):
                field_entry = field_entry.strip()
                if "=" not in field_entry:
                    continue
                key, value = field_entry.split("=", 1)
                key = key.strip().lower().replace(" ", "_")
                field_ref = _WORK_ITEM_FIELDS.get(key, key)
                # If it looks like a System.* or Microsoft.* path, use as-is
                if "." in field_ref and not field_ref.startswith(("System.", "Microsoft.")):
                    field_ref = _WORK_ITEM_FIELDS.get(key, key)
                cmd.extend(["--fields", f"{field_ref}={value.strip()}"])

        result = run_command(cmd)
        if "error" in result.lower():
            return f"Create failed:\n{result}"

        try:
            data = json.loads(result)
            wi_id = data.get("id", "N/A")
            url = data.get("_links", {}).get("html", {}).get("href", "")
            output = [f"Work item created successfully!",
                      f"  ID: {wi_id}",
                      f"  Type: {work_item_type}",
                      f"  Title: {title}"]
            if url:
                output.append(f"  URL: {url}")
            return "\n".join(output)
        except (json.JSONDecodeError, ValueError):
            return result

    # ---- READ ----
    if action == "read":
        if not work_item_id:
            return "Error: work_item_id is required for read"

        cmd = ["az", "boards", "work-item", "show",
               "--id", str(work_item_id),
               "--org", organization,
               "-o", "json"]

        result = run_command(cmd)
        if "error" in result.lower():
            return f"Read failed:\n{result}"

        try:
            data = json.loads(result)
            f = data.get("fields", {})
            output = [
                f"Work Item #{data.get('id', 'N/A')}",
                f"  Title:          {f.get('System.Title', 'N/A')}",
                f"  Type:           {f.get('System.WorkItemType', 'N/A')}",
                f"  State:          {f.get('System.State', 'N/A')}",
                f"  Reason:         {f.get('System.Reason', 'N/A')}",
                f"  Assigned To:    {f.get('System.AssignedTo', {}).get('displayName', 'Unassigned') if isinstance(f.get('System.AssignedTo'), dict) else f.get('System.AssignedTo', 'Unassigned')}",
                f"  Area Path:      {f.get('System.AreaPath', 'N/A')}",
                f"  Iteration Path: {f.get('System.IterationPath', 'N/A')}",
                f"  Priority:       {f.get('Microsoft.VSTS.Common.Priority', 'N/A')}",
                f"  Activity:       {f.get('Microsoft.VSTS.Common.Activity', 'N/A')}",
                f"  Story Points:   {f.get('Microsoft.VSTS.Scheduling.StoryPoints', 'N/A')}",
                f"  Effort:         {f.get('Microsoft.VSTS.Scheduling.Effort', 'N/A')}",
                f"  Original Est:   {f.get('Microsoft.VSTS.Scheduling.OriginalEstimate', 'N/A')}",
                f"  Completed Work: {f.get('Microsoft.VSTS.Scheduling.CompletedWork', 'N/A')}",
                f"  Remaining Work: {f.get('Microsoft.VSTS.Scheduling.RemainingWork', 'N/A')}",
                f"  Start Date:     {f.get('Microsoft.VSTS.Scheduling.StartDate', 'N/A')}",
                f"  Target Date:    {f.get('Microsoft.VSTS.Scheduling.TargetDate', 'N/A')}",
                f"  Tags:           {f.get('System.Tags', 'N/A')}",
                f"  Created By:     {f.get('System.CreatedBy', {}).get('displayName', 'N/A') if isinstance(f.get('System.CreatedBy'), dict) else f.get('System.CreatedBy', 'N/A')}",
                f"  Created Date:   {f.get('System.CreatedDate', 'N/A')}",
                f"  Changed Date:   {f.get('System.ChangedDate', 'N/A')}",
            ]
            desc = f.get("System.Description", "")
            if desc:
                # Strip HTML for readability
                import re
                desc_clean = re.sub(r"<[^>]+>", "", desc).strip()
                output.append(f"  Description:    {desc_clean[:500]}")

            # Fetch comments
            comments_url = data.get("_links", {}).get("workItemComments", {}).get("href", "")
            if comments_url:
                comment_cmd = ["az", "boards", "work-item", "show",
                               "--id", str(work_item_id),
                               "--org", organization,
                               "--expand", "all", "-o", "json"]
                # Use discussion separately
                disc_cmd = ["az", "boards", "work-item", "relation", "list-for-work-item",
                            "--id", str(work_item_id),
                            "--org", organization, "-o", "json"]

            return "\n".join(output)
        except (json.JSONDecodeError, ValueError):
            return result

    # ---- UPDATE ----
    if action == "update":
        if not work_item_id:
            return "Error: work_item_id is required for update"
        if not fields and not title:
            return "Error: Provide 'fields' (key=value,key2=value2) or 'title' to update"

        cmd = ["az", "boards", "work-item", "update",
               "--id", str(work_item_id),
               "--org", organization,
               "-o", "json"]

        if title:
            cmd.extend(["--title", title])

        if fields:
            for field_entry in fields.split(","):
                field_entry = field_entry.strip()
                if "=" not in field_entry:
                    continue
                key, value = field_entry.split("=", 1)
                key = key.strip().lower().replace(" ", "_")
                field_ref = _WORK_ITEM_FIELDS.get(key, key)
                cmd.extend(["--fields", f"{field_ref}={value.strip()}"])

        result = run_command(cmd)
        if "error" in result.lower():
            return f"Update failed:\n{result}"

        try:
            data = json.loads(result)
            return f"Work item #{work_item_id} updated successfully."
        except (json.JSONDecodeError, ValueError):
            return result

    # ---- ADD-COMMENT ----
    if action == "add-comment":
        if not work_item_id:
            return "Error: work_item_id is required for add-comment"
        if not comment:
            return "Error: comment text is required for add-comment"

        cmd = ["az", "boards", "work-item", "update",
               "--id", str(work_item_id),
               "--org", organization,
               "--discussion", comment,
               "-o", "json"]

        result = run_command(cmd)
        if "error" in result.lower():
            return f"Add comment failed:\n{result}"

        return f"Comment added to work item #{work_item_id}."

    return "Error: Unexpected state."
