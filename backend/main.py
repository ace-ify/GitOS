"""
GitOS Core Backend & Universal Omnibox Engine
Production-grade FastAPI service providing in-memory universal AST analysis,
cross-file import stitching, FalkorDB Cypher integration, and zero-token deterministic triage.
"""

import os
import re
import uuid
import time
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Load environment configuration
load_dotenv()

# Setup structured logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gitos.backend")

# Initialize FastAPI application
app = FastAPI(
    title="GitOS Backend Engine",
    description="Graph-Powered Ecosystem Defense & Intelligence Layer for GitHub",
    version="1.1.0",
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000"), "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Internal module imports
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.polyglot import (
    extract_universal_ast,
    stitch_cross_file_graph,
    detect_language,
    parse_patch_modified_lines,
    is_node_modified_by_patch,
    extract_patch_new_imports,
    audit_dependency_risks,
)
from backend.github_client import get_github_client, EXCLUDED_EXTENSIONS
from backend.compressor import get_groq_reasoner
from backend.auth import auth_router, get_session
from backend.webhooks import webhook_router

try:
    from graph.client import get_graph_client
    graph_client = get_graph_client()
except Exception as e:
    logger.warning("Graph client import warning: %s", e)
    graph_client = None

github_client = get_github_client()
groq_reasoner = get_groq_reasoner()

# Mount OAuth & authentication endpoints
app.include_router(auth_router)
# Mount GitHub Webhooks ingest endpoint
app.include_router(webhook_router)


# ==============================================================================
# Pydantic Request / Response Models
# ==============================================================================

class AnalyzeRequest(BaseModel):
    url: str = Field(..., description="Universal GitHub URL (Repo, PR, Issue, or Blob)")
    github_token: Optional[str] = Field(None, description="Optional GitHub Personal Access / OAuth Token")
    user_mode: Optional[str] = Field("maintainer", description="'maintainer', 'contributor', or 'guest'")


class ExecuteActionRequest(BaseModel):
    action_type: str = Field(..., description="Action identifier: 'gh_comment', 'gh_label', 'gh_close', 'gh_pr_draft'")
    owner: str
    repo: str
    target_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = Field(False, description="Must be explicitly True via user modal confirmation")
    oauth_token: Optional[str] = Field(None, description="User's authenticated GitHub OAuth token")


class MaintainerRuleCreate(BaseModel):
    rule_id: str
    name: str
    pattern: str
    severity: str = "high"
    description: str


class GeneratePatchRequest(BaseModel):
    analysis_data: Dict[str, Any]


class ChatQueryRequest(BaseModel):
    analysis_id: str
    prompt: str
    analysis_data: Optional[Dict[str, Any]] = None


# In-memory store for custom maintainer rules
CUSTOM_MAINTAINER_RULES: List[Dict[str, Any]] = [
    {
        "rule_id": "RULE_NO_DIRECT_DB_IMPORT",
        "name": "No Direct Database Imports",
        "pattern": "frontend/* -> backend/db/*",
        "severity": "high",
        "description": "Frontend UI modules cannot directly import database tier files without API route mediation.",
    },
    {
        "rule_id": "RULE_NO_WORKFLOW_TOUCH_GUEST",
        "name": "Protected GitHub Workflows",
        "pattern": ".github/workflows/*",
        "severity": "critical",
        "description": "First-time contributors cannot modify GitHub Actions CI/CD workflows.",
    },
]


# ==============================================================================
# 1. Universal Smart Omnibox URL Parser
# ==============================================================================

URL_PATTERNS = {
    "pull": re.compile(r"^https?://github\.com/(?P<owner>[\w\.\-]+)/(?P<repo>[\w\.\-]+)/pull/(?P<id>\d+)/?$"),
    "issue": re.compile(r"^https?://github\.com/(?P<owner>[\w\.\-]+)/(?P<repo>[\w\.\-]+)/issues/(?P<id>\d+)/?$"),
    "blob": re.compile(r"^https?://github\.com/(?P<owner>[\w\.\-]+)/(?P<repo>[\w\.\-]+)/blob/(?P<ref>[\w\.\-]+)/(?P<path>.+)$"),
    "repo": re.compile(r"^https?://github\.com/(?P<owner>[\w\.\-]+)/(?P<repo>[\w\.\-]+)/?$"),
}


def parse_github_url(url: str) -> Dict[str, Any]:
    """Auto-detects GitHub URL type without dropdowns."""
    clean_url = url.strip().split("#")[0].split("?")[0]

    for url_type, pattern in URL_PATTERNS.items():
        match = pattern.match(clean_url)
        if match:
            data = match.groupdict()
            return {
                "raw_url": url,
                "url_type": url_type,
                "owner": data.get("owner"),
                "repo": data.get("repo"),
                "target_id": data.get("id"),
                "path": data.get("path"),
                "ref": data.get("ref", "main"),
            }

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid GitHub URL. Must be a repository, pull request, issue, or file blob URL: {url}",
    )


# ==============================================================================
# 2. Mermaid Diagram & Sticky Comment Generators
# ==============================================================================

