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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("garc.main")

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
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

@app.get("/")
def root():
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

@app.get("/api/nist-scorecard")
def nist_scorecard():
    """Generates dynamic NIST 800-171 gap analysis summary based on active topology."""
    nodes = topology_parser.active_topology_nodes
    edges = topology_parser.active_topology_edges

    if not nodes:
        return {
            "status": "Unassessed",
            "message": "No active network topology committed. Use Engine 2 to describe your organization's network setup.",
            "total_controls": 110,
            "implemented_controls": 0,
            "partial_controls": 0,
            "gap_controls": 110,
            "compliance_score_pct": 0.0,
            "family_scores": [
                {"family": "Access Control (3.1)", "score": 0, "status": "Not Assessed"},
                {"family": "Awareness & Training (3.2)", "score": 0, "status": "Not Assessed"},
                {"family": "Audit & Accountability (3.3)", "score": 0, "status": "Not Assessed"},
                {"family": "Identification & Auth (3.5)", "score": 0, "status": "Not Assessed"},
                {"family": "System & Comm Protection (3.13)", "score": 0, "status": "Not Assessed"},
                {"family": "System & Info Integrity (3.14)", "score": 0, "status": "Not Assessed"}
            ]
        }

    # Dynamic scoring evaluation
    has_mfa_or_fw = any(n.has_firewall_or_mfa for n in nodes)
    has_firewall_node = any(n.type == "firewall" for n in nodes)
    has_cui = any(n.stores_cui for n in nodes)
    cui_secured = has_cui and has_mfa_or_fw

    ac_score = 75 if has_mfa_or_fw else 30
    ia_score = 85 if has_mfa_or_fw else 20
    sc_score = 90 if has_firewall_node else (50 if has_mfa_or_fw else 25)
    si_score = 60 if has_mfa_or_fw else 30

    implemented = 0
    if has_mfa_or_fw: implemented += 25
    if has_firewall_node: implemented += 20
    if cui_secured: implemented += 15
    if len(nodes) > 1: implemented += 10

    partial = 20 if implemented > 0 else 0
    gaps = max(0, 110 - (implemented + partial))

    total_score = round(((implemented * 1.0) + (partial * 0.5)) / 110 * 100, 1)

    return {
        "status": "Assessed",
        "total_controls": 110,
        "implemented_controls": implemented,
        "partial_controls": partial,
        "gap_controls": gaps,
        "compliance_score_pct": total_score,
        "active_node_count": len(nodes),
        "family_scores": [
            {"family": "Access Control (3.1)", "score": ac_score, "status": "Good" if ac_score >= 70 else "Action Needed"},
            {"family": "Identification & Auth (3.5)", "score": ia_score, "status": "Good" if ia_score >= 70 else "Critical Gap"},
            {"family": "System & Comm Protection (3.13)", "score": sc_score, "status": "Good" if sc_score >= 70 else "Action Needed"},
            {"family": "System & Info Integrity (3.14)", "score": si_score, "status": "Action Needed" if si_score >= 50 else "Critical Gap"}
        ]
    }
