import unittest
from backend.polyglot import (
    parse_patch_modified_lines,
    is_node_modified_by_patch,
    extract_patch_new_imports,
    audit_dependency_risks,
)
from fastapi.testclient import TestClient
from backend.main import (
    app,
    generate_mermaid_blast_radius,
    build_sticky_comment_body,
    run_deterministic_filters,
)


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

    def test_generate_mermaid_blast_radius(self):
        nodes = [
            {"id": "auth.py::login", "label": "login", "type": "function", "status": "modified"},
            {"id": "billing.py::charge", "label": "charge", "type": "function", "status": "untested"},
            {"id": "tests/test_auth.py::test_login", "label": "test_login", "type": "test", "status": "clean"},
        ]
        edges = [
            {"source": "auth.py::login", "target": "billing.py::charge", "type": "CALLS"},
            {"source": "auth.py::login", "target": "tests/test_auth.py::test_login", "type": "TESTED_BY"},
        ]
        mermaid_text = generate_mermaid_blast_radius(nodes, edges)
        self.assertIn("graph TD", mermaid_text)
        self.assertIn("classDef modified", mermaid_text)
        self.assertIn("classDef untested", mermaid_text)
        self.assertIn("classDef tested", mermaid_text)
        self.assertIn(":::modified", mermaid_text)
        self.assertIn(":::untested", mermaid_text)
        self.assertIn(":::tested", mermaid_text)
        self.assertIn("-->|calls|", mermaid_text)

    def test_build_sticky_comment_body(self):
        payload = {
            "verdict": "CRITICAL_BLAST",
            "risk_score": 85,
            "summary": "Untested callers in billing pipeline.",
            "nodes": [{"id": "a.py::f", "label": "f", "status": "modified"}],
            "edges": [],
            "untested_callers": ["billing.py::charge"],
            "slopsquatting_alerts": [{"package": "fake-dep-xyz", "message": "Hallucinated package"}],
        }
        body = build_sticky_comment_body(payload, "owner", "repo", "42")
        self.assertIn("<!-- gitos-sticky-intelligence -->", body)
        self.assertIn("CRITICAL_BLAST", body)
        self.assertIn("85 / 100", body)
        self.assertIn("billing.py::charge", body)
        self.assertIn("fake-dep-xyz", body)
        self.assertIn("```mermaid", body)

    def test_extract_patch_new_imports_python(self):
        patch = """@@ -1,5 +1,9 @@
 import os
+import requests_async_pool
+from fastapi_jwt_authx import AuthJWT
+from .local_module import my_func
"""
        new_pkgs = extract_patch_new_imports(patch, language="python")
        self.assertIn("requests_async_pool", new_pkgs)
        self.assertIn("fastapi_jwt_authx", new_pkgs)
        self.assertNotIn("os", new_pkgs)
        self.assertNotIn("local_module", new_pkgs)

    def test_extract_patch_new_imports_js(self):
        patch = """@@ -1,5 +1,8 @@
 const path = require('path');
+const lodash_ext = require('lodash-super-ext');
+import { CoolWidget } from '@scope/hallucinated-widget';
"""
        new_pkgs = extract_patch_new_imports(patch, language="javascript")
        self.assertIn("lodash-super-ext", new_pkgs)
        self.assertIn("@scope/hallucinated-widget", new_pkgs)
        self.assertNotIn("path", new_pkgs)

    def test_deterministic_filters_slopsquatting(self):
        dep_alerts = [
            {
                "package": "fake-pkg-xyz",
                "severity": "CRITICAL",
                "message": "Package was NOT found on PYPI",
            }
        ]
        res = run_deterministic_filters(
            repo_id="test/repo",
            commit_sha="c123",
            modified_functions=["a.py::f"],
            modified_tests=[],
            new_functions=[],
            ast_delta=10,
            text_diff_lines=15,
            file_paths=["a.py"],
            dependency_alerts=dep_alerts,
        )
        self.assertEqual(res["verdict"], "SLOPSQUATTING_ALERT")
        self.assertGreaterEqual(res["risk_score"], 70)
        self.assertTrue(res["deterministic_checks"]["slopsquatting_sentinel"]["critical_alert"])

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
                    "nodes": [{"id": "a.py::f", "status": "modified"}],
                    "edges": [],
                    "untested_callers": ["a.py::caller"],
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

    def test_mcp_tools_list(self):
        resp = self.client.get("/mcp/tools")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("tools", data)
        tool_names = [t["name"] for t in data["tools"]]
        self.assertIn("gitos_blast_radius", tool_names)
        self.assertIn("gitos_slop_check", tool_names)

    def test_mcp_blast_radius_endpoint(self):
        patch = """@@ -5,3 +5,6 @@ def existing():
+    new_step()
+    another_step()
"""
        resp = self.client.post(
            "/mcp/blast-radius",
            json={"patch": patch, "language": "python", "file_path": "backend/api.py"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn(5, data["modified_lines"])

    def test_mcp_slop_check_endpoint(self):
        # 30 lines diff but only 1 modified AST line -> cosmetic slop
        patch = "\n".join([f"+ # comment line {i}" for i in range(30)])
        resp = self.client.post(
            "/mcp/slop-check",
            json={"patch": patch, "language": "python"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn(data["verdict"], ["AI_SLOP_SUSPECTED", "LOW_RISK", "CLEAN"])

    def test_agent_swarm_status(self):
        resp = self.client.get("/api/agents/swarm")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["orchestrator"], "GitOSOrchestrator")
        self.assertEqual(len(data["agents"]), 5)
        agent_ids = [a["id"] for a in data["agents"]]
        self.assertIn("triage_agent", agent_ids)
        self.assertIn("graph_agent", agent_ids)
        self.assertIn("security_agent", agent_ids)
        self.assertIn("onboarding_agent", agent_ids)
        self.assertIn("reasoning_agent", agent_ids)

    def test_security_sinks_detection(self):
        from backend.polyglot import scan_patch_security_sinks
        patch = """@@ -1,3 +1,5 @@
 def execute_cmd(user_arg):
+    import subprocess
+    subprocess.Popen(f"ls {user_arg}", shell=True)
+    eval(user_arg)
"""
        sinks = scan_patch_security_sinks(patch)
        self.assertGreaterEqual(len(sinks), 2)
        sink_types = [s["type"] for s in sinks]
        self.assertIn("COMMAND_INJECTION", sink_types)
        self.assertIn("CODE_INJECTION", sink_types)

    def test_generate_test_stub_endpoint(self):
        resp = self.client.post(
            "/api/generate-test-stub",
            json={
                "symbol_name": "APIRouter.add_api_route",
                "file_path": "fastapi/routing.py",
                "language": "python",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("pytest", data["framework"])
        self.assertIn("test_add_api_route", data["test_code"])

    def test_mcp_generate_test_stub(self):
        resp = self.client.post(
            "/mcp/generate-test-stub",
            json={
                "symbol_name": "formatQuery",
                "file_path": "src/utils/query.ts",
                "language": "typescript",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("vitest", data["framework"])
        self.assertIn("describe", data["test_code"])

    def test_reasoning_agent_synthesis(self):
        from backend.agents.reasoning_agent import ReasoningAgent
        agent = ReasoningAgent()
        report = agent.synthesize_maintainer_brief(
            repo_id="owner/repo",
            pr_id="42",
            verdict="NEEDS_TESTS",
            risk_score=50,
            modified_functions=["core.py::process_payment"],
            untested_callers=["core.py::process_payment"],
            dependency_alerts=[],
            rule_violations=[],
            security_sinks=[],
            is_cosmetic_slop=False,
            ast_vs_text_ratio=0.8,
            dead_code_symbols=[],
        )
        self.assertEqual(report["status"], "completed")
        self.assertIn("Maintainer Brief", report["brief_markdown"])
        self.assertIn("TESTING GAP", report["executive_verdict"])
        self.assertGreater(len(report["action_plan"]), 0)

    def test_onboarding_tour_endpoint(self):
        resp = self.client.post(
            "/api/onboarding/tour",
            json={"repo_url": "https://github.com/fastapi/fastapi"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("onboarding_tour", data)
        tour = data["onboarding_tour"]
        self.assertIn("core_modules", tour)
        self.assertIn("contributor_tips", tour)
        self.assertIn("entry_points", tour)

    def test_onboarding_agent_pathfinder(self):
        from backend.agents.onboarding_agent import OnboardingAgent
        agent = OnboardingAgent()
        nodes = [
            {"id": "routing.py::APIRouter.add_api_route", "label": "add_api_route", "file_path": "routing.py", "type": "function"},
            {"id": "auth.py::verify_token", "label": "verify_token", "file_path": "auth.py", "type": "function"},
        ]
        res = agent.pathfind_issue_to_code(
            issue_title="Error in routing when adding api route",
            issue_body="Calling add_api_route throws KeyError",
            ast_nodes=nodes,
            file_paths=["routing.py", "auth.py"],
        )
        self.assertEqual(res["status"], "completed")
        self.assertGreater(len(res["candidate_entrypoints"]), 0)
        self.assertEqual(res["candidate_entrypoints"][0]["label"], "add_api_route")


if __name__ == "__main__":
    unittest.main()

