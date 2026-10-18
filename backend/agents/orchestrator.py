"""
GitOS Multi-Agent Orchestrator (GitOSOrchestrator)
Supervisor agent coordinating specialized autonomous agents:
- TriageAgent (AI Slop Defense & Operational Triage)
- GraphAgent (AST Extraction, FalkorDB Traversal, Mermaid Compilation)
- SecurityAgent (Slopsquatting Sentinel, AST Sinks & Architectural Rule Enforcement)
- OnboardingAgent (Modernized Contributor Onboarding & Issue Pathfinder)
- ReasoningAgent (Autonomous Maintainer Reasoning & Review Synthesis)
"""

import time
import logging
from typing import Any, Dict, List, Optional

from backend.agents.triage_agent import TriageAgent
from backend.agents.graph_agent import GraphAgent
from backend.agents.security_agent import SecurityAgent
from backend.agents.onboarding_agent import OnboardingAgent
from backend.agents.reasoning_agent import ReasoningAgent
from backend.compressor import get_groq_reasoner

logger = logging.getLogger("gitos.orchestrator")


class GitOSOrchestrator:
    """
    Supervisor Agent coordinating autonomous workflows across the multi-agent swarm.
    Synthesizes graph reasoning, security auditing, triage heuristics, onboarding,
    and autonomous maintainer review synthesis.
    """

    def __init__(self, graph_client: Optional[Any] = None, maintainer_rules: Optional[List[Dict[str, Any]]] = None):
        self.triage_agent = TriageAgent()
        self.graph_agent = GraphAgent(graph_client=graph_client)
        self.security_agent = SecurityAgent(maintainer_rules=maintainer_rules)
        self.onboarding_agent = OnboardingAgent()
        self.groq_reasoner = get_groq_reasoner()
        self.reasoning_agent = ReasoningAgent(llm_reasoner=self.groq_reasoner)

    async def coordinate_analysis(
        self,
        repo_id: str,
        commit_sha: str,
        file_contents: Dict[str, str],
        modified_functions: List[str],
        modified_tests: List[str],
        new_functions: List[str],
        file_paths: List[str],
        raw_patch: str = "",
        language: str = "python",
        manifest_text: Optional[str] = None,
        issue_context: Optional[Dict[str, str]] = None,
        pr_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Coordinates the multi-agent swarm in an end-to-end autonomous analysis pipeline.
        """
        start_time = time.time()

        # 1. GraphAgent parses AST and traces multi-hop blast radius
        parsed_files = self.graph_agent.parse_repository_files(file_contents)
        graph_report = self.graph_agent.analyze_blast_radius(
            repo_id=repo_id,
            commit_sha=commit_sha,
            parsed_files=parsed_files,
            modified_functions=modified_functions,
            modified_tests=modified_tests,
        )

        # 2. SecurityAgent runs supply-chain, AST sinks, and maintainer boundary audit
        security_report = await self.security_agent.run_full_security_audit(
            patch=raw_patch,
            language=language,
            modified_files=file_paths,
            manifest_text=manifest_text,
            edges=graph_report.get("edges", []),
            parsed_files=parsed_files,
        )

        # 3. TriageAgent evaluates slop, untested callers, and calculates risk score
        untested_check = {
            "flagged": len(graph_report["untested_callers"]) > 0,
            "score": 0.85 if graph_report["untested_callers"] else 0.1,
            "untested_functions": graph_report["untested_callers"],
        }
        text_lines = max(len(raw_patch.splitlines()), 1)
        ast_delta = sum(f.get("ast_node_count", 0) for f in parsed_files.values())

        triage_report = self.triage_agent.evaluate_slop_and_triage(
            ast_delta=ast_delta,
            text_diff_lines=text_lines,
            modified_functions=modified_functions,
            modified_tests=modified_tests,
            new_functions=new_functions,
            untested_check=untested_check,
            violations=security_report["rule_violations"],
            dep_alerts=security_report["dependency_alerts"],
            security_sinks=security_report.get("security_sinks", []),
            edges=graph_report.get("edges", []),
        )

        # 4. OnboardingAgent generates architecture tour and issue pathfinding
        all_ast_nodes = graph_report["nodes"]
        onboarding_tour = self.onboarding_agent.generate_architecture_tour(
            repo_owner=repo_id.split("/")[0] if "/" in repo_id else "repo",
            repo_name=repo_id.split("/")[-1] if "/" in repo_id else repo_id,
            file_tree=file_paths,
            ast_nodes=all_ast_nodes,
        )

        pathfinder_report = None
        if issue_context and issue_context.get("title"):
            pathfinder_report = self.onboarding_agent.pathfind_issue_to_code(
                issue_title=issue_context.get("title", ""),
                issue_body=issue_context.get("body", ""),
                ast_nodes=all_ast_nodes,
                file_paths=file_paths,
            )

        # 5. ReasoningAgent synthesizes the multi-agent findings into Maintainer Brief
        reasoning_report = self.reasoning_agent.synthesize_maintainer_brief(
            repo_id=repo_id,
            pr_id=pr_id,
            verdict=triage_report["verdict"],
            risk_score=triage_report["risk_score"],
            modified_functions=modified_functions,
            untested_callers=graph_report["untested_callers"],
            dependency_alerts=security_report["dependency_alerts"],
            rule_violations=security_report["rule_violations"],
            security_sinks=security_report.get("security_sinks", []),
            is_cosmetic_slop=triage_report["is_cosmetic_slop"],
            ast_vs_text_ratio=triage_report["ast_vs_text_ratio"],
            dead_code_symbols=triage_report.get("dead_code_symbols", []),
        )

        # 6. Compile Mermaid diagram for GitHub markdown comments
        mermaid_dag = self.graph_agent.compile_mermaid_dag(
            nodes=graph_report["nodes"],
            edges=graph_report["edges"],
        )

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Multi-Agent Swarm Telemetry
        swarm_telemetry = {
            "triage_agent": {
                "name": "TriageAgent",
                "role": self.triage_agent.role,
                "status": "active",
                "verdict": triage_report["verdict"],
                "risk_score": triage_report["risk_score"],
                "slop_detected": triage_report["is_cosmetic_slop"],
                "recommendation": triage_report["recommendation"],
            },
            "graph_agent": {
                "name": "GraphAgent",
                "role": self.graph_agent.role,
                "status": "active",
                "total_nodes": graph_report["total_nodes"],
                "total_edges": graph_report["total_edges"],
                "untested_callers": graph_report["untested_callers"],
                "mermaid_compiled": bool(mermaid_dag),
            },
            "security_agent": {
                "name": "SecurityAgent",
                "role": self.security_agent.role,
                "status": "active",
                "passed": security_report["passed"],
                "threats_count": security_report["total_threats_found"],
                "slopsquatting_alerts": security_report["dependency_alerts"],
                "rule_violations": security_report["rule_violations"],
                "security_sinks": security_report.get("security_sinks", []),
            },
            "onboarding_agent": {
                "name": "OnboardingAgent",
                "role": self.onboarding_agent.role,
                "status": "active",
                "core_modules": onboarding_tour["core_modules"],
                "entry_points": onboarding_tour["entry_points"],
                "pathfinder_active": bool(pathfinder_report),
                "tips_count": len(onboarding_tour["contributor_tips"]),
            },
            "reasoning_agent": {
                "name": "ReasoningAgent",
                "role": self.reasoning_agent.role,
                "status": "active",
                "executive_verdict": reasoning_report["executive_verdict"],
                "risk_drivers": reasoning_report["risk_drivers"],
                "action_plan": reasoning_report["action_plan"],
            },
        }

        return {
            "orchestrator_status": "success",
            "swarm_telemetry": swarm_telemetry,
            "verdict": triage_report["verdict"],
            "risk_score": triage_report["risk_score"],
            "graph_report": graph_report,
            "security_report": security_report,
            "triage_report": triage_report,
            "onboarding_tour": onboarding_tour,
            "pathfinder_report": pathfinder_report,
            "reasoning_report": reasoning_report,
            "maintainer_brief": reasoning_report["brief_markdown"],
            "mermaid_dag": mermaid_dag,
            "latency_ms": elapsed_ms,
        }


# Singleton Orchestrator instance
_orchestrator_instance: Optional[GitOSOrchestrator] = None

def get_orchestrator(graph_client: Optional[Any] = None, maintainer_rules: Optional[List[Dict[str, Any]]] = None) -> GitOSOrchestrator:
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = GitOSOrchestrator(graph_client=graph_client, maintainer_rules=maintainer_rules)
    return _orchestrator_instance
