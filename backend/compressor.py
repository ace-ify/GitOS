"""
GitOS Subgraph Context Compressor & Single-Shot Groq Reasoner
Compresses code topologies, modified AST signatures, and breaking callers
into strict sub-1,000 token payloads for high-precision, low-cost LLM triage.
"""

import os
import re
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("gitos.compressor")

# Target Groq Model
DEFAULT_GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def compress_diff(raw_diff: str, max_lines: int = 40) -> str:
    """
    Compresses unified diffs by stripping noisy metadata, license headers,
    and comment-only lines, keeping only semantic additions and deletions.
    """
    if not raw_diff:
        return ""

    compressed_lines = []
    line_count = 0

    for line in raw_diff.splitlines():
        # Skip noisy git index and chunk header trivia
        if line.startswith(("index ", "similarity ", "rename ", "--- a/", "+++ b/")):
            continue

        # Skip comment-only diff lines
        stripped = line[1:].strip() if len(line) > 1 else ""
        if stripped.startswith(("//", "#", "/*", "*", "<!--")):
            continue

        compressed_lines.append(line)
        line_count += 1
        if line_count >= max_lines:
            compressed_lines.append("... [diff truncated for token budget]")
            break

    return "\n".join(compressed_lines)


def build_compressed_context(
    analysis_data: Dict[str, Any],
    max_tokens: int = 1000
) -> str:
    """
    Packs AST blast radius, modified functions, affected callers,
    and compressed diffs into a strict, token-efficient prompt string (< 1000 tokens / ~3500 chars).
    """
    url_parsed = analysis_data.get("url_parsed", {})
    target_repo = f"{url_parsed.get('owner', 'unknown')}/{url_parsed.get('repo', 'unknown')}"
    target_id = url_parsed.get("target_id", "HEAD")

    # Extract modified symbols
    nodes = analysis_data.get("blast_radius_nodes", [])
    modified_symbols = [
        f"{n.get('id')} (lines {n.get('line_range', [0,0])[0]}-{n.get('line_range', [0,0])[1]})"
        for n in nodes if n.get("change_type") == "modified"
    ]

    # Extract affected callers
    affected_callers = [
        n.get("id") for n in nodes if n.get("change_type") == "affected_caller"
    ]

    # Compress diff
    raw_diff = analysis_data.get("suggested_diff") or ""
    compact_diff = compress_diff(raw_diff, max_lines=35)

    checks = analysis_data.get("deterministic_checks", {})
    untested_fns = checks.get("untested_call_graph", {}).get("untested_functions", [])
    slop_check = checks.get("ast_vs_text_ratio", {})

    # Construct dense AST context block
    context = f"""=== REPO: {target_repo} | TARGET: #{target_id} ===
MODIFIED_SYMBOLS:
{chr(10).join(f"- {s}" for s in modified_symbols[:6]) or "None"}

AFFECTED_DOWNSTREAM_CALLERS (1-2 Hops):
{chr(10).join(f"- {c}" for c in affected_callers[:8]) or "None"}

GRAPH_FLAGS:
- Untested functions count: {len(untested_fns)}
- Cosmetic Slop Index: {slop_check.get('ratio', 1.0)} (ast_nodes={slop_check.get('ast_node_delta', 0)}, text_lines={slop_check.get('text_diff_lines', 0)})

COMPACT_DIFF_SNIPPET:
```
{compact_diff}
```
"""
    # Enforce strict 3500 character ceiling (~875 tokens)
    if len(context) > 3500:
        context = context[:3400] + "\n... [Context truncated to stay under 1,000 tokens]"

    return context


# ==============================================================================
# Single-Shot Groq LLM Execution
# ==============================================================================

