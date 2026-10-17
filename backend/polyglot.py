"""
GitOS Universal Polyglot Symbol & Import Resolution Engine
Parses Python, TypeScript, JavaScript, Go, Rust, Java, and generic source code
into normalized AST symbols (Functions, Classes, Tests, Calls, Imports)
and performs cross-file import stitching without crashing on any language.
"""

import os
import re
import ast
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("gitos.polyglot")


# ==============================================================================
# Universal Language File Extension Mapping
# ==============================================================================

LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".rb": "ruby",
    ".php": "php",
}


def detect_language(file_path: str) -> str:
    """Detects programming language from file extension or returns 'generic'."""
    ext = os.path.splitext(file_path.lower())[1]
    return LANGUAGE_EXTENSIONS.get(ext, "generic")


# ==============================================================================
# 1. Python AST Parser
# ==============================================================================

class PythonSymbolVisitor(ast.NodeVisitor):
    """Walks Python AST to extract Class, Function, Calls, and Import statements."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.nodes: List[Dict[str, Any]] = []
        self.edges: List[Dict[str, Any]] = []
        self.imports: Dict[str, str] = {}  # symbol_name -> module_source
        self.current_scope: List[str] = [file_path]
        self.ast_node_count = 0

    def visit(self, node):
        self.ast_node_count += 1
        super().visit(node)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = alias.asname or alias.name
            self.imports[name] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        for alias in node.names:
            name = alias.asname or alias.name
            self.imports[name] = f"{module}.{alias.name}" if module else alias.name
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        class_id = f"{self.file_path}::{node.name}"
        self.nodes.append({
            "id": class_id,
            "label": node.name,
            "type": "class",
            "file_path": self.file_path,
            "line_range": [node.lineno, getattr(node, "end_lineno", node.lineno)],
            "incoming_calls": 0,
            "outgoing_calls": 0,
        })
        self.edges.append({
            "source": self.current_scope[-1],
            "target": class_id,
            "relationship": "DEFINES",
        })
        self.current_scope.append(class_id)
        self.generic_visit(node)
        self.current_scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._record_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._record_func(node)

    def _record_func(self, node: Any):
        is_test = node.name.startswith("test_") or "test" in self.file_path.lower()
        func_id = f"{self.file_path}::{node.name}"
        self.nodes.append({
            "id": func_id,
            "label": node.name,
            "type": "test" if is_test else "function",
            "file_path": self.file_path,
            "line_range": [node.lineno, getattr(node, "end_lineno", node.lineno)],
            "incoming_calls": 0,
            "outgoing_calls": 0,
        })
        self.edges.append({
            "source": self.current_scope[-1],
            "target": func_id,
            "relationship": "DEFINES",
        })
        self.current_scope.append(func_id)
        self.generic_visit(node)
        self.current_scope.pop()

    def visit_Call(self, node: ast.Call):
        called_name = None
        if isinstance(node.func, ast.Name):
            called_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            called_name = node.func.attr

        if called_name and len(self.current_scope) > 1:
            caller_id = self.current_scope[-1]
            resolved_target = self.imports.get(called_name, called_name)
            self.edges.append({
                "source": caller_id,
                "target": resolved_target,
                "relationship": "CALLS",
                "is_external": called_name in self.imports,
            })
        self.generic_visit(node)


# ==============================================================================
# 2. Universal Polyglot Heuristic Parser (TS/JS/Go/Rust/Java/etc.)
# ==============================================================================

RE_TS_IMPORT = re.compile(r"""import\s+(?:\{([^}]+)\}|\*\s+as\s+([A-Za-z0-9_$]+)|([A-Za-z0-9_$]+))\s+from\s+['"]([^'"]+)['"]""")
RE_TS_FUNCTION_DEF = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)\s*\(")
RE_TS_ARROW_DEF = re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>")
RE_TS_CLASS_DEF = re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z0-9_$]+)")
RE_TS_CALL = re.compile(r"\b([A-Za-z0-9_$]+)\s*\(")

KEYWORDS_EXCLUDED = {
    "if", "for", "while", "switch", "catch", "import", "require",
    "function", "const", "let", "var", "return", "throw", "export",
    "class", "async", "await", "new", "typeof", "instanceof", "else"
}


def parse_polyglot_symbols(code_str: str, file_path: str, lang: str) -> Dict[str, Any]:
    """
    Universal multi-language parser extracting functions, classes, calls, and imports.
    Accurately avoids mistaking function definitions for function calls.
    """
    lines = code_str.splitlines()
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    imports: Dict[str, str] = {}
    is_test_file = "test" in file_path.lower() or "spec" in file_path.lower()

    current_scope = file_path
    declared_names = set()

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "/*", "*", "#")):
            continue

        # 1. Imports
        import_match = RE_TS_IMPORT.search(line)
        if import_match:
            named, namespace, default, module = import_match.groups()
            mod_path = module or ""
            if named:
                for sym in named.split(","):
                    sym = sym.strip().split(" as ")[-1].strip()
                    if sym:
                        imports[sym] = f"{mod_path}::{sym}"
            if default:
                imports[default] = mod_path
            if namespace:
                imports[namespace] = mod_path
            continue

        # 2. Class Definitions
        cls_match = RE_TS_CLASS_DEF.search(line)
        if cls_match:
            cls_name = cls_match.group(1)
            declared_names.add(cls_name)
            cls_id = f"{file_path}::{cls_name}"
            nodes.append({
                "id": cls_id,
                "label": cls_name,
                "type": "class",
                "file_path": file_path,
                "line_range": [idx, idx + 15],
                "incoming_calls": 0,
                "outgoing_calls": 0,
            })
            current_scope = cls_id
            continue

        # 3. Function Definitions
        fn_match = RE_TS_FUNCTION_DEF.search(line) or RE_TS_ARROW_DEF.search(line)
        if fn_match:
            fn_name = fn_match.group(1)
            declared_names.add(fn_name)
            is_test = is_test_file or fn_name.startswith(("test", "it", "describe"))
            fn_id = f"{file_path}::{fn_name}"
            nodes.append({
                "id": fn_id,
                "label": fn_name,
                "type": "test" if is_test else "function",
                "file_path": file_path,
                "line_range": [idx, idx + 10],
                "incoming_calls": 0,
                "outgoing_calls": 0,
            })
            current_scope = fn_id
            continue

        # 4. Function Calls inside current function scope
        for match in RE_TS_CALL.finditer(line):
            target_name = match.group(1)
            if target_name in KEYWORDS_EXCLUDED or target_name in declared_names:
                continue

            target_resolved = imports.get(target_name, target_name)
            edges.append({
                "source": current_scope,
                "target": target_resolved,
                "relationship": "CALLS",
                "is_external": target_name in imports,
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "imports": imports,
        "ast_node_count": len(nodes) * 3 + len(edges),
    }


# ==============================================================================
# 3. Universal Extractor Entrypoint
# ==============================================================================

def extract_universal_ast(code_str: str, file_path: str) -> Dict[str, Any]:
    """
    Universal entry point: routes to Python AST visitor if Python,
    otherwise uses polyglot pattern extractor. Never throws syntax errors.
    """
    lang = detect_language(file_path)

    if lang == "python":
        try:
            visitor = PythonSymbolVisitor(file_path)
            tree = ast.parse(code_str, filename=file_path)
            visitor.visit(tree)
            return {
                "nodes": visitor.nodes,
                "edges": visitor.edges,
                "imports": visitor.imports,
                "ast_node_count": visitor.ast_node_count,
                "language": "python",
            }
        except SyntaxError:
            logger.warning("Python syntax error in %s. Falling back to polyglot regex parser.", file_path)
            res = parse_polyglot_symbols(code_str, file_path, "python")
            res["language"] = "python"
            return res

    res = parse_polyglot_symbols(code_str, file_path, lang)
    res["language"] = lang
    return res


# ==============================================================================
# 4. Cross-File Symbol Stitching Engine
# ==============================================================================

def stitch_cross_file_graph(
    project_files: Dict[str, Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Resolves imported symbols across different files in the repository.
    Example:
      If 'app.ts' calls 'authenticate', and 'app.ts' imports that from './auth',
      this stitches an edge directly to 'src/auth.py::authenticate'.
    """
    all_nodes: List[Dict[str, Any]] = []
    stitched_edges: List[Dict[str, Any]] = []

    symbol_table: Dict[str, List[str]] = {}

    for file_path, ast_data in project_files.items():
        all_nodes.extend(ast_data.get("nodes", []))
        for node in ast_data.get("nodes", []):
            label = node.get("label")
            node_id = node.get("id")
            if label and node_id:
                symbol_table.setdefault(label, []).append(node_id)

    for file_path, ast_data in project_files.items():
        imports = ast_data.get("imports", {})
        raw_edges = ast_data.get("edges", [])

        for edge in raw_edges:
            target = edge.get("target")
            relationship = edge.get("relationship", "CALLS")

            # Already fully resolved
            if "::" in target:
                # Check if target is a placeholder like './auth::authenticate'
                mod_part, sym_part = target.split("::", 1)
                resolved_id = None
                for cand_file in project_files.keys():
                    base = os.path.splitext(os.path.basename(cand_file))[0]
                    if base in mod_part or mod_part.rstrip("/").endswith(base):
                        resolved_id = f"{cand_file}::{sym_part}"
                        break
                if resolved_id:
                    stitched_edges.append({
                        "source": edge.get("source"),
                        "target": resolved_id,
                        "relationship": relationship,
                        "is_cross_file": True,
                    })
                else:
                    stitched_edges.append(edge)
                continue

            # Check if target is a known imported symbol
            resolved = False
            if target in imports:
                import_src = imports[target]
                for cand_file in project_files.keys():
                    base = os.path.splitext(os.path.basename(cand_file))[0]
                    if base in import_src or import_src.rstrip("/").endswith(base):
                        stitched_edges.append({
                            "source": edge.get("source"),
                            "target": f"{cand_file}::{target}",
                            "relationship": relationship,
                            "is_cross_file": True,
                        })
                        resolved = True
                        break

            # If not in imports, check unique global symbol table
            if not resolved and target in symbol_table:
                candidates = symbol_table[target]
                if len(candidates) == 1 and candidates[0] != edge.get("source"):
                    stitched_edges.append({
                        "source": edge.get("source"),
                        "target": candidates[0],
                        "relationship": relationship,
                        "is_cross_file": True,
                    })
                    resolved = True

            if not resolved:
                stitched_edges.append(edge)

    return all_nodes, stitched_edges


