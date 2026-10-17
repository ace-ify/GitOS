"""
GitOS FalkorDB Graph Connector & Query Runner
Handles low-latency Cypher graph execution, AST subgraph persistence,
and zero-token deterministic queries against code topologies.
"""

import os
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("gitos.graph")

# FalkorDB client import with graceful degradation
try:
    from falkordb import FalkorDB  # type: ignore
    FALKORDB_AVAILABLE = True
except ImportError:
    FALKORDB_AVAILABLE = False
    logger.warning("FalkorDB Python library not found. Running in fallback in-memory graph mode.")


class FalkorDBClient:
    """
    Manages connection and Cypher query execution on FalkorDB.
    Supports in-memory fallback mode for local testing without active Docker instance.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
    ):
        self.host = host or os.getenv("FALKORDB_HOST", "127.0.0.1")
        self.port = int(port or os.getenv("FALKORDB_PORT", "6379"))
        self.password = password or os.getenv("FALKORDB_PASSWORD") or None
        self._db: Optional[Any] = None
        self._is_connected: bool = False
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

    def connect(self) -> bool:
        """Establishes connection to FalkorDB instance."""
        if not FALKORDB_AVAILABLE:
            self._is_connected = False
            return False

        try:
            self._db = FalkorDB(
                host=self.host,
                port=self.port,
                password=self.password
            )
            # Ping connection by querying a lightweight system graph
            test_graph = self._db.select_graph("gitos_healthcheck")
            test_graph.query("RETURN 1")
            self._is_connected = True
            logger.info("Successfully connected to FalkorDB at %s:%s", self.host, self.port)
            return True
        except Exception as e:
            logger.warning("Could not connect to FalkorDB (%s:%s): %s. Falling back to in-memory mode.", self.host, self.port, e)
            self._is_connected = False
            self._db = None
            return False

    def is_connected(self) -> bool:
        """Returns True if live FalkorDB instance is reachable."""
        return self._is_connected

    def _get_graph_name(self, repo_id: str) -> str:
        """Normalizes repo string (e.g. 'owner/repo') to valid graph identifier."""
        return f"gitos_{repo_id.replace('/', '_').replace('-', '_')}"

    def save_ast_subgraph(
        self,
        repo_id: str,
        commit_sha: str,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
    ) -> bool:
        """
        Persists extracted AST nodes and relationships into FalkorDB,
        keyed by repo_id and commit_sha.
        """
        graph_name = self._get_graph_name(repo_id)

        # Store in fallback memory cache first
        cache_key = f"{repo_id}:{commit_sha}"
        self._memory_cache[cache_key] = {
            "nodes": nodes,
            "edges": edges,
            "commit_sha": commit_sha,
        }

        if not self._is_connected or not self._db:
            return True

        try:
            g = self._db.select_graph(graph_name)

            # Insert or update nodes
            for node in nodes:
                node_id = node.get("id")
                label = node.get("type", "Symbol").capitalize()
                file_path = node.get("file_path", "")
                line_range = node.get("line_range", [0, 0])
                name = node.get("label", node_id)

                cypher = (
                    f"MERGE (n:{label} {{id: $id}}) "
                    f"SET n.name = $name, n.file_path = $file_path, "
                    f"n.line_start = $line_start, n.line_end = $line_end, "
                    f"n.commit_sha = $commit_sha"
                )
                params = {
                    "id": node_id,
                    "name": name,
                    "file_path": file_path,
                    "line_start": line_range[0] if len(line_range) > 0 else 0,
                    "line_end": line_range[1] if len(line_range) > 1 else 0,
                    "commit_sha": commit_sha,
                }
                g.query(cypher, params)

            # Insert edges
            for edge in edges:
                source = edge.get("source")
                target = edge.get("target")
                rel = edge.get("relationship", "CALLS")

                cypher_edge = (
                    f"MATCH (a {{id: $source}}), (b {{id: $target}}) "
                    f"MERGE (a)-[r:{rel}]->(b)"
                )
                g.query(cypher_edge, {"source": source, "target": target})

            return True
        except Exception as e:
            logger.error("Failed saving AST subgraph to FalkorDB: %s", e)
            return False

    def get_blast_radius(
        self,
        repo_id: str,
        commit_sha: str,
        modified_function_ids: List[str],
        hops: int = 2,
    ) -> Dict[str, Any]:
        """
        Traverses 1..N hops of incoming [:CALLS] or [:IMPORTS] edges from modified functions
        to determine downstream blast radius.
        """
        if not modified_function_ids:
            return {"nodes": [], "edges": []}

        # Check in-memory fallback if FalkorDB not connected
        if not self._is_connected or not self._db:
            return self._memory_blast_radius(repo_id, commit_sha, modified_function_ids, hops)

        graph_name = self._get_graph_name(repo_id)
        try:
            g = self._db.select_graph(graph_name)
            cypher = (
                f"MATCH (target:Function) WHERE target.id IN $targets "
                f"MATCH path = (caller:Function)-[:CALLS*1..{hops}]->(target) "
                f"RETURN caller.id, target.id, length(path) AS hop_distance "
                f"LIMIT 100"
            )
            res = g.query(cypher, {"targets": modified_function_ids})

            affected_nodes = []
            affected_edges = []
            seen_ids = set(modified_function_ids)

            for record in res.result_set:
                caller_id, target_id, distance = record[0], record[1], record[2]
                if caller_id not in seen_ids:
                    seen_ids.add(caller_id)
                    affected_nodes.append({
                        "id": caller_id,
                        "label": caller_id.split("::")[-1],
                        "type": "function",
                        "hop_distance": distance,
                        "change_type": "affected_caller",
                    })
                affected_edges.append({
                    "source": caller_id,
                    "target": target_id,
                    "relationship": "CALLS",
                })

            return {"nodes": affected_nodes, "edges": affected_edges}
        except Exception as e:
            logger.error("Error computing blast radius in FalkorDB: %s", e)
            return self._memory_blast_radius(repo_id, commit_sha, modified_function_ids, hops)

    def _memory_blast_radius(
        self,
        repo_id: str,
        commit_sha: str,
        modified_function_ids: List[str],
        hops: int,
    ) -> Dict[str, Any]:
        """In-memory BFS blast radius calculation for fallback mode."""
        cache_key = f"{repo_id}:{commit_sha}"
        cached = self._memory_cache.get(cache_key, {})
        edges = cached.get("edges", [])
        nodes_dict = {n["id"]: n for n in cached.get("nodes", [])}

        target_set = set(modified_function_ids)
        current_layer = set(modified_function_ids)
        visited = set(modified_function_ids)

        blast_nodes = []
        blast_edges = []

        for h in range(1, hops + 1):
            next_layer = set()
            for edge in edges:
                if edge.get("target") in current_layer and edge.get("relationship") in ("CALLS", "IMPORTS"):
                    src = edge.get("source")
                    blast_edges.append(edge)
                    if src not in visited:
                        visited.add(src)
                        next_layer.add(src)
                        node_info = nodes_dict.get(src, {"id": src, "label": src.split("::")[-1], "type": "function"})
                        blast_nodes.append({
                            **node_info,
                            "hop_distance": h,
                            "change_type": "affected_caller",
                        })
            current_layer = next_layer
            if not current_layer:
                break

        return {"nodes": blast_nodes, "edges": blast_edges}

    def check_untested_callers(
        self,
        repo_id: str,
        commit_sha: str,
        modified_function_ids: List[str],
        modified_test_ids: List[str],
    ) -> Dict[str, Any]:
        """
        Deterministic Filter 1: Untested Call Impact
        Finds modified functions where connected tests were NOT modified.
        """
        cache_key = f"{repo_id}:{commit_sha}"
        cached = self._memory_cache.get(cache_key, {})
        edges = cached.get("edges", [])

        # Find test connections
        tested_map: Dict[str, List[str]] = {}
        for edge in edges:
            if edge.get("relationship") == "TESTED_BY":
                src = edge.get("source")  # Function
                tgt = edge.get("target")  # Test function
                tested_map.setdefault(src, []).append(tgt)

        untested = []
        for fn_id in modified_function_ids:
            associated_tests = tested_map.get(fn_id, [])
            # If no tests exist or none of the associated tests were modified in PR
            covered = any(t in modified_test_ids for t in associated_tests)
            if not covered:
                untested.append(fn_id)

        flagged = len(untested) > 0
        score = (len(untested) / len(modified_function_ids)) if modified_function_ids else 0.0

        return {
            "flagged": flagged,
            "score": round(score, 2),
            "untested_functions": untested,
        }

    def check_dead_code(
        self,
        repo_id: str,
        commit_sha: str,
        new_function_ids: List[str],
    ) -> List[str]:
        """
        Deterministic Filter 3: Dead Code Injection
        Finds newly added functions with 0 incoming CALLS edges across the project.
        """
        cache_key = f"{repo_id}:{commit_sha}"
        cached = self._memory_cache.get(cache_key, {})
        edges = cached.get("edges", [])

        incoming_counts: Dict[str, int] = {fn: 0 for fn in new_function_ids}
        for edge in edges:
            tgt = edge.get("target")
            if tgt in incoming_counts and edge.get("relationship") == "CALLS":
                incoming_counts[tgt] += 1

        # Dead code = 0 incoming calls (excluding tests, main, or exported public entrypoints)
        dead_symbols = [
            fn for fn, count in incoming_counts.items()
            if count == 0 and not fn.split("::")[-1].startswith(("test_", "__", "main"))
        ]
        return dead_symbols

    def check_maintainer_rules(
        self,
        repo_id: str,
        commit_sha: str,
    ) -> List[Dict[str, str]]:
        """
        Deterministic Filter 4: Maintainer Architectural Boundary Rules
        Evaluates graph edges against forbidden architectural patterns.
        """
        cache_key = f"{repo_id}:{commit_sha}"
        cached = self._memory_cache.get(cache_key, {})
        edges = cached.get("edges", [])

        violations = []
        for edge in edges:
            src = edge.get("source", "")
            tgt = edge.get("target", "")

            # Default Rule: Frontend modules cannot directly import/call Database modules
            if "frontend" in src and ("database" in tgt or "db_client" in tgt or "models" in tgt):
                violations.append({
                    "rule_id": "RULE_NO_DIRECT_DB_IMPORT",
                    "description": "Frontend UI module violates boundary by directly referencing database tier",
                    "offending_node": f"{src} -> {tgt}",
                })

            # Security Rule: Workflow scripts cannot be dynamically imported by API handlers
            if "api" in src and ".github" in tgt:
                violations.append({
                    "rule_id": "RULE_NO_WORKFLOW_IMPORT",
                    "description": "API service cannot import workflow orchestration files",
                    "offending_node": f"{src} -> {tgt}",
                })

        return violations

    def get_cached_snapshot(self, repo_id: str, commit_sha: str) -> Optional[Dict[str, Any]]:
        """Returns cached graph and analysis metadata for fast 50ms replay."""
        cache_key = f"{repo_id}:{commit_sha}"
        return self._memory_cache.get(cache_key)


# Singleton factory helper
_client_instance: Optional[FalkorDBClient] = None

def get_graph_client() -> FalkorDBClient:
    """Provides application-wide FalkorDB client singleton."""
    global _client_instance
    if _client_instance is None:
        _client_instance = FalkorDBClient()
        _client_instance.connect()
    return _client_instance