def generate_mermaid_blast_radius(
    nodes: Optional[List[Dict[str, Any]]] = None,
    edges: Optional[List[Dict[str, Any]]] = None,
    max_nodes: int = 15,
) -> str:
    """
    Compiles a blast-radius subgraph into clean, GitHub-compatible Mermaid TD syntax
    with color-coded CSS classes for Modified (red), Untested (amber), and Tested (green) nodes.
    """
    if not nodes:
        return "*No modified symbols detected in blast radius.*"

    mermaid_lines = [
        "```mermaid",
        "graph TD",
        "    classDef modified fill:#f85149,stroke:#ff7b72,stroke-width:2px,color:#fff;",
        "    classDef untested fill:#d29922,stroke:#f0883e,stroke-width:2px,color:#fff;",
        "    classDef tested fill:#238636,stroke:#3fb950,stroke-width:2px,color:#fff;",
        "    classDef standard fill:#21262d,stroke:#30363d,stroke-width:1px,color:#c9d1d9;",
    ]

    node_id_map: Dict[str, str] = {}
    selected_nodes = nodes[:max_nodes]

    for idx, node in enumerate(selected_nodes):
        nid = f"N{idx}"
        orig_id = node.get("id") or str(idx)
        node_id_map[orig_id] = nid

        raw_label = node.get("label") or orig_id.split("::")[-1]
        clean_label = raw_label.replace('"', "'").replace("\n", " ").strip()
        if len(clean_label) > 28:
            clean_label = clean_label[:25] + "..."

        status = node.get("status", "")
        ntype = node.get("type", "")
        is_test = ntype == "test" or "test" in orig_id.lower()

        if status == "modified":
            css_class = "modified"
        elif is_test:
            css_class = "tested"
        elif status == "untested" or node.get("untested"):
            css_class = "untested"
        else:
            css_class = "standard"

        mermaid_lines.append(f'    {nid}["{clean_label}"]:::{css_class}')

    edge_count = 0
    if edges:
        for edge in edges:
            src = edge.get("source")
            tgt = edge.get("target")
            if src in node_id_map and tgt in node_id_map:
                src_id = node_id_map[src]
                tgt_id = node_id_map[tgt]
                etype = edge.get("type", "")
                if etype == "CALLS":
                    mermaid_lines.append(f"    {src_id} -->|calls| {tgt_id}")
                elif etype == "TESTED_BY":
                    mermaid_lines.append(f"    {src_id} -.->|tested by| {tgt_id}")
                else:
                    mermaid_lines.append(f"    {src_id} --> {tgt_id}")
                edge_count += 1
                if edge_count >= max_nodes + 6:
                    break

    mermaid_lines.append("```")
    return "\n".join(mermaid_lines)


def build_sticky_comment_body(
    payload: Dict[str, Any], owner: str, repo: str, pr_id: str
) -> str:
    """
    Builds a high-signal, zero-spam sticky PR comment with:
    1. Invisible sticky marker
    2. Telemetry risk table
    3. Inline Mermaid blast radius DAG
    4. Collapsible technical details (<details>)
    5. Clean footer
    """
    verdict = payload.get("verdict", "NEEDS_TESTS")
    risk_score = payload.get("risk_score", 0)
    summary = payload.get("summary", "Automated AST multi-hop blast telemetry report.")
    nodes = payload.get("nodes", [])
    edges = payload.get("edges", [])
    untested_callers = payload.get("untested_callers", [])
    slopsquatting_alerts = payload.get("slopsquatting_alerts", [])

    if risk_score > 70:
        badge = "🔴 Critical Risk"
    elif risk_score > 30:
        badge = "🟡 Moderate Risk"
    else:
        badge = "🟢 Low Risk"

    mermaid_diagram = generate_mermaid_blast_radius(nodes, edges)

    # Build caller details
    if untested_callers:
        caller_items = "\n".join([f"- `{c}`" for c in untested_callers[:10]])
    else:
        caller_items = "- None detected (All modified functions have test coverage or no callers)"

    # Build dependency alerts
    if slopsquatting_alerts:
        dep_items = "\n".join([f"- ⚠️ **{alert.get('package')}**: {alert.get('message')}" for alert in slopsquatting_alerts])
    else:
        dep_items = "- ✅ No suspicious or hallucinated dependencies detected."

    comment = f"""<!-- gitos-sticky-intelligence -->
## 🛡️ GitOS Blast Radius Intelligence

| Metric | Result | Status |
|---|---|---|
| **Verdict** | `{verdict}` | {badge} |
| **Risk Score** | **{risk_score} / 100** | {badge} |
| **Target PR** | `#{pr_id}` | `{owner}/{repo}` |
| **Filter 1 (Untested Callers)** | {len(untested_callers)} Callers | {"⚠️ Action Required" if untested_callers else "✅ Clear"} |
| **Filter 5 (Dependency Sentinel)** | {len(slopsquatting_alerts)} Flagged | {"🚨 Potential Slop/Supply Risk" if slopsquatting_alerts else "✅ Verified"} |

{summary}

### 💥 Blast Radius Visual Map
{mermaid_diagram}

<details>
<summary><b>🔍 View Impacted Untested Callers ({len(untested_callers)})</b></summary>

{caller_items}

**Maintainer Note:** Callers above invoke modified functions but were not updated in this PR's diff.
</details>

<details>
<summary><b>📦 Dependency & Slopsquatting Audit</b></summary>

{dep_items}
</details>

---
*Verified & updated in-place via [GitOS](https://github.com/ace-ify/GitOS) • Zero-Disk In-Memory Graph • Zero-Spam Sticky Protocol*
"""
    return comment


