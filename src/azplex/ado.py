# ============================================================================
# ADO FUNCTIONS - Azure DevOps logic
# ============================================================================

import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request

try:
    from .utils import (
        run_powershell_script, get_script_path,
        detect_pipeline_type, PIPELINE_TEMPLATE_MAP,
        resolve_principal_id
    )
except ImportError:
    from utils import (
        run_powershell_script, get_script_path,
        detect_pipeline_type, PIPELINE_TEMPLATE_MAP,
        resolve_principal_id
    )

try:
    from . import guardrails
except ImportError:
    from azplex import guardrails


ADO_RESOURCE_ID = "499b84ac-1321-427f-aa17-267ca6975798"
ADO_API_VERSION = "7.1"

WORK_ITEM_FIELDS = {
    "title": "System.Title",
    "description": "System.Description",
    "assigned_to": "System.AssignedTo",
    "state": "System.State",
    "iteration_path": "System.IterationPath",
    "area_path": "System.AreaPath",
    "priority": "Microsoft.VSTS.Common.Priority",
    "story_points": "Microsoft.VSTS.Scheduling.StoryPoints",
    "start_date": "Microsoft.VSTS.Scheduling.StartDate",
    "target_date": "Microsoft.VSTS.Scheduling.TargetDate",
    "tags": "System.Tags",
}


class AdoWorkItemError(Exception):
    """Actionable Azure DevOps work-item operation failure."""

    def __init__(self, message: str, code: str = "request_failed", status: int = None):
        super().__init__(message)
        self.code = code
        self.status = status


def _normalize_organization(organization: str) -> str:
    value = (organization or "").strip().rstrip("/")
    if not value:
        raise AdoWorkItemError("organization is required", "validation_error")

    if "://" not in value:
        if not all(character.isalnum() or character in "-_." for character in value):
            raise AdoWorkItemError("organization must be an Azure DevOps organization name or URL", "validation_error")
        return f"https://dev.azure.com/{value}"

    parsed = urllib.parse.urlparse(value)
    hostname = (parsed.hostname or "").lower()
    if hostname == "dev.azure.com":
        organization_name = parsed.path.strip("/").split("/")[0]
    elif hostname.endswith(".visualstudio.com"):
        organization_name = hostname.removesuffix(".visualstudio.com")
    else:
        raise AdoWorkItemError("organization URL must use dev.azure.com or visualstudio.com", "validation_error")

    if not organization_name:
        raise AdoWorkItemError("organization URL must include the organization name", "validation_error")
    return f"https://dev.azure.com/{urllib.parse.quote(organization_name, safe='')}"


