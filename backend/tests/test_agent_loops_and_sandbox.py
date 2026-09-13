import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.engine_topology.parser import topology_parser
from app.engine_topology.schema import NetworkNode, NetworkEdge, ClarificationPrompt

client = TestClient(app)

def test_critic_and_repair_loop_orphan_healing():
    """Verify Engine 2 Critic loop heals orphan devices by attaching them to subnets."""
    nodes = [
        NetworkNode(id="sub_lan", name="Office LAN Subnet", type="subnet", ip_or_subnet="192.168.1.0/24"),
        NetworkNode(id="dev_workstation", name="Accounting PC", type="device", ip_or_subnet="192.168.1.20"),
    ]
    edges = [] # dev_workstation has no edge
    prompts = []

    repaired_nodes, repaired_edges, repaired_prompts, critic_actions = topology_parser._critic_and_repair_loop(
        nodes, edges, prompts, "Accounting PC on Office LAN"
    )

    # Verify orphan was healed
    assert len(repaired_edges) == 1
    assert repaired_edges[0].source == "dev_workstation"
    assert repaired_edges[0].target == "sub_lan"
    assert any("Healed orphan asset" in act for act in critic_actions)

def test_critic_and_repair_loop_dangling_edge_pruning():
    """Verify Engine 2 Critic loop removes edges pointing to non-existent nodes."""
    nodes = [
        NetworkNode(id="dev_1", name="PC 1", type="device"),
    ]
    edges = [
        NetworkEdge(source="dev_1", target="non_existent_node", relationship="CONNECTS_TO")
    ]
    prompts = []

    repaired_nodes, repaired_edges, repaired_prompts, critic_actions = topology_parser._critic_and_repair_loop(
        nodes, edges, prompts, "Sample"
    )

    assert len(repaired_edges) == 0
    assert any("Pruned dangling edge" in act for act in critic_actions)

def test_critic_and_repair_loop_cui_clarification_generation():
    """Verify Engine 2 Critic loop automatically generates clarification for unencrypted CUI assets."""
    nodes = [
        NetworkNode(id="storage_nas", name="Synology NAS", type="storage", stores_cui=True, has_firewall_or_mfa=False)
    ]
    edges = []
    prompts = []

    repaired_nodes, repaired_edges, repaired_prompts, critic_actions = topology_parser._critic_and_repair_loop(
        nodes, edges, prompts, "NAS storing sensitive client files"
    )

    assert len(repaired_prompts) >= 1
    assert repaired_prompts[0].node_id == "storage_nas"
    assert "encryption" in repaired_prompts[0].question.lower()
    assert any("Generated precision encryption clarification" in act for act in critic_actions)

def test_conversational_copilot_educational_qa():
    """Verify Copilot answers general compliance and cybersecurity questions in plain English."""
    mock_llm = MagicMock()
    mock_llm.generate_structured_json.return_value = {}
    with patch("app.engine_topology.parser.get_llm_provider", return_value=mock_llm):
        res = topology_parser.conversational_copilot(
            message="What is CUI and why does my business need to protect it?",
            history=[]
        )
    assert "reply" in res
    assert len(res["reply"]) > 50
    assert "cui" in res["reply"].lower() or "unclassified" in res["reply"].lower()
    assert len(res["suggested_followups"]) > 0
    assert "kg_traces" in res
    assert len(res["kg_traces"]) > 0

def test_conversational_copilot_topology_mutation():
    """Verify Copilot extracts equipment from natural conversation and updates the topology."""
    mock_llm = MagicMock()
    mock_llm.generate_structured_json.return_value = {}
    with patch("app.engine_topology.parser.get_llm_provider", return_value=mock_llm):
        res = topology_parser.conversational_copilot(
            message="We just installed a Synology NAS for backup contracts.",
            history=[]
        )
    assert "reply" in res
    assert res["topology_updated"] is True
    node_names = [n["name"] for n in res["topology"]["nodes"]]
    assert any("NAS" in name or "Synology" in name for name in node_names)
    assert "kg_traces" in res
    assert len(res["kg_traces"]) > 0

def test_what_if_simulation_and_revert():
    """Verify What-If Sandbox applies simulation, boosts readiness score, and reverts to baseline."""
    # Seed a baseline topology
    topology_parser.load_template("clinic")
    
    # Run simulation
    sim_res = topology_parser.simulate_what_if_remediation("ENCRYPT_CUI_VOLUME")
    assert sim_res["success"] is True
    assert "score_delta" in sim_res
    assert sim_res["score_delta"] >= 0
    assert "ENCRYPT_CUI_VOLUME" in sim_res["active_fixes"]

    # Run undo / revert
    rev_res = topology_parser.revert_what_if_remediation()
    assert rev_res["success"] is True
    assert len(topology_parser.active_what_if_fixes) == 0

def test_api_endpoints_agent_loops_and_sandbox():
    """Verify FastAPI routes for Copilot chat, simulate fix, and revert fix."""
    client = TestClient(app)

    # 1. Copilot Chat endpoint
    mock_llm = MagicMock()
    mock_llm.generate_structured_json.return_value = {}
    with patch("app.engine_topology.parser.get_llm_provider", return_value=mock_llm):
        chat_res = client.post("/api/chat/copilot", json={
            "message": "What is CUI?",
            "history": []
        })
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert "reply" in chat_data
    assert "kg_traces" in chat_data

    # 2. Simulate Fix endpoint
    sim_res = client.post("/api/sandbox/simulate-fix", json={
        "fix_type": "ENFORCE_MFA"
    })
    assert sim_res.status_code == 200
    sim_data = sim_res.json()
    assert sim_data["success"] is True

    # 3. Revert Fix endpoint
    rev_res = client.post("/api/sandbox/revert-fix")
    assert rev_res.status_code == 200
    rev_data = rev_res.json()
    assert rev_data["success"] is True
