import unittest
from backend.polyglot import parse_patch_modified_lines, is_node_modified_by_patch
from fastapi.testclient import TestClient
from backend.main import app


class TestHunkMatchingAndActions(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_parse_patch_modified_lines(self):
        patch = """@@ -10,4 +10,6 @@ def existing():
-    old_line()
+    new_line_1()
+    new_line_2()
"""
        modified_lines = parse_patch_modified_lines(patch)
        self.assertIn(10, modified_lines)
        self.assertIn(11, modified_lines)

    def test_is_node_modified_by_patch(self):
        node_affected = {"id": "test.py::func_a", "line_range": [10, 20]}
        node_unaffected = {"id": "test.py::func_b", "line_range": [30, 40]}
        modified_lines = {12, 13}

        self.assertTrue(is_node_modified_by_patch(node_affected, modified_lines))
        self.assertFalse(is_node_modified_by_patch(node_unaffected, modified_lines))

    def test_execute_action_endpoint(self):
        resp = self.client.post(
            "/api/execute-action",
            json={
                "action_type": "gh_comment",
                "owner": "fastapi",
                "repo": "fastapi",
                "target_id": "9999",
                "confirmed": True,
                "payload": {
                    "verdict": "CRITICAL_BLAST",
                    "risk_score": 82,
                    "summary": "14 callers untested",
                },
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn(data["status"], ["success", "simulated"])
        self.assertIn("html_url", data)

    def test_execute_action_label(self):
        resp = self.client.post(
            "/api/execute-action",
            json={
                "action_type": "gh_label",
                "owner": "fastapi",
                "repo": "fastapi",
                "target_id": "9999",
                "confirmed": True,
                "payload": {
                    "verdict": "NEEDS_TESTS",
                    "labels": ["gitos:needs-tests"],
                },
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn(data["status"], ["success", "simulated"])
        self.assertEqual(data["action_type"], "gh_label")
        self.assertIn("gitos:needs-tests", data["labels"])

    def test_execute_action_pr_draft(self):
        resp = self.client.post(
            "/api/execute-action",
            json={
                "action_type": "gh_pr_draft",
                "owner": "fastapi",
                "repo": "fastapi",
                "target_id": "1234",
                "confirmed": True,
                "payload": {},
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["action_type"], "gh_pr_draft")
        self.assertIn("gitos/test-patch-pr1234", data["branch"])


if __name__ == "__main__":
    unittest.main()
