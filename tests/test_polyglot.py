import unittest
from backend.polyglot import extract_universal_ast, stitch_cross_file_graph, detect_language


class TestPolyglotEngine(unittest.TestCase):
    def test_language_detection(self):
        self.assertEqual(detect_language("src/index.ts"), "typescript")
        self.assertEqual(detect_language("main.py"), "python")
        self.assertEqual(detect_language("server.go"), "go")
        self.assertEqual(detect_language("lib.rs"), "rust")

    def test_python_parsing(self):
        code = "def calculate_risk(score: int):\n    return score * 2\n"
        res = extract_universal_ast(code, "calc.py")
        self.assertEqual(len(res["nodes"]), 1)
        self.assertEqual(res["nodes"][0]["label"], "calculate_risk")
        self.assertEqual(res["nodes"][0]["type"], "function")

    def test_typescript_parsing_and_cross_file_stitching(self):
        py_code = "def authenticate():\n    pass\n"
        ts_code = 'import { authenticate } from "./auth";\nfunction handleLogin() {\n    authenticate();\n}\n'

        py_res = extract_universal_ast(py_code, "src/auth.py")
        ts_res = extract_universal_ast(ts_code, "src/login.ts")

        nodes, edges = stitch_cross_file_graph({
            "src/auth.py": py_res,
            "src/login.ts": ts_res,
        })

        self.assertGreaterEqual(len(nodes), 2)
        # Check that cross-file edge connects login to auth
        stitched = [e for e in edges if e.get("is_cross_file")]
        self.assertGreaterEqual(len(stitched), 1)
        self.assertEqual(stitched[0]["target"], "src/auth.py::authenticate")


if __name__ == "__main__":
    unittest.main()
