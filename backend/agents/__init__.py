"""
GitOS Multi-Agent Intelligence Swarm
Coordinates specialized autonomous agents for repository management,
security auditing, slop defense, contributor onboarding, and autonomous reasoning.
"""

from backend.agents.triage_agent import TriageAgent
from backend.agents.graph_agent import GraphAgent
from backend.agents.security_agent import SecurityAgent
from backend.agents.onboarding_agent import OnboardingAgent
from backend.agents.reasoning_agent import ReasoningAgent
from backend.agents.orchestrator import GitOSOrchestrator, get_orchestrator

__all__ = [
    "TriageAgent",
    "GraphAgent",
    "SecurityAgent",
    "OnboardingAgent",
    "ReasoningAgent",
    "GitOSOrchestrator",
    "get_orchestrator",
]
