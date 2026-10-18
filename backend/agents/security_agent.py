"""
GitOS Security & Supply-Chain Audit Agent (SecurityAgent)
Specialized agent for open-source security auditing, Filter 5 Slopsquatting detection,
hallucinated package interception, AST security sinks, and architectural boundary enforcement.
"""

import re
import logging
from typing import Any, Dict, List, Optional
from backend.polyglot import (
    extract_patch_new_imports,
    audit_dependency_risks,
    scan_patch_security_sinks,
)

logger = logging.getLogger("gitos.agent.security")


class SecurityAgent:
    """
    Audits pull requests for supply chain attacks, typo-squatted/hallucinated packages,
    AST-level dangerous sinks (shell injection, eval, hardcoded secrets), and
    architectural boundary violations (e.g. UI directly importing DB tier).
    """

    def __init__(self, maintainer_rules: Optional[List[Dict[str, Any]]] = None):
        self.agent_name = "SecurityAgent"
        self.role = "Supply-Chain & Architectural Security Audit"
        self.maintainer_rules = maintainer_rules or []

    async def audit_dependencies(
        self,
        patch: str,
        language: str = "python",
        manifest_text: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extracts new imports from unified diff and cross-checks them against
        the repository manifest and official registries (PyPI, npm).
        """
        new_packages = extract_patch_new_imports(patch, language=language)
        ecosystem = "npm" if language in ("javascript", "typescript") else "pypi"
        alerts = await audit_dependency_risks(
            new_packages, manifest_text=manifest_text, ecosystem=ecosystem
        )
        return alerts

    def check_architectural_rules(
        self,
        modified_files: List[str],
        edges: Optional[List[Dict[str, Any]]] = None,
        parsed_files: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Checks whether any modified file or cross-module call/import violates
        maintainer architectural rules (e.g., untrusted contributors editing CI/CD workflows,
        or frontend modules directly importing/calling database tier).
        """
        violations: List[Dict[str, Any]] = []
        edges = edges or []
        parsed_files = parsed_files or {}

        for rule in self.maintainer_rules:
            pattern = rule.get("pattern", "")
            rule_id = rule.get("rule_id", "RULE_CUSTOM")
            description = rule.get("description", "")
            rule_type = rule.get("type", "boundary")

            # Rule Type A: File Path Boundary (e.g. guest contributors cannot modify workflows)
            if rule_id == "RULE_NO_WORKFLOW_TOUCH_GUEST" or ".github/workflows" in pattern:
                for f in modified_files:
                    if ".github/workflows" in f:
                        violations.append({
                            "rule_id": rule_id,
                            "severity": "critical",
                            "description": description or "Guest or untrusted contributor modified protected GitHub Actions workflows.",
                            "offending_file": f,
                            "offending_node": f,
                        })

            # Rule Type B: Cross-Module Import & Call Boundary (e.g. frontend/* -> backend/db/*)
            if "frontend" in pattern and ("db" in pattern or "database" in pattern) or rule_id == "RULE_NO_DIRECT_DB_IMPORT":
                # Check cross-file edges
                for edge in edges:
                    src = edge.get("source", "")
                    tgt = edge.get("target", "")
                    if "frontend" in src and any(db_kw in tgt for db_kw in ("database", "db_client", "models", "db/", "db.")):
                        violations.append({
                            "rule_id": "RULE_NO_DIRECT_DB_IMPORT",
                            "severity": "high",
                            "description": description or "Frontend UI module violates architectural boundary by directly importing/calling database tier.",
                            "offending_node": f"{src} -> {tgt}",
                            "offending_file": src.split("::")[0],
                        })

                # Check parsed AST imports in modified frontend files
                for f_path, ast_data in parsed_files.items():
                    if "frontend" in f_path:
                        imports = ast_data.get("imports", {})
                        for sym, mod in imports.items():
                            if any(db_kw in mod.lower() for db_kw in ("database", "db_client", "models", "backend.db", "backend/db")):
                                violations.append({
                                    "rule_id": "RULE_NO_DIRECT_DB_IMPORT",
                                    "severity": "high",
                                    "description": description or f"Frontend module '{f_path}' directly imports database target '{mod}'.",
                                    "offending_node": f"{f_path} -> {mod}",
                                    "offending_file": f_path,
                                })

            # Generic Regex Boundary rules (if custom rule defines from_pattern and to_pattern)
            from_pattern = rule.get("from_pattern")
            to_pattern = rule.get("to_pattern")
            if from_pattern and to_pattern:
                re_from = re.compile(from_pattern)
                re_to = re.compile(to_pattern)
                for edge in edges:
                    src = edge.get("source", "")
                    tgt = edge.get("target", "")
                    if re_from.search(src) and re_to.search(tgt):
                        violations.append({
                            "rule_id": rule_id,
                            "severity": rule.get("severity", "high"),
                            "description": description or f"Boundary leak from {src} to forbidden layer {tgt}.",
                            "offending_node": f"{src} -> {tgt}",
                            "offending_file": src.split("::")[0],
                        })

        return violations

    def scan_code_sinks(self, patch: str, language: str = "python") -> List[Dict[str, Any]]:
        """
        Scans unified diff patch for dangerous security sinks (eval, shell injection, secrets, SQLi).
        """
        return scan_patch_security_sinks(patch, language=language)

    async def run_full_security_audit(
        self,
        patch: str,
        language: str,
        modified_files: List[str],
        manifest_text: Optional[str] = None,
        edges: Optional[List[Dict[str, Any]]] = None,
        parsed_files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Runs comprehensive multi-dimensional security audit:
        1. Supply-chain dependency risk & slopsquatting check
        2. AST and code security sink inspection (eval, shell=True, hardcoded secrets, SQLi)
        3. Maintainer architectural boundary enforcement across graph edges
        """
        dep_alerts = await self.audit_dependencies(patch, language, manifest_text)
        rule_violations = self.check_architectural_rules(
            modified_files=modified_files,
            edges=edges,
            parsed_files=parsed_files,
        )
        security_sinks = self.scan_code_sinks(patch, language=language)

        has_critical = (
            any(a.get("severity") == "CRITICAL" for a in dep_alerts)
            or any(v.get("severity") == "critical" for v in rule_violations)
            or any(s.get("severity") == "CRITICAL" for s in security_sinks)
        )

        total_threats = len(dep_alerts) + len(rule_violations) + len(security_sinks)

        # Generate actionable maintainer remediation summary
        remediations: List[str] = []
        if any(a.get("severity") == "CRITICAL" for a in dep_alerts):
            remediations.append("Block PR: remove or verify unindexed/hallucinated third-party dependencies.")
        if security_sinks:
            for sink in security_sinks[:3]:
                remediations.append(f"Security Sink in line {sink.get('line_number')}: {sink.get('remediation')}")
        if rule_violations:
            remediations.append("Enforce boundary: decouple UI layer from direct database tier calls via API router.")

        return {
            "agent": self.agent_name,
            "status": "completed",
            "passed": not has_critical and total_threats == 0,
            "has_critical_vulnerabilities": has_critical,
            "dependency_alerts": dep_alerts,
            "rule_violations": rule_violations,
            "security_sinks": security_sinks,
            "total_threats_found": total_threats,
            "remediations": remediations,
        }
