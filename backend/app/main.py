import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any

from app.config import settings
from app.db.neo4j_client import neo4j_client
from app.db.seed_nist_800_171 import seed_database
from app.engine_graphrag.xai_reasoner import xai_reasoner
from app.engine_topology.parser import topology_parser
from app.engine_topology.schema import CopilotChatRequest, WhatIfSimulateRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("garc.main")

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response
import os

app = FastAPI(
    title="GaRC - GraphRAG Automated Risk & Compliance API",
    description="Dual-Engine XAI NIST SP 800-171 Compliance & Network Topology Platform",
    version="1.0.0"
)

# CORS middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
@app.get("/app", response_class=HTMLResponse)
def serve_web_ui():
    html_path = os.path.join(static_dir, "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

class Engine1QueryRequest(BaseModel):
    query: str

class Engine2ParseRequest(BaseModel):
    text: str

class Engine2CommitRequest(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]

class ExplainControlRequest(BaseModel):
    control_id: str

class UpdateNodeRequest(BaseModel):
    node_id: str
    updates: Dict[str, Any]

class AddNodeRequest(BaseModel):
    id: str
    name: str
    type: str
    os_or_system: str = "Unknown"
    ip_or_subnet: str = "192.168.1.0/24"
    stores_cui: bool = False
    has_firewall_or_mfa: bool = False

class DeleteNodeRequest(BaseModel):
    node_id: str

class AddEdgeRequest(BaseModel):
    source: str
    target: str
    relationship: str = "CONNECTS_TO"
    is_encrypted: bool = False

class AnswerClarificationRequest(BaseModel):
    node_id: str
    property_name: str
    value: Any

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)

@app.get("/api")
def api_info():
    return {
        "service": "GaRC - GraphRAG Automated Risk & Compliance",
        "status": "online",
        "llm_provider": settings.LLM_PROVIDER,
        "neo4j_mode": "mock" if neo4j_client.mock_mode else "active"
    }

@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "db_connected": not neo4j_client.mock_mode,
        "llm_provider": settings.LLM_PROVIDER
    }

@app.get("/api/templates")
def get_templates():
    """Returns available quick-start small business templates."""
    return topology_parser.get_available_templates()

@app.post("/api/templates/load/{template_id}")
def load_template_endpoint(template_id: str):
    """Loads a small business template into active session."""
    return topology_parser.load_template(template_id)

@app.post("/api/topology/update-node")
def update_node_endpoint(req: UpdateNodeRequest):
    """Updates properties of a specific node."""
    return topology_parser.update_node(req.node_id, req.updates)

@app.post("/api/topology/add-node")
def add_node_endpoint(req: AddNodeRequest):
    """Adds a new node to the active topology."""
    return topology_parser.add_node(req.model_dump())

@app.post("/api/topology/delete-node")
def delete_node_endpoint(req: DeleteNodeRequest):
    """Deletes a node and connected edges."""
    return topology_parser.delete_node(req.node_id)

@app.post("/api/topology/clear")
def clear_topology_endpoint():
    """Clears all active topology nodes (empty workspace)."""
    return topology_parser.clear_topology()

@app.post("/api/topology/add-edge")
def add_edge_endpoint(req: AddEdgeRequest):
    """Adds a connection between two nodes."""
    return topology_parser.add_edge(req.model_dump())

@app.post("/api/topology/answer-clarification")
def answer_clarification_endpoint(req: AnswerClarificationRequest):
    """Answers a clarification prompt and updates node state."""
    return topology_parser.answer_clarification(req.node_id, req.property_name, req.value)

@app.get("/api/report/export")
def export_report_endpoint(org_name: str = "Client Organization"):
    """Generates complete structured data for executive & assessor reporting."""
    return xai_reasoner.generate_executive_report_data(org_name)

@app.post("/api/seed")
def seed_kg():
    res = seed_database()
    return res

