# 🏛️ GitOS: System Architecture & Technical Specification

**Document Version:** 1.1.0  
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
|  | - 3D Force-Graph Canvas (WebGL / Canvas node rendering)                     |  |
|  | - Side-Panel Telemetry (Risk Gauge, Verdict, 4 Filter Slop Breakdown)       |  |
|  | - Contextual Action Dock + Explicit OAuth Confirmation Modal                |  |
|  | - Maintainer Rule Builder UI & Patch Diff Viewer                            |  |
|  +-----------------------------------------------------------------------------+  |
+---------------------------------------┬────────────────────────────────-----------+
                                        │ HTTPS / JSON / Bearer OAuth
                                        ▼
+-----------------------------------------------------------------------------------+
|                               FASTAPI ENGINE                                      |
|  +-------------------+  +-----------------------+  +---------------------------+  |
|  | Omnibox Router    |  | Scoped PR Diff Stream |  | Polyglot Symbol Parser    |  |
|  | Regex URL parsing |  | ETag 304 + Rate Limit |  | Python, TS, Go, Rust, etc.|  |
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

## 2. Universal Polyglot Engine & Cross-File Symbol Stitching

GitOS supports any language or framework via its **Universal Polyglot Engine (`backend/polyglot.py`)**:

### 2.1 Multi-Language AST & Heuristic Dispatch
- **Python (`.py`):** Utilizes Python's native `ast` module with AST NodeVisitor for extraction of classes, functions, calls, and imports. Falls back to polyglot regex on partial diff syntax errors.
- **TypeScript & JavaScript (`.ts`, `.tsx`, `.js`, `.jsx`):** Extracts ES classes, exported functions, arrow declarations, method bodies, ES6 imports (`import { x } from "./y"`), and invocation call-sites.
- **Go (`.go`):** Extracts `func`, `type struct`, import packages, and call signatures.
- **Rust (`.rs`):** Extracts `fn`, `struct`, `impl`, `use` statements, and invocation expressions.
- **Generic Fallback:** High-precision regex pattern matcher extracts symbol headers across any language without crashing.

### 2.2 Cross-File Import Stitching
Rather than treating files as isolated islands, GitOS resolves imported symbols:
1. Maps import statements: `import { authenticate } from "./auth"` $\rightarrow$ `{ "authenticate": "./auth::authenticate" }`.
2. Matches `./auth` against active files in the project tree (`src/auth.ts` or `src/auth.py`).
3. Stitches cross-file edges:
   $$\text{CallEdge} = (\text{src/login.ts::handleLogin}) \xrightarrow{\text{[:CALLS \{is\_cross\_file: true\}]}} (\text{src/auth.ts::authenticate})$$

---

## 3. FalkorDB Graph Schema & Cypher Specifications

FalkorDB stores fine-grained AST symbols and repository topology in an in-memory graph representation. Graph instances are namespaced by `repo_id` (e.g. `gitos:fastapi/fastapi`) with snapshots indexed by `commit_sha`.

### 3.1 Node Labels & Schema

| Node Label | Key Properties | Description |
|---|---|---|
| `(:Repository)` | `id` (str), `owner` (str), `name` (str), `default_branch` (str) | Top-level repository metadata |
| `(:Commit)` | `sha` (str), `author` (str), `timestamp` (datetime), `message` (str) | Commit snapshot delimiter |
| `(:File)` | `path` (str), `language` (str), `loc` (int), `ast_hash` (str) | Individual source file |
| `(:Class)` | `id` (str), `name` (str), `line_start` (int), `line_end` (int) | Class declaration |
| `(:Function)` | `id` (str), `name` (str), `signature` (str), `is_async` (bool), `is_test` (bool), `line_start` (int), `line_end` (int) | Function or method declaration |
| `(:Parameter)` | `name` (str), `type_annotation` (str), `default_val` (str), `pos` (int) | Formal parameter |
| `(:MaintainerRule)` | `id` (str), `name` (str), `pattern` (str), `severity` (str), `description` (str) | Declared architectural constraint |

### 3.2 Edge Types & Semantics

| Edge Type | Source Node $\rightarrow$ Target Node | Properties |
|---|---|---|
| `[:DEFINES]` | `(:File)` $\rightarrow$ `(:Class)` or `(:Function)` | `line_number` (int) |
| `[:DEFINES]` | `(:Class)` $\rightarrow$ `(:Function)` | `line_number` (int) |
| `[:DEFINES]` | `(:Function)` $\rightarrow$ `(:Parameter)` | `position` (int) |
| `[:CALLS]` | `(:Function)` $\rightarrow$ `(:Function)` | `is_cross_file` (bool) |
| `[:IMPORTS]` | `(:File)` $\rightarrow$ `(:File)` | `symbols` (list) |
| `[:TESTED_BY]` | `(:Function)` $\rightarrow$ `(:Function {is_test: true})` | `confidence` (float) |
| `[:VIOLATES]` | `(:Function)` or `(:File)` $\rightarrow$ `(:MaintainerRule)` | `detected_at` (datetime) |

---

## 4. GitHub API Strategy & Rate Limit Defense

Handling large repos and PRs without exceeding rate limits:
1. **Scoped PR Diff Inspection:** Uses `GET /repos/{owner}/{repo}/pulls/{id}/files?per_page=100` instead of dumping full repository trees.
2. **Exclusion of Non-Code Assets:** Excludes lockfiles (`package-lock.json`, `poetry.lock`), binary images, SVG files, and minified bundles.
3. **ETag 304 Caching:** Sends `If-None-Match: <etag>`. Replays return HTTP `304 Not Modified`, which does **not** decrement GitHub rate limit quotas.
4. **Rate Limit Headers:** Automatically monitors `X-RateLimit-Remaining` and `X-RateLimit-Reset` with exponential backoff on `429 Too Many Requests`.

---

## 5. The 4 Deterministic Slop & Quality Filters

GitOS performs zero-LLM-cost filtering before any external model invocation:

```
                  Unified PR Diff
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
   Raw Text Lines                   Polyglot AST Tree
  (Additions/Deletions)             (Nodes & Edges)
        │                                 │
        ├─────────────────┬───────────────┤
        ▼                 ▼               ▼
   [Filter 1]        [Filter 2]      [Filter 3]      [Filter 4]
 Untested Calls   AST / Text Ratio   Dead Code    Maintainer Rules
```

1. **Filter 1 (Untested Call Impact):** Flags modified functions missing corresponding test caller updates.
2. **Filter 2 (AST vs Text Diff Ratio):** Compares semantic AST modifications against raw text lines to catch cosmetic rewordings and comment-only spam.
3. **Filter 3 (Dead Code Injection Check):** In-degree check (`degree_in == 0`) identifies newly injected functions with no callers in the codebase.
4. **Filter 4 (Maintainer Architectural Rules):** Graph pattern-matching enforces module boundaries (e.g. `frontend/* -> backend/db/*`).

---

## 6. Security & OAuth Token Protection

- **Token Isolation:** Tokens are sent via HTTP headers (`Authorization: Bearer <token>`) rather than query parameters.
- **Zero Ambient Bot Writes:** No unsolicited actions are performed. Actions strictly require interactive confirmation modals.
- **Enterprise Storage Standard:** Tokens in production deployment should be sealed in `HttpOnly`, `SameSite=Lax`, `Secure` session cookies.
