# 🏛️ GitOS: System Architecture & Technical Specification

**Document Version:** 1.0.0  
**Target:** Production Engine Blueprint  
**Subsystems:** Next.js Canvas UI, FastAPI Engine, FalkorDB Graph Store, Groq LLM  

---

## 1. System Topology & Architectural Overview

GitOS operates on a hybrid architecture designed for **sub-second deterministic evaluation**, **zero server-side disk consumption**, and **cost-optimal AI reasoning**:

```
+-----------------------------------------------------------------------------------+
|                                CLIENT BROWSER                                     |
|  +-----------------------------------------------------------------------------+  |
|  | Next.js App Router (TypeScript + React 19)                                 |  |
|  | - Universal Omnibox Parser (Instant URL validation)                         |  |
|  | - 3D Force-Graph Canvas (WebGL / Three.js node rendering)                   |  |
|  | - Side-Panel Telemetry (Risk Gauge, Verdict, 4 Filter Slop Breakdown)       |  |
|  | - Contextual Action Dock + Explicit OAuth Confirmation Modal                |  |
|  +-----------------------------------------------------------------------------+  |
+---------------------------------------┬────────────────────────────────-----------+
                                        │ HTTPS / WSS / JSON
                                        ▼
+-----------------------------------------------------------------------------------+
|                               FASTAPI ENGINE                                      |
|  +-------------------+  +-----------------------+  +---------------------------+  |
|  | Omnibox Router    |  | In-Memory Tree Ingest |  | Python AST Symbol Parser  |  |
|  | Regex URL parsing |  | GitHub API /trees RAM |  | Funcs, Classes, Imports   |  |
|  +-------------------+  +-----------------------+  +---------------------------+  |
|                                       │                                           |
|       +-------------------------------+-------------------------------+           |
|       ▼                                                               ▼           |
|  +--------------------------+                               +------------------+  |
|  | FalkorDB Graph Client    |                               | Context          |  |
|  | Cypher Queries & Filters |                               | Compressor       |  |
|  | (0-Token Deterministic)  |                               | < 1000 Tokens    |  |
|  +-------------┬------------+                               +--------┬---------+  |
+----------------┼-----------------------------------------------------┼------------+
                 ▼                                                     ▼
+--------------------------------+                  +-------------------------------+
|       FALKORDB ENGINE          |                  |        GROQ CLOUD API         |
|  - Graph: commit_sha keyed     |                  |  - Model: Llama-3.3-70B       |
|  - Nodes: Files, Funcs, Rules  |                  |  - Sub-second micro-patching  |
|  - Edges: CALLS, IMPORTS, TEST |                  |  - Single-shot triage verdict |
+--------------------------------+                  +-------------------------------+
```

---

## 2. FalkorDB Graph Schema & Cypher Specifications

FalkorDB stores fine-grained AST symbols and repository topology in an in-memory graph representation. Graph instances are namespaced by `repo_id` (e.g. `gitos:fastapi/fastapi`) with snapshots indexed by `commit_sha`.

### 2.1 Node Labels & Schema

| Node Label | Key Properties | Description |
|---|---|---|
| `(:Repository)` | `id` (str), `owner` (str), `name` (str), `default_branch` (str) | Top-level repository metadata |
| `(:Commit)` | `sha` (str), `author` (str), `timestamp` (datetime), `message` (str) | Commit snapshot delimiter |
| `(:File)` | `path` (str), `language` (str), `loc` (int), `ast_hash` (str) | Individual source file |
| `(:Class)` | `id` (str), `name` (str), `line_start` (int), `line_end` (int) | Class declaration |
| `(:Function)` | `id` (str), `name` (str), `signature` (str), `is_async` (bool), `is_test` (bool), `line_start` (int), `line_end` (int) | Function or method declaration |
| `(:Parameter)` | `name` (str), `type_annotation` (str), `default_val` (str), `pos` (int) | Formal parameter |
| `(:MaintainerRule)` | `id` (str), `name` (str), `pattern` (str), `severity` (str), `description` (str) | Declared architectural constraint |