# ==============================================================================
# 4. Git Diff Hunk Line Intersect Matcher
# ==============================================================================

HUNK_HEADER_REGEX = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

def parse_patch_modified_lines(patch: str) -> Set[int]:
    """
    Parses unified diff hunks into a set of line numbers touched in the new file.
    Enables exact symbol targeting rather than assuming all functions in a file changed.
    """
    modified_lines: Set[int] = set()
    if not patch:
        return modified_lines

    current_line = 0
    in_hunk = False

    for line in patch.splitlines():
        match = HUNK_HEADER_REGEX.match(line)
        if match:
            new_start = int(match.group(3))
            current_line = new_start
            in_hunk = True
            continue

        if in_hunk:
            if line.startswith("+") and not line.startswith("+++"):
                modified_lines.add(current_line)
                current_line += 1
            elif line.startswith("-") and not line.startswith("---"):
                # Deleted line corresponds to the current line position
                modified_lines.add(max(1, current_line))
            elif line.startswith(" "):
                current_line += 1
            elif line.startswith("\\"):
                pass  # e.g. \ No newline at end of file

    return modified_lines


def is_node_modified_by_patch(node: Dict[str, Any], modified_lines: Set[int]) -> bool:
    """
    Checks if an AST node's line range intersects with the patch's modified lines.
    """
    if not modified_lines:
        return True  # If no patch details available, default to modified

    line_range = node.get("line_range")
    if not line_range or len(line_range) != 2:
        return True

    start_line, end_line = line_range[0], line_range[1]
    # Check if any modified line falls within [start_line, end_line]
    for line_num in range(start_line, end_line + 1):
        if line_num in modified_lines:
            return True

    return False