def _get_ado_token() -> str:
    try:
        result = subprocess.run(
            [
                "az", "account", "get-access-token",
                "--resource", ADO_RESOURCE_ID,
                "--query", "accessToken",
                "--output", "tsv",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError as error:
        raise AdoWorkItemError(
            "Azure CLI was not found. Install Azure CLI and run 'az login'.",
            "authentication_error",
        ) from error
    except subprocess.TimeoutExpired as error:
        raise AdoWorkItemError(
            "Timed out acquiring an Azure DevOps token. Run 'az login' and try again.",
            "authentication_error",
        ) from error

    token = result.stdout.strip()
    if result.returncode != 0 or not token:
        detail = result.stderr.strip() or "Azure CLI returned no access token"
        raise AdoWorkItemError(
            f"Azure DevOps authentication failed. Run 'az login' and verify tenant access. {detail}",
            "authentication_error",
        )
    return token


def _ado_request(method: str, url: str, body=None, content_type: str = "application/json"):
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=payload,
        method=method,
        headers={
            "Authorization": f"Bearer {_get_ado_token()}",
            "Accept": "application/json",
            "Content-Type": content_type,
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body) if response_body else {}
    except urllib.error.HTTPError as error:
        response_body = error.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(response_body).get("message", response_body)
        except json.JSONDecodeError:
            detail = response_body

        if error.code == 401:
            message = "Azure DevOps rejected the access token. Run 'az login' and verify the active tenant."
            code = "authentication_error"
        elif error.code == 403:
            message = "Azure DevOps denied this operation. Verify project access and work-item permissions."
            code = "permission_error"
        elif error.code == 404:
            message = "The Azure DevOps project or work item was not found."
            code = "not_found"
        else:
            message = f"Azure DevOps API request failed with HTTP {error.code}."
            code = "request_failed"
        if detail:
            message = f"{message} {detail}"
        raise AdoWorkItemError(message, code, error.code) from error
    except urllib.error.URLError as error:
        raise AdoWorkItemError(
            f"Could not reach Azure DevOps: {error.reason}",
            "network_error",
        ) from error


def _normalize_work_item(item: dict) -> dict:
    fields = item.get("fields", {})
    normalized_fields = {
        name: fields[field_name]
        for name, field_name in WORK_ITEM_FIELDS.items()
        if field_name in fields
    }
    normalized_fields["work_item_type"] = fields.get("System.WorkItemType")
    normalized_fields["created_date"] = fields.get("System.CreatedDate")
    normalized_fields["changed_date"] = fields.get("System.ChangedDate")
    return {
        "id": item.get("id"),
        "revision": item.get("rev"),
        "url": item.get("url"),
        "fields": {key: value for key, value in normalized_fields.items() if value is not None},
        "relations": item.get("relations", []),
    }


def _work_item_patch(
    organization_url: str,
    project_name: str,
    title=None,
    description=None,
    assigned_to=None,
    state=None,
    iteration_path=None,
    area_path=None,
    priority=None,
    story_points=None,
    start_date=None,
    target_date=None,
    tags=None,
    parent_id=None,
) -> list:
    values = {
        "title": title,
        "description": description,
        "assigned_to": assigned_to,
        "state": state,
        "iteration_path": iteration_path,
        "area_path": area_path,
        "priority": priority,
        "story_points": story_points,
        "start_date": start_date,
        "target_date": target_date,
        "tags": "; ".join(tags) if isinstance(tags, list) else tags,
    }
    patch = [
        {"op": "add", "path": f"/fields/{WORK_ITEM_FIELDS[name]}", "value": value}
        for name, value in values.items()
        if value is not None
    ]
    if parent_id is not None:
        if not isinstance(parent_id, int) or parent_id <= 0:
            raise AdoWorkItemError("parent_id must be a positive integer", "validation_error")
        project = urllib.parse.quote(project_name, safe="")
        patch.append({
            "op": "add",
            "path": "/relations/-",
            "value": {
                "rel": "System.LinkTypes.Hierarchy-Reverse",
                "url": f"{organization_url}/{project}/_apis/wit/workItems/{parent_id}",
            },
        })
    return patch


def manage_work_item(
    action: str,
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
    tags: list = None,
    parent_id: int = None,
    comment: str = None,
    wiql: str = None,
    top: int = 50,
) -> str:
    """Creates, reads, updates, queries, or comments on an Azure DevOps work item."""
    normalized_action = (action or "").strip().lower()
    try:
        if normalized_action not in {"create", "show", "update", "query", "comment"}:
            raise AdoWorkItemError(
                "action must be one of: create, show, update, query, comment",
                "validation_error",
            )
        organization_url = _normalize_organization(organization)
        if not project_name or not project_name.strip():
            raise AdoWorkItemError("project_name is required", "validation_error")
        project = urllib.parse.quote(project_name.strip(), safe="")
        base_url = f"{organization_url}/{project}/_apis/wit"

        if normalized_action == "create":
            if not work_item_type or not work_item_type.strip():
                raise AdoWorkItemError("work_item_type is required for create", "validation_error")
            if not title or not title.strip():
                raise AdoWorkItemError("title is required for create", "validation_error")
            patch = _work_item_patch(
                organization_url, project_name.strip(), title, description, assigned_to, state,
                iteration_path, area_path, priority, story_points, start_date, target_date, tags, parent_id,
            )
            item_type = urllib.parse.quote(work_item_type.strip(), safe="")
            data = _ado_request(
                "POST",
                f"{base_url}/workitems/${item_type}?api-version={ADO_API_VERSION}",
                patch,
                "application/json-patch+json",
            )
            result = _normalize_work_item(data)
        elif normalized_action == "show":
            if not isinstance(work_item_id, int) or work_item_id <= 0:
                raise AdoWorkItemError("work_item_id must be a positive integer for show", "validation_error")
            data = _ado_request(
                "GET",
                f"{base_url}/workitems/{work_item_id}?$expand=relations&api-version={ADO_API_VERSION}",
            )
            result = _normalize_work_item(data)
        elif normalized_action == "update":
            if not isinstance(work_item_id, int) or work_item_id <= 0:
                raise AdoWorkItemError("work_item_id must be a positive integer for update", "validation_error")
            patch = _work_item_patch(
                organization_url, project_name.strip(), title, description, assigned_to, state,
                iteration_path, area_path, priority, story_points, start_date, target_date, tags, parent_id,
            )
            if not patch:
                raise AdoWorkItemError("update requires at least one field or parent_id", "validation_error")
            data = _ado_request(
                "PATCH",
                f"{base_url}/workitems/{work_item_id}?api-version={ADO_API_VERSION}",
                patch,
                "application/json-patch+json",
            )
            result = _normalize_work_item(data)
        elif normalized_action == "comment":
            if not isinstance(work_item_id, int) or work_item_id <= 0:
                raise AdoWorkItemError("work_item_id must be a positive integer for comment", "validation_error")
            if not comment or not comment.strip():
                raise AdoWorkItemError("comment is required for comment", "validation_error")
            result = _ado_request(
                "POST",
                f"{base_url}/workitems/{work_item_id}/comments?api-version=7.1-preview.4",
                {"text": comment.strip()},
            )
        else:
            if not isinstance(top, int) or not 1 <= top <= 200:
                raise AdoWorkItemError("top must be an integer from 1 to 200", "validation_error")
            query = wiql.strip() if wiql and wiql.strip() else (
                "SELECT [System.Id], [System.Title], [System.State], [System.AssignedTo] "
                "FROM WorkItems WHERE [System.TeamProject] = @project ORDER BY [System.ChangedDate] DESC"
            )
            response = _ado_request(
                "POST",
                f"{base_url}/wiql?$top={top}&api-version={ADO_API_VERSION}",
                {"query": query},
            )
            result = {
                "query_type": response.get("queryType"),
                "columns": response.get("columns", []),
                "work_items": response.get("workItems", []),
                "work_item_relations": response.get("workItemRelations", []),
            }

        return json.dumps({"success": True, "action": normalized_action, "data": result}, indent=2)
    except AdoWorkItemError as error:
        return json.dumps({
            "success": False,
            "action": normalized_action or action,
            "error": {
                "code": error.code,
                "message": str(error),
                "status": error.status,
            },
        }, indent=2)


# ============================================================================
# Azure DevOps - Projects & Repos
# ============================================================================

def create_project(organization: str = None, project_name: str = None, repo_name: str = None, description: str = None) -> str:
    """Creates an Azure DevOps project using AZ CLI via the PS1 script and sets the initial repo name."""
    if organization and not organization.strip().lower().startswith("http"):
        organization = f"https://dev.azure.com/{organization.strip()}"

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

    def execute():
        try:
            return run_powershell_script(project_script, proj_params)
        except Exception as e:
            return f"Project creation failed\n\nError: {str(e)}\nError Type: {type(e).__name__}\n\nScript: {project_script}\nParameters: {proj_params}"

    def verify():
        readback = list_projects(organization)
        return (project_name.strip().lower() in readback.lower(), readback)

    result = guardrails.run_verified_operation(
        f"ado_create_project:{project_name}", execute, verify
    )
    return result.to_json()


def create_repo(organization: str = None, project_name: str = None, repo_name: str = None) -> str:
    """Creates a new Azure DevOps Git repository via the PS1 script."""
    if organization and not organization.strip().lower().startswith("http"):
        organization = f"https://dev.azure.com/{organization.strip()}"

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

    def execute():
        try:
            return run_powershell_script(repo_script, params)
        except Exception as e:
            return f"Repository creation failed\n\nError: {str(e)}\nError Type: {type(e).__name__}\n\nScript: {repo_script}\nParameters: {params}"

    def verify():
        readback = list_repos(organization, project_name)
        return (repo_name.strip().lower() in readback.lower(), readback)

    result = guardrails.run_verified_operation(
        f"ado_create_repo:{repo_name}", execute, verify
    )
    return result.to_json()


def list_projects(organization: str = None) -> str:
    """Lists all Azure DevOps projects in an organization."""
    if organization and not organization.strip().lower().startswith("http"):
        organization = f"https://dev.azure.com/{organization.strip()}"

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
    if organization and not organization.strip().lower().startswith("http"):
        organization = f"https://dev.azure.com/{organization.strip()}"

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
    if organization and not organization.strip().lower().startswith("http"):
        organization = f"https://dev.azure.com/{organization.strip()}"

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

def deploy_custom_yaml(organization: str, project_name: str, repo_name: str,
                       branch: str, file_name: str, yaml_content: str,
                       folder_path: str = "pipelines") -> str:
    """Deploys custom YAML content directly to an Azure DevOps repository."""
    missing = []
    if not organization or not organization.strip():
        missing.append("organization (Azure DevOps org URL)")
    if not project_name or not project_name.strip():
        missing.append("project_name (existing project)")
    if not repo_name or not repo_name.strip():
        missing.append("repo_name (existing repo)")
    if not branch or not branch.strip():
        missing.append("branch (target branch, e.g., 'main', 'dev')")
    if not file_name or not file_name.strip():
        missing.append("file_name (display name for YAML, e.g., 'sourcebranchvalidation.yml')")
    if not yaml_content or not yaml_content.strip():
        missing.append("yaml_content (the actual YAML content to deploy)")
    
    if missing:
        return (
            "Deploy Custom YAML - Missing Required Parameters\n\n"
            "Please provide:\n"
            + "\n".join([f"  - {m}" for m in missing]) +
            "\n\nExample usage:\n"
            "  organization: 'https://dev.azure.com/myorg'\n"
            "  project_name: 'MyProject'\n"
            "  repo_name: 'MyRepo'\n"
            "  branch: 'dev'\n"
            "  file_name: 'my-pipeline.yml'\n"
            "  yaml_content: '<paste your YAML content>'"
        )
    
    if not organization.strip().lower().startswith("http"):
        organization = f"https://dev.azure.com/{organization.strip()}"
    
    if not file_name.endswith('.yml') and not file_name.endswith('.yaml'):
        file_name = f"{file_name}.yml"
    
    deploy_script = get_script_path("deploy-pipeline-yaml.ps1")
    if not os.path.exists(deploy_script):
        return "Error: deploy-pipeline-yaml.ps1 not found"
    
    params = {
        "Organization": organization,
        "ProjectName": project_name,
        "RepoName": repo_name,
        "TemplateName": file_name.replace('.yml', '').replace('.yaml', ''),
        "Branch": branch,
        "FolderPath": folder_path,
        "CustomYamlContent": yaml_content,
        "YamlFileName": file_name
    }
    
    try:
        out = run_powershell_script(deploy_script, params)
        return out.strip()
    except Exception as e:
        return f"Custom YAML deployment failed\n\nError: {str(e)}\nError Type: {type(e).__name__}\n\nScript: {deploy_script}\nParameters: {params}\n\nCommon causes:\n- Repository not initialized\n- Branch does not exist\n- No write access\n- Git authentication failed\n- Invalid YAML syntax"


def deploy_pipeline_yaml(organization: str = None, project_name: str = None, 
                         repo_name: str = None, pipeline_type: str = None,
                         branch: str = None, folder_path: str = None,
                         custom_yaml_content: str = None, yaml_file_name: str = None) -> str:
    """Deploys a pipeline YAML template from agent/templates OR custom YAML content to an Azure DevOps repository."""
    if organization and not organization.strip().lower().startswith("http"):
        organization = f"https://dev.azure.com/{organization.strip()}"

    missing = []
    if not organization or not organization.strip():
        missing.append("organization (org URL)")
    if not project_name or not project_name.strip():
        missing.append("project_name (existing project)")
    if not repo_name or not repo_name.strip():
        missing.append("repo_name (existing repo)")
    if not pipeline_type or not pipeline_type.strip():
        missing.append("pipeline_type (template key from PIPELINE_TEMPLATE_MAP, or name for custom)")
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
    if organization and not organization.strip().lower().startswith("http"):
        organization = f"https://dev.azure.com/{organization.strip()}"

    if pipeline_name and not pipeline_type:
        pipeline_type = detect_pipeline_type(pipeline_name, "")
    elif not pipeline_type:
        pipeline_type = pipeline_name.lower().replace('_', '-').replace(' ', '-') if pipeline_name else ""

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
    if organization and not organization.strip().lower().startswith("http"):
        organization = f"https://dev.azure.com/{organization.strip()}"
    
    # Auto-resolve: accept email, display name, group name, or Object ID
    resolved_id, resolve_info = resolve_principal_id(principal_id)
    if not resolved_id:
        return f"Error resolving principal: {resolve_info}"
    principal_id = resolved_id
    
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
