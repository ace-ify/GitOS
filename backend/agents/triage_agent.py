"""
GitOS Triage & Slop Defense Agent (TriageAgent)
Specialized agent responsible for operational PR triage, AI slop detection,
cosmetic diff filtering, dead code resolution, and composite risk scoring.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("gitos.agent.triage")


class TriageAgent:
    """
    Evaluates pull request diffs to eliminate AI-generated review noise.
    Determines whether changes are cosmetic slop, dangerous sinks, or genuine semantic modifications.
    """

    def __init__(self):
        self.agent_name = "TriageAgent"
        self.role = "Operational Triage & AI Slop Defense"

    def evaluate_slop_and_triage(
        self,
        ast_delta: int,
        text_diff_lines: int,
        modified_functions: List[str],
        modified_tests: List[str],
        new_functions: List[str],
        untested_check: Dict[str, Any],
        violations: List[Dict[str, Any]],
        dep_alerts: List[Dict[str, Any]],
        security_sinks: Optional[List[Dict[str, Any]]] = None,
        dead_code_symbols: Optional[List[str]] = None,
        edges: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Executes deterministic triage heuristics and produces composite risk metrics.
        Uses real graph in-degree to verify dead code instead of naive string matching.
        """
        security_sinks = security_sinks or []
        ratio = ast_delta / max(text_diff_lines, 1)
        is_cosmetic_slop = text_diff_lines > 25 and ratio < 0.15

        # Precise Dead Code Resolution:
        # If dead_code_symbols was not provided, compute it using graph edges
        if dead_code_symbols is None:
            if edges:
                called_targets = {e.get("target") for e in edges if e.get("relationship") == "CALLS"}
                dead_code_symbols = [
                    fn for fn in new_functions
                    if fn not in called_targets
                    and not fn.split("::")[-1].startswith(("test_", "__", "main", "handler", "on_"))
                ]
            else:
                # If no graph edges are available, do NOT blindly penalize new functions
                dead_code_symbols = []

        has_critical_deps = any(a.get("severity") == "CRITICAL" for a in dep_alerts)
        has_critical_sinks = any(s.get("severity") == "CRITICAL" for s in security_sinks)

        risk_score = 10
        if untested_check.get("flagged"):
            risk_score += int(untested_check.get("score", 0.5) * 35)
        if is_cosmetic_slop:
            risk_score += 45
        if len(dead_code_symbols) > 0:
            risk_score += min(len(dead_code_symbols) * 15, 30)
        if len(violations) > 0:
            risk_score += 50
        if has_critical_deps:
            risk_score += 60
        elif len(dep_alerts) > 0:
            risk_score += 20
        if has_critical_sinks:
            risk_score += 65
        elif len(security_sinks) > 0:
            risk_score += 25

        risk_score = min(risk_score, 100)

        # Priority-ordered Verdict Determination
        if has_critical_sinks:
            verdict = "SECURITY_SINK_ALERT"
        elif has_critical_deps:
            verdict = "SLOPSQUATTING_ALERT"
        elif len(violations) > 0:
            verdict = "RULE_VIOLATION"
        elif is_cosmetic_slop:
            verdict = "AI_SLOP_SUSPECTED"
        elif risk_score >= 70:
            verdict = "CRITICAL_BLAST"
        elif untested_check.get("flagged"):
            verdict = "NEEDS_TESTS"
        elif risk_score > 30:
            verdict = "LOW_RISK"
        else:
            verdict = "CLEAN"

        return {
            "agent": self.agent_name,
            "status": "completed",
            "verdict": verdict,
            "risk_score": risk_score,
            "is_cosmetic_slop": is_cosmetic_slop,
            "ast_vs_text_ratio": round(ratio, 2),
            "dead_code_symbols": dead_code_symbols,
            "dead_code_count": len(dead_code_symbols),
            "security_sinks_count": len(security_sinks),
            "recommendation": self._generate_recommendation(verdict, risk_score),
        }

    def _generate_recommendation(self, verdict: str, risk_score: int) -> str:
        if verdict == "SECURITY_SINK_ALERT":
            return "Block PR immediately. Dangerous code execution sinks, command injection, or exposed secrets detected."
        elif verdict == "SLOPSQUATTING_ALERT":
            return "Block PR immediately. Hallucinated or malicious dependency imports detected."
        elif verdict == "RULE_VIOLATION":
            return "Request architectural changes. PR violates maintainer boundary rules."
        elif verdict == "AI_SLOP_SUSPECTED":
            return "Close or reject PR. High text diff volume with minimal semantic AST changes suggests AI formatting slop."
        elif verdict in ("CRITICAL_BLAST", "NEEDS_TESTS"):
            return "Request unit test coverage for modified functions before merging."
        elif risk_score > 30:
            return "Low risk. Standard peer review recommended."
        return "Clean PR. Safe for automated CI verification and merge."
