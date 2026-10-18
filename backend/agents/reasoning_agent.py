"""
GitOS Autonomous Reasoning & Maintainer Brief Synthesizer (ReasoningAgent)
Synthesizes multi-agent swarm findings (Graph blast radius, Security sinks,
Dependency alerts, Triage slop heuristics) into an authoritative, contextual Maintainer Brief.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("gitos.agent.reasoning")


class ReasoningAgent:
    """
    Autonomous Reasoning Agent that transforms raw AST graph metrics,
    vulnerability alerts, and diff heuristics into a coherent, maintainer-grade
    review brief with actionable recommendations for both maintainers and contributors.
    """

    def __init__(self, llm_reasoner: Optional[Any] = None):
        self.agent_name = "ReasoningAgent"
        self.role = "Autonomous Maintainer Reasoning & Synthesis"
        self.llm_reasoner = llm_reasoner

    def synthesize_maintainer_brief(
        self,
        repo_id: str,
        pr_id: Optional[str],
        verdict: str,
        risk_score: int,
        modified_functions: List[str],
        untested_callers: List[str],
        dependency_alerts: List[Dict[str, Any]],
        rule_violations: List[Dict[str, Any]],
        security_sinks: List[Dict[str, Any]],
        is_cosmetic_slop: bool,
        ast_vs_text_ratio: float,
        dead_code_symbols: List[str],
    ) -> Dict[str, Any]:
        """
        Produces an authoritative, structured maintainer reasoning brief.
        Zero LLM tokens required for baseline synthesis, with rich narrative output.
        """
        # 1. Executive Verdict Line
        if verdict == "SECURITY_SINK_ALERT":
            executive_verdict = f"CRITICAL: Pull Request introduces {len(security_sinks)} severe code injection or credential vulnerabilities."
        elif verdict == "SLOPSQUATTING_ALERT":
            executive_verdict = f"BLOCK PR: {len(dependency_alerts)} unindexed or hallucinated dependencies detected in diff."
        elif verdict == "RULE_VIOLATION":
            executive_verdict = f"ARCHITECTURAL VIOLATION: PR violates {len(rule_violations)} maintainer-defined boundary constraints."
        elif verdict == "AI_SLOP_SUSPECTED":
            executive_verdict = f"SUSPECTED AI SLOP: High diff line count with low semantic AST density ({ast_vs_text_ratio} ratio)."
        elif verdict == "CRITICAL_BLAST":
            executive_verdict = f"HIGH IMPACT: Wide blast radius affecting {len(untested_callers)} downstream callers without corresponding test coverage."
        elif verdict == "NEEDS_TESTS":
            executive_verdict = f"TESTING GAP: {len(modified_functions)} core function signatures updated without companion test suite coverage."
        elif verdict == "LOW_RISK":
            executive_verdict = "LOW RISK: Semantic modifications verified with minimal blast radius. Standard peer review recommended."
        else:
            executive_verdict = "VERIFIED CLEAN: Changes pass all graph, security, and architectural boundary invariants."

        # 2. Risk Driver Narrative
        risk_drivers: List[str] = []
        if security_sinks:
            for s in security_sinks[:3]:
                risk_drivers.append(f"Dangerous code sink: {s.get('description')} (Line {s.get('line_number')})")
        if dependency_alerts:
            for d in dependency_alerts[:3]:
                risk_drivers.append(f"Supply chain risk: {d.get('message')}")
        if rule_violations:
            for v in rule_violations[:3]:
                risk_drivers.append(f"Boundary breach: {v.get('description')} ({v.get('offending_node', '')})")
        if untested_callers:
            risk_drivers.append(f"{len(untested_callers)} downstream caller(s) invoke modified code but lack updated tests in this diff.")
        if is_cosmetic_slop:
            risk_drivers.append(f"Cosmetic formatting or documentation re-write without functional AST modifications (Ratio: {ast_vs_text_ratio}).")
        if dead_code_symbols:
            risk_drivers.append(f"{len(dead_code_symbols)} newly defined function(s) have 0 incoming references across the repository graph.")

        if not risk_drivers:
            risk_drivers.append("No adverse risk factors identified across code AST or dependency manifests.")

        # 3. Actionable Maintainer Plan
        action_plan: List[str] = []
        if verdict in ("SECURITY_SINK_ALERT", "SLOPSQUATTING_ALERT"):
            action_plan.append("1. Block merge and notify contributor of security finding.")
            action_plan.append("2. Request immediate removal of unverified package or unsafe shell/eval invocation.")
            action_plan.append("3. Run automated sandbox verification before unblocking CI.")
        elif verdict == "RULE_VIOLATION":
            action_plan.append("1. Request architectural realignment to preserve module boundary encapsulation.")
            action_plan.append("2. Route data requests through approved service/API layer.")
        elif verdict == "AI_SLOP_SUSPECTED":
            action_plan.append("1. Check whether PR provides meaningful behavioral improvements.")
            action_plan.append("2. Close or request contributor condense diff if changes are purely superficial.")
        elif verdict in ("CRITICAL_BLAST", "NEEDS_TESTS"):
            action_plan.append("1. Request contributor add unit tests covering the modified function signatures.")
            action_plan.append("2. Generate and provide automated test scaffolding stubs.")
            action_plan.append("3. Verify downstream callers in the blast radius.")
        else:
            action_plan.append("1. Review code diff for business logic nuances.")
            action_plan.append("2. Approve and merge when standard CI passes.")

        # 4. Constructive Contributor Guidance
        if untested_callers or verdict == "NEEDS_TESTS":
            contributor_guidance = (
                "To get this PR merged quickly: Add unit tests covering the modified functions "
                f"({', '.join(modified_functions[:3])}). Use the 1-Click Test Stub Generator in the Contributor Flight Deck "
                "to scaffold the missing test fixtures."
            )
        elif security_sinks:
            contributor_guidance = (
                "Security Alert: Your patch contains code constructs (such as eval, shell=True, or exposed secrets) "
                "flagged by security policy. Please replace them with parameterized or safe alternatives."
            )
        elif dependency_alerts:
            contributor_guidance = (
                "Dependency Alert: One or more imported packages could not be verified on PyPI/npm. "
                "Ensure package names are spelled correctly and declared in project manifest files."
            )
        else:
            contributor_guidance = "Your pull request adheres to architectural boundaries and maintains test coverage. Thank you for contributing!"

        # 5. Narrative Reasoning Synthesis
        brief_markdown = f"""### 🧠 GitOS Autonomous Maintainer Brief

**Executive Verdict:** {executive_verdict}  
**Composite Risk Rating:** **{risk_score} / 100** (`{verdict}`)

#### 🔍 Architectural & Structural Findings:
{chr(10).join([f"- {driver}" for driver in risk_drivers])}

#### 📋 Step-by-Step Review Action Plan:
{chr(10).join([f"{step}" for step in action_plan])}

#### 💡 Contributor Guidance:
> {contributor_guidance}
"""

        return {
            "agent": self.agent_name,
            "status": "completed",
            "executive_verdict": executive_verdict,
            "risk_drivers": risk_drivers,
            "action_plan": action_plan,
            "contributor_guidance": contributor_guidance,
            "brief_markdown": brief_markdown.strip(),
        }