### 2.2 Edge Types & Semantics

| Edge Type | Source Node $\rightarrow$ Target Node | Properties |
|---|---|---|
| `[:DEFINES]` | `(:File)` $\rightarrow$ `(:Class)` or `(:Function)` | `line_number` (int) |
| `[:DEFINES]` | `(:Class)` $\rightarrow$ `(:Function)` | `line_number` (int) |
| `[:DEFINES]` | `(:Function)` $\rightarrow$ `(:Parameter)` | `position` (int) |
| `[:CALLS]` | `(:Function)` $\rightarrow$ `(:Function)` | `call_count` (int), `call_sites` (list) |
| `[:IMPORTS]` | `(:File)` $\rightarrow$ `(:File)` | `symbols` (list), `is_wildcard` (bool) |
| `[:TESTED_BY]` | `(:Function)` $\rightarrow$ `(:Function {is_test: true})` | `confidence` (float) |
| `[:VIOLATES]` | `(:Function)` or `(:File)` $\rightarrow$ `(:MaintainerRule)` | `detected_at` (datetime) |

### 2.3 Core Cypher Query Patterns

#### A. 1..3 Hop Multi-Hop Blast Radius
```cypher
MATCH (target:Function)
WHERE target.id IN $modified_function_ids
MATCH path = (caller:Function)-[:CALLS*1..3]->(target)
RETURN caller, relationships(path), target
LIMIT 100;
```

#### B. Untested Call Impact Detection
```cypher
MATCH (target:Function)
WHERE target.id IN $modified_function_ids
OPTIONAL MATCH (target)<-[:TESTED_BY]-(test:Function)
WHERE test.id IN $modified_test_ids
WITH target, count(test) AS covered_tests
WHERE covered_tests = 0
RETURN target.id AS untested_function, target.file_path AS file;
```

#### C. Dead Code Injection Check (Zero In-Degree)
```cypher
MATCH (new_func:Function)
WHERE new_func.id IN $newly_introduced_function_ids
  AND NOT new_func.name STARTS WITH "_"
  AND NOT new_func.name STARTS WITH "test_"
OPTIONAL MATCH (caller:Function)-[:CALLS]->(new_func)
WITH new_func, count(caller) AS incoming_calls
WHERE incoming_calls = 0
RETURN new_func.id AS dead_code_symbol;
```

---

## 3. Universal Omnibox Parser & URL Routing Rules

The Omnibox endpoint (`parse_github_url`) uses regular expression patterns without dropdown selectors:

```python
import re

PATTERNS = {
    "pull": r"^https?://github\.com/(?P<owner>[\w\.\-]+)/(?P<repo>[\w\.\-]+)/pull/(?P<id>\d+)/?$",
    "issue": r"^https?://github\.com/(?P<owner>[\w\.\-]+)/(?P<repo>[\w\.\-]+)/issues/(?P<id>\d+)/?$",
    "blob": r"^https?://github\.com/(?P<owner>[\w\.\-]+)/(?P<repo>[\w\.\-]+)/blob/(?P<ref>[\w\.\-]+)/(?P<path>.+)$",
    "repo": r"^https?://github\.com/(?P<owner>[\w\.\-]+)/(?P<repo>[\w\.\-]+)/?$",
}
```

### Route Dispatch Table

| Matched Type | Input Example | Target Workflow |
|---|---|---|
| **`repo`** | `github.com/fastapi/fastapi` | Full repository health map, architecture overview, open PR risk overlay |
| **`pull`** | `github.com/fastapi/fastapi/pull/999` | PR defense triage, AST diff blast radius, 4-filter slop scoring |
| **`issue`** | `github.com/fastapi/fastapi/issues/45` | Issue-to-code pathfinder, target function matching, test scaffold |
| **`blob`** | `github.com/fastapi/fastapi/blob/main/routing.py` | Surgical symbol inspector, class/function call hierarchy |

