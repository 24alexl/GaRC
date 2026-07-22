from app.engine_topology.parser import topology_parser

def test_topology_parser():
    sample_text = "We have 5 PCs on 192.168.1.0/24 connected to a Synology NAS storing CUI."
    res = topology_parser.parse_natural_language_topology(sample_text)
    assert "nodes" in res
    assert "edges" in res
    assert "confidence_score" in res
    assert "cytoscape_graph" in res
    assert len(res["nodes"]) > 0