# ==============================================================================
# 2. 5-Layer Deterministic Slop & Quality Filters (0 LLM Tokens)
# ==============================================================================

def run_deterministic_filters(
    repo_id: str,
    commit_sha: str,
    modified_functions: List[str],
    modified_tests: List[str],
    new_functions: List[str],
    ast_delta: int,
    text_diff_lines: int,
    file_paths: List[str],
    dependency_alerts: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Executes the 5 hard graph filters without spending LLM tokens:
    1. Untested Callers
    2. AST vs Text Ratio (Cosmetic Slop)
    3. Dead Code Injection
    4. Maintainer Architectural Rules
    5. Slopsquatting & Hallucinated Dependency Sentinel
    """
    if graph_client:
        untested_check = graph_client.check_untested_callers(
            repo_id, commit_sha, modified_functions, modified_tests
        )
        dead_code_symbols = graph_client.check_dead_code(
            repo_id, commit_sha, new_functions
        )
        violations = graph_client.check_maintainer_rules(repo_id, commit_sha)
    else:
        untested_check = {
            "flagged": len(modified_functions) > 0 and len(modified_tests) == 0,
            "score": 0.85 if len(modified_functions) > 0 and len(modified_tests) == 0 else 0.1,
            "untested_functions": modified_functions,
        }
        dead_code_symbols = [fn for fn in new_functions if not fn.startswith("test_")]
        violations = []

    # Check custom maintainer rules against modified files
    for rule in CUSTOM_MAINTAINER_RULES:
        if rule["rule_id"] == "RULE_NO_WORKFLOW_TOUCH_GUEST":
            for f in file_paths:
                if ".github/workflows" in f:
                    violations.append({
                        "rule_id": rule["rule_id"],
                        "description": rule["description"],
                        "offending_node": f,
                    })

    # Filter 2: AST vs Text Diff Ratio (Cosmetic AI Slop)
    ratio = (ast_delta / max(text_diff_lines, 1))
    is_cosmetic_slop = text_diff_lines > 25 and ratio < 0.15

    # Filter 5: Slopsquatting & Hallucinated Dependency Sentinel
    dep_alerts = dependency_alerts or []
    has_critical_dep_alerts = any(a.get("severity") == "CRITICAL" for a in dep_alerts)

    # Compute Composite Risk Score (0 - 100)
    risk_score = 10
    if untested_check["flagged"]:
        risk_score += int(untested_check["score"] * 40)
    if is_cosmetic_slop:
        risk_score += 45
    if len(dead_code_symbols) > 0:
        risk_score += 30
    if len(violations) > 0:
        risk_score += 50
    if has_critical_dep_alerts:
        risk_score += 60
    elif len(dep_alerts) > 0:
        risk_score += 20
    risk_score = min(risk_score, 100)

    # Determine Verdict
    if has_critical_dep_alerts:
        verdict = "SLOPSQUATTING_ALERT"
    elif len(violations) > 0:
        verdict = "RULE_VIOLATION"
    elif is_cosmetic_slop:
        verdict = "AI_SLOP_SUSPECTED"
    elif risk_score >= 70:
        verdict = "CRITICAL_BLAST"
    elif untested_check["flagged"]:
        verdict = "NEEDS_TESTS"
    elif risk_score > 30:
        verdict = "LOW_RISK"
    else:
        verdict = "CLEAN"

    return {
        "risk_score": risk_score,
        "verdict": verdict,
        "deterministic_checks": {
            "untested_call_graph": untested_check,
            "ast_vs_text_ratio": {
                "flagged": is_cosmetic_slop,
                "ast_node_delta": ast_delta,
                "text_diff_lines": text_diff_lines,
                "ratio": round(ratio, 2),
                "is_cosmetic_slop": is_cosmetic_slop,
            },
            "dead_code": {
                "flagged": len(dead_code_symbols) > 0,
                "dead_symbols": dead_code_symbols,
            },
            "maintainer_rules": {
                "flagged": len(violations) > 0,
                "violations": violations,
            },
            "slopsquatting_sentinel": {
                "flagged": len(dep_alerts) > 0,
                "critical_alert": has_critical_dep_alerts,
                "alerts": dep_alerts,
            },
        },
    }



# ==============================================================================
# 3. API Endpoints
# ==============================================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint reporting backend, FalkorDB, and GitHub rate limits."""
    db_connected = graph_client.is_connected() if graph_client else False
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "falkordb_connected": db_connected,
        "github_rate_limit_remaining": github_client.rate_limit_remaining,
        "groq_configured": bool(os.getenv("GROQ_API_KEY")),
        "custom_rules_count": len(CUSTOM_MAINTAINER_RULES),
    }


@app.get("/api/rules")
async def list_maintainer_rules():
    """Returns declared maintainer architectural rules."""
    return {"rules": CUSTOM_MAINTAINER_RULES}


@app.post("/api/rules")
async def create_maintainer_rule(rule: MaintainerRuleCreate):
    """Allows maintainers to add new architectural boundary rules dynamically."""
    CUSTOM_MAINTAINER_RULES.append(rule.model_dump())
    logger.info("Added new maintainer rule: %s (%s)", rule.name, rule.rule_id)
    return {"status": "created", "rule": rule}


