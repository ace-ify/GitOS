"""
GitOS Security & Supply-Chain Audit Agent (SecurityAgent)
Specialized agent for open-source security auditing, Filter 5 Slopsquatting detection,
hallucinated package interception, and maintainer architectural boundary enforcement.
"""

import logging
from typing import Any, Dict, List, Optional
from backend.polyglot import extract_patch_new_imports, audit_dependency_risks

logger = logging.getLogger("gitos.agent.security")


class SecurityAgent:
    """
    Audits pull requests for supply chain attacks, typo-squatted/hallucinated packages,
    and architectural boundary violations (e.g. UI directly importing DB tier).
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
        self, modified_files: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Checks whether any modified file violates custom maintainer boundary rules
        (e.g., untrusted contributors editing CI/CD workflows, or frontend touching DB).
        """
        violations = []
        for rule in self.maintainer_rules:
            pattern = rule.get("pattern", "")
            rule_id = rule.get("rule_id", "RULE_CUSTOM")
            description = rule.get("description", "")

            if rule_id == "RULE_NO_WORKFLOW_TOUCH_GUEST":
                for f in modified_files:
                    if ".github/workflows" in f:
                        violations.append({
                            "rule_id": rule_id,
                            "severity": "critical",
                            "description": description,
                            "offending_file": f,
                        })
            elif "frontend/* -> backend/db/*" in pattern:
                for f in modified_files:
                    if f.startswith("frontend/") and ("backend/db" in f or "database" in f):
                        violations.append({
                            "rule_id": rule_id,
                            "severity": "high",
                            "description": description,
                            "offending_file": f,
                        })

        return violations

    async def run_full_security_audit(
        self,
        patch: str,
        language: str,
        modified_files: List[str],
        manifest_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Runs both supply-chain and architectural security audits."""
        dep_alerts = await self.audit_dependencies(patch, language, manifest_text)
        rule_violations = self.check_architectural_rules(modified_files)

        has_critical = any(a.get("severity") == "CRITICAL" for a in dep_alerts) or any(
            v.get("severity") == "critical" for v in rule_violations
        )

        return {
            "agent": self.agent_name,
            "status": "completed",
            "passed": not has_critical and len(rule_violations) == 0,
            "has_critical_vulnerabilities": has_critical,
            "dependency_alerts": dep_alerts,
            "rule_violations": rule_violations,
            "total_threats_found": len(dep_alerts) + len(rule_violations),
        }