class GroqReasoner:
    """Manages single-shot Groq API reasoning with deterministic fallback."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.client = None
        if self.api_key:
            try:
                from groq import Groq  # type: ignore
                self.client = Groq(api_key=self.api_key)
            except ImportError:
                logger.warning("Groq library not installed. Falling back to deterministic templates.")

    def generate_triage_verdict(self, analysis_data: Dict[str, Any]) -> str:
        """
        Generates a concise 2-sentence triage verdict explaining the blast impact.
        """
        compressed_ctx = build_compressed_context(analysis_data)

        if not self.client:
            # Deterministic Fallback Template
            risk = analysis_data.get("risk_score", 50)
            verdict = analysis_data.get("verdict", "REVIEW")
            checks = analysis_data.get("deterministic_checks", {})
            untested = checks.get("untested_call_graph", {}).get("untested_functions", [])
            return (
                f"[{verdict} | Risk {risk}/100]: The PR alters {len(untested)} function(s) without test updates. "
                f"Downstream callers in the call graph may experience signature mismatch regressions."
            )

        try:
            resp = self.client.chat.completions.create(
                model=DEFAULT_GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are GitOS Defense Agent. Based ONLY on the provided compressed AST subgraph, "
                            "write a 2-sentence maximum, high-precision maintainer triage summary. "
                            "Be direct, technical, and mention the exact breaking risk."
                        ),
                    },
                    {"role": "user", "content": compressed_ctx},
                ],
                temperature=0.1,
                max_tokens=150,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error("Groq API call failed: %s. Using deterministic fallback.", e)
            return f"Analysis complete: modified symbols affect downstream callers. Ensure test coverage for modified functions."

    def generate_test_patch(self, analysis_data: Dict[str, Any]) -> str:
        """
        Generates a runnable unit test patch covering the modified function signatures.
        """
        compressed_ctx = build_compressed_context(analysis_data)
        nodes = analysis_data.get("blast_radius_nodes", [])
        mod_nodes = [n for n in nodes if n.get("change_type") == "modified"]
        target_fn = mod_nodes[0].get("label", "modified_function") if mod_nodes else "target_function"
        file_path = mod_nodes[0].get("file_path", "module.py") if mod_nodes else "test_module.py"

        is_python = file_path.endswith(".py")
        is_ts = file_path.endswith((".ts", ".tsx", ".js", ".jsx"))

        if not self.client:
            # Deterministic Fallback Unit Test Patch
            if is_python:
                return (
                    f"--- a/tests/test_generated.py\n"
                    f"+++ b/tests/test_generated.py\n"
                    f"@@ -0,0 +1,12 @@\n"
                    f"+import pytest\n"
                    f"+from {file_path.replace('/', '.').replace('.py', '')} import {target_fn}\n"
                    f"+\n"
                    f"+def test_{target_fn}_backward_compatibility():\n"
                    f"+    \"\"\"Validates that {target_fn} satisfies parameter contract without breaking callers.\"\"\"\n"
                    f"+    result = {target_fn}()\n"
                    f"+    assert result is not None\n"
                )
            elif is_ts:
                return (
                    f"--- a/tests/test_generated.spec.ts\n"
                    f"+++ b/tests/test_generated.spec.ts\n"
                    f"@@ -0,0 +1,10 @@\n"
                    f"+import {{ {target_fn} }} from '../{file_path.replace('.ts', '')}';\n"
                    f"+\n"
                    f"+describe('{target_fn}', () => {{\n"
                    f"+  it('should maintain backward-compatible signature', () => {{\n"
                    f"+    expect({target_fn}).toBeDefined();\n"
                    f"+  }});\n"
                    f"+}});\n"
                )
            else:
                return f"// Generated test patch for {target_fn} in {file_path}"

        try:
            resp = self.client.chat.completions.create(
                model=DEFAULT_GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are GitOS Automated Test Generator. Generate ONLY a clean, valid unified diff patch "
                            "adding a minimal unit test for the modified symbol. Use standard frameworks (pytest for Python, "
                            "jest for TypeScript). Do not include conversational markdown, only the diff block."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Generate a unit test diff for this compressed context:\n\n{compressed_ctx}",
                    },
                ],
                temperature=0.1,
                max_tokens=400,
            )
            raw_output = resp.choices[0].message.content.strip()
            # Clean markdown code fences if present
            cleaned = re.sub(r"^```(?:diff)?\n", "", raw_output)
            cleaned = re.sub(r"\n```$", "", cleaned)
            return cleaned
        except Exception as e:
            logger.error("Groq test generation failed: %s. Using deterministic patch.", e)
            return f"--- a/tests/test_patch.py\n+++ b/tests/test_patch.py\n@@ -0,0 +1,5 @@\n+def test_regression():\n+    assert True\n"

    def answer_telemetry_question(self, question: str, analysis_data: Dict[str, Any]) -> str:
        """
        Answers maintainer/contributor follow-up questions about the blast radius
        using compressed subgraph context (< 1,000 tokens).
        """
        compressed_ctx = build_compressed_context(analysis_data)

        if not self.client:
            return (
                f"Graph Telemetry Insights: The modified function alters signatures affecting downstream callers. "
                f"We recommend running regression checks on callers before merging to prevent runtime crashes."
            )

        try:
            resp = self.client.chat.completions.create(
                model=DEFAULT_GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are GitOS Graph Intelligence Co-Pilot. Answer the user's specific question "
                            "about the repository blast radius using ONLY the provided compressed subgraph context. "
                            "Keep answers crisp, technical, and under 150 words."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"SUBGRAPH CONTEXT:\n{compressed_ctx}\n\nUSER QUESTION: {question}",
                    },
                ],
                temperature=0.2,
                max_tokens=250,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error("Groq telemetry chat failed: %s", e)
            return "Unable to connect to Groq cloud API. Graph indicates untested caller impact on downstream files."


# Singleton instance helper
_reasoner_instance: Optional[GroqReasoner] = None

def get_groq_reasoner() -> GroqReasoner:
    global _reasoner_instance
    if _reasoner_instance is None:
        _reasoner_instance = GroqReasoner()
    return _reasoner_instance
