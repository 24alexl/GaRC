import logging
import json
import re
from typing import Dict, Any, List
from app.engine_topology.schema import TopologyParseResult, NetworkNode, NetworkEdge, ClarificationPrompt
from app.engine_topology.templates import SMALL_BIZ_TEMPLATES
from app.db.neo4j_client import neo4j_client

logger = logging.getLogger("garc.engine2.parser")

class TopologyParser:
    def __init__(self):
        # Active session state for evaluated topologies
        self.active_topology_nodes: List[NetworkNode] = []
        self.active_topology_edges: List[NetworkEdge] = []
        self.active_clarification_prompts: List[ClarificationPrompt] = []

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
- id: unique snake_case string (e.g. dev_wifi_pcs, dev_front_desk, server_proxmox, storage_nas, data_cui, fw_gateway, subnet_lan, subnet_wifi)
- name: concise human readable label (e.g. "5x Windows PCs (Wi-Fi)", "1x Front Desk PC", "Proxmox VE Hypervisor", "Proxmox Storage / NAS", "Payroll CUI Data")
- type: one of the Allowed Node Types
  * Use "server" for hypervisors, hosts, virtualization servers, domain controllers (e.g. Proxmox VE, ESXi, Hyper-V, Ubuntu Server).
  * Use "device" for client endpoints, PCs, laptops, workstations.
  * Use "storage" for NAS, SAN, shared storage volumes, ZFS pools, databases.
  * Use "data_asset" for CUI, sensitive files, contracts, financial data.
  * Use "subnet" for IP subnets, VLANs, Wi-Fi networks, wired LANs.
  * Use "firewall" for perimeter routers, firewalls, security gateways.
- os_or_system: operating system or firmware if specified (e.g. "Windows 11", "Proxmox VE", "Debian Linux", "TrueNAS SCALE")
- ip_or_subnet: CIDR range or IP address if specified (e.g. "192.168.1.0/24")
- stores_cui: boolean true if node stores or processes CUI or sensitive compliance data
- has_firewall_or_mfa: boolean true if firewall, EDR, or MFA is explicitly active on this asset
- confidence: float 0.0 to 1.0

Edge Rules:
- source: node id
- target: node id
- relationship: one of the Allowed Relationship Types (MEMBER_OF, LOGS_IN_VIA, ROUTES_TO, ACCESSES, STORES, PROTECTS, STORES_CUI)
- is_encrypted: boolean true if traffic/storage uses TLS, VPN, BitLocker, or volume encryption
- Note: If the text states a device does NOT access the NAS or storage, do NOT add an ACCESSES edge between them!

