from app.engine_graphrag.retriever import graphrag_retriever
from app.engine_graphrag.xai_reasoner import xai_reasoner
from app.engine_topology.schema import NetworkNode, NetworkEdge

def test_graphrag_retriever():
    query = "How do I protect CUI stored on NAS?"
    res = graphrag_retriever.retrieve_relevant_subgraph(query)
    assert "controls" in res
    assert "graph" in res
    assert len(res["graph"]["nodes"]) > 0
    assert len(res["graph"]["edges"]) > 0

def test_technical_family_subgraphs():
    fams = graphrag_retriever.get_technical_family_subgraphs()
    assert len(fams) == 5
    for code in ["03.01", "03.05", "03.08", "03.13", "03.14"]:
        assert code in fams
        assert fams[code]["control_count"] > 0
        first_ctrl = fams[code]["controls"][0]
        assert "objectives" in first_ctrl

def test_parallel_topology_audit():
    sample_nodes = [
        NetworkNode(id="fw_1", name="pfSense Firewall", type="firewall", ip_or_subnet="192.168.1.1", has_firewall_or_mfa=True),
        NetworkNode(id="nas_1", name="Synology NAS", type="storage", ip_or_subnet="192.168.1.50", stores_cui=True, has_firewall_or_mfa=False)
    ]
    sample_edges = [
        NetworkEdge(source="fw_1", target="nas_1", relationship="PROTECTS", is_encrypted=False)
    ]
    res = xai_reasoner.run_parallel_topology_audit(sample_nodes, sample_edges)
    assert res["status"] == "completed"
    assert res["total_controls_evaluated"] > 0
    assert len(res["family_scorecards"]) == 5
    assert len(res["evaluated_controls"]) > 0
    assert "cytoscape_graph" in res

def test_explain_control_finding():
    res = xai_reasoner.explain_control_finding("03.13.01", [], [])
    assert res["control_id"] == "03.13.01"
    assert "title" in res
    assert "action_for_assessor" in res

