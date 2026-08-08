import json
import unittest
import urllib.error
from unittest.mock import patch

from azplex import ado


class ManageWorkItemTests(unittest.TestCase):
    @patch("azplex.ado._ado_request")
    def test_create_builds_whitelisted_json_patch_and_parent_relation(self, request):
        request.return_value = {
            "id": 42,
            "rev": 1,
            "url": "https://dev.azure.com/example/Project/_apis/wit/workItems/42",
            "fields": {
                "System.Title": "Ship feature",
                "System.WorkItemType": "User Story",
                "Microsoft.VSTS.Scheduling.StoryPoints": 5,
            },
        }

        result = json.loads(ado.manage_work_item(
            action="create",
            organization="example",
            project_name="My Project",
            work_item_type="User Story",
            title="Ship feature",
            story_points=5,
            tags=["release", "mcp"],
            parent_id=7,
        ))

        self.assertTrue(result["success"])
        method, url, body, content_type = request.call_args.args
        self.assertEqual(method, "POST")
        self.assertIn("/My%20Project/_apis/wit/workitems/$User%20Story", url)
        self.assertEqual(content_type, "application/json-patch+json")
        self.assertEqual(body[0], {"op": "add", "path": "/fields/System.Title", "value": "Ship feature"})
        self.assertIn(
            {"op": "add", "path": "/fields/System.Tags", "value": "release; mcp"},
            body,
        )
        self.assertEqual(body[-1]["path"], "/relations/-")
        self.assertTrue(body[-1]["value"]["url"].endswith("/My%20Project/_apis/wit/workItems/7"))
        self.assertEqual(result["data"]["fields"]["work_item_type"], "User Story")

    @patch("azplex.ado._ado_request")
    def test_update_requires_a_safe_supported_change(self, request):
        result = json.loads(ado.manage_work_item(
            action="update",
            organization="example",
            project_name="Project",
            work_item_id=42,
        ))

        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "validation_error")
        request.assert_not_called()

    @patch("azplex.ado._ado_request")
    def test_query_uses_default_wiql_and_bounds_top(self, request):
        request.return_value = {
            "queryType": "flat",
            "columns": [{"referenceName": "System.Id"}],
            "workItems": [{"id": 42, "url": "work-item-url"}],
        }

        result = json.loads(ado.manage_work_item(
            action="query",
            organization="https://dev.azure.com/example",
            project_name="Project",
            top=25,
        ))

        self.assertTrue(result["success"])
        method, url, body = request.call_args.args
        self.assertEqual(method, "POST")
        self.assertIn("/wiql?$top=25", url)
        self.assertIn("[System.TeamProject] = @project", body["query"])
        self.assertEqual(result["data"]["work_items"][0]["id"], 42)

        invalid = json.loads(ado.manage_work_item(
            action="query",
            organization="example",
            project_name="Project",
            top=201,
        ))
        self.assertEqual(invalid["error"]["code"], "validation_error")

    @patch("azplex.ado._ado_request")
    def test_comment_uses_comments_endpoint(self, request):
        request.return_value = {"id": 3, "text": "Reviewed"}

        result = json.loads(ado.manage_work_item(
            action="comment",
            organization="example",
            project_name="Project",
            work_item_id=42,
            comment="Reviewed",
        ))

        self.assertTrue(result["success"])
        self.assertIn("/workitems/42/comments", request.call_args.args[1])
        self.assertEqual(request.call_args.args[2], {"text": "Reviewed"})

    @patch("azplex.ado._ado_request")
    def test_actionable_permission_error_is_structured(self, request):
        request.side_effect = ado.AdoWorkItemError(
            "Azure DevOps denied this operation. Verify work-item permissions.",
            "permission_error",
            403,
        )

        result = json.loads(ado.manage_work_item(
            action="show",
            organization="example",
            project_name="Project",
            work_item_id=42,
        ))

        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["status"], 403)
        self.assertIn("permissions", result["error"]["message"])


class AdoRequestTests(unittest.TestCase):
    @patch("azplex.ado.urllib.request.urlopen")
    @patch("azplex.ado._get_ado_token", return_value="test-token")
    def test_request_uses_bearer_token_and_json_patch_content_type(self, token, urlopen):
        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = b'{"id": 42}'

        result = ado._ado_request(
            "PATCH",
            "https://dev.azure.com/example/Project/_apis/wit/workitems/42",
            [{"op": "add", "path": "/fields/System.Title", "value": "Updated"}],
            "application/json-patch+json",
        )

        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "PATCH")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")
        self.assertEqual(request.get_header("Content-type"), "application/json-patch+json")
        self.assertEqual(result["id"], 42)
        token.assert_called_once_with()

    @patch("azplex.ado.urllib.request.urlopen")
    @patch("azplex.ado._get_ado_token", return_value="test-token")
    def test_http_403_maps_to_actionable_permission_error(self, token, urlopen):
        urlopen.side_effect = urllib.error.HTTPError(
            "https://dev.azure.com/example/Project/_apis/wit/workitems/42",
            403,
            "Forbidden",
            {},
            None,
        )
        urlopen.side_effect.read = lambda: b'{"message":"Edit work items permission is required."}'

        with self.assertRaises(ado.AdoWorkItemError) as raised:
            ado._ado_request("GET", "https://dev.azure.com/example/Project/_apis/wit/workitems/42")

        self.assertEqual(raised.exception.code, "permission_error")
        self.assertEqual(raised.exception.status, 403)
        self.assertIn("work-item permissions", str(raised.exception))


if __name__ == "__main__":
    unittest.main()