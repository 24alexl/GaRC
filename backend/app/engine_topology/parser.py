import logging
import json
import re
from typing import Dict, Any, List
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
        1. Attempts LLM structured extraction to handle complex/messy natural language prompts.
        2. Falls back to deterministic rule-based parser if LLM is unreachable or times out.
        3. Evaluates confidence scores & security attributes (MFA, CUI flag, Encryption).
        4. Identifies missing or ambiguous cybersecurity attributes & generates clarification cards.
        5. Calculates compliance readiness for gap scorecard.
        """
        logger.info(f"Engine 2: Executing network topology extraction for input: '{text[:60]}...'")
        
        nodes, edges, clarification_prompts = None, None, None
        try:
            nodes, edges, clarification_prompts = self._llm_structured_parser(text)
        except Exception as e:
            logger.warning(f"Engine 2: LLM structured parsing failed ({e}). Falling back to rule-based parser.")

        if not nodes:
            nodes, edges, clarification_prompts = self._fallback_rule_based_parser(text)

        # Update active session topology
        self.active_topology_nodes = nodes
        self.active_topology_edges = edges

        # Overall topology confidence average
        conf_scores = [n.confidence for n in nodes] + [e.confidence for e in edges]
        avg_conf = sum(conf_scores) / len(conf_scores) if conf_scores else 0.88
        requires_clarification = len(clarification_prompts) > 0 or avg_conf < 0.8

        # Format Cytoscape graph payload
        cyto_nodes = []
        cyto_edges = []

        for n in nodes:
            cyto_nodes.append({
                "data": {
                    "id": n.id,
                    "label": f"{n.name}\n({n.type.upper()})",
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

    def _llm_structured_parser(self, text: str):
        """
        Uses configured LLM provider to parse freeform natural language network descriptions
        into structured NetworkNodes, NetworkEdges, and ClarificationPrompts.
        """
        from app.llm.factory import get_llm_provider
        
        system_instruction = """You are an expert cybersecurity network architect.
Parse the user's natural language network description into a structured JSON graph according to the formal GaRC topology schema.

Schema Requirements:
Allowed Node Types: ["device", "server", "storage", "data_asset", "firewall", "user", "subnet", "cloud_service"]
Allowed Relationship Types: ["MEMBER_OF", "LOGS_IN_VIA", "ROUTES_TO", "ACCESSES", "STORES", "PROTECTS", "STORES_CUI"]

Node Rules:
- id: unique snake_case string (e.g. dev_laptops, server_win2022, storage_truenas, data_cui_files, cloud_aws)
- name: concise human readable label (e.g. "Dell Laptops", "Windows Server 2022", "TrueNAS Volume", "Client CUI Files")
- type: one of the Allowed Node Types
- os_or_system: operating system or firmware if specified (e.g. "Windows 11", "TrueNAS SCALE", "AWS S3")
- ip_or_subnet: CIDR range or IP address if specified (e.g. "192.168.1.0/24")
- stores_cui: boolean true if node stores or processes CUI or sensitive compliance data
- has_firewall_or_mfa: boolean true if firewall, EDR, or MFA is explicitly active on this asset
- confidence: float 0.0 to 1.0

Edge Rules:
- source: node id
- target: node id
- relationship: one of the Allowed Relationship Types (MEMBER_OF, LOGS_IN_VIA, ROUTES_TO, ACCESSES, STORES, PROTECTS, STORES_CUI)
- is_encrypted: boolean true if traffic/storage uses TLS, VPN, BitLocker, or volume encryption
- confidence: float 0.0 to 1.0