@app.post("/api/engine1/query")
def engine1_query(req: Engine1QueryRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    res = xai_reasoner.answer_query(req.query)
    return res

@app.post("/api/engine2/parse-topology")
def engine2_parse(req: Engine2ParseRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Topology text description cannot be empty.")
    res = topology_parser.parse_natural_language_topology(req.text)
    return res

@app.post("/api/engine2/commit-topology")
def engine2_commit(req: Engine2CommitRequest):
    res = topology_parser.persist_topology_to_neo4j(req.nodes, req.edges)
    return res

@app.post("/api/chat/copilot")
def copilot_chat_endpoint(req: CopilotChatRequest):
    """
    Unified Cyber Clinic Copilot:
    Answers cybersecurity/NIST questions in plain English and incrementally mutates
    the live Cytoscape network topology with Agentic Critic validation.
    """
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    return topology_parser.conversational_copilot(req.message, req.history)

@app.post("/api/sandbox/simulate-fix")
def simulate_fix_endpoint(req: WhatIfSimulateRequest):
    """
    Interactive 'What-If' Remediation Sandbox:
    Simulates a high-impact security fix on active topology and returns recalculated scorecard.
    """
    return topology_parser.simulate_what_if_remediation(req.fix_type, req.target_node_id)

@app.post("/api/sandbox/revert-fix")
def revert_fix_endpoint():
    """
    Reverts all active What-If simulations to original topology baseline.
    """
    return topology_parser.revert_what_if_remediation()

@app.post("/api/audit/evaluate-topology")

def audit_evaluate_topology():
    """
    Executes a high-speed parallel audit across the 5 core technical families
    evaluating active topology against CPRT assessment objectives.
    """
    nodes = topology_parser.active_topology_nodes
    edges = topology_parser.active_topology_edges
    res = xai_reasoner.run_parallel_topology_audit(nodes, edges)
    return res

@app.get("/api/compliance/baseline-graph")
def get_baseline_compliance_graph():
    """
    Returns the static NIST SP 800-171 Rev 3 CPRT Knowledge Graph
    across the 5 technical families immediately without waiting for an active audit.
    """
    return xai_reasoner.get_baseline_cprt_graph()

@app.post("/api/audit/explain-control")
def audit_explain_control(req: ExplainControlRequest):
    """
    Generates single-click contextual explanation for a specific control finding.
    """
    nodes = topology_parser.active_topology_nodes
    edges = topology_parser.active_topology_edges
    res = xai_reasoner.explain_control_finding(req.control_id, nodes, edges)
    return res

@app.get("/api/nist-scorecard")
def nist_scorecard():
    """Generates dynamic NIST 800-171 gap analysis summary based on active topology."""
    nodes = topology_parser.active_topology_nodes
    edges = topology_parser.active_topology_edges

    # If audit results already exist, return high-fidelity objective metrics
    if xai_reasoner.latest_audit_result:
        audit = xai_reasoner.latest_audit_result
        return {
            "status": "Assessed",
            "total_controls": audit.get("total_controls_evaluated", 30),
            "implemented_controls": audit.get("met_count", 0),
            "partial_controls": audit.get("insufficient_data_count", 0),
            "gap_controls": audit.get("unmet_count", 0),
            "compliance_score_pct": audit.get("overall_score_pct", 0.0),
            "active_node_count": len(nodes),
            "family_scores": [
                {
                    "family": f"{f['family_name']} ({f['family_code']})",
                    "score": f["score_pct"],
                    "status": f["status"],
                    "met": f["met"],
                    "unmet": f["unmet"],
                    "insufficient_data": f["insufficient_data"]
                }
                for f in audit.get("family_scorecards", [])
            ],
            "evaluated_controls": audit.get("evaluated_controls", [])
        }

    if not nodes:
        return {
            "status": "Unassessed",
            "message": "No active network topology committed. Use Step 1 to describe your organization's network setup.",
            "total_controls": 30,
            "implemented_controls": 0,
            "partial_controls": 0,
            "gap_controls": 30,
            "compliance_score_pct": 0.0,
            "family_scores": [
                {"family": "Access Control (03.01)", "score": 0, "status": "Not Assessed"},
                {"family": "Identification & Auth (03.05)", "score": 0, "status": "Not Assessed"},
                {"family": "Media Protection (03.08)", "score": 0, "status": "Not Assessed"},
                {"family": "System & Comm Protection (03.13)", "score": 0, "status": "Not Assessed"},
                {"family": "System & Info Integrity (03.14)", "score": 0, "status": "Not Assessed"}
            ]
        }

    # Run instant evaluation if topology is present
    audit = xai_reasoner.run_parallel_topology_audit(nodes, edges)
    return {
        "status": "Assessed",
        "total_controls": audit.get("total_controls_evaluated", 30),
        "implemented_controls": audit.get("met_count", 0),
        "partial_controls": audit.get("insufficient_data_count", 0),
        "gap_controls": audit.get("unmet_count", 0),
        "compliance_score_pct": audit.get("overall_score_pct", 0.0),
        "active_node_count": len(nodes),
        "family_scores": [
            {
                "family": f"{f['family_name']} ({f['family_code']})",
                "score": f["score_pct"],
                "status": f["status"],
                "met": f["met"],
                "unmet": f["unmet"],
                "insufficient_data": f["insufficient_data"]
            }
            for f in audit.get("family_scorecards", [])
        ],
        "evaluated_controls": audit.get("evaluated_controls", [])
    }