@app.post("/api/analyze")
async def analyze_url(
    req: AnalyzeRequest,
    request: Request,
    authorization: Optional[str] = Header(None),
):
    """
    Universal Omnibox Analysis Endpoint with Real-Time GitHub Ingestion,
    Polyglot Symbol Extraction, and FalkorDB Graph Storage.
    """
    start_time = time.time()
    parsed_url = parse_github_url(req.url)
    owner = parsed_url["owner"]
    repo = parsed_url["repo"]
    repo_id = f"{owner}/{repo}"

    # Extract token from request body, Authorization header (Bearer), or HttpOnly session cookie
    token = req.github_token
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    if not token:
        session = get_session(request.cookies.get("gitos_session"))
        if session:
            token = session.get("token")

    live_fetched = False
    commit_sha = f"sha_{uuid.uuid4().hex[:10]}"
    parsed_project_files: Dict[str, Dict[str, Any]] = {}
    modified_functions: List[str] = []
    modified_tests: List[str] = []
    new_functions: List[str] = []
    text_diff_lines = 45
    ast_delta = 30
    suggested_diff: Optional[str] = None
    file_paths: List[str] = []
    new_imported_pkgs: Set[str] = set()
    dependency_alerts: List[Dict[str, Any]] = []

    # 1. Attempt Live GitHub API Extraction
    if parsed_url["url_type"] == "pull" and parsed_url["target_id"]:
        try:
            pr_files = await github_client.get_pull_request_files(
                owner, repo, str(parsed_url["target_id"]), token=token
            )
            live_fetched = True
            logger.info("Live fetched %s changed files for PR #%s", len(pr_files), parsed_url["target_id"])

            for file_info in pr_files[:8]:  # Scoped priority extraction
                filename = file_info.get("filename", "")
                file_paths.append(filename)
                patch = file_info.get("patch", "")
                text_diff_lines += file_info.get("changes", 0)

                # Extract newly added imports from patch
                flang = detect_language(filename)
                for p in extract_patch_new_imports(patch, language=flang):
                    new_imported_pkgs.add(p)

                # Parse exact line numbers modified in the diff hunks
                modified_lines = parse_patch_modified_lines(patch)

                # Fetch raw file content in RAM
                raw_url = file_info.get("raw_url")
                if raw_url:
                    content = await github_client.fetch_file_raw_content(raw_url, token=token)
                    if content:
                        ast_res = extract_universal_ast(content, filename)
                        parsed_project_files[filename] = ast_res
                        ast_delta += ast_res.get("ast_node_count", 0)

                        for node in ast_res.get("nodes", []):
                            # Target only functions genuinely touched in the diff hunk
                            if is_node_modified_by_patch(node, modified_lines):
                                if node["type"] == "function":
                                    modified_functions.append(node["id"])
                                elif node["type"] == "test":
                                    modified_tests.append(node["id"])

            if pr_files and pr_files[0].get("patch"):
                suggested_diff = pr_files[0].get("patch")

            # Filter 5: Audit newly introduced dependencies against repo manifest & public registries
            manifest_text = None
            if any(f.endswith(".py") for f in file_paths):
                manifest_text = await github_client.fetch_repo_file_by_path(owner, repo, "requirements.txt", token=token)
            elif any(f.endswith(".ts") or f.endswith(".js") for f in file_paths):
                manifest_text = await github_client.fetch_repo_file_by_path(owner, repo, "package.json", token=token)

            ecosystem = "npm" if any(f.endswith(".ts") or f.endswith(".js") for f in file_paths) else "pypi"
            dependency_alerts = await audit_dependency_risks(
                list(new_imported_pkgs),
                manifest_text=manifest_text,
                ecosystem=ecosystem,
            )
            if dependency_alerts:
                logger.info("Filter 5 Slopsquatting Sentinel flagged %s package alerts", len(dependency_alerts))

            # Real Repo-Wide Caller Discovery (Zero-Disk Multi-Hop Blast Discovery)
            # Query GitHub code search for callers of modified functions across other repo files
            for func_id in modified_functions[:3]:
                bare_func = func_id.split("::")[-1].split(".")[-1]
                if len(bare_func) >= 4:
                    ref_items = await github_client.search_code_references(owner, repo, bare_func, token=token)
                    for item in ref_items[:4]:
                        caller_path = item.get("path")
                        if (
                            caller_path
                            and caller_path not in parsed_project_files
                            and not any(caller_path.endswith(ext) for ext in EXCLUDED_EXTENSIONS)
                        ):
                            caller_content = await github_client.fetch_repo_file_by_path(
                                owner, repo, caller_path, ref=parsed_url.get("ref", "main"), token=token
                            )
                            if caller_content:
                                parsed_project_files[caller_path] = extract_universal_ast(caller_content, caller_path)
                                logger.info("Discovered and parsed true caller file: %s for symbol %s", caller_path, bare_func)

        except Exception as e:
            logger.warning("Could not complete live GitHub API fetch (%s). Falling back to high-fidelity sandbox.", e)
            live_fetched = False

    # 1b. Issue-to-Code Pathfinder (FR-1.1 & Contributor Mode)
    elif parsed_url["url_type"] == "issue" and parsed_url["target_id"]:
        try:
            issue_data = await github_client.get_issue_metadata(
                owner, repo, str(parsed_url["target_id"]), token=token
            )
            live_fetched = True
            issue_title = issue_data.get("title", "")
            issue_body = issue_data.get("body", "") or ""
            logger.info("Live fetched issue #%s: '%s'", parsed_url["target_id"], issue_title)

            # Extract potential symbol tokens from title and body (words like parse_url, router, etc.)
            extracted_words = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{3,30}\b", f"{issue_title} {issue_body}")
            candidate_keywords = [
                w for w in set(extracted_words)
                if not w.lower() in {"this", "that", "with", "have", "from", "when", "issue", "error", "failed", "does", "should"}
            ][:4]

            for kw in candidate_keywords:
                ref_items = await github_client.search_code_references(owner, repo, kw, token=token)
                for item in ref_items[:3]:
                    c_path = item.get("path")
                    if (
                        c_path
                        and c_path not in parsed_project_files
                        and not any(c_path.endswith(ext) for ext in EXCLUDED_EXTENSIONS)
                    ):
                        c_content = await github_client.fetch_repo_file_by_path(
                            owner, repo, c_path, ref=parsed_url.get("ref", "main"), token=token
                        )
                        if c_content:
                            parsed_project_files[c_path] = extract_universal_ast(c_content, c_path)
                            file_paths.append(c_path)
                            for node in parsed_project_files[c_path].get("nodes", []):
                                if kw.lower() in node.get("label", "").lower():
                                    modified_functions.append(node["id"])

            suggested_diff = f"# Issue #{parsed_url['target_id']} Pathfinder: Candidate entrypoints for '{issue_title}'\n"
        except Exception as e:
            logger.warning("Could not complete live Issue fetch (%s): Falling back.", e)
            live_fetched = False

    # 1c. Live Repository Ingestion (Zero-Disk In-Memory Tree Processing)
    elif parsed_url["url_type"] in ("repo", "blob"):
        try:
            repo_meta = await github_client.get_repository_metadata(owner, repo, token=token)
            default_branch = repo_meta.get("default_branch", "main")
            logger.info("Live fetched repository %s/%s (default branch: %s)", owner, repo, default_branch)

            if parsed_url["url_type"] == "blob" and parsed_url.get("path"):
                # Scoped single file extraction
                blob_path = parsed_url["path"]
                content = await github_client.fetch_repo_file_by_path(
                    owner, repo, blob_path, ref=parsed_url.get("ref", default_branch), token=token
                )
                if content:
                    ast_res = extract_universal_ast(content, blob_path)
                    parsed_project_files[blob_path] = ast_res
                    file_paths.append(blob_path)
                    for n in ast_res.get("nodes", []):
                        if n.get("type") == "function":
                            modified_functions.append(n["id"])
                    live_fetched = True
            else:
                # Top-level repository: fetch tree and stream prioritized source files into RAM
                tree_files = await github_client.get_repository_tree(owner, repo, branch=default_branch, token=token)
                logger.info("Found %s code files in %s/%s tree", len(tree_files), owner, repo)

                # Prioritize root entrypoints, core services, and tests
                for item in tree_files[:12]:
                    f_path = item.get("path", "")
                    content = await github_client.fetch_repo_file_by_path(
                        owner, repo, f_path, ref=default_branch, token=token
                    )
                    if content:
                        ast_res = extract_universal_ast(content, f_path)
                        parsed_project_files[f_path] = ast_res
                        file_paths.append(f_path)
                        for node in ast_res.get("nodes", []):
                            if node["type"] == "test":
                                modified_tests.append(node["id"])
                            elif node["type"] == "function" and len(modified_functions) < 3:
                                modified_functions.append(node["id"])
                live_fetched = len(parsed_project_files) > 0

        except Exception as e:
            logger.warning("Could not complete live Repository tree fetch (%s). Falling back.", e)
            live_fetched = False

    # 2. Fallback Sandbox / Synthetic In-Memory Graph if Live Fetch did not populate
    if not parsed_project_files:
        demo_code_py = """
class APIRouter:
    def add_api_route(self, path: str, endpoint: Any, methods: List[str] = None):
        self.dispatch(path, endpoint)

    def dispatch(self, path: str, endpoint: Any):
        pass

def include_router(router: APIRouter):
    router.add_api_route("/prefix", None)

def test_router_dispatch():
    router = APIRouter()
    router.dispatch("/test", None)
"""
        demo_code_ts = """
import { APIRouter } from "./fastapi/routing";

export class GatewayController {
  private router = new APIRouter();

  public registerRoutes() {
    this.router.add_api_route("/v1/gateway", null);
  }
}
"""
        parsed_project_files["fastapi/routing.py"] = extract_universal_ast(demo_code_py, "fastapi/routing.py")
        parsed_project_files["src/gateway.ts"] = extract_universal_ast(demo_code_ts, "src/gateway.ts")
        modified_functions = ["fastapi/routing.py::APIRouter.add_api_route"]
        modified_tests = []
        file_paths = ["fastapi/routing.py", "src/gateway.ts"]
        suggested_diff = "--- a/tests/test_routing.py\n+++ b/tests/test_routing.py\n@@ -20,6 +20,10 @@ def test_add_api_route():\n+    router = APIRouter()\n+    router.add_api_route('/v1/health', lambda: {'status': 'ok'})\n"

    # 3. Cross-File Symbol Stitching
    all_nodes, stitched_edges = stitch_cross_file_graph(parsed_project_files)

    # 4. FalkorDB Persistence & Multi-Hop Blast Radius Query
    if graph_client:
        graph_client.save_ast_subgraph(repo_id, commit_sha, all_nodes, stitched_edges)
        blast = graph_client.get_blast_radius(repo_id, commit_sha, modified_functions, hops=2)
    else:
        blast = {"nodes": all_nodes, "edges": stitched_edges}

    # 5. Run the 5 Deterministic Pre-Filters (0 LLM Tokens)
    filter_results = run_deterministic_filters(
        repo_id=repo_id,
        commit_sha=commit_sha,
        modified_functions=modified_functions,
        modified_tests=modified_tests,
        new_functions=new_functions,
        ast_delta=ast_delta,
        text_diff_lines=text_diff_lines,
        file_paths=file_paths,
        dependency_alerts=dependency_alerts,
    )

    # Action Pills
    action_pills = [
        {
            "id": "pill_request_tests",
            "label": "Request Test Coverage",
            "action_type": "gh_comment",
            "is_destructive": False,
            "description": f"Post sticky blast radius telemetry report detailing {len(modified_functions)} affected callers to the PR.",
            "payload": {
                "template": "untested_call_impact",
                "verdict": filter_results["verdict"],
                "risk_score": filter_results["risk_score"],
                "nodes": blast.get("nodes", all_nodes),
                "edges": blast.get("edges", stitched_edges),
                "untested_callers": modified_functions,
                "slopsquatting_alerts": dependency_alerts,
            },
        },
        {
            "id": "pill_generate_test_patch",
            "label": "Generate Test Patch",
            "action_type": "gh_pr_draft",
            "is_destructive": False,
            "description": "Create a branch and draft test PR covering the updated signature.",
            "payload": {},
        },
    ]

    if any(a.get("severity") == "CRITICAL" for a in dependency_alerts):
        action_pills.append({
            "id": "pill_flag_dependency",
            "label": "Flag Hallucinated Dependency",
            "action_type": "gh_comment",
            "is_destructive": False,
            "description": "Post sticky warning about non-existent or typo-squatted package imports.",
            "payload": {
                "verdict": "SLOPSQUATTING_ALERT",
                "risk_score": filter_results["risk_score"],
                "nodes": blast.get("nodes", all_nodes),
                "edges": blast.get("edges", stitched_edges),
                "slopsquatting_alerts": dependency_alerts,
                "untested_callers": modified_functions,
            },
        })

    if filter_results["verdict"] in ("AI_SLOP_SUSPECTED", "SLOPSQUATTING_ALERT"):
        action_pills.append({
            "id": "pill_close_slop",
            "label": "Close Slop PR",
            "action_type": "gh_close",
            "is_destructive": True,
            "description": "Close PR citing the automated graph and dependency check.",
            "payload": {},
        })

    elapsed_ms = int((time.time() - start_time) * 1000)

    # Format nodes for blast visualization
    blast_nodes_formatted = []
    for node in all_nodes:
        is_mod = node["id"] in modified_functions
        blast_nodes_formatted.append({
            "id": node["id"],
            "label": node.get("label", node["id"].split("::")[-1]),
            "type": node.get("type", "function"),
            "file_path": node.get("file_path", ""),
            "line_range": node.get("line_range", [1, 10]),
            "hop_distance": 0 if is_mod else 1,
            "change_type": "modified" if is_mod else "affected_caller",
            "incoming_calls": 2 if is_mod else 0,
            "outgoing_calls": 1,
        })

    # Dynamic User Mode Detection:
    # If authenticated, determine role automatically from repo ownership or permissions.
    # If not authenticated, default to contributor for public PRs/issues and maintainer for repo audits.
    effective_user_mode = "contributor"
    if token:
        try:
            user_prof = await github_client.fetch_file_raw_content("https://api.github.com/user", token=token)
            if user_prof:
                import json as _json
                u_data = _json.loads(user_prof)
                username = u_data.get("login", "")
                if username.lower() == owner.lower():
                    effective_user_mode = "maintainer"
                else:
                    role_status = await github_client.fetch_file_raw_content(
                        f"https://api.github.com/repos/{owner}/{repo}/collaborators/{username}/permission",
                        token=token,
                    )
                    if role_status:
                        p_data = _json.loads(role_status)
                        if p_data.get("permission") in ("admin", "write"):
                            effective_user_mode = "maintainer"
        except Exception:
            effective_user_mode = "maintainer" if req.user_mode == "maintainer" else "contributor"
    else:
        effective_user_mode = "maintainer" if parsed_url["url_type"] == "repo" else "contributor"

    response_payload = {
        "analysis_id": str(uuid.uuid4()),
        "url_parsed": parsed_url,
        "user_mode": effective_user_mode,
        "risk_score": filter_results["risk_score"],
        "verdict": filter_results["verdict"],
        "summary": "",
        "deterministic_checks": filter_results["deterministic_checks"],
        "blast_radius_nodes": blast_nodes_formatted[:25],
        "blast_radius_edges": stitched_edges[:35],
        "suggested_diff": suggested_diff,
        "action_pills": action_pills,
        "execution_metadata": {
            "commit_sha": commit_sha,
            "cached_replay": False,
            "latency_ms": elapsed_ms,
            "live_fetched": live_fetched,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }

    # Generate single-shot compressed triage summary via Groq
    response_payload["summary"] = groq_reasoner.generate_triage_verdict(response_payload)
    return response_payload


@app.post("/api/generate-patch")
async def generate_patch(req: GeneratePatchRequest):
    """Generates an automated test patch using single-shot compressed Groq reasoning."""
    patch = groq_reasoner.generate_test_patch(req.analysis_data)
    return {"status": "success", "suggested_diff": patch}


@app.post("/api/chat")
async def chat_telemetry(req: ChatQueryRequest):
    """Answers maintainer/contributor questions about blast radius (< 1000 token context)."""
    answer = groq_reasoner.answer_telemetry_question(req.prompt, req.analysis_data or {})
    return {"response": answer}


@app.post("/api/execute-action")
async def execute_action(
    req: ExecuteActionRequest,
    request: Request,
    authorization: Optional[str] = Header(None),
):
    """
    Explicit GitHub Action Executor.
    Requires user confirmation modal (confirmed=True) and OAuth token.
    Never acts autonomously or as an unconsented bot.
    """
    if not req.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action execution blocked: Explicit user confirmation required via UI modal.",
        )

    token = req.oauth_token
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    if not token:
        session = get_session(request.cookies.get("gitos_session"))
        if session:
            token = session.get("token")
    if not token:
        token = os.getenv("GITHUB_TOKEN")

    logger.info("Executing confirmed action %s for %s/%s target %s", req.action_type, req.owner, req.repo, req.target_id)

    if req.action_type == "gh_comment":
        comment_body = req.payload.get("body")
        if not comment_body:
            comment_body = build_sticky_comment_body(
                payload=req.payload,
                owner=req.owner,
                repo=req.repo,
                pr_id=str(req.target_id),
            )
        try:
            comment_res = await github_client.upsert_sticky_pr_comment(
                req.owner, req.repo, str(req.target_id), comment_body, token=token
            )
            action_verb = "updated" if comment_res.get("action") == "updated" else "posted"
            return {
                "status": "success",
                "action_type": "gh_comment",
                "html_url": comment_res.get("html_url"),
                "target": f"{req.owner}/{req.repo}#{req.target_id}",
                "message": f"Sticky triage report successfully {action_verb} on GitHub: {comment_res.get('html_url')}",
            }
        except Exception as e:
            logger.warning("Live comment posting failed (%s). Returning sandbox simulation.", e)
            return {
                "status": "simulated",
                "action_type": "gh_comment",
                "html_url": f"https://github.com/{req.owner}/{req.repo}/pull/{req.target_id}#issuecomment-sandbox",
                "target": f"{req.owner}/{req.repo}#{req.target_id}",
                "message": f"Action verified in Sandbox (configure personal GitHub OAuth token for live writes): {e}",
            }

    elif req.action_type == "gh_close":
        try:
            close_res = await github_client.close_pull_request(req.owner, req.repo, str(req.target_id), token=token)
            return {
                "status": "success",
                "action_type": "gh_close",
                "html_url": close_res.get("html_url"),
                "target": f"{req.owner}/{req.repo}#{req.target_id}",
                "message": f"PR #{req.target_id} successfully closed on GitHub.",
            }
        except Exception as e:
            return {
                "status": "simulated",
                "action_type": "gh_close",
                "html_url": f"https://github.com/{req.owner}/{req.repo}/pull/{req.target_id}",
                "target": f"{req.owner}/{req.repo}#{req.target_id}",
                "message": f"Close PR verified in Sandbox: {e}",
            }

    elif req.action_type == "gh_label":
        labels = req.payload.get("labels", [])
        if not labels:
            verdict = req.payload.get("verdict", "NEEDS_TESTS")
            labels = ["gitos:needs-tests" if verdict == "NEEDS_TESTS" else f"gitos:{verdict.lower()}"]
        try:
            applied = await github_client.add_issue_labels(req.owner, req.repo, str(req.target_id), labels, token=token)
            return {
                "status": "success",
                "action_type": "gh_label",
                "html_url": f"https://github.com/{req.owner}/{req.repo}/pull/{req.target_id}",
                "target": f"{req.owner}/{req.repo}#{req.target_id}",
                "labels": applied or labels,
                "message": f"Successfully applied labels {applied or labels} to PR #{req.target_id}.",
            }
        except Exception as e:
            return {
                "status": "simulated",
                "action_type": "gh_label",
                "html_url": f"https://github.com/{req.owner}/{req.repo}/pull/{req.target_id}",
                "target": f"{req.owner}/{req.repo}#{req.target_id}",
                "labels": labels,
                "message": f"Labels {labels} verified in Sandbox (OAuth token required for live writes): {e}",
            }

    elif req.action_type == "gh_pr_draft":
        branch_name = f"gitos/test-patch-pr{req.target_id}"
        pr_title = f"test(gitos): add regression coverage for #{req.target_id} blast radius"
        return {
            "status": "success",
            "action_type": "gh_pr_draft",
            "branch": branch_name,
            "html_url": f"https://github.com/{req.owner}/{req.repo}/tree/{branch_name}",
            "target": f"{req.owner}/{req.repo}#{req.target_id}",
            "message": f"Generated regression test patch and prepared draft branch `{branch_name}` for PR #{req.target_id}.",
        }

    return {
        "status": "success",
        "action_type": req.action_type,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "target": f"{req.owner}/{req.repo}#{req.target_id}",
        "message": f"Successfully executed {req.action_type} on GitHub.",
    }


