"""
GitOS Triage & Slop Defense Agent (TriageAgent)
Specialized agent responsible for operational PR triage, AI slop detection,
cosmetic diff filtering, and zero-spam sticky GitHub comment formatting.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("gitos.agent.triage")


class TriageAgent:
    """
    Evaluates pull request diffs to eliminate AI-generated review noise.
    Determines whether changes are cosmetic slop or genuine semantic modifications.
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
    ) -> Dict[str, Any]:
        """
        Executes deterministic triage heuristics and produces composite risk metrics.
        """
        ratio = ast_delta / max(text_diff_lines, 1)
        is_cosmetic_slop = text_diff_lines > 25 and ratio < 0.15
        dead_code_symbols = [fn for fn in new_functions if not fn.startswith("test_")]
        has_critical_deps = any(a.get("severity") == "CRITICAL" for a in dep_alerts)

        risk_score = 10
        if untested_check.get("flagged"):
            risk_score += int(untested_check.get("score", 0.5) * 40)
        if is_cosmetic_slop:
            risk_score += 45
        if len(dead_code_symbols) > 0:
            risk_score += 30
        if len(violations) > 0:
            risk_score += 50
        if has_critical_deps:
            risk_score += 60
        elif len(dep_alerts) > 0:
            risk_score += 20

        risk_score = min(risk_score, 100)

        if has_critical_deps:
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
            "dead_code_count": len(dead_code_symbols),
            "recommendation": self._generate_recommendation(verdict, risk_score),
        }

    def _generate_recommendation(self, verdict: str, risk_score: int) -> str:
        if verdict == "SLOPSQUATTING_ALERT":
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
