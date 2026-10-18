"""
GitOS Contributor Onboarding & Pathfinder Agent (OnboardingAgent)
Specialized agent for modernized contributor onboarding, repository architecture tours,
issue-to-code pathfinding, and automated backward-compatible unit test generation.
"""

import re
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("gitos.agent.onboarding")


class OnboardingAgent:
    """
    Onboards new contributors to unfamiliar open-source repositories.
    Provides architecture walkthroughs, maps issue descriptions to candidate code entry points,
    and synthesizes minimal test stubs to help contributors get their PRs approved.
    """

    def __init__(self):
        self.agent_name = "OnboardingAgent"
        self.role = "Modernized Contributor Onboarding & Pathfinder"

    def generate_architecture_tour(
        self,
        repo_owner: str,
        repo_name: str,
        file_tree: List[str],
        ast_nodes: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Synthesizes a structured architectural overview of the codebase for new contributors.
        Categorizes entry points, business logic, APIs, and test suites.
        """
        entry_points = []
        modules = set()
        test_suites = []

        ENTRY_FILE_PATTERNS = (
            "main.py", "app.py", "api.py", "index.ts", "index.js", "server.ts",
            "server.js", "main.go", "lib.rs", "main.rs", "cli.py", "client.py",
            "applications.py", "routing.py", "sessions.py", "__init__.py",
        )

        # Filter true code files
        code_files = [
            p for p in file_tree
            if any(p.endswith(ext) for ext in (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".c", ".cpp"))
        ]

        for path in file_tree:
            p_lower = path.lower()
            if "test" in p_lower or p_lower.startswith("tests/") or "spec." in p_lower:
                test_suites.append(path)
            elif any(p_lower.endswith(e) for e in ENTRY_FILE_PATTERNS):
                entry_points.append(path)

        for p in code_files:
            parts = p.split("/")
            if len(parts) > 1:
                if parts[0] in ("src", "lib") and len(parts) > 2:
                    modules.add(f"{parts[0]}/{parts[1]}")
                elif parts[0] not in (".github", "docs", "doc", "public", ".git", "tests", "test", "__pycache__"):
                    modules.add(parts[0])
            else:
                base = parts[0].split(".")[0]
                if base not in ("setup", "conftest", "test", "manage"):
                    modules.add(base)

        if not entry_points and code_files:
            entry_points = [f for f in code_files if "test" not in f.lower()][:3]

        # Identify core symbols (classes, main routers)
        core_classes = [n.get("label") for n in ast_nodes if n.get("type") == "class"][:5]

        sorted_modules = sorted(list(modules))[:6]
        entry_list = entry_points[:4] or (code_files[:2] if code_files else ["main.py"])

        return {
            "agent": self.agent_name,
            "status": "completed",
            "repo": f"{repo_owner}/{repo_name}",
            "core_modules": sorted_modules or ["core"],
            "entry_points": entry_list,
            "test_suites_count": len(test_suites),
            "key_classes": core_classes,
            "onboarding_summary": (
                f"Welcome to {repo_owner}/{repo_name}! The repository is structured into {len(sorted_modules) or 1} primary module(s) "
                f"({', '.join(sorted_modules[:3]) or 'core'}). "
                f"Main entry points are located in {', '.join(entry_list[:2])}, "
                f"with {len(test_suites)} test files ensuring continuous regression safety."
            ),
            "contributor_tips": [
                "Run unit tests locally before pushing to verify no callers broke.",
                "Ensure public function signature changes are covered with backward-compatibility assertions.",
                "Avoid modifying CI/CD workflows under `.github/` without maintainer pre-approval.",
            ],
        }

    def pathfind_issue_to_code(
        self,
        issue_title: str,
        issue_body: str,
        ast_nodes: List[Dict[str, Any]],
        file_paths: List[str],
    ) -> Dict[str, Any]:
        """
        Analyzes an issue description and identifies candidate files and functions
        that the contributor should modify to fix the issue.
        """
        combined_text = f"{issue_title} {issue_body}".lower()
        tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{3,30}\b", combined_text)
        candidate_keywords = set(tokens) - {
            "this", "that", "with", "have", "from", "when", "issue", "error",
            "failed", "does", "should", "could", "would", "about", "after",
        }

        matched_functions = []
        matched_files = set()

        for node in ast_nodes:
            lbl = node.get("label", "").lower()
            node_id = node.get("id", "")
            fpath = node.get("file_path", "")

            for kw in candidate_keywords:
                if kw in lbl or kw in node_id.lower():
                    matched_functions.append({
                        "id": node.get("id"),
                        "label": node.get("label"),
                        "file_path": fpath,
                        "type": node.get("type"),
                        "matched_keyword": kw,
                    })
                    if fpath:
                        matched_files.add(fpath)
                    break

        return {
            "agent": self.agent_name,
            "status": "completed",
            "query_keywords": list(candidate_keywords)[:5],
            "candidate_entrypoints": matched_functions[:6],
            "relevant_files": sorted(list(matched_files))[:5],
            "confidence": "high" if len(matched_functions) > 0 else "medium",
            "guidance": (
                f"Identified {len(matched_functions)} candidate function(s) across {len(matched_files)} file(s) "
                f"relevant to issue '{issue_title}'."
                if matched_functions
                else "No exact symbol match found; check top-level module routes."
            ),
        }

    def synthesize_test_stub(
        self,
        target_fn: str,
        file_path: str,
        language: str = "python",
    ) -> str:
        """
        Synthesizes a starter unit test patch covering the target function signature.
        """
        if language in ("python", "generic"):
            module_name = file_path.replace("/", ".").replace(".py", "")
            return (
                f"--- a/tests/test_onboarding.py\n"
                f"+++ b/tests/test_onboarding.py\n"
                f"@@ -0,0 +1,12 @@\n"
                f"+import pytest\n"
                f"+from {module_name} import {target_fn}\n"
                f"+\n"
                f"+def test_{target_fn}_contract():\n"
                f"+    \"\"\"Verifies {target_fn} maintains backward compatibility.\"\"\"\n"
                f"+    # TODO: Add assertions matching the issue criteria\n"
                f"+    res = {target_fn}()\n"
                f"+    assert res is not None\n"
            )
        else:
            clean_path = file_path.replace(".ts", "").replace(".js", "")
            return (
                f"--- a/tests/test_onboarding.spec.ts\n"
                f"+++ b/tests/test_onboarding.spec.ts\n"
                f"@@ -0,0 +1,10 @@\n"
                f"+import {{ {target_fn} }} from '../{clean_path}';\n"
                f"+\n"
                f"+describe('{target_fn}', () => {{\n"
                f"+  it('should conform to expected signature', () => {{\n"
                f"+    expect({target_fn}).toBeDefined();\n"
                f"+  }});\n"
                f"+}});\n"
            )