---

## 4. The 4 Deterministic Slop & Quality Filters

GitOS performs zero-LLM-cost filtering before any external model invocation:

```
                  Unified PR Diff
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
   Raw Text Lines                   AST Symbol Tree
  (Additions/Deletions)             (Nodes & Edges)
        │                                 │
        ├─────────────────┬───────────────┤
        ▼                 ▼               ▼
   [Filter 1]        [Filter 2]      [Filter 3]      [Filter 4]
 Untested Calls   AST / Text Ratio   Dead Code    Maintainer Rules
```

### 4.1 Filter 1: Untested Call-Graph Impact
- **Formula:**
  $$\text{UntestedRatio} = \frac{|\{f \in \mathcal{F}_{\text{mod}} \mid \text{Tests}(\text{PR}) \cap \text{CoveredBy}(f) = \emptyset\}|}{|\mathcal{F}_{\text{mod}}|}$$
- If $\text{UntestedRatio} > 0.5$ and the modified function is called by $>5$ downstream nodes, triage flags `NEEDS_TESTS` with high severity.

### 4.2 Filter 2: AST vs. Text Diff Ratio (Cosmetic AI Slop)
- Compares semantic AST modifications against raw textual diff:
  $$\text{SlopIndex} = 1.0 - \min\left(1.0, \frac{\Delta \text{AST Nodes}}{\Delta \text{Text Lines} \times 0.25}\right)$$
- If a PR adds 200 lines of docstrings, markdown restatements, or comment formatting with zero change to function AST or control flow, $\text{SlopIndex} \to 1.0$, triggering `AI_SLOP_SUSPECTED`.

### 4.3 Filter 3: Dead Code Injection Check
- Detects hallucinated helper functions commonly created by LLMs that are never called anywhere in the codebase.
- Newly added functions with in-degree = 0 (and not registered in public router decorators, `__all__`, or entry points) are flagged.

### 4.4 Filter 4: Maintainer Rule Boundaries
- Maintainers can define boundary constraints, such as:
  - *Forbidden:* `(:File {path: "frontend/*"})-[:IMPORTS]->(:File {path: "backend/models/*"})`
  - *Forbidden:* Non-maintainer editing files in `.github/workflows/*`.
- Violations trigger an immediate `RULE_VIOLATION` verdict.

---

## 5. In-Memory Cloud Tree Processing

To guarantee extreme speed and safety:
1. **GitHub Git Trees API:** Calls `GET /repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1`.
2. **Handling the 100,000 File / 7 MB Truncation Limit:**
   - If the response contains `"truncated": true`, GitOS switches to shallow path inspection, fetching sub-trees only for paths modified in the PR diff.
3. **RAM-Only Processing:** Diff patches from `GET /repos/{owner}/{repo}/pulls/{id}/files` are parsed in memory using Python's `ast` module. No temporary directories or disk writes are ever made.

---

## 6. Single-Shot Groq LLM Compression Strategy

When a user requests an explanation or an automated test fix:
- GitOS does **not** send the entire repository or entire files to the LLM.
- **Context Compression Pipeline:**
  1. Extract only the modified function AST signature and diff snippet.
  2. Extract only immediate 1-hop caller function names and signatures.
  3. Extract existing test signatures for the target module.
  4. Compress payload to **< 1,000 tokens**.
- Single-shot execution via **Groq Cloud API** running `llama-3.3-70b-versatile` with response latency under 1.2 seconds.

---

## 7. Security, OAuth & Explicit User Execution Model

GitOS enforces a strict non-spamming guarantee:
- **No Autonomous Writes:** The server possesses no ambient bot credentials that modify public repositories without user consent.
- **User Token Delegation:** Write actions execute via the user's personal GitHub OAuth token (`workflow`, `repo`, `pull_requests:write`).
- **Confirmation Gate:** Every action pill (e.g. `Post Triage Comment`, `Apply Test Diff`) displays an interactive modal showing the exact GitHub API request and body preview before dispatch.
