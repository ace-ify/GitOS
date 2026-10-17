import unittest
from backend.compressor import compress_diff, build_compressed_context, GroqReasoner


class TestContextCompressor(unittest.TestCase):
    def setUp(self):
        self.sample_analysis = {
            "url_parsed": {"owner": "fastapi", "repo": "fastapi", "target_id": "9999"},
            "risk_score": 85,
            "verdict": "CRITICAL_BLAST",
            "blast_radius_nodes": [
                {
                    "id": "fastapi/routing.py::APIRouter.add_api_route",
                    "label": "APIRouter.add_api_route",
                    "file_path": "fastapi/routing.py",
                    "line_range": [10, 25],
                    "change_type": "modified",
                },
                {
                    "id": "fastapi/applications.py::FastAPI.include_router",
                    "label": "FastAPI.include_router",
                    "file_path": "fastapi/applications.py",
                    "change_type": "affected_caller",
                },
            ],
            "deterministic_checks": {
                "untested_call_graph": {
                    "untested_functions": ["APIRouter.add_api_route"]
                },
                "ast_vs_text_ratio": {
                    "ratio": 0.65,
                    "ast_node_delta": 40,
                    "text_diff_lines": 55,
                },
            },
            "suggested_diff": "--- a/routing.py\n+++ b/routing.py\n@@ -10,3 +10,4 @@\n def add_api_route():\n-    pass\n+    # Added comment\n+    return True\n",
        }

    def test_compress_diff_strips_comments(self):
        raw = "--- a/file.py\n+++ b/file.py\n+    # Some comment\n+    val = 10\n"
        compressed = compress_diff(raw)
        self.assertNotIn("# Some comment", compressed)
        self.assertIn("val = 10", compressed)

    def test_build_compressed_context_token_ceiling(self):
        ctx = build_compressed_context(self.sample_analysis)
        self.assertLessEqual(len(ctx), 3500)
        self.assertIn("fastapi/fastapi", ctx)
        self.assertIn("APIRouter.add_api_route", ctx)

    def test_reasoner_deterministic_fallback(self):
        # Without API key, reasoner should provide deterministic triage & test
        reasoner = GroqReasoner(api_key=None)
        verdict = reasoner.generate_triage_verdict(self.sample_analysis)
        self.assertIn("CRITICAL_BLAST", verdict)

        test_patch = reasoner.generate_test_patch(self.sample_analysis)
        self.assertIn("def test_", test_patch)
        self.assertIn("assert", test_patch)


if __name__ == "__main__":
    unittest.main()