Clarification Rules:
Generate a clarification_prompt if security features (MFA, CUI volume encryption, firewall) are unstated or ambiguous.
"""

        schema_description = """{
  "nodes": [
    {
      "id": "dev_laptops",
      "name": "Dell Laptops",
      "type": "device",
      "os_or_system": "Windows 11",
      "ip_or_subnet": "192.168.1.0/24",
      "stores_cui": false,
      "has_firewall_or_mfa": false,
      "confidence": 0.95
    }
  ],
  "edges": [
    {
      "source": "dev_laptops",
      "target": "subnet_lan",
      "relationship": "MEMBER_OF",
      "is_encrypted": false,
      "confidence": 0.95
    }
  ],
  "clarification_prompts": [
    {
      "node_id": "storage_truenas",
      "question": "Is the TrueNAS volume encrypted with BitLocker/AES-256?",
      "property_in_question": "is_encrypted",
      "suggested_options": ["Encrypted", "Unencrypted"]
    }
  ]
}"""

        prompt = f"Parse this natural language network description into structured JSON:\n\n\"{text}\""
        
        llm = get_llm_provider()
        payload = llm.generate_structured_json(prompt, schema_description=schema_description, system_instruction=system_instruction)

        if not payload or not isinstance(payload, dict) or "nodes" not in payload:
            return None, None, None

        nodes: List[NetworkNode] = []
        edges: List[NetworkEdge] = []
        prompts: List[ClarificationPrompt] = []

        valid_node_types = {"device", "server", "storage", "data_asset", "firewall", "user", "subnet", "cloud_service"}
        valid_rel_types = {"MEMBER_OF", "LOGS_IN_VIA", "ROUTES_TO", "ACCESSES", "STORES", "PROTECTS", "STORES_CUI"}

        for raw_node in payload.get("nodes", []):
            try:
                ntype = str(raw_node.get("type", "device")).lower()
                if ntype not in valid_node_types:
                    ntype = "device"
                nodes.append(NetworkNode(
                    id=str(raw_node.get("id", "node_1")),
                    name=str(raw_node.get("name", "Network Asset")),
                    type=ntype,
                    os_or_system=str(raw_node.get("os_or_system", "Unknown")),
                    ip_or_subnet=str(raw_node.get("ip_or_subnet", "Unknown")),
                    stores_cui=bool(raw_node.get("stores_cui", False)),
                    has_firewall_or_mfa=bool(raw_node.get("has_firewall_or_mfa", False)),
                    confidence=float(raw_node.get("confidence", 0.90))
                ))
            except Exception as ne:
                logger.debug(f"Failed to parse LLM raw node: {ne}")

        node_ids = {n.id for n in nodes}

        for raw_edge in payload.get("edges", []):
            try:
                src = str(raw_edge.get("source", ""))
                tgt = str(raw_edge.get("target", ""))
                rel = str(raw_edge.get("relationship", "ACCESSES")).upper()
                if rel not in valid_rel_types:
                    rel = "ACCESSES"
                if src in node_ids and tgt in node_ids:
                    edges.append(NetworkEdge(
                        source=src,
                        target=tgt,
                        relationship=rel,
                        is_encrypted=bool(raw_edge.get("is_encrypted", False)),
                        confidence=float(raw_edge.get("confidence", 0.90))
                    ))
            except Exception as ee:
                logger.debug(f"Failed to parse LLM raw edge: {ee}")

        for raw_prompt in payload.get("clarification_prompts", []):
            try:
                prompts.append(ClarificationPrompt(
                    node_id=raw_prompt.get("node_id"),
                    edge=raw_prompt.get("edge"),
                    question=str(raw_prompt.get("question", "Please clarify asset security setting.")),
                    property_in_question=str(raw_prompt.get("property_in_question", "has_firewall_or_mfa")),
                    suggested_options=list(raw_prompt.get("suggested_options", ["Yes", "No"]))
                ))
            except Exception as pe:
                logger.debug(f"Failed to parse LLM raw prompt: {pe}")

        return nodes, edges, prompts

    def _fallback_rule_based_parser(self, text: str):
        text_lower = text.lower()
        nodes: List[NetworkNode] = []
        edges: List[NetworkEdge] = []
        prompts: List[ClarificationPrompt] = []

        # Find IP subnets or addresses using regex
        ip_matches = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?\b', text)
        ip_subnet = ip_matches[0] if ip_matches else "192.168.1.0/24"

        # 1. Subnet Node
        subnet_node_id = "subnet_lan"
        nodes.append(NetworkNode(
            id=subnet_node_id,
            name=f"LAN Subnet ({ip_subnet})",
            type="subnet",
            ip_or_subnet=ip_subnet,
            confidence=0.95
        ))

        # 2. Firewall / Gateway Node
        if any(w in text_lower for w in ["firewall", "router", "gateway", "pfsense", "fortinet", "netgear", "cisco", "meraki"]):
            fw_name = "Perimeter Firewall / Gateway"
            if "pfsense" in text_lower: fw_name = "pfSense Firewall"
            elif "fortinet" in text_lower: fw_name = "Fortinet Firewall"
            elif "meraki" in text_lower: fw_name = "Cisco Meraki Router"
            
            fw_node_id = "fw_gateway"
            nodes.append(NetworkNode(
                id=fw_node_id,
                name=fw_name,
                type="firewall",
                ip_or_subnet="192.168.1.1",
                has_firewall_or_mfa=True,
                confidence=0.95
            ))
            edges.append(NetworkEdge(source=fw_node_id, target=subnet_node_id, relationship="PROTECTS", confidence=0.95))
        else:
            prompts.append(ClarificationPrompt(
                node_id="subnet_lan",
                question="Is your local network subnet protected by a perimeter firewall or security gateway?",
                property_in_question="has_firewall_or_mfa",
                suggested_options=["Yes, stateful firewall installed", "No, direct ISP modem", "Managed Cloud Gateway"]
            ))

        # 3. Workstations / Endpoints Node
        ws_node_id = "ws_pcs"
        
        # Extract explicit count specifically associated with device/workstation/laptop/pc words (avoid matching IP octets!)
        count_match = re.search(r'\b(\d+)\s*(?:x\s*)?(?:windows|mac|macbook|dell|linux|workstation|pc|laptop|desktop|user|accountant)', text_lower)
        if count_match:
            num_pcs = f"{count_match.group(1)}x"
        elif "6" in text_lower and "6" not in ip_subnet:
            num_pcs = "6x"
        elif "8" in text_lower and "8" not in ip_subnet:
            num_pcs = "8x"
        elif "10" in text_lower and "10" not in ip_subnet:
            num_pcs = "10x"
        else:
            num_pcs = ""

        # Determine exact device form-factor and OS
        if "laptop" in text_lower or "macbook" in text_lower:
            if "windows" in text_lower: os_name = "Windows Laptops"
            elif "mac" in text_lower or "macbook" in text_lower: os_name = "MacBook Laptops"
            else: os_name = "Workstation Laptops"
        elif "windows 11" in text_lower:
            os_name = "Windows 11 Workstations"
        elif "windows" in text_lower:
            os_name = "Windows Workstations"
        elif "mac" in text_lower:
            os_name = "Mac Workstations"
        else:
            os_name = "Desktop Workstations"

        ws_name = f"{num_pcs} {os_name}".strip()

        nodes.append(NetworkNode(
            id=ws_node_id,
            name=ws_name,
            type="device",
            os_or_system=os_name,
            ip_or_subnet=ip_subnet,
            confidence=0.90
        ))
        edges.append(NetworkEdge(source=ws_node_id, target=subnet_node_id, relationship="CONNECTS_TO", confidence=0.95))

        # 4. Storage / NAS / Database Node
        has_local_storage = any(w in text_lower for w in ["nas", "storage", "synology", "qnap", "truenas", "file server", "database", "sql", "windows server", "local windows server"])
        nas_node_id = None
        has_cui = any(w in text_lower for w in ["cui", "payroll", "contracts", "sensitive", "confidential", "hipaa", "tax", "donor"])
        has_mfa = any(w in text_lower for w in ["mfa enabled", "bitlocker", "mfa active", "encrypted"])
        
        if has_local_storage:
            nas_node_id = "storage_local"
            nas_name = "Local File Server / NAS"
            if "synology" in text_lower: nas_name = "Synology NAS Storage"
            elif "qnap" in text_lower: nas_name = "QNAP NAS Storage"
            elif "truenas" in text_lower: nas_name = "TrueNAS Storage Server"
            elif "windows server" in text_lower: nas_name = "Windows Server 2022"

            nodes.append(NetworkNode(
                id=nas_node_id,
                name=nas_name,
                type="storage",
                os_or_system="Storage OS",
                ip_or_subnet="192.168.1.50",
                stores_cui=False, # Wait until we know where CUI is stored
                has_firewall_or_mfa=has_mfa,
                confidence=0.90
            ))
            edges.append(NetworkEdge(source=nas_node_id, target=subnet_node_id, relationship="CONNECTS_TO", confidence=0.95))
            edges.append(NetworkEdge(source=ws_node_id, target=nas_node_id, relationship="ACCESSES", confidence=0.90))
            
            # Local non-CUI financial/doc assets
            if "financial" in text_lower or "documents" in text_lower:
                doc_node_id = "data_financial"
                nodes.append(NetworkNode(
                    id=doc_node_id,
                    name="Financial Documents & Files",
                    type="data_asset",
                    stores_cui=False,
                    confidence=0.95
                ))
                edges.append(NetworkEdge(source=nas_node_id, target=doc_node_id, relationship="STORES", confidence=0.95))


        # 5. Cloud / VPN Gateway Node
        has_cloud = any(w in text_lower for w in ["aws", "azure", "cloud", "vpn", "openvpn"])
        cloud_node_id = None
        if has_cloud:
            cloud_node_id = "cloud_vpn"
            cloud_name = "Cloud Gateway / OpenVPN"
            if "aws" in text_lower: cloud_name = "AWS Cloud Gateway (OpenVPN)"
            elif "azure" in text_lower: cloud_name = "Azure Virtual Network"

            nodes.append(NetworkNode(
                id=cloud_node_id,
                name=cloud_name,
                type="cloud_service",
                has_firewall_or_mfa=True,
                confidence=0.85
            ))
            # Workstations connect to VPN
            edges.append(NetworkEdge(source=ws_node_id, target=cloud_node_id, relationship="CONNECTS_TO", confidence=0.90))

            # Optional: Infrastructure behind the cloud
            cloud_storage_id = "cloud_storage"
            nodes.append(NetworkNode(
                id=cloud_storage_id,
                name=f"{cloud_name.split()[0]} Storage Infrastructure",
                type="storage",
                has_firewall_or_mfa=True,
                confidence=0.85
            ))
            edges.append(NetworkEdge(source=cloud_node_id, target=cloud_storage_id, relationship="ROUTES_TO", confidence=0.90))


        # 6. CUI Data Asset Node
        if has_cui:
            cui_node_id = "cui_data"
            cui_label = "Payroll Contracts & CUI Data"
            if "hipaa" in text_lower or "patient" in text_lower: cui_label = "Patient Records & CUI"
            elif "dod" in text_lower or "cad" in text_lower: cui_label = "DoD CAD Blueprints & CUI"
            elif "tax" in text_lower: cui_label = "Tax Returns & Client CUI"
            elif "donor" in text_lower: cui_label = "Donor Files & CUI"

            nodes.append(NetworkNode(
                id=cui_node_id,
                name=cui_label,
                type="data_asset",
                stores_cui=True,
                confidence=0.95
            ))
            
            # Determine where CUI is stored
            if has_cloud and ("cloud" in text_lower[text_lower.find("cui")-20:text_lower.find("cui")+20] or "aws" in text_lower or "azure" in text_lower):
                # Stored in Cloud
                edges.append(NetworkEdge(source=cloud_storage_id, target=cui_node_id, relationship="STORES", confidence=0.95))
            elif nas_node_id:
                # Stored locally
                edges.append(NetworkEdge(source=nas_node_id, target=cui_node_id, relationship="STORES", confidence=0.95))
                if not has_mfa:
                    prompts.append(ClarificationPrompt(
                        node_id=nas_node_id,
                        question=f"Does '{nas_name}' enforce Multifactor Authentication (MFA) or AES-256 volume encryption for CUI data?",
                        property_in_question="has_firewall_or_mfa",
                        suggested_options=["Yes, MFA & Encryption active", "No encryption currently", "Unsure"]
                    ))

        return nodes, edges, prompts

    def persist_topology_to_neo4j(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Persists the user-approved topology nodes & edges to Neo4j database."""
        if neo4j_client.mock_mode or not neo4j_client.driver:
            logger.info(f"Neo4j in mock mode. Topology ({len(nodes)} nodes, {len(edges)} edges) saved in session memory.")
            return {"status": "mock_saved", "node_count": len(nodes), "edge_count": len(edges)}

        cypher_nodes = """
        UNWIND $nodes AS n
        MERGE (node:NetworkAsset {id: n.id})
        SET node.name = n.name,
            node.type = n.type,
            node.os_or_system = n.os_or_system,
            node.ip_or_subnet = n.ip_or_subnet,
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
        SET r.is_encrypted = e.is_encrypted,
            r.confidence = e.confidence
        """
        neo4j_client.execute_write(cypher_edges, {"edges": edges})

        logger.info(f"Successfully committed topology ({len(nodes)} nodes, {len(edges)} edges) to Neo4j.")
        return {"status": "persisted", "node_count": len(nodes), "edge_count": len(edges)}

topology_parser = TopologyParser()