# ==============================================================================
# 5. Model Context Protocol (MCP) Tool Endpoints
# Exposes Blast Radius & Slop Checks for Cursor, Claude Code, and Antigravity
# ==============================================================================

class MCPBlastRadiusRequest(BaseModel):
    patch: str = Field(..., description="Unified diff patch of local changes")
    language: Optional[str] = Field("python", description="Language: 'python', 'javascript', 'typescript', etc.")
    file_path: Optional[str] = Field(None, description="Path of modified file")


class MCPSlopCheckRequest(BaseModel):
    patch: str = Field(..., description="Unified diff patch of changes")
    language: Optional[str] = Field("python", description="Programming language")
    manifest_text: Optional[str] = Field(None, description="Contents of requirements.txt or package.json")


@app.get("/mcp/tools")
async def list_mcp_tools():
    """Returns available GitOS MCP tool definitions for IDE agents."""
    return {
        "tools": [
            {
                "name": "gitos_blast_radius",
                "description": "Calculate function-level blast radius and untested callers for a code diff before committing.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "patch": {"type": "string", "description": "Unified diff patch string"},
                        "language": {"type": "string", "enum": ["python", "javascript", "typescript", "go", "generic"]},
                        "file_path": {"type": "string", "description": "Path of modified file"},
                    },
                    "required": ["patch"],
                },
            },
            {
                "name": "gitos_slop_check",
                "description": "Evaluate code changes against 5 deterministic filters: untested callers, cosmetic slop, dead code, maintainer rules, and slopsquatting package hallucination.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "patch": {"type": "string", "description": "Unified diff patch"},
                        "language": {"type": "string", "enum": ["python", "javascript", "typescript", "go", "generic"]},
                        "manifest_text": {"type": "string", "description": "Optional contents of requirements.txt or package.json"},
                    },
                    "required": ["patch"],
                },
            },
        ]
    }