# ==============================================================================
# Filter 5: Slopsquatting & Hallucinated Dependency Sentinel
# ==============================================================================

PYTHON_STDLIB = {
    "sys", "os", "math", "re", "json", "time", "logging", "typing", "datetime",
    "unittest", "collections", "itertools", "functools", "asyncio", "hashlib",
    "uuid", "pathlib", "copy", "random", "string", "io", "tempfile", "shutil",
    "subprocess", "threading", "multiprocessing", "queue", "socket", "http",
    "urllib", "email", "xml", "csv", "sqlite3", "contextlib", "dataclasses",
    "enum", "inspect", "abc", "traceback", "weakref", "warnings", "gc",
    "platform", "cmath", "bisect", "heapq", "array", "struct", "zipfile",
    "tarfile", "gzip", "pickle", "ctypes", "typing_extensions"
}

NODE_BUILTINS = {
    "fs", "path", "http", "https", "url", "querystring", "crypto", "os",
    "stream", "events", "util", "child_process", "buffer", "assert", "zlib",
    "cluster", "dgram", "dns", "net", "readline", "tls", "tty", "v8", "vm",
    "worker_threads", "constants", "perf_hooks"
}

PY_IMPORT_REGEX = re.compile(r"^\+\s*(?:import\s+([\w\.\-]+)|from\s+([\w\.\-]+)\s+import)")
JS_IMPORT_REGEX = re.compile(r"^\+\s*(?:import\s+.*?from\s+['\"]([^'\"]+)['\"]|const\s+.*?=\s*require\(['\"]([^'\"]+)['\"]\))")


