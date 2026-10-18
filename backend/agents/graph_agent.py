"""
GitOS Graph & Blast Radius Agent (GraphAgent)
Specialized agent for universal AST parsing, cross-file symbol dependency stitching,
FalkorDB graph traversal, and inline GitHub Mermaid diagram generation.
"""

import logging
from typing import Any, Dict, List, Optional, Set
from backend.polyglot import (
    extract_universal_ast,
    stitch_cross_file_graph,
    parse_patch_modified_lines,
    is_node_modified_by_patch,
)

logger = logging.getLogger("gitos.agent.graph")


class GraphAgent:
    """
    Constructs and analyzes in-memory code graphs.
    Identifies multi-hop downstream callers that break when functions are modified.
    """

    def __init__(self, graph_client: Optional[Any] = None):
        self.agent_name = "GraphAgent"
        self.role = "Structural Reasoning & Blast Radius Mapping"
        self.graph_client = graph_client

    def parse_repository_files(
        self, file_contents: Dict[str, str]
    ) -> Dict[str, Dict[str, Any]]:
        """Parses raw file contents in RAM into normalized AST symbols."""
        parsed_files = {}
        for file_path, content in file_contents.items():
            parsed_files[file_path] = extract_universal_ast(content, file_path)
        return parsed_files

    def analyze_blast_radius(
        self,
        repo_id: str,
        commit_sha: str,
        parsed_files: Dict[str, Dict[str, Any]],
        modified_functions: List[str],
        modified_tests: List[str],
        hops: int = 2,
    ) -> Dict[str, Any]:
        """
        Stitches symbols across files, persists to FalkorDB, and computes multi-hop caller impact.
        """
        all_nodes, stitched_edges = stitch_cross_file_graph(parsed_files)

        if self.graph_client:
            try:
                self.graph_client.save_ast_subgraph(repo_id, commit_sha, all_nodes, stitched_edges)
                blast = self.graph_client.get_blast_radius(repo_id, commit_sha, modified_functions, hops=hops)
            except Exception as e:
                logger.warning("FalkorDB query error: %s. Using memory graph.", e)
                blast = {"nodes": all_nodes, "edges": stitched_edges}
        else:
            blast = {"nodes": all_nodes, "edges": stitched_edges}

        # Calculate untested callers
        untested_callers = []
        if len(modified_functions) > 0 and len(modified_tests) == 0:
            untested_callers = modified_functions

        return {
            "agent": self.agent_name,
            "status": "completed",
            "nodes": blast.get("nodes", all_nodes),
            "edges": blast.get("edges", stitched_edges),
            "total_nodes": len(all_nodes),
            "total_edges": len(stitched_edges),
            "modified_symbols_count": len(modified_functions),
            "untested_callers": untested_callers,
            "untested_ratio": 1.0 if untested_callers else 0.0,
        }

    def compile_mermaid_dag(
        self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], max_nodes: int = 15
    ) -> str:
        """
        Generates clean GitHub Mermaid TD syntax with color coding.
        """
        if not nodes:
            return "*No nodes detected in blast radius.*"

        lines = [
            "```mermaid",
            "graph TD",
            "    classDef modified fill:#f85149,stroke:#ff7b72,stroke-width:2px,color:#fff;",
            "    classDef untested fill:#d29922,stroke:#f0883e,stroke-width:2px,color:#fff;",
            "    classDef tested fill:#238636,stroke:#3fb950,stroke-width:2px,color:#fff;",
            "    classDef standard fill:#21262d,stroke:#30363d,stroke-width:1px,color:#c9d1d9;",
        ]

        id_map: Dict[str, str] = {}
        for idx, node in enumerate(nodes[:max_nodes]):
            nid = f"N{idx}"
            orig_id = node.get("id") or str(idx)
            id_map[orig_id] = nid

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

            lines.append(f'    {nid}["{clean_label}"]:::{css_class}')

        edge_count = 0
        for edge in edges:
            src, tgt = edge.get("source"), edge.get("target")
            if src in id_map and tgt in id_map:
                src_id, tgt_id = id_map[src], id_map[tgt]
                etype = edge.get("type", "")
                if etype == "CALLS":
                    lines.append(f"    {src_id} -->|calls| {tgt_id}")
                elif etype == "TESTED_BY":
                    lines.append(f"    {src_id} -.->|tested by| {tgt_id}")
                else:
                    lines.append(f"    {src_id} --> {tgt_id}")
                edge_count += 1
                if edge_count >= max_nodes + 6:
                    break

        lines.append("```")
        return "\n".join(lines)