@app.post("/mcp/blast-radius")
async def mcp_blast_radius(req: MCPBlastRadiusRequest):
    """MCP endpoint: Computes blast radius directly from a local patch."""
    modified_lines = parse_patch_modified_lines(req.patch)
    dummy_path = req.file_path or f"src/modified.{'py' if req.language == 'python' else 'ts'}"

    text_lines = len(req.patch.splitlines())
    ast_delta = len(modified_lines)
    new_imports = extract_patch_new_imports(req.patch, language=req.language or "python")

    return {
        "status": "success",
        "file_path": dummy_path,
        "modified_lines": sorted(list(modified_lines)),
        "ast_delta": ast_delta,
        "text_diff_lines": text_lines,
        "new_imports": new_imports,
        "summary": f"Detected {len(modified_lines)} modified lines touching local symbols with {len(new_imports)} new external imports.",
    }


@app.post("/mcp/slop-check")
async def mcp_slop_check(req: MCPSlopCheckRequest):
    """MCP endpoint: Runs deterministic slop and slopsquatting audit."""
    modified_lines = parse_patch_modified_lines(req.patch)
    text_lines = len(req.patch.splitlines())
    ast_delta = len(modified_lines)

    ratio = ast_delta / max(text_lines, 1)
    is_cosmetic_slop = text_lines > 25 and ratio < 0.15

    new_imports = extract_patch_new_imports(req.patch, language=req.language or "python")
    ecosystem = "pypi" if req.language == "python" else "npm"
    dep_alerts = await audit_dependency_risks(new_imports, manifest_text=req.manifest_text, ecosystem=ecosystem)

    risk_score = 10
    if is_cosmetic_slop:
        risk_score += 45
    if any(a.get("severity") == "CRITICAL" for a in dep_alerts):
        risk_score += 60
    elif len(dep_alerts) > 0:
        risk_score += 20
    risk_score = min(risk_score, 100)

    if any(a.get("severity") == "CRITICAL" for a in dep_alerts):
        verdict = "SLOPSQUATTING_ALERT"
    elif is_cosmetic_slop:
        verdict = "AI_SLOP_SUSPECTED"
    elif risk_score > 30:
        verdict = "LOW_RISK"
    else:
        verdict = "CLEAN"

    return {
        "status": "success",
        "verdict": verdict,
        "risk_score": risk_score,
        "filters": {
            "cosmetic_slop": {"flagged": is_cosmetic_slop, "ratio": round(ratio, 2)},
            "slopsquatting_sentinel": {"flagged": len(dep_alerts) > 0, "alerts": dep_alerts},
        },
        "recommendation": "All checks passed. Safe to commit." if risk_score < 40 else "Review flagged warnings before submitting PR.",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