def extract_patch_new_imports(patch: str, language: str = "python") -> List[str]:
    """
    Extracts external package names imported in newly added lines of a unified diff patch.
    Filters out standard library modules and relative local imports.
    """
    if not patch:
        return []

    packages: Set[str] = set()

    for line in patch.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue

        if language in ("python", "generic"):
            m = PY_IMPORT_REGEX.match(line)
            if m:
                raw_pkg = m.group(1) or m.group(2)
                if raw_pkg:
                    top_pkg = raw_pkg.split(".")[0].strip()
                    if top_pkg and not top_pkg.startswith(".") and top_pkg.lower() not in PYTHON_STDLIB:
                        packages.add(top_pkg)

        if language in ("javascript", "typescript", "generic"):
            m = JS_IMPORT_REGEX.match(line)
            if m:
                raw_pkg = m.group(1) or m.group(2)
                if raw_pkg:
                    raw_pkg = raw_pkg.strip()
                    if not raw_pkg.startswith(".") and not raw_pkg.startswith("/"):
                        if raw_pkg.startswith("@"):
                            parts = raw_pkg.split("/")
                            top_pkg = "/".join(parts[:2]) if len(parts) >= 2 else raw_pkg
                        else:
                            top_pkg = raw_pkg.split("/")[0]
                        if top_pkg.lower() not in NODE_BUILTINS:
                            packages.add(top_pkg)

    return sorted(list(packages))


async def audit_dependency_risks(
    new_packages: List[str],
    manifest_text: Optional[str] = None,
    ecosystem: str = "pypi",
) -> List[Dict[str, Any]]:
    """
    Cross-checks newly added packages against the repo manifest and official registries.
    Flags hallucinated/slopsquatted packages that do not exist on PyPI or npm.
    """
    import httpx

    alerts: List[Dict[str, Any]] = []
    if not new_packages:
        return alerts

    manifest_lower = manifest_text.lower() if manifest_text else ""

    async with httpx.AsyncClient(timeout=4.0) as client:
        for pkg in new_packages:
            in_manifest = pkg.lower() in manifest_lower

            if ecosystem == "pypi":
                registry_url = f"https://pypi.org/pypi/{pkg}/json"
            else:
                registry_url = f"https://registry.npmjs.org/{pkg}"

            try:
                resp = await client.get(registry_url)
                if resp.status_code == 404:
                    alerts.append({
                        "package": pkg,
                        "type": "HALLUCINATED_PACKAGE",
                        "severity": "CRITICAL",
                        "in_manifest": in_manifest,
                        "message": f"Package '{pkg}' was NOT found on {ecosystem.upper()}. Likely AI hallucination or slopsquatting vulnerability.",
                    })
                elif not in_manifest and manifest_text:
                    alerts.append({
                        "package": pkg,
                        "type": "UNDECLARED_DEPENDENCY",
                        "severity": "MEDIUM",
                        "in_manifest": False,
                        "message": f"Package '{pkg}' is imported in code but not listed in project manifest files.",
                    })
            except Exception as e:
                logger.debug("Registry check skipped for '%s': %s", pkg, e)
                if not in_manifest and manifest_text:
                    alerts.append({
                        "package": pkg,
                        "type": "UNDECLARED_DEPENDENCY",
                        "severity": "LOW",
                        "in_manifest": False,
                        "message": f"Package '{pkg}' is not found in manifest (offline registry check).",
                    })

    return alerts


