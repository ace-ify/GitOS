import unittest
from fastapi.testclient import TestClient
from backend.main import (
    app,
    generate_ast_release_notes,
    triage_github_issue,
)


class TestInheritedCompetitiveFeatures(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_release_notes_major_bump_on_breaking_symbols(self):
        analysis_data = {
            "blast_radius_nodes": [
                {
                    "id": "sessions.py::Session.send",
                    "label": "Session.send",
                    "type": "function",
                    "status": "modified",
                    "in_degree": 12,
                }
            ],
            "deterministic_checks": {
                "security_sinks": {"sinks": []},
                "slopsquatting_sentinel": {"alerts": []},
                "maintainer_rules": {"violations": []},
            },
        }
        res = generate_ast_release_notes("https://github.com/psf/requests", analysis_data=analysis_data)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["recommended_bump"], "MAJOR")
        self.assertEqual(res["suggested_version"], "v2.0.0")
        self.assertTrue(len(res["categories"]["breaking"]) > 0)
        self.assertIn("Breaking Changes", res["markdown"])

    def test_release_notes_minor_bump_on_new_feature(self):
        analysis_data = {
            "blast_radius_nodes": [
                {
                    "id": "adapters.py::HTTP2Adapter",
                    "label": "HTTP2Adapter",
                    "type": "class",
                    "status": "new",
                    "in_degree": 0,
                }
            ],
            "deterministic_checks": {
                "security_sinks": {"sinks": []},
                "slopsquatting_sentinel": {"alerts": []},
                "maintainer_rules": {"violations": []},
            },
        }
        res = generate_ast_release_notes("https://github.com/psf/requests", analysis_data=analysis_data)
        self.assertEqual(res["recommended_bump"], "MINOR")
        self.assertTrue(len(res["categories"]["features"]) > 0)
        self.assertIn("New Features", res["markdown"])

    def test_release_notes_patch_bump_on_fix(self):
        analysis_data = {
            "blast_radius_nodes": [
                {
                    "id": "utils.py::parse_header",
                    "label": "parse_header",
                    "type": "function",
                    "status": "modified",
                    "in_degree": 2,
                }
            ],
            "deterministic_checks": {
                "security_sinks": {"sinks": []},
                "slopsquatting_sentinel": {"alerts": []},
                "maintainer_rules": {"violations": []},
            },
        }
        res = generate_ast_release_notes("https://github.com/psf/requests", analysis_data=analysis_data)
        self.assertEqual(res["recommended_bump"], "PATCH")
        self.assertTrue(len(res["categories"]["fixes"]) > 0)

    def test_issue_triage_anchoring_and_repro_score(self):
        title = "Session.send throws AttributeError with custom HTTPAdapter"
        body = """When executing `Session.send(request)` in requests/sessions.py line 650:
```python
s = requests.Session()
s.send(req)
```
Steps to reproduce:
1. Initialize session
2. Call send
Environment: Python 3.11, Ubuntu 22.04
"""
        res = triage_github_issue(title, body)
        self.assertEqual(res["status"], "success")
        self.assertIn("bug", res["recommended_labels"])
        self.assertIn("ast-anchored", res["recommended_labels"])
        self.assertTrue(any(a["symbol"] == "Session.send" for a in res["code_anchors"]))
        self.assertEqual(res["suggested_entrypoint"], "requests/sessions.py")
        self.assertGreaterEqual(res["reproduction_health"]["score"], 70)
        self.assertTrue(res["reproduction_health"]["has_reproduction_steps"])
        self.assertTrue(res["reproduction_health"]["has_code_block"])

    def test_issue_triage_missing_reproduction(self):
        title = "it is broken"
        body = "nothing works please fix"
        res = triage_github_issue(title, body)
        self.assertIn("needs-repro", res["recommended_labels"])
        self.assertLess(res["reproduction_health"]["score"], 50)
        self.assertIn("Explicit numbered reproduction steps", res["reproduction_health"]["missing_elements"])

    def test_api_endpoints_via_client(self):
        # 1. /api/release-notes
        rel_resp = self.client.post("/api/release-notes", json={
            "repo_url": "https://github.com/psf/requests",
            "version": "v3.0.0",
        })
        self.assertEqual(rel_resp.status_code, 200)
        self.assertEqual(rel_resp.json()["suggested_version"], "v3.0.0")

        # 2. /api/issues/triage
        issue_resp = self.client.post("/api/issues/triage", json={
            "title": "Vulnerability in auth token decoding",
            "body": "Found security bypass in `auth.py::verify_token` without signature validation.",
        })
        self.assertEqual(issue_resp.status_code, 200)
        self.assertIn("security", issue_resp.json()["recommended_labels"])

        # 3. MCP tools listing
        mcp_tools = self.client.get("/mcp/tools").json()["tools"]
        tool_names = [t["name"] for t in mcp_tools]
        self.assertIn("gitos_generate_release_notes", tool_names)
        self.assertIn("gitos_triage_issue", tool_names)

        # 4. /mcp/release-notes
        mcp_rel = self.client.post("/mcp/release-notes", json={
            "repo_url": "https://github.com/psf/requests",
        })
        self.assertEqual(mcp_rel.status_code, 200)

        # 5. /mcp/triage-issue
        mcp_issue = self.client.post("/mcp/triage-issue", json={
            "title": "Feature request: HTTP3 support",
            "body": "Please add support for HTTP/3 in `client.py`.",
        })
        self.assertEqual(mcp_issue.status_code, 200)
        self.assertIn("enhancement", mcp_issue.json()["recommended_labels"])


if __name__ == "__main__":
    unittest.main()