Clarification Rules:
Generate a clarification_prompt if security features (MFA, CUI volume encryption, firewall) are unstated or ambiguous.
"""

        schema_description = """{
  "nodes": [
    {
      "id": "subnet_wifi",
      "name": "Employee Wi-Fi Network",
      "type": "subnet",
      "ip_or_subnet": "192.168.2.0/24",
      "stores_cui": false,
      "has_firewall_or_mfa": false,
      "confidence": 0.95
    },
    {
      "id": "server_proxmox",
      "name": "Proxmox VE Hypervisor",
      "type": "server",
      "os_or_system": "Proxmox VE / Linux",
      "ip_or_subnet": "192.168.1.100",
      "stores_cui": false,
      "has_firewall_or_mfa": false,
      "confidence": 0.95
    },
    {
      "id": "storage_nas",
      "name": "Proxmox Storage / NAS",
      "type": "storage",
      "os_or_system": "ZFS Pool",
      "stores_cui": true,
      "has_firewall_or_mfa": false,
      "confidence": 0.95
    }
  ],
  "edges": [
    {
      "source": "server_proxmox",
      "target": "storage_nas",
      "relationship": "STORES",
      "is_encrypted": false,
      "confidence": 0.95
    }
  ],
  "clarification_prompts": [
    {
      "node_id": "storage_nas",
      "question": "Is the Proxmox CUI storage volume encrypted at rest with AES-256?",
      "property_in_question": "has_firewall_or_mfa",
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

        # 1. Subnets (Wired LAN & Wireless Wi-Fi Segments)
        has_wifi = any(w in text_lower for w in ["wifi", "wi-fi", "wireless", "ssid", "wlan"])
        has_lan = any(w in text_lower for w in ["ethernet", "wired", "lan", "switch", "cat6", "desk"]) or not has_wifi

        subnet_lan_id = "subnet_lan"
        subnet_wifi_id = "subnet_wifi"

        if has_lan:
            nodes.append(NetworkNode(
                id=subnet_lan_id,
                name=f"Wired LAN ({ip_subnet})",
                type="subnet",
                ip_or_subnet=ip_subnet,
                confidence=0.95
            ))

        if has_wifi:
            nodes.append(NetworkNode(
                id=subnet_wifi_id,
                name="Employee Wi-Fi Network",
                type="subnet",
                ip_or_subnet="192.168.2.0/24",
                confidence=0.95
            ))

        # Primary subnet reference for devices without explicit network specified
        primary_subnet_id = subnet_wifi_id if (has_wifi and not has_lan) else subnet_lan_id

        # 2. Firewall / Router / Gateway Node
        if any(w in text_lower for w in ["firewall", "router", "gateway", "pfsense", "fortinet", "netgear", "cisco", "meraki", "udm", "opnsense"]):
            fw_name = "Perimeter Firewall & Router"
            if "pfsense" in text_lower: fw_name = "pfSense Security Gateway"
            elif "opnsense" in text_lower: fw_name = "OPNsense Firewall"
            elif "fortinet" in text_lower or "fortigate" in text_lower: fw_name = "Fortinet FortiGate Firewall"
            elif "meraki" in text_lower: fw_name = "Cisco Meraki Security Appliance"
            elif "router" in text_lower and "firewall" not in text_lower: fw_name = "Network Router"
            
            fw_node_id = "fw_gateway"
            nodes.append(NetworkNode(
                id=fw_node_id,
                name=fw_name,
                type="firewall",
                ip_or_subnet="192.168.1.1",
                has_firewall_or_mfa=True,
                confidence=0.95
            ))

            if has_lan:
                edges.append(NetworkEdge(source=fw_node_id, target=subnet_lan_id, relationship="PROTECTS", confidence=0.95))
            if has_wifi:
                edges.append(NetworkEdge(source=fw_node_id, target=subnet_wifi_id, relationship="PROTECTS", confidence=0.95))
        else:
            prompts.append(ClarificationPrompt(
                node_id=primary_subnet_id,
                question="Is your local network subnet protected by a perimeter firewall or security gateway?",
                property_in_question="has_firewall_or_mfa",
                suggested_options=["Yes, stateful firewall installed", "No, direct ISP modem", "Managed Cloud Gateway"]
            ))

        # 3. Servers & Hypervisors (Proxmox, ESXi, Windows Server, Linux Server, etc.)
        has_server = any(w in text_lower for w in ["proxmox", "esxi", "hyper-v", "hypervisor", "vmware", "virtualization", "windows server", "linux server", "ubuntu server", "debian", "server", "domain controller", "active directory"])
        server_node_id = None

        if has_server:
            server_node_id = "server_host"
            server_name = "Virtualization Server"
            server_os = "Virtualization OS"

            if "proxmox" in text_lower:
                server_node_id = "server_proxmox"
                server_name = "Proxmox VE Hypervisor"
                server_os = "Proxmox VE / Debian Linux"
            elif "esxi" in text_lower or "vmware" in text_lower:
                server_node_id = "server_esxi"
                server_name = "VMware ESXi Host"
                server_os = "VMware ESXi"
            elif "hyper-v" in text_lower:
                server_node_id = "server_hyperv"
                server_name = "Hyper-V Host Server"
                server_os = "Windows Server Hyper-V"
            elif "windows server" in text_lower:
                server_node_id = "server_win2022"
                server_name = "Windows Server 2022"
                server_os = "Windows Server 2022"
            elif "ubuntu" in text_lower or "debian" in text_lower or "linux" in text_lower:
                server_node_id = "server_linux"
                server_name = "Linux Application Server"
                server_os = "Linux (Debian/Ubuntu)"

            nodes.append(NetworkNode(
                id=server_node_id,
                name=server_name,
                type="server",
                os_or_system=server_os,
                ip_or_subnet="192.168.1.100",
                has_firewall_or_mfa=False,
                confidence=0.95
            ))
            # Attach server to wired LAN
            target_sub = subnet_lan_id if has_lan else primary_subnet_id
            edges.append(NetworkEdge(source=server_node_id, target=target_sub, relationship="CONNECTS_TO", confidence=0.95))

        # 4. Multi-Cohort Endpoints & Workstations
        # Detect specific device groups: (e.g. "5 Windows PC on employee wifi", "1 front desk pc ethernet", etc.)
        device_cohorts = []

        # Check for Wi-Fi PCs / Laptops
        wifi_pc_match = re.search(r'(\d+)?\s*(?:x\s*)?(?:windows|mac|dell|linux|workstation|pc|laptop)?\s*(?:pc|pcs|laptops|workstations|computers|users)?\s*(?:on|via|connected to)?\s*(?:employee\s*)?(?:wifi|wi-fi|wireless)', text_lower)
        if wifi_pc_match and has_wifi:
            cnt = wifi_pc_match.group(1) or "5"
            device_cohorts.append({
                "id": "dev_wifi_pcs",
                "name": f"{cnt}x Windows PCs (Employee Wi-Fi)",
                "os": "Windows 11",
                "target_subnet": subnet_wifi_id
            })

        # Check for Front Desk / Reception / Admin PCs
        front_desk_match = re.search(r'(\d+)?\s*(?:x\s*)?(?:front\s*desk|reception|admin|billing|receptionist)\s*(?:pc|computer|workstation)?(?:\s*(?:ethernet|wired|lan))?', text_lower)
        if front_desk_match:
            cnt = front_desk_match.group(1) or "1"
            device_cohorts.append({
                "id": "dev_front_desk",
                "name": f"{cnt}x Front Desk PC (Ethernet)",
                "os": "Windows 11 Pro",
                "target_subnet": subnet_lan_id if has_lan else primary_subnet_id
            })

        # If no specific cohorts were matched by patterns above, use standard endpoint extractor
        if not device_cohorts:
            count_match = re.search(r'\b(\d+)\s*(?:x\s*)?(?:windows|mac|macbook|dell|linux|workstation|pc|laptop|desktop|user|accountant)', text_lower)
            num_pcs = f"{count_match.group(1)}x" if count_match else ""
            
            if "laptop" in text_lower or "macbook" in text_lower:
                os_name = "Windows Laptops" if "windows" in text_lower else "MacBook Laptops" if "mac" in text_lower else "Workstation Laptops"
            elif "windows 11" in text_lower:
                os_name = "Windows 11 Workstations"
            elif "windows" in text_lower:
                os_name = "Windows Workstations"
            elif "mac" in text_lower:
                os_name = "Mac Workstations"
            else:
                os_name = "Workstations"

            device_cohorts.append({
                "id": "ws_pcs",
                "name": f"{num_pcs} {os_name}".strip(),
                "os": os_name,
                "target_subnet": primary_subnet_id
            })

        for dev in device_cohorts:
            nodes.append(NetworkNode(
                id=dev["id"],
                name=dev["name"],
                type="device",
                os_or_system=dev["os"],
                ip_or_subnet="DHCP Client Range",
                confidence=0.90
            ))
            edges.append(NetworkEdge(source=dev["id"], target=dev["target_subnet"], relationship="CONNECTS_TO", confidence=0.95))

        # 5. Storage / NAS / Volumes / Databases
        has_local_storage = any(w in text_lower for w in ["nas", "storage", "synology", "qnap", "truenas", "file server", "database", "sql", "volume", "share", "nfs", "smb", "san"])
        has_cui = any(w in text_lower for w in ["cui", "payroll", "contracts", "sensitive", "confidential", "hipaa", "tax", "donor", "defense"])
        has_mfa = any(w in text_lower for w in ["mfa enabled", "bitlocker", "mfa active", "encrypted", "aes-256", "zfs encryption"])

        storage_node_id = None
        if has_local_storage or (server_node_id and ("storage" in text_lower or has_cui)):
            storage_node_id = "storage_cui_volume" if has_cui else "storage_local"
            storage_name = "Network Storage / NAS"
            
            if "synology" in text_lower: storage_name = "Synology NAS Storage"
            elif "qnap" in text_lower: storage_name = "QNAP NAS Storage"
            elif "truenas" in text_lower: storage_name = "TrueNAS Storage Volume"
            elif server_node_id == "server_proxmox": storage_name = "Proxmox Virtual Storage / NAS"
            elif server_node_id: storage_name = "Virtual Storage Volume (Server)"

            nodes.append(NetworkNode(
                id=storage_node_id,
                name=storage_name,
                type="storage",
                os_or_system="ZFS / Storage OS",
                ip_or_subnet="192.168.1.50",
                stores_cui=has_cui,
                has_firewall_or_mfa=has_mfa,
                confidence=0.90
            ))

            # If storage is on a server/hypervisor, link server -> storage
            if server_node_id:
                edges.append(NetworkEdge(source=server_node_id, target=storage_node_id, relationship="STORES", confidence=0.95))
            else:
                target_sub = subnet_lan_id if has_lan else primary_subnet_id
                edges.append(NetworkEdge(source=storage_node_id, target=target_sub, relationship="CONNECTS_TO", confidence=0.95))

            # Access rules: Check if access is explicitly denied or limited (e.g. "Windows doesnt access the NAS")
            windows_blocked = any(w in text_lower for w in ["windows doesnt access", "windows doesn't access", "no access to nas", "isolated from nas", "blocked from nas", "cannot access"])
            
            for dev in device_cohorts:
                # If Windows is explicitly blocked, do NOT add ACCESSES edge for wifi/windows pcs
                if windows_blocked and ("wifi" in dev["id"] or "windows" in dev["name"].lower()):
                    continue
                # Front desk or authorized devices access storage
                if not windows_blocked or "front_desk" in dev["id"] or "admin" in dev["id"]:
                    edges.append(NetworkEdge(source=dev["id"], target=storage_node_id, relationship="ACCESSES", confidence=0.90))

        # 6. Cloud / VPN Gateway Node
        has_cloud = any(w in text_lower for w in ["aws", "azure", "cloud", "vpn", "openvpn", "wireguard"])
        cloud_node_id = None
        if has_cloud:
            cloud_node_id = "cloud_vpn"
            cloud_name = "Cloud Gateway / VPN"
            if "aws" in text_lower: cloud_name = "AWS Cloud Gateway (OpenVPN)"
            elif "azure" in text_lower: cloud_name = "Azure Virtual Network"

            nodes.append(NetworkNode(
                id=cloud_node_id,
                name=cloud_name,
                type="cloud_service",
                has_firewall_or_mfa=True,
                confidence=0.85
            ))
            for dev in device_cohorts:
                edges.append(NetworkEdge(source=dev["id"], target=cloud_node_id, relationship="CONNECTS_TO", confidence=0.90))

        # 7. CUI Data Asset Node
        if has_cui:
            cui_node_id = "cui_data"
            cui_label = "Controlled Unclassified Information (CUI)"
            if "payroll" in text_lower or "contract" in text_lower: cui_label = "Payroll Contracts & CUI Data"
            elif "hipaa" in text_lower or "patient" in text_lower: cui_label = "Patient Records & CUI"
            elif "tax" in text_lower: cui_label = "Tax Returns & Client CUI"

            nodes.append(NetworkNode(
                id=cui_node_id,
                name=cui_label,
                type="data_asset",
                stores_cui=True,
                confidence=0.95
            ))
            
            if storage_node_id:
                edges.append(NetworkEdge(source=storage_node_id, target=cui_node_id, relationship="STORES_CUI", confidence=0.95))
                if not has_mfa:
                    prompts.append(ClarificationPrompt(
                        node_id=storage_node_id,
                        question=f"Is CUI storage on '{storage_name}' encrypted with AES-256 / ZFS at-rest encryption?",
                        property_in_question="has_firewall_or_mfa",
                        suggested_options=["Yes, AES-256 / BitLocker encrypted", "No encryption currently", "Unsure"]
                    ))

        return nodes, edges, prompts

    def get_available_templates(self) -> List[Dict[str, Any]]:
        """Returns summary list of all available small business templates."""
        return [
            {
                "id": t["id"],
                "name": t["name"],
                "badge": t["badge"],
                "description": t["description"],
                "node_count": len(t["nodes"]),
                "edge_count": len(t["edges"])
            }
            for t in SMALL_BIZ_TEMPLATES.values()
        ]

    def load_template(self, template_id: str) -> Dict[str, Any]:
        """Loads a preconfigured small business network template into active session."""
        if template_id not in SMALL_BIZ_TEMPLATES:
            template_id = "clinic"
        
        tpl = SMALL_BIZ_TEMPLATES[template_id]
        nodes = [NetworkNode(**n) for n in tpl["nodes"]]
        edges = [NetworkEdge(**e) for e in tpl["edges"]]
        prompts = [ClarificationPrompt(**cp) for cp in tpl.get("clarification_prompts", [])]

        self.active_topology_nodes = nodes
        self.active_topology_edges = edges
        self.active_clarification_prompts = prompts

        return self.format_topology_response(f"Template: {tpl['name']}", nodes, edges, prompts)

    def format_topology_response(self, text: str, nodes: List[NetworkNode], edges: List[NetworkEdge], prompts: List[ClarificationPrompt]) -> Dict[str, Any]:
        """Helper to format uniform topology response payload for API & Cytoscape with compound subnet grouping and clean labels."""
        conf_scores = [n.confidence for n in nodes] + [e.confidence for e in edges]
        avg_conf = sum(conf_scores) / len(conf_scores) if conf_scores else 0.95

        # 1. Identify all subnet nodes
        subnet_ids = {n.id for n in nodes if n.type == "subnet"}

        # 2. Map devices/servers/storage to their respective parent subnets
        node_to_parent_subnet = {}
        for e in edges:
            if e.relationship in ["CONNECTS_TO", "MEMBER_OF"]:
                if e.target in subnet_ids and e.source not in subnet_ids:
                    node_to_parent_subnet[e.source] = e.target
                elif e.source in subnet_ids and e.target not in subnet_ids:
                    node_to_parent_subnet[e.target] = e.source

        cyto_nodes = []
        cyto_edges = []

        # 3. Add Subnet Parent Compound Nodes first
        for n in nodes:
            if n.type == "subnet":
                cyto_nodes.append({
                    "data": {
                        "id": n.id,
                        "label": n.name,
                        "type": "subnet",
                        "is_parent": True,
                        "confidence": n.confidence,
                        "ip_or_subnet": n.ip_or_subnet,
                        "details": f"Subnet / VLAN: {n.ip_or_subnet}"
                    }
                })

        # 4. Add Child Device / Asset Nodes inside their subnets
        for n in nodes:
            if n.type == "subnet":
                continue

            sec_tags = []
            if n.stores_cui: sec_tags.append("CUI")
            if n.has_firewall_or_mfa: sec_tags.append("MFA/FW")
            tag_str = f" [{ ' | '.join(sec_tags) }]" if sec_tags else ""

            node_data = {
                "id": n.id,
                "label": f"{n.name}{tag_str}",
                "type": n.type,
                "confidence": n.confidence,
                "stores_cui": n.stores_cui,
                "has_firewall_or_mfa": n.has_firewall_or_mfa,
                "os_or_system": n.os_or_system,
                "ip_or_subnet": n.ip_or_subnet,
                "details": f"OS: {n.os_or_system} | IP: {n.ip_or_subnet}"
            }

            # Assign parent compound subnet if mapped
            if n.id in node_to_parent_subnet:
                node_data["parent"] = node_to_parent_subnet[n.id]

            cyto_nodes.append({"data": node_data})

        # 5. Add meaningful inter-device and perimeter edges (filter redundant device->parent subnet edges)
        for e in edges:
            # Skip edge if it simply links a child node to its containing parent subnet box
            if (node_to_parent_subnet.get(e.source) == e.target) or (node_to_parent_subnet.get(e.target) == e.source):
                continue

            cyto_edges.append({
                "data": {
                    "id": f"{e.source}_{e.target}",
                    "source": e.source,
                    "target": e.target,
                    "label": e.relationship,
                    "relationship": e.relationship,
                    "is_encrypted": e.is_encrypted,
                    "confidence": e.confidence
                }
            })

        return {
            "raw_text": text,
            "nodes": [n.model_dump() for n in nodes],
            "edges": [e.model_dump() for e in edges],
            "confidence_score": round(avg_conf, 2),
            "requires_clarification": len(prompts) > 0,
            "clarification_prompts": [cp.model_dump() for cp in prompts],
            "cytoscape_graph": {
                "nodes": cyto_nodes,
                "edges": cyto_edges
            }
        }

    def update_node(self, node_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Updates properties of an existing node in the active topology and manages subnet assignment."""
        subnet_ids = {n.id for n in self.active_topology_nodes if n.type == "subnet"}

        # If subnet_id was passed, manage subnet connection edge
        if "subnet_id" in updates:
            new_subnet_id = updates.pop("subnet_id")
            # Remove existing subnet connection edges for this node
            self.active_topology_edges = [
                e for e in self.active_topology_edges 
                if not ((e.source == node_id and e.target in subnet_ids) or (e.target == node_id and e.source in subnet_ids))
            ]
            if new_subnet_id and new_subnet_id in subnet_ids:
                self.active_topology_edges.append(
                    NetworkEdge(source=node_id, target=new_subnet_id, relationship="CONNECTS_TO", confidence=1.0)
                )

        for idx, n in enumerate(self.active_topology_nodes):
            if n.id == node_id:
                curr = n.model_dump()
                curr.update(updates)
                self.active_topology_nodes[idx] = NetworkNode(**curr)
                break
        return self.format_topology_response("Node updated", self.active_topology_nodes, self.active_topology_edges, self.active_clarification_prompts)

    def add_node(self, node_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Adds a new node to the active topology with optional subnet assignment."""
        subnet_id = node_dict.pop("subnet_id", None)
        new_node = NetworkNode(**node_dict)
        # Avoid duplicate ids
        self.active_topology_nodes = [n for n in self.active_topology_nodes if n.id != new_node.id]
        self.active_topology_nodes.append(new_node)

        subnet_ids = {n.id for n in self.active_topology_nodes if n.type == "subnet"}
        if subnet_id and subnet_id in subnet_ids:
            self.active_topology_edges.append(
                NetworkEdge(source=new_node.id, target=subnet_id, relationship="CONNECTS_TO", confidence=1.0)
            )

        return self.format_topology_response("Node added", self.active_topology_nodes, self.active_topology_edges, self.active_clarification_prompts)

    def delete_node(self, node_id: str) -> Dict[str, Any]:
        """Deletes a node and all its connected edges."""
        self.active_topology_nodes = [n for n in self.active_topology_nodes if n.id != node_id]
        self.active_topology_edges = [e for e in self.active_topology_edges if e.source != node_id and e.target != node_id]
        self.active_clarification_prompts = [cp for cp in self.active_clarification_prompts if cp.node_id != node_id]
        return self.format_topology_response("Node deleted", self.active_topology_nodes, self.active_topology_edges, self.active_clarification_prompts)

    def clear_topology(self) -> Dict[str, Any]:
        """Clears all active topology nodes, edges, and clarifications (blank canvas)."""
        self.active_topology_nodes = []
        self.active_topology_edges = []
        self.active_clarification_prompts = []
        return self.format_topology_response("Workspace cleared", [], [], [])

    def add_edge(self, edge_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Adds a connection edge between two nodes."""
        new_edge = NetworkEdge(**edge_dict)
        self.active_topology_edges = [e for e in self.active_topology_edges if not (e.source == new_edge.source and e.target == new_edge.target)]
        self.active_topology_edges.append(new_edge)
        return self.format_topology_response("Edge added", self.active_topology_nodes, self.active_topology_edges, self.active_clarification_prompts)

    def answer_clarification(self, node_id: str, property_name: str, value: Any) -> Dict[str, Any]:
        """Resolves a clarification prompt and updates node property."""
        self.update_node(node_id, {property_name: value})
        # Remove resolved clarification prompt
        self.active_clarification_prompts = [
            cp for cp in self.active_clarification_prompts 
            if not (cp.node_id == node_id and cp.property_in_question == property_name)
        ]
        return self.format_topology_response("Clarification resolved", self.active_topology_nodes, self.active_topology_edges, self.active_clarification_prompts)

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

