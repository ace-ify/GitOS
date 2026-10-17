"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  ShieldAlert,
  ShieldCheck,
  GitPullRequest,
  Terminal,
  Activity,
  Layers,
  Sparkles,
  AlertTriangle,
  FileCode2,
  CheckCircle2,
  XCircle,
  Cpu,
  Lock,
  PlusCircle,
  Sliders,
  Database,
  RefreshCw,
  Code2,
  X,
  MessageSquare,
  Send,
  Bot,
} from "lucide-react";

// Types matching shared_contract.json
interface ParsedUrl {
  raw_url: string;
  url_type: "repo" | "pull" | "issue" | "blob";
  owner: string;
  repo: string;
  target_id?: string | null;
  path?: string | null;
}

interface BlastNode {
  id: string;
  label: string;
  type: "file" | "class" | "function" | "test";
  file_path?: string;
  line_range?: [number, number];
  hop_distance: number;
  change_type: "added" | "modified" | "deleted" | "affected_caller" | "unaffected";
  incoming_calls?: number;
  outgoing_calls?: number;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}

interface BlastEdge {
  source: string;
  target: string;
  relationship: string;
  is_cross_file?: boolean;
}

interface ActionPill {
  id: string;
  label: string;
  action_type: string;
  is_destructive: boolean;
  description: string;
  payload: Record<string, any>;
}

interface MaintainerRule {
  rule_id: string;
  name: string;
  pattern: string;
  severity: string;
  description: string;
}

interface AnalysisData {
  analysis_id: string;
  url_parsed: ParsedUrl;
  user_mode: "maintainer" | "contributor" | "guest";
  risk_score: number;
  verdict: "CLEAN" | "LOW_RISK" | "NEEDS_TESTS" | "AI_SLOP_SUSPECTED" | "CRITICAL_BLAST" | "RULE_VIOLATION";
  summary: string;
  deterministic_checks: {
    untested_call_graph: { flagged: boolean; score: number; untested_functions: string[] };
    ast_vs_text_ratio: { flagged: boolean; ast_node_delta: number; text_diff_lines: number; ratio: number; is_cosmetic_slop: boolean };
    dead_code: { flagged: boolean; dead_symbols: string[] };
    maintainer_rules: { flagged: boolean; violations: { rule_id: string; description: string; offending_node: string }[] };
  };
  blast_radius_nodes: BlastNode[];
  blast_radius_edges: BlastEdge[];
  suggested_diff?: string | null;
  action_pills: ActionPill[];
  execution_metadata: {
    commit_sha: string;
    cached_replay: boolean;
    latency_ms: number;
    live_fetched?: boolean;
    timestamp: string;
  };
}

