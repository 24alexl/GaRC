from app.engine_topology.parser import topology_parser

def test_topology_parser():
    sample_text = "We have 5 PCs on 192.168.1.0/24 connected to a Synology NAS storing CUI."
    res = topology_parser.parse_natural_language_topology(sample_text)
    assert "nodes" in res
    assert "edges" in res
    assert "confidence_score" in res
    assert "cytoscape_graph" in res
    assert len(res["nodes"]) > 0

def test_user_proxmox_topology_prompt():
    prompt = "5 Windows PC on employee wifi, 1 front desk pc ethernet, 1 proxmox server for virtualization. we run a firewall. router. our storage is on the proxmox with CUI. Windows doesnt access the NAS"
    res = topology_parser.parse_natural_language_topology(prompt)
    node_names = [n["name"] for n in res["nodes"]]
    node_types = [n["type"] for n in res["nodes"]]
    
    # Verify Proxmox server extracted
    assert any("Proxmox" in name or "server" in ntype for name, ntype in zip(node_names, node_types))
    # Verify Wi-Fi and Ethernet subnets / devices extracted
    assert any("Wi-Fi" in name or "WiFi" in name for name in node_names)
    assert any("Front Desk" in name for name in node_names)
    # Verify storage & CUI extracted
    assert any(n.get("stores_cui") is True for n in res["nodes"])
    # Verify firewall extracted
    assert "firewall" in node_types

