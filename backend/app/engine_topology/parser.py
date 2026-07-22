import logging
import json
import re
from typing import Dict, Any, List
from app.llm.factory import get_llm_provider
from app.engine_topology.schema import TopologyParseResult, NetworkNode, NetworkEdge, ClarificationPrompt
from app.db.neo4j_client import neo4j_client

logger = logging.getLogger("garc.engine2.parser")

class TopologyParser:
    def __init__(self):
        # Active session state for evaluated topologies
        self.active_topology_nodes: List[NetworkNode] = []
        self.active_topology_edges: List[NetworkEdge] = []

    def parse_natural_language_topology(self, text: str) -> Dict[str, Any]:
        """
        Engine 2 Pipeline:
        1. Translates natural language network description into structured nodes/edges.
        2. Evaluates confidence scores.
        3. Identifies missing or ambiguous cybersecurity attributes (MFA, CUI flag, encryption).
        4. Generates clarification prompts for low-confidence items.
        """
        llm = get_llm_provider()
        
        schema_desc = """
{
  "nodes": [
    {
      "id": "string (unique snake_case id e.g. dev_ws1, storage_nas, fw_gw)",
      "name": "string (human readable label)",
      "type": "device|server|storage|firewall|user|subnet|cloud_service",
      "os_or_system": "string",
      "ip_or_subnet": "string",
      "stores_cui": boolean,
      "has_firewall_or_mfa": boolean,
      "confidence": float (0.0 to 1.0)
    }
  ],
  "edges": [
    {
      "source": "string node_id",
      "target": "string node_id",
      "relationship": "CONNECTS_TO|ACCESSES|STORES|PROTECTS",
      "is_encrypted": boolean,
      "confidence": float (0.0 to 1.0)
    }
  ]
}
"""
        system_instruction = "You are a Cyber Network Topology Extractor. Extract all devices, servers, subnets, firewalls, and storage units from the natural language description into valid JSON graph nodes and edges. Respond ONLY with valid JSON."

        parsed_json = llm.generate_structured_json(text, schema_desc, system_instruction)

        nodes: List[NetworkNode] = []
        edges: List[NetworkEdge] = []
        clarification_prompts: List[ClarificationPrompt] = []

        if parsed_json and isinstance(parsed_json, dict) and "nodes" in parsed_json:
            for n in parsed_json.get("nodes", []):
                try:
                    nodes.append(NetworkNode(**n))
                except Exception as e:
                    logger.warning(f"Error parsing LLM node {n}: {e}")

            for e in parsed_json.get("edges", []):
                try:
                    edges.append(NetworkEdge(**e))
                except Exception as ex:
                    logger.warning(f"Error parsing LLM edge {e}: {ex}")

        # If LLM didn't return nodes, run regex & keyword rule extraction
        if not nodes:
            logger.info("Using smart rule-based regex parser fallback...")
            nodes, edges, clarification_prompts = self._fallback_rule_based_parser(text)
        else:
            # Check for low confidence or ambiguous properties to generate clarification prompts
            for node in nodes:
                if node.confidence < 0.8:
                    clarification_prompts.append(ClarificationPrompt(
                        node_id=node.id,
                        question=f"Does '{node.name}' process or store Controlled Unclassified Information (CUI)?",
                        property_in_question="stores_cui",
                        suggested_options=["Yes, stores CUI", "No, general business data only", "Unsure / Mixed"]
                    ))
                if node.stores_cui and not node.has_firewall_or_mfa:
                    clarification_prompts.append(ClarificationPrompt(
                        node_id=node.id,
                        question=f"Is Multifactor Authentication (MFA) or a hardware firewall enforcing access control for '{node.name}'?",
                        property_in_question="has_firewall_or_mfa",
                        suggested_options=["Yes, MFA enabled", "Yes, protected by Firewall", "No security controls currently"]
                    ))

        # Update active session topology
        self.active_topology_nodes = nodes
        self.active_topology_edges = edges

        # Overall topology confidence average
        conf_scores = [n.confidence for n in nodes] + [e.confidence for e in edges]
        avg_conf = sum(conf_scores) / len(conf_scores) if conf_scores else 0.85
        requires_clarification = len(clarification_prompts) > 0 or avg_conf < 0.8

        # Format Cytoscape graph payload
        cyto_nodes = []
        cyto_edges = []

        for n in nodes:
            cyto_nodes.append({
                "data": {
                    "id": n.id,
                    "label": f"{n.name} ({n.type})",
                    "type": n.type,
                    "confidence": n.confidence,
                    "stores_cui": n.stores_cui,
                    "has_firewall_or_mfa": n.has_firewall_or_mfa,
                    "details": f"OS: {n.os_or_system} | IP/Subnet: {n.ip_or_subnet}"
                }
            })

        for e in edges:
            cyto_edges.append({
                "data": {
                    "source": e.source,
                    "target": e.target,
                    "label": e.relationship,
                    "is_encrypted": e.is_encrypted,
                    "confidence": e.confidence
                }
            })

        result = {
            "raw_text": text,
            "nodes": [n.model_dump() for n in nodes],
            "edges": [e.model_dump() for e in edges],
            "confidence_score": round(avg_conf, 2),
            "requires_clarification": requires_clarification,
            "clarification_prompts": [cp.model_dump() for cp in clarification_prompts],
            "cytoscape_graph": {
                "nodes": cyto_nodes,
                "edges": cyto_edges
            }
        }
        return result

    def _fallback_rule_based_parser(self, text: str):
        text_lower = text.lower()
        nodes: List[NetworkNode] = []
        edges: List[NetworkEdge] = []
        prompts: List[ClarificationPrompt] = []

        # Find IP subnets or addresses using regex
        ip_matches = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?\b', text)
        ip_subnet = ip_matches[0] if ip_matches else "192.168.1.0/24"

        # Detect firewall / gateway
        if any(w in text_lower for w in ["firewall", "router", "gateway", "pfsense", "fortinet", "netgear", "cisco"]):
            nodes.append(NetworkNode(
                id="fw_gateway",
                name="Perimeter Firewall / Gateway",
                type="firewall",
                ip_or_subnet="192.168.1.1",
                has_firewall_or_mfa=True,
                confidence=0.95
            ))
        else:
            prompts.append(ClarificationPrompt(
                node_id="fw_gateway",
                question="Is your network protected by a perimeter firewall or gateway security appliance?",
                property_in_question="has_firewall_or_mfa",
                suggested_options=["Yes, stateful firewall installed", "No, direct ISP modem", "Managed Cloud Gateway"]
            ))

        # Detect workstations / endpoints
        if any(w in text_lower for w in ["pc", "workstation", "laptop", "macbook", "desktop", "computer", "windows", "staff"]):
            nodes.append(NetworkNode(
                id="ws_staff",
                name="Staff Workstations & Laptops",
                type="device",
                os_or_system="Windows 11 / macOS",
                ip_or_subnet=ip_subnet,
                confidence=0.90
            ))

        # Detect NAS / Storage / Database
        if any(w in text_lower for w in ["nas", "storage", "synology", "qnap", "file server", "database", "postgres", "sql", "payroll", "cui"]):
            has_cui = any(w in text_lower for w in ["cui", "payroll", "contracts", "sensitive", "confidential"])
            nodes.append(NetworkNode(
                id="nas_storage",
                name="Network Storage / NAS",
                type="storage",
                os_or_system="Linux RAID / NAS",
                ip_or_subnet="192.168.1.50",
                stores_cui=has_cui,
                confidence=0.75
            ))
            if has_cui:
                prompts.append(ClarificationPrompt(
                    node_id="nas_storage",
                    question="Does your Network Storage (NAS) enforce Multifactor Authentication or BitLocker encryption?",
                    property_in_question="has_firewall_or_mfa",
                    suggested_options=["Yes, MFA & Encryption active", "No encryption currently", "Unsure"]
                ))

        # Detect Cloud / Remote servers
        if any(w in text_lower for w in ["aws", "azure", "cloud", "ec2", "vpn", "openvpn", "remote"]):
            nodes.append(NetworkNode(
                id="cloud_vpn",
                name="Cloud Gateway / Remote VPN",
                type="cloud_service",
                has_firewall_or_mfa=True,
                confidence=0.85
            ))

        # Fallback default node if text was very short
        if not nodes:
            nodes.append(NetworkNode(
                id="office_endpoint",
                name="Office Workstation Network",
                type="device",
                ip_or_subnet=ip_subnet,
                confidence=0.80
            ))

        # Link nodes together
        has_fw = any(n.id == "fw_gateway" for n in nodes)
        has_ws = any(n.id == "ws_staff" for n in nodes)
        has_nas = any(n.id == "nas_storage" for n in nodes)

        if has_ws and has_nas:
            edges.append(NetworkEdge(
                source="ws_staff",
                target="nas_storage",
                relationship="ACCESSES",
                is_encrypted=False,
                confidence=0.85
            ))

        if has_fw and has_ws:
            edges.append(NetworkEdge(
                source="fw_gateway",
                target="ws_staff",
                relationship="PROTECTS",
                is_encrypted=True,
                confidence=0.95
            ))

        return nodes, edges, prompts

    def persist_topology_to_neo4j(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]):
        """Persists approved topology nodes & edges into Neo4j graph instance."""
        # Convert dict back to Pydantic objects to update active session state
        try:
            self.active_topology_nodes = [NetworkNode(**n) for n in nodes]
            self.active_topology_edges = [NetworkEdge(**e) for e in edges]
        except Exception as ex:
            logger.warning(f"Error updating active topology session: {ex}")

        if neo4j_client.mock_mode or not neo4j_client.driver:
            logger.info("Persisted topology in mock graph mode.")
            return {"status": "mock_persisted", "node_count": len(nodes)}

        cypher_nodes = """
        UNWIND $nodes AS n
        MERGE (node:NetworkAsset {id: n.id})
        SET node.name = n.name,
            node.type = n.type,
            node.stores_cui = n.stores_cui,
            node.has_firewall_or_mfa = n.has_firewall_or_mfa,
            node.confidence = n.confidence
        """
        neo4j_client.execute_write(cypher_nodes, {"nodes": nodes})

        cypher_edges = """
        UNWIND $edges AS e
        MATCH (src:NetworkAsset {id: e.source})
        MATCH (tgt:NetworkAsset {id: e.target})
        MERGE (src)-[r:CONNECTED_TO {relationship: e.relationship}]->(tgt)
        SET r.is_encrypted = e.is_encrypted
        """
        neo4j_client.execute_write(cypher_edges, {"edges": edges})

        return {"status": "persisted", "node_count": len(nodes), "edge_count": len(edges)}

topology_parser = TopologyParser()