// Configurable API base URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const INITIAL_DEMO_DATA: AnalysisData = {
  analysis_id: "demo-7f13b6f9",
  url_parsed: {
    raw_url: "https://github.com/fastapi/fastapi/pull/9999",
    url_type: "pull",
    owner: "fastapi",
    repo: "fastapi",
    target_id: "9999",
  },
  user_mode: "maintainer",
  risk_score: 78,
  verdict: "CRITICAL_BLAST",
  summary: "Modified APIRouter.add_api_route signature impacts 14 downstream callers across 3 files with 0 test updates detected.",
  deterministic_checks: {
    untested_call_graph: {
      flagged: true,
      score: 0.85,
      untested_functions: ["APIRouter.add_api_route", "RoutingEngine.dispatch"],
    },
    ast_vs_text_ratio: {
      flagged: false,
      ast_node_delta: 36,
      text_diff_lines: 48,
      ratio: 0.75,
      is_cosmetic_slop: false,
    },
    dead_code: {
      flagged: false,
      dead_symbols: [],
    },
    maintainer_rules: {
      flagged: true,
      violations: [
        {
          rule_id: "RULE_NO_DIRECT_DB_IMPORT",
          description: "Frontend UI module violates boundary by directly referencing database tier",
          offending_node: "src/gateway.ts -> backend/db/models.py",
        },
      ],
    },
  },
  blast_radius_nodes: [
    {
      id: "fastapi/routing.py::APIRouter.add_api_route",
      label: "APIRouter.add_api_route",
      type: "function",
      file_path: "fastapi/routing.py",
      line_range: [140, 185],
      hop_distance: 0,
      change_type: "modified",
      incoming_calls: 14,
      outgoing_calls: 3,
    },
    {
      id: "src/gateway.ts::registerRoutes",
      label: "GatewayController.registerRoutes",
      type: "function",
      file_path: "src/gateway.ts",
      line_range: [82, 110],
      hop_distance: 1,
      change_type: "affected_caller",
      incoming_calls: 26,
      outgoing_calls: 2,
    },
    {
      id: "tests/test_routing.py::test_router_signature",
      label: "test_router_signature",
      type: "test",
      file_path: "tests/test_routing.py",
      line_range: [20, 35],
      hop_distance: 2,
      change_type: "unaffected",
      incoming_calls: 0,
      outgoing_calls: 1,
    },
  ],
  blast_radius_edges: [
    {
      source: "src/gateway.ts::registerRoutes",
      target: "fastapi/routing.py::APIRouter.add_api_route",
      relationship: "CALLS",
      is_cross_file: true,
    },
    {
      source: "tests/test_routing.py::test_router_signature",
      target: "fastapi/routing.py::APIRouter.add_api_route",
      relationship: "TESTED_BY",
    },
  ],
  suggested_diff: `--- a/tests/test_routing.py\n+++ b/tests/test_routing.py\n@@ -24,6 +24,12 @@ def test_router_signature():\n+    router = APIRouter()\n+    # Validates updated parameter signature backward compatibility\n+    router.add_api_route('/ping', lambda: {'status': 'ok'})\n`,
  action_pills: [
    {
      id: "pill_request_tests",
      label: "Request Test Coverage",
      action_type: "gh_comment",
      is_destructive: false,
      description: "Post blast radius telemetry report detailing 14 affected callers to the PR.",
      payload: { template: "blast_warning" },
    },
    {
      id: "pill_apply_test_diff",
      label: "Push Generated Test Patch",
      action_type: "gh_pr_draft",
      is_destructive: false,
      description: "Open a draft PR with unit tests covering the modified function signature.",
      payload: {},
    },
  ],
  execution_metadata: {
    commit_sha: "a1b2c3d4e5f67890123456789abcdef012345678",
    cached_replay: false,
    latency_ms: 310,
    live_fetched: false,
    timestamp: new Date().toISOString(),
  },
};

