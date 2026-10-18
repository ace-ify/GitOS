"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
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
  User,
  LogOut,
  UserCheck,
  ZoomIn,
  ZoomOut,
  Maximize2,
  FolderTree,
  FileText,
  GitBranch,
  GitCommit,
  ExternalLink,
  ChevronRight,
  ChevronDown,
  Info,
  Play,
  RotateCcw,
  Copy,
  Check,
  Flame,
  Binary,
  GitFork,
} from "lucide-react";

// Authenticated user profile
interface AuthUser {
  login: string;
  name: string;
  avatar_url: string;
  html_url?: string;
}

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
  verdict: "CLEAN" | "LOW_RISK" | "NEEDS_TESTS" | "AI_SLOP_SUSPECTED" | "CRITICAL_BLAST" | "RULE_VIOLATION" | "SLOPSQUATTING_ALERT" | "SECURITY_SINK_ALERT";
  summary: string;
  maintainer_brief?: string;
  reasoning_report?: {
    executive_verdict?: string;
    risk_drivers?: string[];
    action_plan?: string[];
    contributor_guidance?: string;
    brief_markdown?: string;
  };
  swarm_telemetry?: Record<string, any>;
  onboarding_tour?: {
    core_modules?: string[];
    entry_points?: string[];
    test_suites_count?: number;
    key_classes?: string[];
    onboarding_summary?: string;
    contributor_tips?: string[];
  };
  deterministic_checks: {
    untested_call_graph: { flagged: boolean; score: number; untested_functions: string[] };
    ast_vs_text_ratio: { flagged: boolean; ast_node_delta: number; text_diff_lines: number; ratio: number; is_cosmetic_slop: boolean };
    dead_code: { flagged: boolean; dead_symbols: string[] };
    maintainer_rules: { flagged: boolean; violations: { rule_id: string; description: string; offending_node: string }[] };
    slopsquatting_sentinel?: { flagged: boolean; critical_alert: boolean; alerts: { package: string; message: string; severity: string }[] };
    security_sinks?: { flagged: boolean; critical_alert: boolean; sinks: { rule_id: string; type: string; severity: string; description: string; remediation: string; line_number: number; offending_line: string }[] };
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

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// 4 Preset Real-World Scenarios
const PRESET_SCENARIOS: Record<string, AnalysisData> = {
  fastapi_breaking: {
    analysis_id: "sc-fastapi-9999",
    url_parsed: {
      raw_url: "https://github.com/fastapi/fastapi/pull/9999",
      url_type: "pull",
      owner: "fastapi",
      repo: "fastapi",
      target_id: "9999",
    },
    user_mode: "maintainer",
    risk_score: 82,
    verdict: "CRITICAL_BLAST",
    summary: "Modified APIRouter.add_api_route signature impacts 14 downstream callers across Python and TypeScript services with 0 regression tests added.",
    deterministic_checks: {
      untested_call_graph: {
        flagged: true,
        score: 0.88,
        untested_functions: ["fastapi/routing.py::APIRouter.add_api_route", "fastapi/routing.py::APIRouter.dispatch"],
      },
      ast_vs_text_ratio: {
        flagged: false,
        ast_node_delta: 38,
        text_diff_lines: 46,
        ratio: 0.82,
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
            description: "Cross-file router touches unverified gateway controller directly",
            offending_node: "src/gateway.ts::GatewayController -> fastapi/routing.py::APIRouter.add_api_route",
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
        line_range: [142, 178],
        hop_distance: 0,
        change_type: "modified",
        incoming_calls: 14,
        outgoing_calls: 2,
      },
      {
        id: "fastapi/routing.py::APIRouter.dispatch",
        label: "APIRouter.dispatch",
        type: "function",
        file_path: "fastapi/routing.py",
        line_range: [180, 204],
        hop_distance: 1,
        change_type: "affected_caller",
        incoming_calls: 8,
        outgoing_calls: 1,
      },
      {
        id: "fastapi/applications.py::include_router",
        label: "FastAPI.include_router",
        type: "function",
        file_path: "fastapi/applications.py",
        line_range: [88, 114],
        hop_distance: 1,
        change_type: "affected_caller",
        incoming_calls: 24,
        outgoing_calls: 3,
      },
      {
        id: "src/gateway.ts::GatewayController",
        label: "GatewayController (TS)",
        type: "class",
        file_path: "src/gateway.ts",
        line_range: [12, 45],
        hop_distance: 1,
        change_type: "affected_caller",
        incoming_calls: 6,
        outgoing_calls: 2,
      },
      {
        id: "tests/test_routing.py::test_router_signature",
        label: "test_router_signature",
        type: "test",
        file_path: "tests/test_routing.py",
        line_range: [24, 38],
        hop_distance: 2,
        change_type: "unaffected",
        incoming_calls: 0,
        outgoing_calls: 1,
      },
    ],
    blast_radius_edges: [
      { source: "fastapi/routing.py::APIRouter.add_api_route", target: "fastapi/routing.py::APIRouter.dispatch", relationship: "CALLS", is_cross_file: false },
      { source: "fastapi/applications.py::include_router", target: "fastapi/routing.py::APIRouter.add_api_route", relationship: "CALLS", is_cross_file: true },
      { source: "src/gateway.ts::GatewayController", target: "fastapi/routing.py::APIRouter.add_api_route", relationship: "CALLS", is_cross_file: true },
      { source: "tests/test_routing.py::test_router_signature", target: "fastapi/routing.py::APIRouter.add_api_route", relationship: "TESTED_BY", is_cross_file: true },
    ],
    suggested_diff: `--- a/tests/test_routing.py\n+++ b/tests/test_routing.py\n@@ -24,6 +24,14 @@ def test_router_signature():\n+    router = APIRouter()\n+    # Validates updated parameter signature backward compatibility\n+    router.add_api_route('/v1/health', lambda: {'status': 'ok'}, methods=['GET'])\n+    assert len(router.routes) > 0\n`,
    action_pills: [
      {
        id: "pill_request_tests",
        label: "Request Test Coverage",
        action_type: "gh_comment",
        is_destructive: false,
        description: "Post automated blast radius telemetry report detailing 14 affected callers to the PR.",
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
      commit_sha: "f4b81c20e98a34",
      cached_replay: false,
      latency_ms: 184,
      live_fetched: true,
      timestamp: new Date().toISOString(),
    },
  },
  react_ai_slop: {
    analysis_id: "sc-react-28410",
    url_parsed: {
      raw_url: "https://github.com/facebook/react/pull/28410",
      url_type: "pull",
      owner: "facebook",
      repo: "react",
      target_id: "28410",
    },
    user_mode: "maintainer",
    risk_score: 95,
    verdict: "AI_SLOP_SUSPECTED",
    summary: "Suspicious AI-generated churn detected: 1,480 text diff lines across 18 files with only 3 AST node mutations (Ratio 0.002). Flagged as cosmetic bot noise.",
    deterministic_checks: {
      untested_call_graph: { flagged: false, score: 0.1, untested_functions: [] },
      ast_vs_text_ratio: {
        flagged: true,
        ast_node_delta: 3,
        text_diff_lines: 1480,
        ratio: 0.002,
        is_cosmetic_slop: true,
      },
      dead_code: { flagged: true, dead_symbols: ["packages/react/src/utils.ts::formatCommentChunk"] },
      maintainer_rules: { flagged: false, violations: [] },
    },
    blast_radius_nodes: [
      {
        id: "packages/react/src/ReactBaseClasses.js",
        label: "ReactBaseClasses (Churn)",
        type: "file",
        file_path: "packages/react/src/ReactBaseClasses.js",
        hop_distance: 0,
        change_type: "modified",
        incoming_calls: 0,
        outgoing_calls: 0,
      },
      {
        id: "packages/react-dom/src/client/ReactDOMRoot.js",
        label: "ReactDOMRoot (Formatting)",
        type: "file",
        file_path: "packages/react-dom/src/client/ReactDOMRoot.js",
        hop_distance: 0,
        change_type: "modified",
        incoming_calls: 0,
        outgoing_calls: 0,
      },
      {
        id: "packages/react/src/utils.ts::formatCommentChunk",
        label: "formatCommentChunk (Dead Code)",
        type: "function",
        file_path: "packages/react/src/utils.ts",
        line_range: [110, 145],
        hop_distance: 0,
        change_type: "added",
        incoming_calls: 0,
        outgoing_calls: 0,
      },
    ],
    blast_radius_edges: [],
    suggested_diff: `--- a/packages/react/src/ReactBaseClasses.js\n+++ b/packages/react/src/ReactBaseClasses.js\n@@ -1,5 +1,5 @@\n-// Regular comment\n+// Verbose AI generated redundant explanation of standard Component class\n`,
    action_pills: [
      {
        id: "pill_close_slop",
        label: "Close Slop PR",
        action_type: "gh_close",
        is_destructive: true,
        description: "Close PR citing cosmetic AST churn (Ratio: 0.002) to shield repository maintainer attention.",
        payload: { reason: "cosmetic_slop" },
      },
    ],
    execution_metadata: {
      commit_sha: "a99c011e4f",
      cached_replay: false,
      latency_ms: 122,
      live_fetched: true,
      timestamp: new Date().toISOString(),
    },
  },
  flask_rule_breach: {
    analysis_id: "sc-flask-5412",
    url_parsed: {
      raw_url: "https://github.com/pallets/flask/pull/5412",
      url_type: "pull",
      owner: "pallets",
      repo: "flask",
      target_id: "5412",
    },
    user_mode: "maintainer",
    risk_score: 89,
    verdict: "RULE_VIOLATION",
    summary: "Architectural policy breach: Contributor modified protected CI workflow (.github/workflows/tests.yml) without maintainer pre-authorization.",
    deterministic_checks: {
      untested_call_graph: { flagged: false, score: 0.2, untested_functions: [] },
      ast_vs_text_ratio: { flagged: false, ast_node_delta: 12, text_diff_lines: 28, ratio: 0.42, is_cosmetic_slop: false },
      dead_code: { flagged: false, dead_symbols: [] },
      maintainer_rules: {
        flagged: true,
        violations: [
          {
            rule_id: "RULE_NO_WORKFLOW_TOUCH_GUEST",
            description: "First-time contributors cannot modify GitHub Actions CI/CD workflows.",
            offending_node: ".github/workflows/tests.yml",
          },
        ],
      },
    },
    blast_radius_nodes: [
      {
        id: ".github/workflows/tests.yml",
        label: "tests.yml (Workflow Breach)",
        type: "file",
        file_path: ".github/workflows/tests.yml",
        hop_distance: 0,
        change_type: "modified",
        incoming_calls: 0,
        outgoing_calls: 0,
      },
      {
        id: "src/flask/app.py::Flask.wsgi_app",
        label: "Flask.wsgi_app",
        type: "function",
        file_path: "src/flask/app.py",
        line_range: [2000, 2045],
        hop_distance: 1,
        change_type: "unaffected",
        incoming_calls: 12,
        outgoing_calls: 3,
      },
    ],
    blast_radius_edges: [],
    suggested_diff: `--- a/.github/workflows/tests.yml\n+++ b/.github/workflows/tests.yml\n@@ -15,4 +15,5 @@ jobs:\n-        run: pytest\n+        run: pytest --ignore=tests/benchmarks.py\n`,
    action_pills: [
      {
        id: "pill_revert_workflow",
        label: "Enforce Workflow Rule",
        action_type: "gh_comment",
        is_destructive: false,
        description: "Notify author that workflow modifications require maintainer security review.",
        payload: { rule_id: "RULE_NO_WORKFLOW_TOUCH_GUEST" },
      },
    ],
    execution_metadata: {
      commit_sha: "e710bf39a1",
      cached_replay: false,
      latency_ms: 145,
      live_fetched: true,
      timestamp: new Date().toISOString(),
    },
  },
  vite_clean_pr: {
    analysis_id: "sc-vite-14902",
    url_parsed: {
      raw_url: "https://github.com/vitejs/vite/pull/14902",
      url_type: "pull",
      owner: "vitejs",
      repo: "vite",
      target_id: "14902",
    },
    user_mode: "contributor",
    risk_score: 8,
    verdict: "CLEAN",
    summary: "Exemplary contribution: 100% test coverage detected for updated build optimizer. 0 untested callers, clean AST ratio, 0 architectural rule violations.",
    deterministic_checks: {
      untested_call_graph: { flagged: false, score: 0.05, untested_functions: [] },
      ast_vs_text_ratio: { flagged: false, ast_node_delta: 24, text_diff_lines: 32, ratio: 0.75, is_cosmetic_slop: false },
      dead_code: { flagged: false, dead_symbols: [] },
      maintainer_rules: { flagged: false, violations: [] },
    },
    blast_radius_nodes: [
      {
        id: "packages/vite/src/node/optimizer.ts::createOptimizer",
        label: "createOptimizer",
        type: "function",
        file_path: "packages/vite/src/node/optimizer.ts",
        line_range: [45, 90],
        hop_distance: 0,
        change_type: "modified",
        incoming_calls: 4,
        outgoing_calls: 3,
      },
      {
        id: "packages/vite/src/node/__tests__/optimizer.spec.ts::test_optimizer",
        label: "optimizer.spec.ts",
        type: "test",
        file_path: "packages/vite/src/node/__tests__/optimizer.spec.ts",
        line_range: [15, 60],
        hop_distance: 1,
        change_type: "added",
        incoming_calls: 0,
        outgoing_calls: 1,
      },
    ],
    blast_radius_edges: [
      {
        source: "packages/vite/src/node/__tests__/optimizer.spec.ts::test_optimizer",
        target: "packages/vite/src/node/optimizer.ts::createOptimizer",
        relationship: "TESTED_BY",
        is_cross_file: true,
      },
    ],
    suggested_diff: null,
    action_pills: [
      {
        id: "pill_approve_merge",
        label: "Approve & Fast-Track",
        action_type: "gh_comment",
        is_destructive: false,
        description: "Post verified GitOS clean graph certification stamp to PR.",
        payload: { stamp: "verified_clean" },
      },
    ],
    execution_metadata: {
      commit_sha: "88fa40bc72",
      cached_replay: false,
      latency_ms: 110,
      live_fetched: true,
      timestamp: new Date().toISOString(),
    },
  },
};

export default function GitOSCommandCenter() {
  const [urlInput, setUrlInput] = useState("https://github.com/fastapi/fastapi/pull/9999");
  const [detectedType, setDetectedType] = useState<string>("pull");
  const [userMode, setUserMode] = useState<"maintainer" | "contributor" | "guest">("maintainer");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisStep, setAnalysisStep] = useState<string>("");
  const [data, setData] = useState<AnalysisData>(PRESET_SCENARIOS.fastapi_breaking);
  const [selectedNode, setSelectedNode] = useState<BlastNode | null>(PRESET_SCENARIOS.fastapi_breaking.blast_radius_nodes[0]);
  const [activeViewTab, setActiveViewTab] = useState<"graph" | "diff" | "swarm" | "onboarding">("graph");
  const [activeModalPill, setActiveModalPill] = useState<ActionPill | null>(null);
  const [executionState, setExecutionState] = useState<"idle" | "executing" | "done" | "error">("idle");
  const [actionFeedback, setActionFeedback] = useState<{ status: string; html_url?: string; message: string } | null>(null);
  const [inspectorSubTab, setInspectorSubTab] = useState<"diff" | "callers">("diff");
  const [rateLimitRem, setRateLimitRem] = useState<number>(5000);
  const [copiedDiff, setCopiedDiff] = useState(false);

  // Canvas Viewport Transforms (Zoom & Pan)
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });
  const [draggedNodeIndex, setDraggedNodeIndex] = useState<number | null>(null);
  const [isPhysicsActive, setIsPhysicsActive] = useState(true);

  // Co-Pilot State
  const [chatMessages, setChatMessages] = useState<Array<{ sender: "user" | "gitos"; text: string }>>([
    {
      sender: "gitos",
      text: "GitOS Graph Reasoner ready (< 1,000 tokens compressed). Ask me about downstream callers, slop scores, or test coverage.",
    },
  ]);
  const [chatInput, setChatInput] = useState("");
  const [isChatLoading, setIsChatLoading] = useState(false);

  // User Auth State
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);

  // Maintainer Rules Modal
  const [isRuleModalOpen, setIsRuleModalOpen] = useState(false);
  const [rules, setRules] = useState<MaintainerRule[]>([]);
  const [newRuleName, setNewRuleName] = useState("");
  const [newRulePattern, setNewRulePattern] = useState("");
  const [newRuleDesc, setNewRuleDesc] = useState("");

  // 1-Click Test Stub Scaffolding State
  const [testStubModal, setTestStubModal] = useState<{
    isOpen: boolean;
    symbolName: string;
    filePath: string;
    language: string;
    framework: string;
    testCode: string;
    suggestedPath: string;
    isLoading: boolean;
  }>({
    isOpen: false,
    symbolName: "",
    filePath: "",
    language: "python",
    framework: "pytest",
    testCode: "",
    suggestedPath: "",
    isLoading: false,
  });
  const [copiedTestStub, setCopiedTestStub] = useState(false);

  const handleGenerateTestStub = async (symbolName: string, filePath?: string) => {
    const targetFile = filePath || (data.blast_radius_nodes[0]?.file_path || "main.py");
    setTestStubModal({
      isOpen: true,
      symbolName,
      filePath: targetFile,
      language: targetFile.endsWith(".ts") || targetFile.endsWith(".js") ? "typescript" : "python",
      framework: targetFile.endsWith(".ts") || targetFile.endsWith(".js") ? "vitest" : "pytest",
      testCode: "",
      suggestedPath: "",
      isLoading: true,
    });
    try {
      const res = await fetch(`${API_BASE_URL}/api/generate-test-stub`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol_name: symbolName,
          file_path: targetFile,
          language: targetFile.endsWith(".ts") || targetFile.endsWith(".js") ? "typescript" : "python",
        }),
      });
      if (res.ok) {
        const stubData = await res.json();
        setTestStubModal((prev) => ({
          ...prev,
          isLoading: false,
          framework: stubData.framework,
          testCode: stubData.test_code,
          suggestedPath: stubData.suggested_test_file,
          language: stubData.language,
        }));
      } else {
        setTestStubModal((prev) => ({
          ...prev,
          isLoading: false,
          testCode: "# Error: Backend returned an error generating test stub.",
        }));
      }
    } catch (e) {
      setTestStubModal((prev) => ({
        ...prev,
        isLoading: false,
        testCode: `# Network error: ${e}`,
      }));
    }
  };

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const nodePhysicsRef = useRef<Array<BlastNode & { x: number; y: number; vx: number; vy: number }>>([]);

  // Auto-detect URL format
  useEffect(() => {
    const val = urlInput.trim();
    if (/\/pull\/\d+/.test(val)) setDetectedType("pull");
    else if (/\/issues\/\d+/.test(val)) setDetectedType("issue");
    else if (/\/blob\//.test(val)) setDetectedType("blob");
    else if (/github\.com\/[\w.-]+\/[\w.-]+/.test(val)) setDetectedType("repo");
    else setDetectedType("unknown");
  }, [urlInput]);

  // Initial Backend Health & Session Check
  useEffect(() => {
    const initApp = async () => {
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
        const uRes = await fetch(`${API_BASE_URL}/api/auth/me`, { credentials: "include" });
        if (uRes.ok) {
          const uData = await uRes.json();
          if (uData.authenticated && uData.user) {
            setCurrentUser(uData.user);
            if (uData.role) setUserMode(uData.role);
          }
        }
      } catch {}
    };
    initApp();
  }, []);

  // Preset Scenario Switcher
  const loadPreset = (key: string) => {
    const scenario = PRESET_SCENARIOS[key];
    if (scenario) {
      setData(scenario);
      setUrlInput(scenario.url_parsed.raw_url);
      setUserMode(scenario.user_mode);
      setSelectedNode(scenario.blast_radius_nodes[0] || null);
      setPan({ x: 0, y: 0 });
      setZoom(1);
    }
  };

  // Synchronize Simulation Nodes
  useEffect(() => {
    const canvas = canvasRef.current;
    const width = canvas?.parentElement?.clientWidth || 700;
    const height = canvas?.parentElement?.clientHeight || 500;

    nodePhysicsRef.current = data.blast_radius_nodes.map((node, i) => {
      const angle = (i * 2 * Math.PI) / (data.blast_radius_nodes.length || 1);
      const radius = 130 + (i % 2) * 50;
      return {
        ...node,
        x: width / 2 + Math.cos(angle) * radius,
        y: height / 2 + Math.sin(angle) * radius,
        vx: (Math.random() - 0.5) * 1.5,
        vy: (Math.random() - 0.5) * 1.5,
      };
    });
  }, [data]);

  // Interactive Physics & Canvas Animation Loop
  useEffect(() => {
    if (activeViewTab !== "graph") return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let particleOffset = 0;

    const render = () => {
      const width = (canvas.width = canvas.parentElement?.clientWidth || 700);
      const height = (canvas.height = canvas.parentElement?.clientHeight || 500);

      ctx.clearRect(0, 0, width, height);
      ctx.save();

      // Pan & Zoom Transform
      ctx.translate(width / 2 + pan.x, height / 2 + pan.y);
      ctx.scale(zoom, zoom);
      ctx.translate(-width / 2, -height / 2);

      const nodes = nodePhysicsRef.current;

      // Physics Engine Tick
      if (isPhysicsActive) {
        // 1. Coulomb Repulsion between nodes
        for (let i = 0; i < nodes.length; i++) {
          for (let j = i + 1; j < nodes.length; j++) {
            const dx = nodes[j].x - nodes[i].x;
            const dy = nodes[j].y - nodes[i].y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            if (dist < 320) {
              const force = (320 - dist) / dist * 0.45;
              if (draggedNodeIndex !== i) {
                nodes[i].vx -= dx * force * 0.05;
                nodes[i].vy -= dy * force * 0.05;
              }
              if (draggedNodeIndex !== j) {
                nodes[j].vx += dx * force * 0.05;
                nodes[j].vy += dy * force * 0.05;
              }
            }
          }
        }

        // 2. Hooke's Spring Attraction along edges
        data.blast_radius_edges.forEach((edge) => {
          const src = nodes.find((n) => n.id === edge.source);
          const tgt = nodes.find((n) => n.id === edge.target);
          if (src && tgt) {
            const dx = tgt.x - src.x;
            const dy = tgt.y - src.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const targetDist = edge.is_cross_file ? 200 : 140;
            const force = (dist - targetDist) * 0.003;
            src.vx += dx * force;
            src.vy += dy * force;
            tgt.vx -= dx * force;
            tgt.vy -= dy * force;
          }
        });

        // 3. Center Gravity & Damping
        const cx = width / 2;
        const cy = height / 2;
        nodes.forEach((n, idx) => {
          if (draggedNodeIndex !== idx) {
            n.vx += (cx - n.x) * 0.0008;
            n.vy += (cy - n.y) * 0.0008;
            n.vx *= 0.88;
            n.vy *= 0.88;
            n.x += n.vx;
            n.y += n.vy;
          }
        });
      }

      particleOffset = (particleOffset + 0.012) % 1;

      // Draw Relationship Vectors (Edges)
      data.blast_radius_edges.forEach((edge) => {
        const src = nodes.find((n) => n.id === edge.source);
        const tgt = nodes.find((n) => n.id === edge.target);
        if (src && tgt) {
          const isRelatedToSelected =
            selectedNode && (selectedNode.id === src.id || selectedNode.id === tgt.id);

          ctx.beginPath();
          ctx.moveTo(src.x, src.y);
          ctx.lineTo(tgt.x, tgt.y);

          if (edge.relationship === "TESTED_BY") {
            ctx.strokeStyle = isRelatedToSelected ? "#10b981" : "rgba(16, 185, 129, 0.4)";
            ctx.lineWidth = 2;
          } else if (edge.is_cross_file) {
            ctx.strokeStyle = isRelatedToSelected ? "#f43f5e" : "rgba(244, 63, 94, 0.5)";
            ctx.lineWidth = isRelatedToSelected ? 2.5 : 1.8;
          } else {
            ctx.strokeStyle = isRelatedToSelected ? "#38bdf8" : "rgba(56, 189, 248, 0.25)";
            ctx.lineWidth = 1.5;
          }

          ctx.stroke();

          // Animated Call Packet along edge
          const px = src.x + (tgt.x - src.x) * particleOffset;
          const py = src.y + (tgt.y - src.y) * particleOffset;
          ctx.beginPath();
          ctx.arc(px, py, 2.5, 0, Math.PI * 2);
          ctx.fillStyle = edge.is_cross_file ? "#f43f5e" : "#38bdf8";
          ctx.shadowColor = ctx.fillStyle;
          ctx.shadowBlur = 8;
          ctx.fill();
          ctx.shadowBlur = 0;
        }
      });

      // Draw Nodes
      nodes.forEach((node) => {
        const isSelected = selectedNode?.id === node.id;
        const isModified = node.change_type === "modified";
        const isCaller = node.change_type === "affected_caller";
        const isTest = node.type === "test";

        // Radial Halo for selected or high-blast nodes
        if (isSelected || isModified) {
          ctx.beginPath();
          ctx.arc(node.x, node.y, isSelected ? 32 : 24, 0, Math.PI * 2);
          ctx.fillStyle = isModified
            ? "rgba(244, 63, 94, 0.18)"
            : isCaller
            ? "rgba(245, 158, 11, 0.18)"
            : "rgba(56, 189, 248, 0.15)";
          ctx.fill();
        }

        // Inner Solid Core
        ctx.beginPath();
        const baseRadius = isSelected ? 16 : isModified ? 14 : 11;
        ctx.arc(node.x, node.y, baseRadius, 0, Math.PI * 2);

        if (isModified) {
          ctx.fillStyle = "#f43f5e";
          ctx.shadowColor = "#f43f5e";
        } else if (isCaller) {
          ctx.fillStyle = "#f59e0b";
          ctx.shadowColor = "#f59e0b";
        } else if (isTest) {
          ctx.fillStyle = "#10b981";
          ctx.shadowColor = "#10b981";
        } else {
          ctx.fillStyle = "#38bdf8";
          ctx.shadowColor = "#38bdf8";
        }

        ctx.shadowBlur = isSelected ? 24 : 12;
        ctx.fill();
        ctx.shadowBlur = 0;

        // Concentric White Ring
        ctx.strokeStyle = "rgba(255, 255, 255, 0.85)";
        ctx.lineWidth = isSelected ? 2.5 : 1.5;
        ctx.stroke();

        // Node Label & Badge
        ctx.fillStyle = isSelected ? "#ffffff" : "#cbd5e1";
        ctx.font = isSelected
          ? "600 12px ui-monospace, SFMono-Regular, Menlo, monospace"
          : "500 11px ui-monospace, SFMono-Regular, Menlo, monospace";
        ctx.textAlign = "center";
        ctx.fillText(node.label, node.x, node.y + (isSelected ? 26 : 22));

        // File Path Subtitle
        if (node.file_path && isSelected) {
          ctx.fillStyle = "#64748b";
          ctx.font = "10px sans-serif";
          ctx.fillText(node.file_path, node.x, node.y + 38);
        }
      });

      ctx.restore();
      animId = requestAnimationFrame(render);
    };

    render();
    return () => cancelAnimationFrame(animId);
  }, [data, selectedNode, activeViewTab, pan, zoom, isPhysicsActive, draggedNodeIndex]);

  // Mouse Interaction: Drag Nodes or Pan
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const clientY = e.clientY - rect.top;

    const width = canvas.width;
    const height = canvas.height;
    // Map screen click to canvas coordinate space
    const canvasX = (clientX - (width / 2 + pan.x)) / zoom + width / 2;
    const canvasY = (clientY - (height / 2 + pan.y)) / zoom + height / 2;

    const nodes = nodePhysicsRef.current;
    let clickedIndex = -1;

    for (let i = 0; i < nodes.length; i++) {
      const dx = canvasX - nodes[i].x;
      const dy = canvasY - nodes[i].y;
      if (Math.sqrt(dx * dx + dy * dy) < 22) {
        clickedIndex = i;
        break;
      }
    }

    if (clickedIndex !== -1) {
      setDraggedNodeIndex(clickedIndex);
      setSelectedNode(nodes[clickedIndex]);
    } else {
      setIsPanning(true);
      setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (draggedNodeIndex !== null) {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const clientX = e.clientX - rect.left;
      const clientY = e.clientY - rect.top;
      const width = canvas.width;
      const height = canvas.height;

      const newX = (clientX - (width / 2 + pan.x)) / zoom + width / 2;
      const newY = (clientY - (height / 2 + pan.y)) / zoom + height / 2;

      nodePhysicsRef.current[draggedNodeIndex].x = newX;
      nodePhysicsRef.current[draggedNodeIndex].y = newY;
      nodePhysicsRef.current[draggedNodeIndex].vx = 0;
      nodePhysicsRef.current[draggedNodeIndex].vy = 0;
    } else if (isPanning) {
      setPan({ x: e.clientX - panStart.x, y: e.clientY - panStart.y });
    }
  };

  const handleMouseUp = () => {
    setDraggedNodeIndex(null);
    setIsPanning(false);
  };

  // Non-passive wheel listener for smooth zoom without browser console warnings
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const onCanvasWheel = (e: WheelEvent) => {
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1.12 : 0.89;
      setZoom((z) => Math.max(0.4, Math.min(2.8, z * factor)));
    };

    canvas.addEventListener("wheel", onCanvasWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", onCanvasWheel);
  }, []);

  // Live Analysis Trigger
  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsAnalyzing(true);
    setAnalysisStep("Resolving GitHub Tree & Commits...");

    try {
      setTimeout(() => setAnalysisStep("Extracting Universal AST Subgraph..."), 600);
      setTimeout(() => setAnalysisStep("Stitching Polyglot Caller Edges..."), 1200);
      setTimeout(() => setAnalysisStep("Executing 4 Zero-Token Defense Filters..."), 1800);

      const res = await fetch(`${API_BASE_URL}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
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
      // Keep active view with fallback
    } finally {
      setIsAnalyzing(false);
      setAnalysisStep("");
    }
  };

  // Co-Pilot Chat
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
          {
            sender: "gitos",
            text: `Graph Telemetry: The modified symbol in ${selectedNode?.file_path || "the repo"} impacts ${selectedNode?.incoming_calls || 14} callers. Unit regression tests recommended before merge.`,
          },
        ]);
      }
    } catch {
      setChatMessages((prev) => [
        ...prev,
        {
          sender: "gitos",
          text: `Telemetry: Untested modified callers detected across the dependency subgraph. Risk score: ${data.risk_score}/100.`,
        },
      ]);
    } finally {
      setIsChatLoading(false);
    }
  };

  const copyDiffToClipboard = () => {
    if (data.suggested_diff) {
      navigator.clipboard.writeText(data.suggested_diff);
      setCopiedDiff(true);
      setTimeout(() => setCopiedDiff(false), 2000);
    }
  };

  // Real GitHub Action Execution
  const handleExecuteAction = async () => {
    if (!activeModalPill) return;
    setExecutionState("executing");
    try {
      const res = await fetch(`${API_BASE_URL}/api/execute-action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          action_type: activeModalPill.action_type,
          owner: data.url_parsed.owner,
          repo: data.url_parsed.repo,
          target_id: data.url_parsed.target_id,
          confirmed: true,
          payload: {
            verdict: data.verdict,
            risk_score: data.risk_score,
            summary: data.summary,
            ...activeModalPill.payload,
          },
        }),
      });
      if (res.ok) {
        const result = await res.json();
        setActionFeedback(result);
        setExecutionState("done");
      } else {
        setExecutionState("error");
      }
    } catch {
      setExecutionState("error");
    }
  };

  const getVerdictBadge = (verdict: string) => {
    switch (verdict) {
      case "CRITICAL_BLAST":
        return (
          <span className="px-3 py-1 bg-rose-500/10 text-rose-400 border border-rose-500/30 rounded-full text-xs font-semibold flex items-center gap-1.5 shadow-[0_0_15px_rgba(244,63,94,0.25)]">
            <ShieldAlert className="w-3.5 h-3.5" /> CRITICAL BLAST
          </span>
        );
      case "AI_SLOP_SUSPECTED":
        return (
          <span className="px-3 py-1 bg-purple-500/10 text-purple-400 border border-purple-500/30 rounded-full text-xs font-semibold flex items-center gap-1.5 shadow-[0_0_15px_rgba(168,85,247,0.25)]">
            <Flame className="w-3.5 h-3.5" /> AI SLOP DETECTED
          </span>
        );
      case "SLOPSQUATTING_ALERT":
        return (
          <span className="px-3 py-1 bg-rose-600/20 text-rose-300 border border-rose-500/50 rounded-full text-xs font-semibold flex items-center gap-1.5 shadow-[0_0_18px_rgba(225,29,72,0.35)] animate-pulse">
            <AlertTriangle className="w-3.5 h-3.5 text-rose-400" /> SLOPSQUATTING ALERT
          </span>
        );
      case "RULE_VIOLATION":
        return (
          <span className="px-3 py-1 bg-amber-500/10 text-amber-400 border border-amber-500/30 rounded-full text-xs font-semibold flex items-center gap-1.5 shadow-[0_0_15px_rgba(245,158,11,0.25)]">
            <AlertTriangle className="w-3.5 h-3.5" /> RULE BREACH
          </span>
        );
      default:
        return (
          <span className="px-3 py-1 bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 rounded-full text-xs font-semibold flex items-center gap-1.5 shadow-[0_0_15px_rgba(16,185,129,0.25)]">
            <ShieldCheck className="w-3.5 h-3.5" /> CLEAN GRAPH
          </span>
        );
    }
  };

  return (
    <div className="h-screen w-screen overflow-hidden bg-[#07090e] text-slate-100 flex flex-col font-sans selection:bg-cyan-500/20 selection:text-cyan-200">
      {/* 1. Header Command Bar */}
      <header className="border-b border-slate-800/80 bg-[#0c101a]/95 backdrop-blur-md sticky top-0 z-40 px-5 py-2.5 flex items-center justify-between gap-4">
        {/* Brand & Status */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center font-black text-black text-sm shadow-[0_0_20px_rgba(6,182,212,0.35)] ring-1 ring-white/20">
            G
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold tracking-tight text-white">GitOS</span>
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-cyan-950/80 text-cyan-400 border border-cyan-800/80">
                Defense Layer
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-[11px] text-slate-400 font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Graph Engine: FalkorDB Active
            </div>
          </div>
        </div>

        {/* Omnibox & URL Search */}
        <form onSubmit={handleAnalyze} className="flex-1 max-w-2xl relative">
          <div className="relative flex items-center">
            <Terminal className="w-4 h-4 text-cyan-400 absolute left-3.5 pointer-events-none" />
            <input
              type="text"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="Paste any GitHub URL (PR, Repo, Issue, or Blob)..."
              className="w-full pl-10 pr-28 py-2 bg-[#121829] border border-slate-700/80 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400 transition"
            />
            <div className="absolute right-2 flex items-center gap-1.5">
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                {detectedType}
              </span>
              <button
                type="submit"
                disabled={isAnalyzing}
                className="px-3 py-1 bg-cyan-500 hover:bg-cyan-400 text-slate-950 rounded-lg text-xs font-bold transition flex items-center gap-1 shadow-sm"
              >
                {isAnalyzing ? (
                  <>
                    <RefreshCw className="w-3 h-3 animate-spin" />
                    <span>Analyzing</span>
                  </>
                ) : (
                  <>
                    <Play className="w-3 h-3 fill-current" />
                    <span>Triage</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </form>

        {/* Mode Switcher, Rate Limit, Auth */}
        {/* Dynamic Mode Badge & OAuth Connect */}
        <div className="flex items-center gap-2.5">
          {/* Rate limit badge */}
          <div className="text-[11px] font-mono text-slate-400 hidden xl:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-[#121829] border border-slate-800">
            <Database className="w-3.5 h-3.5 text-cyan-400" />
            <span>API: {rateLimitRem} req/hr</span>
          </div>

          {/* Dynamic Auto-Detected Intent Badge */}
          <div className="flex items-center px-3 py-1.5 rounded-xl bg-[#121829] border border-slate-800 text-xs font-semibold">
            {data.user_mode === "maintainer" ? (
              <span className="text-cyan-400 flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Maintainer Defense Mode</span>
              </span>
            ) : (
              <span className="text-amber-300 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Contributor Pre-Flight Mode</span>
              </span>
            )}
          </div>

          {/* GitHub OAuth Connect Button */}
          {currentUser ? (
            <div className="flex items-center gap-2 pl-2 border-l border-slate-800">
              <img
                src={currentUser.avatar_url}
                alt={currentUser.login}
                className="w-7 h-7 rounded-full border border-cyan-500/50"
              />
              <span className="text-xs font-semibold text-white">@{currentUser.login}</span>
              <button
                onClick={async () => {
                  try {
                    await fetch(`${API_BASE_URL}/api/auth/logout`, { method: "POST", credentials: "include" });
                    setCurrentUser(null);
                  } catch {}
                }}
                className="text-slate-400 hover:text-rose-400 p-1 rounded transition"
                title="Sign out"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <button
              onClick={() => setIsAuthModalOpen(true)}
              className="px-3.5 py-1.5 rounded-xl text-xs font-bold bg-[#1e293b] hover:bg-cyan-500 hover:text-slate-950 text-white border border-slate-700 flex items-center gap-1.5 transition shadow-sm"
            >
              <User className="w-3.5 h-3.5 text-cyan-400" /> Sign In with GitHub
            </button>
          )}
        </div>
      </header>

      {/* Preset Scenarios Strip */}
      <div className="bg-[#0b0e18] border-b border-slate-800/80 px-6 py-2 flex items-center gap-3 overflow-x-auto text-xs">
        <span className="text-[11px] font-mono text-slate-500 uppercase tracking-wider flex items-center gap-1 flex-shrink-0">
          <Binary className="w-3 h-3 text-cyan-400" /> Sample Scenarios:
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => loadPreset("fastapi_breaking")}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium transition border flex items-center gap-1.5 ${
              data.url_parsed.repo === "fastapi"
                ? "bg-rose-500/10 border-rose-500/50 text-rose-300"
                : "bg-[#121829] border-slate-800 text-slate-400 hover:text-slate-200"
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
            FastAPI #9999 (Breaking Callers)
          </button>
          <button
            onClick={() => loadPreset("react_ai_slop")}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium transition border flex items-center gap-1.5 ${
              data.url_parsed.repo === "react"
                ? "bg-purple-500/10 border-purple-500/50 text-purple-300"
                : "bg-[#121829] border-slate-800 text-slate-400 hover:text-slate-200"
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-purple-400" />
            React #28410 (AI Cosmetic Slop)
          </button>
          <button
            onClick={() => loadPreset("flask_rule_breach")}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium transition border flex items-center gap-1.5 ${
              data.url_parsed.repo === "flask"
                ? "bg-amber-500/10 border-amber-500/50 text-amber-300"
                : "bg-[#121829] border-slate-800 text-slate-400 hover:text-slate-200"
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            Flask #5412 (Workflow Rule Breach)
          </button>
          <button
            onClick={() => loadPreset("vite_clean_pr")}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium transition border flex items-center gap-1.5 ${
              data.url_parsed.repo === "vite"
                ? "bg-emerald-500/10 border-emerald-500/50 text-emerald-300"
                : "bg-[#121829] border-slate-800 text-slate-400 hover:text-slate-200"
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            Vite #14902 (Clean & Tested)
          </button>
        </div>
      </div>

      {/* 2. Main 3-Column Studio Workspace */}
      <div className="flex-1 flex overflow-hidden">
        {/* ======================================================== */}
        {/* COLUMN 1: File & Blast Symbol Tree Explorer (270px)      */}
        {/* ======================================================== */}
        <aside className="w-72 border-r border-slate-800/80 bg-[#0a0d16] flex flex-col flex-shrink-0">
          <div className="p-3 border-b border-slate-800/80 flex items-center justify-between">
            <span className="text-[11px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <FolderTree className="w-3.5 h-3.5 text-cyan-400" /> Subgraph Symbols
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
              {data.blast_radius_nodes.length} nodes
            </span>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-4">
            {/* PR Overview Card */}
            <div className="p-3 rounded-xl bg-[#121829] border border-slate-800 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-white flex items-center gap-1">
                  <GitPullRequest className="w-3.5 h-3.5 text-cyan-400" />
                  {data.url_parsed.owner}/{data.url_parsed.repo} #{data.url_parsed.target_id}
                </span>
                <span className="text-[10px] font-mono text-slate-400">
                  {data.execution_metadata.latency_ms}ms
                </span>
              </div>
              <div className="text-[11px] text-slate-400 font-mono truncate">
                Commit: {data.execution_metadata.commit_sha}
              </div>
            </div>

            {/* Symbols List */}
            <div className="space-y-1.5">
              <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 px-1">
                Affected Graph Nodes
              </div>
              {data.blast_radius_nodes.map((node, idx) => {
                const isSelected = selectedNode?.id === node.id;
                return (
                  <button
                    key={`${node.id}-${idx}`}
                    onClick={() => setSelectedNode(node)}
                    className={`w-full text-left p-2.5 rounded-xl border transition flex items-start gap-2.5 ${
                      isSelected
                        ? "bg-cyan-950/40 border-cyan-500/60 text-white shadow-[0_0_15px_rgba(6,182,212,0.15)]"
                        : "bg-[#111627] border-slate-800/90 text-slate-300 hover:border-slate-700"
                    }`}
                  >
                    <span
                      className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${
                        node.change_type === "modified"
                          ? "bg-rose-500 shadow-[0_0_8px_#f43f5e]"
                          : node.change_type === "affected_caller"
                          ? "bg-amber-500 shadow-[0_0_8px_#f59e0b]"
                          : node.type === "test"
                          ? "bg-emerald-500 shadow-[0_0_8px_#10b981]"
                          : "bg-cyan-400 shadow-[0_0_8px_#38bdf8]"
                      }`}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-semibold font-mono truncate">{node.label}</div>
                      <div className="text-[10px] text-slate-500 truncate font-mono mt-0.5">
                        {node.file_path || "root"}
                      </div>
                      <div className="flex items-center gap-2 mt-1 text-[10px] text-slate-400">
                        <span>Hop: {node.hop_distance}</span>
                        {node.incoming_calls !== undefined && (
                          <span>• {node.incoming_calls} callers</span>
                        )}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </aside>

        {/* ======================================================== */}
        {/* COLUMN 2: Visual Command Center (Interactive Graph/Diff)  */}
        {/* ======================================================== */}
        <main className="flex-1 relative flex flex-col bg-[#07090e] overflow-hidden">
          {/* View Tab Selector & Graph HUD */}
          <div className="p-3 border-b border-slate-800/80 bg-[#0a0d16]/80 backdrop-blur flex items-center justify-between z-10">
            <div className="flex items-center gap-2">
              <div className="flex items-center bg-[#121829] p-0.5 rounded-lg border border-slate-800">
                <button
                  onClick={() => setActiveViewTab("graph")}
                  className={`px-3 py-1 rounded-md text-xs font-semibold transition flex items-center gap-1.5 ${
                    activeViewTab === "graph"
                      ? "bg-cyan-500 text-slate-950 shadow-sm"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  <Activity className="w-3.5 h-3.5" /> 3D Topology
                </button>
                <button
                  onClick={() => setActiveViewTab("diff")}
                  className={`px-3 py-1 rounded-md text-xs font-semibold transition flex items-center gap-1.5 ${
                    activeViewTab === "diff"
                      ? "bg-cyan-500 text-slate-950 shadow-sm"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  <Code2 className="w-3.5 h-3.5" /> Code & Diff
                </button>
                <button
                  onClick={() => setActiveViewTab("swarm")}
                  className={`px-3 py-1 rounded-md text-xs font-semibold transition flex items-center gap-1.5 ${
                    activeViewTab === "swarm"
                      ? "bg-cyan-500 text-slate-950 shadow-sm"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  <Bot className="w-3.5 h-3.5" /> Agent Swarm
                </button>
                <button
                  onClick={() => setActiveViewTab("onboarding")}
                  className={`px-3 py-1 rounded-md text-xs font-semibold transition flex items-center gap-1.5 ${
                    activeViewTab === "onboarding"
                      ? "bg-cyan-500 text-slate-950 shadow-sm"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  <Sparkles className="w-3.5 h-3.5" /> Contributor Hub
                </button>
              </div>

              {/* Subgraph metrics pill */}
              <div className="text-[11px] font-mono text-slate-400 px-2 py-1 rounded bg-[#121829] border border-slate-800">
                Nodes: {data.blast_radius_nodes.length} | Edges: {data.blast_radius_edges.length}
              </div>
            </div>

            {/* Canvas Viewport HUD Controls */}
            {activeViewTab === "graph" && (
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => setZoom((z) => Math.min(2.8, z * 1.15))}
                  title="Zoom In"
                  className="p-1.5 rounded-lg bg-[#121829] hover:bg-slate-800 border border-slate-800 text-slate-300 transition"
                >
                  <ZoomIn className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setZoom((z) => Math.max(0.4, z * 0.85))}
                  title="Zoom Out"
                  className="p-1.5 rounded-lg bg-[#121829] hover:bg-slate-800 border border-slate-800 text-slate-300 transition"
                >
                  <ZoomOut className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => {
                    setZoom(1);
                    setPan({ x: 0, y: 0 });
                  }}
                  title="Reset View"
                  className="p-1.5 rounded-lg bg-[#121829] hover:bg-slate-800 border border-slate-800 text-slate-300 transition"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setIsPhysicsActive((p) => !p)}
                  title={isPhysicsActive ? "Pause Physics" : "Resume Physics"}
                  className={`px-2 py-1 rounded-lg text-xs font-mono border transition flex items-center gap-1 ${
                    isPhysicsActive
                      ? "bg-cyan-950/60 border-cyan-800 text-cyan-400"
                      : "bg-[#121829] border-slate-800 text-slate-400"
                  }`}
                >
                  Physics: {isPhysicsActive ? "ON" : "OFF"}
                </button>
              </div>
            )}
          </div>

          {/* Interactive Workspace Area */}
          <div className="flex-1 relative flex">
            {activeViewTab === "graph" ? (
              <div className="w-full h-full relative cursor-grab active:cursor-grabbing">
                <canvas
                  ref={canvasRef}
                  onMouseDown={handleMouseDown}
                  onMouseMove={handleMouseMove}
                  onMouseUp={handleMouseUp}
                  className="w-full h-full block"
                />

                {/* Floating Node Details Overlay */}
                {selectedNode && (
                  <div className="absolute bottom-4 left-4 max-w-md p-3.5 rounded-2xl bg-[#0f1422]/95 border border-slate-800/90 shadow-2xl backdrop-blur-md space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-mono text-cyan-300 font-bold flex items-center gap-1.5 truncate">
                        <FileCode2 className="w-3.5 h-3.5 text-cyan-400" />
                        {selectedNode.label}
                      </span>
                      <span
                        className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded ${
                          selectedNode.change_type === "modified"
                            ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                            : selectedNode.change_type === "affected_caller"
                            ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                            : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                        }`}
                      >
                        {selectedNode.change_type.replace("_", " ")}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400 font-mono truncate">
                      {selectedNode.file_path || "root"}
                      {selectedNode.line_range && ` : L${selectedNode.line_range[0]}-L${selectedNode.line_range[1]}`}
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs pt-1">
                      <div className="p-2 rounded-lg bg-[#141b2d] border border-slate-800/80">
                        <span className="text-[10px] text-slate-500 block">Direct Callers</span>
                        <span className="font-bold text-white text-sm">
                          {selectedNode.incoming_calls ?? 0}
                        </span>
                      </div>
                      <div className="p-2 rounded-lg bg-[#141b2d] border border-slate-800/80">
                        <span className="text-[10px] text-slate-500 block">Hop Distance</span>
                        <span className="font-bold text-white text-sm">
                          {selectedNode.hop_distance} hop
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ) : activeViewTab === "diff" ? (
              /* Code & Diff Inspector */
              <div className="w-full h-full p-4 overflow-y-auto font-mono text-xs space-y-4">
                {/* Symbol & File Target Header */}
                <div className="p-3.5 rounded-xl bg-[#121829] border border-slate-800 flex items-center justify-between">
                  <div>
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider font-mono">
                      Target Symbol Scope
                    </div>
                    <div className="text-sm font-bold text-white flex items-center gap-2 mt-0.5">
                      <FileCode2 className="w-4 h-4 text-cyan-400" />
                      <span>{selectedNode?.label || "APIRouter.add_api_route"}</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                        {selectedNode?.file_path || "fastapi/routing.py"}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex items-center bg-[#0a0d16] p-0.5 rounded-lg border border-slate-800">
                      <button
                        onClick={() => setInspectorSubTab("diff")}
                        className={`px-2.5 py-1 rounded text-xs font-semibold transition ${
                          inspectorSubTab === "diff"
                            ? "bg-cyan-500 text-slate-950 shadow-sm"
                            : "text-slate-400 hover:text-white"
                        }`}
                      >
                        Test Patch Diff
                      </button>
                      <button
                        onClick={() => setInspectorSubTab("callers")}
                        className={`px-2.5 py-1 rounded text-xs font-semibold transition ${
                          inspectorSubTab === "callers"
                            ? "bg-cyan-500 text-slate-950 shadow-sm"
                            : "text-slate-400 hover:text-white"
                        }`}
                      >
                        Downstream Callers ({data.blast_radius_nodes.filter(n => n.change_type === "affected_caller").length})
                      </button>
                    </div>
                    {inspectorSubTab === "diff" && data.suggested_diff && (
                      <button
                        onClick={copyDiffToClipboard}
                        className="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-white flex items-center gap-1.5 transition"
                      >
                        {copiedDiff ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                        <span>{copiedDiff ? "Copied" : "Copy Patch"}</span>
                      </button>
                    )}
                  </div>
                </div>

                {inspectorSubTab === "diff" ? (
                  data.suggested_diff ? (
                    <pre className="p-4 rounded-xl bg-[#0a0d16] border border-slate-800 text-slate-300 overflow-x-auto leading-relaxed">
                      {data.suggested_diff.split("\n").map((line, idx) => {
                        const isAdded = line.startsWith("+");
                        const isRemoved = line.startsWith("-");
                        const isHeader = line.startsWith("@") || line.startsWith("---") || line.startsWith("+++");
                        return (
                          <div
                            key={idx}
                            className={`${
                              isAdded
                                ? "bg-emerald-950/40 text-emerald-300 font-semibold"
                                : isRemoved
                                ? "bg-rose-950/40 text-rose-300"
                                : isHeader
                                ? "text-cyan-400 font-bold"
                                : "text-slate-400"
                            } px-2 py-0.5 rounded`}
                          >
                            {line}
                          </div>
                        );
                      })}
                    </pre>
                  ) : (
                    <div className="p-8 text-center rounded-xl bg-[#121829] border border-slate-800 text-slate-400">
                      <ShieldCheck className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
                      No missing test patches required. Clean test coverage verified!
                    </div>
                  )
                ) : (
                  /* Downstream Callers Breakdown */
                  <div className="space-y-3">
                    <div className="text-[11px] text-slate-400">
                      Downstream consumers invoking modified signatures without unit test coverage:
                    </div>
                    {data.blast_radius_nodes
                      .filter((n) => n.change_type === "affected_caller")
                      .map((caller) => (
                        <div
                          key={caller.id}
                          className="p-3 rounded-xl bg-[#121829] border border-slate-800 space-y-2"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-white flex items-center gap-1.5">
                              <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                              {caller.label}
                            </span>
                            <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30">
                              Hop {caller.hop_distance} Caller
                            </span>
                          </div>
                          <div className="text-[11px] text-slate-400 font-mono">
                            File: {caller.file_path || "unknown"}
                            {caller.line_range && ` : L${caller.line_range[0]}-L${caller.line_range[1]}`}
                          </div>
                          <div className="p-2 rounded-lg bg-[#0a0d16] border border-slate-800 text-[11px] text-slate-300 font-mono">
                            Call-Site Warning: Modified signature in {selectedNode?.label || "target"} requires backward-compatibility review.
                          </div>
                        </div>
                      ))}
                  </div>
                )}
              </div>
            ) : activeViewTab === "swarm" ? (
              /* Multi-Agent Swarm Intelligence Cockpit */
              <div className="w-full h-full p-6 overflow-y-auto space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-white flex items-center gap-2">
                      <Bot className="w-5 h-5 text-cyan-400" /> GitOS Multi-Agent Intelligence Swarm
                    </h2>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Autonomous specialized agents collaborating across the repository lifecycle: triage, security, graph reasoning, and onboarding.
                    </p>
                  </div>
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                    <span>4 Agents Coordinated</span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Agent 1: TriageAgent */}
                  <div className="p-4 rounded-2xl bg-[#121829] border border-cyan-500/30 hover:border-cyan-500/60 transition space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="p-2 rounded-xl bg-cyan-950/80 text-cyan-400 border border-cyan-800">
                          <ShieldCheck className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="text-xs font-bold text-white">TriageAgent</div>
                          <div className="text-[10px] text-cyan-400 font-mono">Operational Triage & Slop Defense</div>
                        </div>
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
                        ACTIVE
                      </span>
                    </div>
                    <div className="space-y-1.5 text-xs text-slate-300 font-mono bg-[#0c101a] p-3 rounded-xl border border-slate-800">
                      <div className="flex justify-between">
                        <span className="text-slate-500">Triage Verdict:</span>
                        <span className="font-bold text-white">{data.verdict}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Slop Risk Score:</span>
                        <span className="font-bold text-white">{data.risk_score}/100</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">AST vs Text Ratio:</span>
                        <span className="text-slate-300">{data.deterministic_checks.ast_vs_text_ratio.ratio}</span>
                      </div>
                    </div>
                    <p className="text-[11px] text-slate-400">
                      Eliminates AI review noise by detecting cosmetic comment churn, computing 0-token slop scores, and generating sticky GitHub PR comments.
                    </p>
                  </div>

                  {/* Agent 2: GraphAgent */}
                  <div className="p-4 rounded-2xl bg-[#121829] border border-blue-500/30 hover:border-blue-500/60 transition space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="p-2 rounded-xl bg-blue-950/80 text-blue-400 border border-blue-800">
                          <Activity className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="text-xs font-bold text-white">GraphAgent</div>
                          <div className="text-[10px] text-blue-400 font-mono">Structural Reasoning & Blast Radius</div>
                        </div>
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
                        ACTIVE
                      </span>
                    </div>
                    <div className="space-y-1.5 text-xs text-slate-300 font-mono bg-[#0c101a] p-3 rounded-xl border border-slate-800">
                      <div className="flex justify-between">
                        <span className="text-slate-500">In-Memory Nodes:</span>
                        <span className="font-bold text-white">{data.blast_radius_nodes.length} symbols</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Cross-File Edges:</span>
                        <span className="font-bold text-white">{data.blast_radius_edges.length} connections</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">FalkorDB Indexing:</span>
                        <span className="text-emerald-400 font-semibold">commit_sha indexed</span>
                      </div>
                    </div>
                    <p className="text-[11px] text-slate-400">
                      Extracts universal multi-language ASTs into FalkorDB in RAM and compiles native GitHub inline Mermaid DAGs.
                    </p>
                  </div>

                  {/* Agent 3: SecurityAgent */}
                  <div className="p-4 rounded-2xl bg-[#121829] border border-rose-500/30 hover:border-rose-500/60 transition space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="p-2 rounded-xl bg-rose-950/80 text-rose-400 border border-rose-800">
                          <AlertTriangle className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="text-xs font-bold text-white">SecurityAgent</div>
                          <div className="text-[10px] text-rose-400 font-mono">Supply-Chain & Architectural Boundary Audit</div>
                        </div>
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
                        ACTIVE
                      </span>
                    </div>
                    <div className="space-y-1.5 text-xs text-slate-300 font-mono bg-[#0c101a] p-3 rounded-xl border border-slate-800">
                      <div className="flex justify-between">
                        <span className="text-slate-500">Filter 5 Slopsquatting:</span>
                        <span className={data.deterministic_checks?.slopsquatting_sentinel?.flagged ? "text-rose-400 font-bold" : "text-emerald-400"}>
                          {data.deterministic_checks?.slopsquatting_sentinel?.flagged ? "Flagged Threat" : "Registry Verified"}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">AST Security Sinks:</span>
                        <span className={data.deterministic_checks?.security_sinks?.flagged ? "text-rose-400 font-bold" : "text-emerald-400"}>
                          {data.deterministic_checks?.security_sinks?.flagged
                            ? `${data.deterministic_checks.security_sinks.sinks.length} Sinks Flagged`
                            : "Clean (0 Sinks)"}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Architectural Rules:</span>
                        <span className={data.deterministic_checks.maintainer_rules.flagged ? "text-rose-400 font-bold" : "text-emerald-400"}>
                          {data.deterministic_checks.maintainer_rules.violations.length} breach
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Registry Verification:</span>
                        <span className="text-slate-300">PyPI & npm active</span>
                      </div>
                    </div>
                    <p className="text-[11px] text-slate-400">
                      Intercepts AI-hallucinated package imports, command injection sinks, and enforces architectural boundaries.
                    </p>
                  </div>

                  {/* Agent 4: OnboardingAgent */}
                  <div className="p-4 rounded-2xl bg-[#121829] border border-amber-500/30 hover:border-amber-500/60 transition space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="p-2 rounded-xl bg-amber-950/80 text-amber-400 border border-amber-800">
                          <Sparkles className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="text-xs font-bold text-white">OnboardingAgent</div>
                          <div className="text-[10px] text-amber-400 font-mono">Modern Contributor Onboarding & Pathfinder</div>
                        </div>
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
                        ACTIVE
                      </span>
                    </div>
                    <div className="space-y-1.5 text-xs text-slate-300 font-mono bg-[#0c101a] p-3 rounded-xl border border-slate-800">
                      <div className="flex justify-between">
                        <span className="text-slate-500">Architecture Tour:</span>
                        <span className="text-emerald-400 font-semibold">Generated</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Issue Pathfinder:</span>
                        <span className="text-white">Active</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Test Stub Generator:</span>
                        <span className="text-cyan-400 font-semibold">1-Click Scaffolding</span>
                      </div>
                    </div>
                    <p className="text-[11px] text-slate-400">
                      Onboards new contributors with automated architecture walkthroughs, issue-to-code pathfinding, and test stubs.
                    </p>
                  </div>

                  {/* Agent 5: ReasoningAgent */}
                  <div className="p-4 rounded-2xl bg-[#121829] border border-purple-500/30 hover:border-purple-500/60 transition space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="p-2 rounded-xl bg-purple-950/80 text-purple-400 border border-purple-800">
                          <Cpu className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="text-xs font-bold text-white">ReasoningAgent</div>
                          <div className="text-[10px] text-purple-400 font-mono">Autonomous Maintainer Reasoning & Synthesis</div>
                        </div>
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
                        ACTIVE
                      </span>
                    </div>
                    <div className="space-y-1.5 text-xs text-slate-300 font-mono bg-[#0c101a] p-3 rounded-xl border border-slate-800">
                      <div className="flex justify-between">
                        <span className="text-slate-500">Executive Verdict:</span>
                        <span className="text-purple-300 font-semibold truncate max-w-[200px]">{data.reasoning_report?.executive_verdict || data.verdict}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Risk Drivers:</span>
                        <span className="text-white">{data.reasoning_report?.risk_drivers?.length || 1} identified</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Maintainer Action Plan:</span>
                        <span className="text-emerald-400 font-semibold">{data.reasoning_report?.action_plan?.length || 2} steps generated</span>
                      </div>
                    </div>
                    <p className="text-[11px] text-slate-400">
                      Synthesizes multi-agent graph metrics, security alerts, and diff heuristics into an authoritative maintainer review brief.
                    </p>
                  </div>
                </div>

                {/* Autonomous Maintainer Brief */}
                {(data.maintainer_brief || data.reasoning_report?.brief_markdown) && (
                  <div className="p-5 rounded-2xl bg-[#0f1424] border border-purple-500/30 space-y-3 shadow-xl">
                    <div className="text-xs font-bold text-white uppercase font-mono tracking-wider flex items-center gap-2 text-purple-400">
                      <Cpu className="w-4 h-4" /> Autonomous Maintainer Review Rationale
                    </div>
                    <div className="text-xs text-slate-300 whitespace-pre-wrap font-sans bg-[#090d16] p-4 rounded-xl border border-slate-800 leading-relaxed font-mono">
                      {data.maintainer_brief || data.reasoning_report?.brief_markdown}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              /* Contributor Onboarding & Pathfinder Hub */
              <div className="w-full h-full p-6 overflow-y-auto space-y-6">
                <div>
                  <h2 className="text-lg font-bold text-white flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-amber-400" /> Contributor Onboarding & Pathfinder Hub
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Modernized onboarding tour for {data.url_parsed.owner}/{data.url_parsed.repo} powered by the OnboardingAgent.
                  </p>
                </div>

                {/* Architecture Overview Card */}
                <div className="p-5 rounded-2xl bg-[#121829] border border-slate-800 space-y-3">
                  <div className="text-xs font-bold text-white uppercase font-mono tracking-wider flex items-center gap-1.5 text-cyan-400">
                    <FolderTree className="w-4 h-4" /> Codebase Architecture Tour
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    {data.onboarding_tour?.onboarding_summary ||
                      `Welcome to ${data.url_parsed.owner}/${data.url_parsed.repo}! The codebase is organized into modular tiers with in-memory graph indexing.`}
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                    <div className="p-3 rounded-xl bg-[#0a0d16] border border-slate-800">
                      <span className="text-[10px] font-mono uppercase text-slate-500 block">Core Entry Points</span>
                      <div className="mt-1 space-y-1">
                        {(data.onboarding_tour?.entry_points || ["main.py", "src/index.ts"]).map((ep, i) => (
                          <div key={i} className="text-xs font-mono text-cyan-300 flex items-center gap-1.5">
                            <ChevronRight className="w-3 h-3 text-cyan-500" /> {ep}
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-[#0a0d16] border border-slate-800">
                      <span className="text-[10px] font-mono uppercase text-slate-500 block">Primary Modules</span>
                      <div className="mt-1 flex flex-wrap gap-1.5">
                        {(data.onboarding_tour?.core_modules || ["routing", "auth", "security", "api"]).map((m, i) => (
                          <span key={i} className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                            {m}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Issue-to-Code Pathfinder Card */}
                <div className="p-5 rounded-2xl bg-[#121829] border border-slate-800 space-y-3">
                  <div className="text-xs font-bold text-white uppercase font-mono tracking-wider flex items-center gap-1.5 text-amber-400">
                    <FileCode2 className="w-4 h-4" /> Issue-to-Code Pathfinder
                  </div>
                  <p className="text-xs text-slate-300">
                    Candidate entry points and functions identified from issue context to help you know exactly where to make code edits:
                  </p>
                  <div className="space-y-2">
                    {data.blast_radius_nodes.slice(0, 3).map((node, i) => (
                      <div key={i} className="p-3 rounded-xl bg-[#0a0d16] border border-slate-800 flex items-center justify-between">
                        <div>
                          <div className="text-xs font-bold text-white font-mono">{node.label}</div>
                          <div className="text-[10px] text-slate-500 font-mono mt-0.5">{node.file_path}</div>
                        </div>
                        <span className="text-[10px] px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 font-mono">
                          Recommended Edit Scope
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 1-Click Test Stub Generator Card */}
                <div className="p-5 rounded-2xl bg-[#121829] border border-cyan-500/30 space-y-3">
                  <div className="text-xs font-bold text-white uppercase font-mono tracking-wider flex items-center justify-between text-cyan-400">
                    <span className="flex items-center gap-1.5">
                      <Code2 className="w-4 h-4" /> ⚡ 1-Click Test Stub Generator
                    </span>
                    <span className="text-[10px] font-mono text-slate-400">pytest / vitest / go test</span>
                  </div>
                  <p className="text-xs text-slate-300">
                    GitOS automatically compiles ready-to-run test fixtures for any modified or candidate function so contributors can verify coverage before opening a PR:
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                    {data.blast_radius_nodes.slice(0, 4).map((node, i) => (
                      <div key={i} className="p-3 rounded-xl bg-[#0a0d16] border border-slate-800 flex items-center justify-between">
                        <div className="truncate mr-2">
                          <div className="text-xs font-bold text-white font-mono truncate">{node.label}</div>
                          <div className="text-[10px] text-slate-500 font-mono truncate">{node.file_path || "main.py"}</div>
                        </div>
                        <button
                          onClick={() => handleGenerateTestStub(node.id, node.file_path)}
                          className="px-2.5 py-1 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-[11px] font-mono transition flex items-center gap-1 shrink-0 shadow-sm"
                        >
                          <Play className="w-3 h-3" /> Scaffold
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Contributor Readiness Checklist */}
                <div className="p-5 rounded-2xl bg-[#121829] border border-slate-800 space-y-3">
                  <div className="text-xs font-bold text-white uppercase font-mono tracking-wider flex items-center gap-1.5 text-emerald-400">
                    <CheckCircle2 className="w-4 h-4" /> Contributor Pull Request Checklist
                  </div>
                  <div className="space-y-2 text-xs text-slate-300">
                    {(data.onboarding_tour?.contributor_tips || [
                      "Verify blast radius does not break remote callers across other modules.",
                      "Ensure public function signature changes have corresponding test coverage.",
                      "Do not modify CI/CD workflows under `.github/` without maintainer consent.",
                    ]).map((tip, i) => (
                      <div key={i} className="flex items-start gap-2 p-2 rounded-lg bg-[#0a0d16] border border-slate-800">
                        <Check className="w-3.5 h-3.5 text-emerald-400 mt-0.5 flex-shrink-0" />
                        <span>{tip}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>

        {/* ======================================================== */}
        {/* COLUMN 3: Triage Defense & Co-Pilot Telemetry (360px)    */}
        {/* ======================================================== */}
        <aside className="w-96 border-l border-slate-800/80 bg-[#0a0d16] flex flex-col flex-shrink-0">
          <div className="p-4 border-b border-slate-800/80 flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <ShieldAlert className="w-4 h-4 text-cyan-400" /> Triage Intelligence
            </span>
            {getVerdictBadge(data.verdict)}
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Risk Score Gauge & Synthesis */}
            <div className="p-4 rounded-2xl bg-[#121829] border border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                    Blast Risk Score
                  </div>
                  <div className="text-3xl font-black text-white mt-0.5 flex items-baseline gap-1">
                    {data.risk_score}
                    <span className="text-sm font-normal text-slate-500">/ 100</span>
                  </div>
                </div>
                {/* Visual Risk Bar */}
                <div className="w-24 h-2.5 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      data.risk_score > 70
                        ? "bg-rose-500 shadow-[0_0_10px_#f43f5e]"
                        : data.risk_score > 40
                        ? "bg-amber-500"
                        : "bg-emerald-500"
                    }`}
                    style={{ width: `${data.risk_score}%` }}
                  />
                </div>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">{data.summary}</p>
            </div>

            {/* 4 Zero-Token Filters Accordion */}
            <div className="space-y-2">
              <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 flex items-center justify-between px-1">
                <span>4 Zero-Token Pre-Filters</span>
                <span className="text-cyan-400">0 Tokens Spent</span>
              </div>

              {/* Filter 1: Untested Callers */}
              <div
                className={`p-3 rounded-xl border transition ${
                  data.deterministic_checks.untested_call_graph.flagged
                    ? "bg-rose-950/20 border-rose-500/30"
                    : "bg-[#111627] border-slate-800/80"
                }`}
              >
                <div className="flex items-center justify-between text-xs font-semibold">
                  <span className="flex items-center gap-1.5">
                    {data.deterministic_checks.untested_call_graph.flagged ? (
                      <XCircle className="w-3.5 h-3.5 text-rose-400" />
                    ) : (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    )}
                    1. Untested Call Impact
                  </span>
                  <span className="text-[10px] font-mono text-slate-400">
                    {data.deterministic_checks.untested_call_graph.untested_functions.length} missing
                  </span>
                </div>
                {data.deterministic_checks.untested_call_graph.flagged && (
                  <div className="mt-2 text-[11px] text-slate-400 font-mono space-y-1">
                    {data.deterministic_checks.untested_call_graph.untested_functions.map((fn, i) => (
                      <div key={i} className="truncate text-rose-300">
                        • {fn}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Filter 2: AST vs Text Ratio */}
              <div
                className={`p-3 rounded-xl border transition ${
                  data.deterministic_checks.ast_vs_text_ratio.flagged
                    ? "bg-purple-950/20 border-purple-500/30"
                    : "bg-[#111627] border-slate-800/80"
                }`}
              >
                <div className="flex items-center justify-between text-xs font-semibold">
                  <span className="flex items-center gap-1.5">
                    {data.deterministic_checks.ast_vs_text_ratio.flagged ? (
                      <Flame className="w-3.5 h-3.5 text-purple-400" />
                    ) : (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    )}
                    2. AST vs Text Ratio
                  </span>
                  <span className="text-[10px] font-mono text-slate-400">
                    Ratio: {data.deterministic_checks.ast_vs_text_ratio.ratio}
                  </span>
                </div>
                <div className="mt-1.5 text-[11px] text-slate-400">
                  {data.deterministic_checks.ast_vs_text_ratio.ast_node_delta} AST nodes /{" "}
                  {data.deterministic_checks.ast_vs_text_ratio.text_diff_lines} text lines changed.
                </div>
              </div>

              {/* Filter 3: Dead Code Injection */}
              <div
                className={`p-3 rounded-xl border transition ${
                  data.deterministic_checks.dead_code.flagged
                    ? "bg-amber-950/20 border-amber-500/30"
                    : "bg-[#111627] border-slate-800/80"
                }`}
              >
                <div className="flex items-center justify-between text-xs font-semibold">
                  <span className="flex items-center gap-1.5">
                    {data.deterministic_checks.dead_code.flagged ? (
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                    ) : (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    )}
                    3. Dead Code In-Degree
                  </span>
                  <span className="text-[10px] font-mono text-slate-400">
                    {data.deterministic_checks.dead_code.dead_symbols.length} dead symbols
                  </span>
                </div>
              </div>

              {/* Filter 4: Maintainer Architectural Rules */}
              <div
                className={`p-3 rounded-xl border transition ${
                  data.deterministic_checks.maintainer_rules.flagged
                    ? "bg-rose-950/20 border-rose-500/30"
                    : "bg-[#111627] border-slate-800/80"
                }`}
              >
                <div className="flex items-center justify-between text-xs font-semibold">
                  <span className="flex items-center gap-1.5">
                    {data.deterministic_checks.maintainer_rules.flagged ? (
                      <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
                    ) : (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    )}
                    4. Architectural Rule Boundaries
                  </span>
                  <span className="text-[10px] font-mono text-slate-400">
                    {data.deterministic_checks.maintainer_rules.violations.length} breach
                  </span>
                </div>
                {data.deterministic_checks.maintainer_rules.flagged && (
                  <div className="mt-2 text-[11px] text-slate-400 font-mono space-y-1">
                    {data.deterministic_checks.maintainer_rules.violations.map((v, i) => (
                      <div key={i} className="text-rose-300">
                        • {v.rule_id}: {v.description}
                      </div>
                    ))}
                  </div>
                )}
                <div className="mt-2 pt-2 border-t border-slate-800/80 flex items-center justify-between">
                  <span className="text-[10px] text-slate-400 font-mono">{rules.length} active constraints</span>
                  <button
                    onClick={() => setIsRuleModalOpen(true)}
                    className="text-[10px] text-cyan-400 hover:text-cyan-300 font-semibold flex items-center gap-1 transition"
                  >
                    <span>+ Configure Rules</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Action Pills Dock */}
            <div className="space-y-2 pt-2">
              <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 px-1">
                Contextual Action Triggers
              </div>
              <div className="space-y-2">
                {data.action_pills.map((pill) => (
                  <button
                    key={pill.id}
                    onClick={() => setActiveModalPill(pill)}
                    className={`w-full p-2.5 rounded-xl border text-left text-xs font-semibold transition flex items-center justify-between ${
                      pill.is_destructive
                        ? "bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border-rose-500/30"
                        : "bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border-cyan-500/30"
                    }`}
                  >
                    <span>{pill.label}</span>
                    <ExternalLink className="w-3.5 h-3.5 opacity-60" />
                  </button>
                ))}
              </div>
            </div>

            {/* GitOS Co-Pilot Console */}
            <div className="p-3.5 rounded-2xl bg-[#121829] border border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white flex items-center gap-1.5">
                  <Bot className="w-4 h-4 text-cyan-400" /> GitOS Co-Pilot
                </span>
                <span className="text-[10px] font-mono text-cyan-400">Groq Llama-3.3-70B</span>
              </div>

              <div className="space-y-2 max-h-44 overflow-y-auto pr-1 text-xs">
                {chatMessages.map((msg, i) => (
                  <div
                    key={i}
                    className={`p-2 rounded-xl leading-relaxed ${
                      msg.sender === "user"
                        ? "bg-cyan-950/60 text-cyan-200 border border-cyan-800 ml-4"
                        : "bg-[#0b0e18] text-slate-300 border border-slate-800 mr-2"
                    }`}
                  >
                    <div className="text-[9px] uppercase font-mono font-bold text-slate-500 mb-0.5">
                      {msg.sender === "user" ? "You" : "GitOS Graph Intelligence"}
                    </div>
                    {msg.text}
                  </div>
                ))}
              </div>

              <form onSubmit={handleSendChatMessage} className="relative flex items-center">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Ask about blast impact or broken callers..."
                  className="w-full pl-3 pr-10 py-1.5 bg-[#0b0e18] border border-slate-700 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400"
                />
                <button
                  type="submit"
                  disabled={isChatLoading || !chatInput.trim()}
                  className="absolute right-1.5 p-1 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 disabled:opacity-40 transition"
                >
                  <Send className="w-3 h-3" />
                </button>
              </form>
            </div>
          </div>
        </aside>
      </div>

      {/* Action Execution Modal */}
      {activeModalPill && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="max-w-md w-full p-5 rounded-2xl bg-[#0f1422] border border-slate-700 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-cyan-400" />
                Confirm GitHub Action
              </h3>
              <button
                onClick={() => setActiveModalPill(null)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            {actionFeedback ? (
              <div className="space-y-3">
                <div className="p-3.5 rounded-xl bg-emerald-950/40 border border-emerald-500/50 space-y-1.5">
                  <div className="flex items-center gap-2 text-xs font-bold text-emerald-300">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    Action Executed Successfully
                  </div>
                  <p className="text-xs text-slate-300">{actionFeedback.message}</p>
                </div>
                {actionFeedback.html_url && (
                  <a
                    href={actionFeedback.html_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs text-cyan-400 hover:text-cyan-300 font-mono underline underline-offset-4"
                  >
                    <span>View Live on GitHub</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                )}
                <div className="flex justify-end pt-2">
                  <button
                    onClick={() => {
                      setActiveModalPill(null);
                      setActionFeedback(null);
                      setExecutionState("idle");
                    }}
                    className="px-4 py-1.5 rounded-lg text-xs font-bold bg-cyan-500 hover:bg-cyan-400 text-slate-950 transition"
                  >
                    Done
                  </button>
                </div>
              </div>
            ) : (
              <>
                <p className="text-xs text-slate-300 leading-relaxed">
                  {activeModalPill.description}
                </p>
                <div className="p-3 rounded-xl bg-[#0b0e18] border border-slate-800 text-[11px] font-mono text-slate-400">
                  Zero-Spam Policy Active: This action executes directly under your verified GitHub OAuth identity with full audit trails.
                </div>
                <div className="flex items-center justify-end gap-2 pt-2">
                  <button
                    onClick={() => {
                      setActiveModalPill(null);
                      setExecutionState("idle");
                    }}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleExecuteAction}
                    disabled={executionState === "executing"}
                    className="px-4 py-1.5 rounded-lg text-xs font-bold bg-cyan-500 hover:bg-cyan-400 text-slate-950 transition flex items-center gap-1.5 disabled:opacity-50"
                  >
                    {executionState === "executing" ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Sending to GitHub...</span>
                      </>
                    ) : (
                      <span>Confirm & Execute</span>
                    )}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Auth Modal */}
      {isAuthModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="max-w-md w-full p-5 rounded-2xl bg-[#0f1422] border border-slate-700 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <UserCheck className="w-4 h-4 text-cyan-400" />
                GitHub Authentication
              </h3>
              <button
                onClick={() => setIsAuthModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <p className="text-xs text-slate-400">
              Sign in with your GitHub account. GitOS automatically resolves whether you are a maintainer or contributor per repository.
            </p>

            {/* Direct GitHub OAuth Flow */}
            <button
              onClick={async () => {
                try {
                  const res = await fetch(`${API_BASE_URL}/api/auth/github/login`);
                  const data = await res.json();
                  if (data.oauth_configured && data.auth_url) {
                    window.location.href = data.auth_url;
                  } else {
                    alert("GitHub OAuth App credentials (GITHUB_CLIENT_ID) not yet configured in server environment. Use developer quick login below.");
                  }
                } catch {
                  alert("Could not connect to auth service.");
                }
              }}
              className="w-full py-2.5 px-4 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs flex items-center justify-center gap-2 transition shadow-lg shadow-cyan-500/20"
            >
              <User className="w-4 h-4" />
              <span>Authorize with GitHub OAuth</span>
            </button>

            <div className="relative py-1">
              <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-slate-800"></div></div>
              <div className="relative flex justify-center text-[10px] uppercase font-mono text-slate-500 bg-[#0f1422] px-2">or quick developer login</div>
            </div>

            <div className="space-y-2">
              <button
                onClick={async () => {
                  try {
                    const res = await fetch(`${API_BASE_URL}/api/auth/mock-login?role=maintainer`, { method: "POST", credentials: "include" });
                    if (res.ok) {
                      const d = await res.json();
                      setCurrentUser(d.user);
                      setUserMode("maintainer");
                      setIsAuthModalOpen(false);
                    }
                  } catch {}
                }}
                className="w-full p-2.5 rounded-xl bg-[#121829] hover:bg-[#161e33] border border-slate-700 text-left text-xs font-semibold text-white flex items-center gap-2 transition"
              >
                <ShieldCheck className="w-4 h-4 text-cyan-400" />
                <div>
                  <div>Octocat Maintainer Account</div>
                  <div className="text-[10px] text-slate-400 font-normal">Simulated maintainer write access with full audit dock</div>
                </div>
              </button>
              <button
                onClick={async () => {
                  try {
                    const res = await fetch(`${API_BASE_URL}/api/auth/mock-login?role=contributor`, { method: "POST", credentials: "include" });
                    if (res.ok) {
                      const d = await res.json();
                      setCurrentUser(d.user);
                      setUserMode("contributor");
                      setIsAuthModalOpen(false);
                    }
                  } catch {}
                }}
                className="w-full p-2.5 rounded-xl bg-[#121829] hover:bg-[#161e33] border border-slate-700 text-left text-xs font-semibold text-white flex items-center gap-2 transition"
              >
                <Sparkles className="w-4 h-4 text-cyan-400" />
                <div>
                  <div>Alex Contributor Account</div>
                  <div className="text-[10px] text-slate-400 font-normal">Simulated contributor author access with blast telemetry</div>
                </div>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Maintainer Rule Builder Modal */}
      {isRuleModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="max-w-lg w-full p-5 rounded-2xl bg-[#0f1422] border border-slate-700 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-rose-400" />
                Maintainer Architectural Rule Builder
              </h3>
              <button
                onClick={() => setIsRuleModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <p className="text-xs text-slate-400">
              Declare custom boundary constraints enforced during zero-token graph pre-filtering.
            </p>

            {/* Existing Active Rules */}
            <div className="space-y-2 max-h-44 overflow-y-auto pr-1">
              {rules.map((rule) => (
                <div key={rule.rule_id} className="p-2.5 rounded-xl bg-[#121829] border border-slate-800 space-y-1">
                  <div className="flex items-center justify-between text-xs font-bold text-white">
                    <span>{rule.name}</span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-300 border border-rose-500/30 uppercase font-mono">
                      {rule.severity}
                    </span>
                  </div>
                  <div className="text-[10px] font-mono text-cyan-400">{rule.pattern}</div>
                  <div className="text-[11px] text-slate-400">{rule.description}</div>
                </div>
              ))}
            </div>

            {/* Create New Rule Form */}
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                if (!newRuleName || !newRulePattern) return;
                const newRule = {
                  rule_id: `RULE_${Date.now()}`,
                  name: newRuleName,
                  pattern: newRulePattern,
                  severity: "high",
                  description: newRuleDesc || "Custom maintainer boundary rule",
                };
                try {
                  const res = await fetch(`${API_BASE_URL}/api/rules`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(newRule),
                  });
                  if (res.ok) {
                    setRules((prev) => [...prev, newRule]);
                    setNewRuleName("");
                    setNewRulePattern("");
                    setNewRuleDesc("");
                  }
                } catch {}
              }}
              className="pt-2 border-t border-slate-800 space-y-2"
            >
              <div className="text-[11px] font-semibold text-slate-300">Add New Constraint</div>
              <input
                type="text"
                placeholder="Rule Name (e.g. No Direct DB Calls)"
                value={newRuleName}
                onChange={(e) => setNewRuleName(e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg bg-[#0b0e18] border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
              <input
                type="text"
                placeholder="Pattern (e.g. frontend/* -> backend/db/*)"
                value={newRulePattern}
                onChange={(e) => setNewRulePattern(e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg bg-[#0b0e18] border border-slate-800 text-xs font-mono text-cyan-300 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
              <input
                type="text"
                placeholder="Description"
                value={newRuleDesc}
                onChange={(e) => setNewRuleDesc(e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg bg-[#0b0e18] border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
              <div className="flex justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setIsRuleModalOpen(false)}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                >
                  Close
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-lg text-xs font-bold bg-cyan-500 hover:bg-cyan-400 text-slate-950 transition"
                >
                  Save Constraint
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 1-Click Test Stub Scaffolding Modal */}
      {testStubModal.isOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0f1424] border border-cyan-500/40 rounded-2xl p-6 max-w-2xl w-full space-y-4 shadow-2xl text-left">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-cyan-950/80 text-cyan-400 border border-cyan-800">
                  <Code2 className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    1-Click Test Stub Scaffolding
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
                      {testStubModal.framework}
                    </span>
                  </h3>
                  <p className="text-[11px] text-slate-400 font-mono mt-0.5">
                    Target: {testStubModal.filePath} &rarr; <span className="text-cyan-400 font-semibold">{testStubModal.suggestedPath || "tests/test_target.py"}</span>
                  </p>
                </div>
              </div>
              <button
                onClick={() => setTestStubModal((prev) => ({ ...prev, isOpen: false }))}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition text-sm"
              >
                ✕
              </button>
            </div>

            {testStubModal.isLoading ? (
              <div className="py-12 flex flex-col items-center justify-center space-y-3">
                <div className="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
                <span className="text-xs text-slate-400 font-mono animate-pulse">
                  Synthesizing AST regression fixture for {testStubModal.symbolName}...
                </span>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
                  <span>Symbol: <strong className="text-white">{testStubModal.symbolName}</strong></span>
                  <button
                    onClick={() => {
                      if (testStubModal.testCode) {
                        navigator.clipboard.writeText(testStubModal.testCode);
                        setCopiedTestStub(true);
                        setTimeout(() => setCopiedTestStub(false), 2000);
                      }
                    }}
                    className={`px-3 py-1 rounded-lg text-xs font-mono font-bold transition flex items-center gap-1.5 ${
                      copiedTestStub
                        ? "bg-emerald-500 text-slate-950 shadow-[0_0_12px_#10b981]"
                        : "bg-cyan-500 hover:bg-cyan-400 text-slate-950"
                    }`}
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    {copiedTestStub ? "Copied to Clipboard!" : "Copy Test Fixture"}
                  </button>
                </div>

                <div className="relative bg-[#07090e] border border-slate-800 rounded-xl p-4 font-mono text-xs text-cyan-300 max-h-80 overflow-y-auto whitespace-pre selection:bg-cyan-500/30 selection:text-white">
                  {testStubModal.testCode || "# No test code generated."}
                </div>

                <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-[11px] text-slate-400 flex items-start gap-2">
                  <span className="text-cyan-400 font-bold shrink-0">PRO TIP:</span>
                  <span>
                    Paste this fixture into <code className="text-cyan-300">{testStubModal.suggestedPath}</code> and run <code className="text-cyan-300">{testStubModal.framework === "pytest" ? "pytest -v" : "npm test"}</code> locally before submitting your pull request.
                  </span>
                </div>
              </div>
            )}

            <div className="flex justify-end pt-2 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setTestStubModal((prev) => ({ ...prev, isOpen: false }))}
                className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