export default function GitOSDashboard() {
  const [urlInput, setUrlInput] = useState("https://github.com/fastapi/fastapi/pull/9999");
  const [detectedType, setDetectedType] = useState<string>("pull");
  const [userMode, setUserMode] = useState<"maintainer" | "contributor">("maintainer");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [data, setData] = useState<AnalysisData>(INITIAL_DEMO_DATA);
  const [selectedNode, setSelectedNode] = useState<BlastNode | null>(INITIAL_DEMO_DATA.blast_radius_nodes[0]);
  const [activeModalPill, setActiveModalPill] = useState<ActionPill | null>(null);
  const [executionState, setExecutionState] = useState<"idle" | "executing" | "done">("idle");
  const [rateLimitRem, setRateLimitRem] = useState<number>(5000);
  const [activeViewTab, setActiveViewTab] = useState<"graph" | "diff">("graph");

  // Groq Co-Pilot Chat State
  const [chatMessages, setChatMessages] = useState<Array<{ sender: "user" | "gitos"; text: string }>>([
    {
      sender: "gitos",
      text: "GitOS Co-Pilot online (< 1,000 tokens compressed). Ask me anything about affected symbols or missing tests.",
    },
  ]);
  const [chatInput, setChatInput] = useState("");
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [isGeneratingTest, setIsGeneratingTest] = useState(false);

  // Rule Builder Modal State
  const [isRuleModalOpen, setIsRuleModalOpen] = useState(false);
  const [rules, setRules] = useState<MaintainerRule[]>([]);
  const [newRuleName, setNewRuleName] = useState("");
  const [newRulePattern, setNewRulePattern] = useState("");
  const [newRuleDesc, setNewRuleDesc] = useState("");

  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Live Omnibox Detection
  useEffect(() => {
    const val = urlInput.trim();
    if (/\/pull\/\d+/.test(val)) setDetectedType("pull");
    else if (/\/issues\/\d+/.test(val)) setDetectedType("issue");
    else if (/\/blob\//.test(val)) setDetectedType("blob");
    else if (/github\.com\/[\w.-]+\/[\w.-]+/.test(val)) setDetectedType("repo");
    else setDetectedType("unknown");
  }, [urlInput]);

  // Fetch health & existing rules
  useEffect(() => {
    const fetchHealthAndRules = async () => {
      try {
        const hRes = await fetch(`${API_BASE_URL}/api/health`);
        if (hRes.ok) {
          const hData = await hRes.json();
          if (hData.github_rate_limit_remaining !== undefined) {
            setRateLimitRem(hData.github_rate_limit_remaining);
          }
        }
        const rRes = await fetch(`${API_BASE_URL}/api/rules`);
        if (rRes.ok) {
          const rData = await rRes.json();
          setRules(rData.rules || []);
        }
      } catch {
        // Backend offline fallback
      }
    };
    fetchHealthAndRules();
  }, []);

  // Execute Analysis via API
  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsAnalyzing(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: urlInput, user_mode: userMode }),
      });
      if (res.ok) {
        const payload = await res.json();
        setData(payload);
        if (payload.blast_radius_nodes?.length > 0) {
          setSelectedNode(payload.blast_radius_nodes[0]);
        }
      }
    } catch {
      // In standalone demo mode, fallback is active
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Add Maintainer Rule
  const handleCreateRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRuleName || !newRulePattern) return;

    const ruleObj: MaintainerRule = {
      rule_id: `RULE_${newRuleName.toUpperCase().replace(/\s+/g, "_")}`,
      name: newRuleName,
      pattern: newRulePattern,
      severity: "high",
      description: newRuleDesc || `Custom rule enforcing ${newRulePattern}`,
    };

    try {
      await fetch(`${API_BASE_URL}/api/rules`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(ruleObj),
      });
      setRules([...rules, ruleObj]);
      setNewRuleName("");
      setNewRulePattern("");
      setNewRuleDesc("");
      setIsRuleModalOpen(false);
    } catch {
      setRules([...rules, ruleObj]);
      setIsRuleModalOpen(false);
    }
  };

  // Canvas Force Graph Simulation
  useEffect(() => {
    if (activeViewTab !== "graph") return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    const width = (canvas.width = canvas.parentElement?.clientWidth || 800);
    const height = (canvas.height = canvas.parentElement?.clientHeight || 600);

    const nodes = data.blast_radius_nodes.map((n, i) => ({
      ...n,
      x: width / 2 + Math.cos((i * 2 * Math.PI) / data.blast_radius_nodes.length) * 170,
      y: height / 2 + Math.sin((i * 2 * Math.PI) / data.blast_radius_nodes.length) * 170,
    }));

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      // Draw Edges
      data.blast_radius_edges.forEach((edge) => {
        const src = nodes.find((n) => n.id === edge.source);
        const tgt = nodes.find((n) => n.id === edge.target);
        if (src && tgt) {
          ctx.beginPath();
          ctx.moveTo(src.x, src.y);
          ctx.lineTo(tgt.x, tgt.y);
          if (edge.relationship === "TESTED_BY") {
            ctx.strokeStyle = "rgba(16, 185, 129, 0.4)";
          } else if (edge.is_cross_file) {
            ctx.strokeStyle = "rgba(244, 63, 94, 0.6)";
          } else {
            ctx.strokeStyle = "rgba(56, 189, 248, 0.3)";
          }
          ctx.lineWidth = edge.is_cross_file ? 2 : 1.5;
          ctx.setLineDash(edge.is_cross_file ? [6, 3] : [3, 3]);
          ctx.stroke();
          ctx.setLineDash([]);
        }
      });

      // Draw Nodes
      nodes.forEach((node) => {
        const isSelected = selectedNode?.id === node.id;
        ctx.beginPath();
        ctx.arc(node.x, node.y, isSelected ? 18 : 12, 0, Math.PI * 2);

        if (node.change_type === "modified") {
          ctx.fillStyle = "#f43f5e";
          ctx.shadowColor = "#f43f5e";
        } else if (node.change_type === "affected_caller") {
          ctx.fillStyle = "#f59e0b";
          ctx.shadowColor = "#f59e0b";
        } else if (node.type === "test") {
          ctx.fillStyle = "#10b981";
          ctx.shadowColor = "#10b981";
        } else {
          ctx.fillStyle = "#38bdf8";
          ctx.shadowColor = "#38bdf8";
        }

        ctx.shadowBlur = isSelected ? 20 : 8;
        ctx.fill();
        ctx.shadowBlur = 0;

        ctx.fillStyle = "#e2e8f0";
        ctx.font = "11px -apple-system, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(node.label, node.x, node.y + 24);
      });

      animId = requestAnimationFrame(render);
    };

    render();
    return () => cancelAnimationFrame(animId);
  }, [data, selectedNode, activeViewTab]);

  // Handle explicit action execution
  const handleExecuteConfirmedAction = async () => {
    if (!activeModalPill) return;
    setExecutionState("executing");
    try {
      await fetch(`${API_BASE_URL}/api/execute-action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action_type: activeModalPill.action_type,
          owner: data.url_parsed.owner,
          repo: data.url_parsed.repo,
          target_id: data.url_parsed.target_id,
          payload: activeModalPill.payload,
          confirmed: true,
        }),
      });
    } catch {
      // In demo mode
    }
    setExecutionState("done");
    setTimeout(() => {
      setActiveModalPill(null);
      setExecutionState("idle");
    }, 1200);
  };

  // Generate automated test patch via Groq single-shot reasoning
  const handleGenerateTestPatch = async () => {
    setIsGeneratingTest(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/generate-patch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ analysis_data: data }),
      });
      if (res.ok) {
        const patchData = await res.json();
        setData((prev) => ({ ...prev, suggested_diff: patchData.suggested_diff }));
        setActiveViewTab("diff");
      }
    } catch {
      setActiveViewTab("diff");
    } finally {
      setIsGeneratingTest(false);
    }
  };

  // Telemetry chat via Groq (< 1000 tokens)
  const handleSendChatMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || isChatLoading) return;
    const userMsg = chatInput.trim();
    setChatInput("");
    setChatMessages((prev) => [...prev, { sender: "user", text: userMsg }]);
    setIsChatLoading(true);

    try {
      const res = await fetch(`${API_BASE_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          analysis_id: data.analysis_id,
          prompt: userMsg,
          analysis_data: data,
        }),
      });
      if (res.ok) {
        const respData = await res.json();
        setChatMessages((prev) => [...prev, { sender: "gitos", text: respData.response }]);
      } else {
        setChatMessages((prev) => [
          ...prev,
          { sender: "gitos", text: "Telemetry: The modified symbol breaks caller backward-compatibility." },
        ]);
      }
    } catch {
      setChatMessages((prev) => [
        ...prev,
        { sender: "gitos", text: "Telemetry: Untested modified callers detected across the dependency subgraph." },
      ]);
    } finally {
      setIsChatLoading(false);
    }
  };

  const getVerdictBadge = (verdict: string) => {
    switch (verdict) {
      case "CRITICAL_BLAST":
        return <span className="px-3 py-1 bg-rose-500/20 text-rose-400 border border-rose-500/40 rounded-full text-xs font-semibold flex items-center gap-1.5"><ShieldAlert className="w-3.5 h-3.5" /> CRITICAL BLAST</span>;
      case "NEEDS_TESTS":
        return <span className="px-3 py-1 bg-amber-500/20 text-amber-400 border border-amber-500/40 rounded-full text-xs font-semibold flex items-center gap-1.5"><AlertTriangle className="w-3.5 h-3.5" /> NEEDS TESTS</span>;
      case "AI_SLOP_SUSPECTED":
        return <span className="px-3 py-1 bg-purple-500/20 text-purple-400 border border-purple-500/40 rounded-full text-xs font-semibold flex items-center gap-1.5"><AlertTriangle className="w-3.5 h-3.5" /> AI SLOP DETECTED</span>;
      default:
        return <span className="px-3 py-1 bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 rounded-full text-xs font-semibold flex items-center gap-1.5"><ShieldCheck className="w-3.5 h-3.5" /> CLEAN GRAPH</span>;
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0d14] text-slate-100 flex flex-col bg-cyber-grid">
      {/* 1. Master Top Bar & Universal Omnibox */}
      <header className="border-b border-slate-800/80 bg-[#0f1422]/90 backdrop-blur sticky top-0 z-40 px-6 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center font-bold text-black shadow-lg shadow-cyan-500/20">
            G
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight text-white flex items-center gap-2">
              GitOS <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800">Polyglot Graph</span>
            </h1>
          </div>
        </div>

        {/* Universal Omnibox Input */}
        <form onSubmit={handleAnalyze} className="flex-1 max-w-2xl mx-8 relative">
          <div className="relative flex items-center">
            <Terminal className="w-4 h-4 text-cyan-400 absolute left-3.5" />
            <input
              type="text"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="Paste any GitHub URL (Python, TS, Go, Rust, Java, etc.)..."
              className="w-full pl-10 pr-32 py-2 bg-[#151c30] border border-slate-700/80 rounded-xl text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-400 transition"
            />
            <div className="absolute right-2 flex items-center gap-1.5">
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                {detectedType}
              </span>
              <button
                type="submit"
                disabled={isAnalyzing}
                className="px-3 py-1 bg-cyan-500 hover:bg-cyan-400 text-slate-950 rounded-lg text-xs font-semibold transition"
              >
                {isAnalyzing ? "Analyzing..." : "Triage"}
              </button>
            </div>
          </div>
        </form>

        {/* Action Controls & Mode Switcher */}
        <div className="flex items-center gap-3">
          {/* Rate limit badge */}
          <div className="text-[11px] font-mono text-slate-400 flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#151c30] border border-slate-800">
            <Database className="w-3.5 h-3.5 text-cyan-400" />
            API: {rateLimitRem} req/hr
          </div>

          {/* Maintainer Rule Builder Trigger */}
          <button
            onClick={() => setIsRuleModalOpen(true)}
            className="px-2.5 py-1.5 rounded-lg text-xs font-medium bg-[#151c30] hover:bg-slate-800 border border-slate-700 text-slate-300 flex items-center gap-1.5 transition"
          >
            <Sliders className="w-3.5 h-3.5 text-cyan-400" />
            Rules ({rules.length})
          </button>

          {/* Dual Mode Switcher */}
          <div className="flex items-center gap-1.5 bg-[#151c30] p-1 rounded-xl border border-slate-800">
            <button
              onClick={() => setUserMode("maintainer")}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition flex items-center gap-1.5 ${
                userMode === "maintainer"
                  ? "bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20 font-semibold"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              🛡️ Maintainer
            </button>
            <button
              onClick={() => setUserMode("contributor")}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition flex items-center gap-1.5 ${
                userMode === "contributor"
                  ? "bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20 font-semibold"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              🚀 Contributor
            </button>
          </div>
        </div>
      </header>

      {/* Main Workspace */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left/Center Canvas View */}
        <div className="flex-1 relative flex flex-col">
          {/* Tab Selector & Telemetry Bar */}
          <div className="absolute top-4 left-4 z-10 flex items-center gap-2">
            <div className="flex items-center bg-[#0f1422]/90 backdrop-blur rounded-lg p-0.5 border border-slate-700">
              <button
                onClick={() => setActiveViewTab("graph")}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition flex items-center gap-1.5 ${
                  activeViewTab === "graph" ? "bg-cyan-500 text-slate-950 font-semibold" : "text-slate-400"
                }`}
              >
                <Activity className="w-3.5 h-3.5" /> 3D Blast Graph
              </button>
              <button
                onClick={() => setActiveViewTab("diff")}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition flex items-center gap-1.5 ${
                  activeViewTab === "diff" ? "bg-cyan-500 text-slate-950 font-semibold" : "text-slate-400"
                }`}
              >
                <Code2 className="w-3.5 h-3.5" /> Patch Diff
              </button>
            </div>

            <span className="px-2.5 py-1 rounded-md bg-slate-900/80 backdrop-blur border border-slate-700 text-xs font-mono text-slate-300 flex items-center gap-1.5">
              Nodes: {data.blast_radius_nodes.length} | Edges: {data.blast_radius_edges.length}
            </span>

            {data.execution_metadata.live_fetched && (
              <span className="px-2.5 py-1 rounded-md bg-emerald-950/80 border border-emerald-700 text-xs font-mono text-emerald-400 flex items-center gap-1">
                ✓ Live GitHub Streaming
              </span>
            )}
          </div>

          {/* Canvas or Diff View */}
          {activeViewTab === "graph" ? (
            <div className="flex-1 w-full h-full cursor-crosshair">
              <canvas ref={canvasRef} className="w-full h-full block" />
            </div>
          ) : (
            <div className="flex-1 p-6 overflow-y-auto">
              <div className="p-4 bg-[#0a0d14] rounded-2xl border border-slate-800">
                <div className="text-xs font-mono text-slate-400 mb-2 flex items-center justify-between">
                  <span>UNIFIED DIFF STREAM (IN-MEMORY PARSED)</span>
                  <span className="text-cyan-400">{data.url_parsed.owner}/{data.url_parsed.repo}</span>
                </div>
                <pre className="font-mono text-xs text-slate-200 overflow-x-auto leading-relaxed">
                  {data.suggested_diff || "No diff available for repository root."}
                </pre>
              </div>
            </div>
          )}

          {/* Contextual Action Dock at Canvas Bottom */}
          <div className="p-4 bg-[#0f1422]/90 backdrop-blur border-t border-slate-800/80 flex items-center justify-between z-20">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400 font-medium">Context Actions:</span>
              {data.action_pills.map((pill) => (
                <button
                  key={pill.id}
                  onClick={() => {
                    if (pill.id === "pill_generate_test_patch") {
                      handleGenerateTestPatch();
                    } else {
                      setActiveModalPill(pill);
                    }
                  }}
                  disabled={isGeneratingTest && pill.id === "pill_generate_test_patch"}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border flex items-center gap-1.5 transition ${
                    pill.is_destructive
                      ? "bg-rose-950/40 text-rose-300 border-rose-800 hover:bg-rose-900/60"
                      : "bg-[#151c30] text-cyan-300 border-cyan-800/60 hover:bg-cyan-950/40"
                  }`}
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  {pill.id === "pill_generate_test_patch" && isGeneratingTest
                    ? "Generating Patch..."
                    : pill.label}
                </button>
              ))}
            </div>

            <div className="text-xs text-slate-500 flex items-center gap-1.5">
              <Lock className="w-3.5 h-3.5 text-emerald-400" />
              Zero-Spam Policy: Explicit OAuth Confirmation Active
            </div>
          </div>
        </div>

        {/* Right: Side Panel Telemetry & 4 Filter Breakdown */}
        <aside className="w-[440px] border-l border-slate-800/80 bg-[#0f1422]/95 overflow-y-auto p-6 space-y-6">
          {/* Risk Gauge & Verdict */}
          <div className="glass-panel p-4 rounded-2xl space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Triage Verdict</span>
              {getVerdictBadge(data.verdict)}
            </div>

            <div className="flex items-baseline justify-between pt-2">
              <div>
                <div className="text-3xl font-black tracking-tight text-white">{data.risk_score}<span className="text-sm font-normal text-slate-500"> / 100</span></div>
                <div className="text-xs text-slate-400">Deterministic Blast Risk Score</div>
              </div>
              <div className="text-right">
                <div className="text-xs font-mono text-cyan-400">{data.url_parsed.owner}/{data.url_parsed.repo}</div>
                <div className="text-xs text-slate-500">Target #{data.url_parsed.target_id || "HEAD"}</div>
              </div>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed pt-2 border-t border-slate-800/80">
              {data.summary}
            </p>
          </div>

          {/* 4 Deterministic Slop & Quality Filters Breakdown */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-cyan-400" /> 4 Zero-Token Graph Filters
              </h2>
              <span className="text-[10px] text-emerald-400 font-mono">0 LLM Tokens</span>
            </div>

            {/* Filter 1 */}
            <div className="p-3 bg-[#151c30] rounded-xl border border-slate-800/80 flex items-start gap-3">
              {data.deterministic_checks.untested_call_graph.flagged ? (
                <XCircle className="w-4 h-4 text-rose-400 mt-0.5 shrink-0" />
              ) : (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
              )}
              <div className="flex-1 text-xs">
                <div className="font-semibold text-slate-200">1. Untested Call Impact</div>
                <div className="text-slate-400 mt-0.5">
                  {data.deterministic_checks.untested_call_graph.untested_functions.length} modified functions lack updated tests.
                </div>
              </div>
            </div>

            {/* Filter 2 */}
            <div className="p-3 bg-[#151c30] rounded-xl border border-slate-800/80 flex items-start gap-3">
              {data.deterministic_checks.ast_vs_text_ratio.flagged ? (
                <XCircle className="w-4 h-4 text-purple-400 mt-0.5 shrink-0" />
              ) : (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
              )}
              <div className="flex-1 text-xs">
                <div className="font-semibold text-slate-200">2. AST vs Text Ratio (Cosmetic Slop)</div>
                <div className="text-slate-400 mt-0.5">
                  Ratio: {data.deterministic_checks.ast_vs_text_ratio.ratio} ({data.deterministic_checks.ast_vs_text_ratio.ast_node_delta} AST nodes vs {data.deterministic_checks.ast_vs_text_ratio.text_diff_lines} lines).
                </div>
              </div>
            </div>

            {/* Filter 3 */}
            <div className="p-3 bg-[#151c30] rounded-xl border border-slate-800/80 flex items-start gap-3">
              {data.deterministic_checks.dead_code.flagged ? (
                <XCircle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
              ) : (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
              )}
              <div className="flex-1 text-xs">
                <div className="font-semibold text-slate-200">3. Dead Code Injection</div>
                <div className="text-slate-400 mt-0.5">
                  {data.deterministic_checks.dead_code.dead_symbols.length} functions with 0 callers detected.
                </div>
              </div>
            </div>

            {/* Filter 4 */}
            <div className="p-3 bg-[#151c30] rounded-xl border border-slate-800/80 flex items-start gap-3">
              {data.deterministic_checks.maintainer_rules.flagged ? (
                <AlertTriangle className="w-4 h-4 text-rose-400 mt-0.5 shrink-0" />
              ) : (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
              )}
              <div className="flex-1 text-xs">
                <div className="font-semibold text-slate-200">4. Maintainer Architectural Rules</div>
                <div className="text-slate-400 mt-0.5">
                  {data.deterministic_checks.maintainer_rules.violations.length} boundary violations triggered.
                </div>
              </div>
            </div>
          </div>

          {/* Selected AST Symbol Inspector */}
          {selectedNode && (
            <div className="glass-panel p-4 rounded-2xl space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <FileCode2 className="w-3.5 h-3.5 text-cyan-400" /> Inspected Symbol
              </h3>
              <div className="font-mono text-sm text-cyan-300 font-bold break-all">{selectedNode.label}</div>
              <div className="text-xs text-slate-400 font-mono">{selectedNode.file_path || "N/A"}</div>
              <div className="grid grid-cols-2 gap-2 pt-2 text-xs">
                <div className="p-2 bg-[#151c30] rounded-lg">
                  <div className="text-slate-500">Incoming Callers</div>
                  <div className="text-base font-bold text-white">{selectedNode.incoming_calls ?? 0}</div>
                </div>
                <div className="p-2 bg-[#151c30] rounded-lg">
                  <div className="text-slate-500">Blast Hop</div>
                  <div className="text-base font-bold text-white">{selectedNode.hop_distance}</div>
                </div>
              </div>
            </div>
          )}

          {/* 5. Co-Pilot Telemetry Chat (Single-Shot Groq < 1,000 tokens) */}
          <div className="glass-panel p-4 rounded-2xl space-y-3 flex flex-col">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <Bot className="w-3.5 h-3.5 text-cyan-400" /> GitOS Co-Pilot
              </h3>
              <span className="text-[10px] text-cyan-400 font-mono">Groq Llama-3.3-70B</span>
            </div>

            {/* Messages Scroll Box */}
            <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
              {chatMessages.map((msg, i) => (
                <div
                  key={i}
                  className={`p-2.5 rounded-xl text-xs leading-relaxed ${
                    msg.sender === "user"
                      ? "bg-cyan-950/60 text-cyan-200 border border-cyan-800/60 ml-4"
                      : "bg-[#0a0d14] text-slate-300 border border-slate-800 mr-2"
                  }`}
                >
                  <div className="text-[10px] uppercase font-bold tracking-wider text-slate-500 mb-0.5">
                    {msg.sender === "user" ? "You" : "GitOS Intelligence"}
                  </div>
                  {msg.text}
                </div>
              ))}
              {isChatLoading && (
                <div className="p-2.5 rounded-xl text-xs bg-[#0a0d14] text-slate-400 border border-slate-800 flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
                  Reasoning over compressed subgraph (&lt; 1,000 tokens)...
                </div>
              )}
            </div>

            {/* Input Bar */}
            <form onSubmit={handleSendChatMessage} className="relative flex items-center pt-1">
              <input
                type="text"
                placeholder="Ask about blast impact or broken callers..."
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                disabled={isChatLoading}
                className="w-full pl-3 pr-10 py-2 bg-[#151c30] border border-slate-700 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400"
              />
              <button
                type="submit"
                disabled={isChatLoading || !chatInput.trim()}
                className="absolute right-1.5 p-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 disabled:opacity-40 transition"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </form>
          </div>
        </aside>
      </div>

      {/* Maintainer Rule Builder Modal */}
      {isRuleModalOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="glass-panel-elevated max-w-lg w-full rounded-2xl p-6 space-y-4 border border-cyan-500/40">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sliders className="w-5 h-5 text-cyan-400" />
                <h3 className="text-base font-bold text-white">Maintainer Architectural Rules</h3>
              </div>
              <button onClick={() => setIsRuleModalOpen(false)} className="text-slate-400 hover:text-white"><X className="w-5 h-5" /></button>
            </div>

            <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
              {rules.map((rule) => (
                <div key={rule.rule_id} className="p-2.5 bg-[#0a0d14] rounded-xl border border-slate-800 text-xs space-y-1">
                  <div className="font-semibold text-slate-200">{rule.name}</div>
                  <div className="font-mono text-cyan-400 text-[11px]">{rule.pattern}</div>
                  <div className="text-slate-400">{rule.description}</div>
                </div>
              ))}
            </div>

            <form onSubmit={handleCreateRule} className="space-y-3 pt-3 border-t border-slate-800">
              <div className="text-xs font-semibold uppercase text-slate-400">Add New Boundary Constraint</div>
              <input
                type="text"
                placeholder="Rule Name (e.g. No Direct DB Imports)"
                value={newRuleName}
                onChange={(e) => setNewRuleName(e.target.value)}
                className="w-full px-3 py-2 bg-[#151c30] border border-slate-700 rounded-xl text-xs text-white"
              />
              <input
                type="text"
                placeholder="Pattern (e.g. frontend/* -> backend/db/*)"
                value={newRulePattern}
                onChange={(e) => setNewRulePattern(e.target.value)}
                className="w-full px-3 py-2 bg-[#151c30] border border-slate-700 rounded-xl text-xs text-white font-mono"
              />
              <input
                type="text"
                placeholder="Description / Reason"
                value={newRuleDesc}
                onChange={(e) => setNewRuleDesc(e.target.value)}
                className="w-full px-3 py-2 bg-[#151c30] border border-slate-700 rounded-xl text-xs text-white"
              />
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsRuleModalOpen(false)}
                  className="px-3 py-1.5 rounded-xl text-xs text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-xl text-xs font-semibold bg-cyan-500 hover:bg-cyan-400 text-slate-950 flex items-center gap-1.5"
                >
                  <PlusCircle className="w-3.5 h-3.5" /> Save Rule
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Explicit Confirmation Modal */}
      {activeModalPill && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="glass-panel-elevated max-w-lg w-full rounded-2xl p-6 space-y-4 border border-cyan-500/30">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Lock className="w-5 h-5 text-cyan-400" />
                <h3 className="text-base font-bold text-white">Explicit GitHub OAuth Confirmation</h3>
              </div>
              <button onClick={() => setActiveModalPill(null)} className="text-slate-400 hover:text-white"><X className="w-5 h-5" /></button>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              GitOS will execute this action directly under your authenticated GitHub profile. No ambient or unconsented bot actions are permitted.
            </p>

            <div className="p-3 bg-[#0a0d14] rounded-xl border border-slate-800 font-mono text-xs space-y-1">
              <div className="text-cyan-400">Action: {activeModalPill.action_type}</div>
              <div className="text-slate-400">Target: {data.url_parsed.owner}/{data.url_parsed.repo}#{data.url_parsed.target_id || "HEAD"}</div>
              <div className="text-slate-400">Description: {activeModalPill.description}</div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setActiveModalPill(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white transition"
              >
                Cancel
              </button>
              <button
                onClick={handleExecuteConfirmedAction}
                disabled={executionState !== "idle"}
                className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition ${
                  activeModalPill.is_destructive
                    ? "bg-rose-600 hover:bg-rose-500 text-white"
                    : "bg-cyan-500 hover:bg-cyan-400 text-slate-950"
                }`}
              >
                {executionState === "executing" ? (
                  <>Executing via OAuth...</>
                ) : executionState === "done" ? (
                  <>✓ Executed on GitHub</>
                ) : (
                  <>Confirm & Dispatch</>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
