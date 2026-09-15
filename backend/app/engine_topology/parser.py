import logging
import json
import re
import copy
from typing import Dict, Any, List, Optional, Tuple
from app.engine_topology.schema import TopologyParseResult, NetworkNode, NetworkEdge, ClarificationPrompt
from app.engine_topology.templates import SMALL_BIZ_TEMPLATES
from app.db.neo4j_client import neo4j_client
from app.llm.factory import get_llm_provider

logger = logging.getLogger("garc.engine2.parser")

class TopologyParser:
    def __init__(self):
        # Active session state for evaluated topologies
        self.active_topology_nodes: List[NetworkNode] = []
        self.active_topology_edges: List[NetworkEdge] = []
        self.active_clarification_prompts: List[ClarificationPrompt] = []
        # Interactive What-If Sandbox State
        self.what_if_backup_nodes: Any = None
        self.what_if_backup_edges: Any = None
        self.active_what_if_fixes: List[str] = []
        self.last_critic_actions: List[str] = []

    def parse_natural_language_topology(self, text: str) -> Dict[str, Any]:
        """
        Engine 2 Pipeline:
        1. Attempts LLM structured extraction to handle complex/messy natural language prompts.
        2. Falls back to deterministic rule-based parser if LLM is unreachable or times out.
        3. Executes Agentic Critic & Self-Repair Loop (prunes dangling edges, connects orphan nodes, enforces CUI protections).
        4. Identifies missing or ambiguous cybersecurity attributes & generates clarification cards.
        5. Formats compound Cytoscape payload with subnets.
        """
        logger.info(f"Engine 2: Executing network topology extraction for input: '{text[:60]}...'")
        
        nodes, edges, clarification_prompts = None, None, None
        try:
            nodes, edges, clarification_prompts = self._llm_structured_parser(text)
        except Exception as e:
            logger.warning(f"Engine 2: LLM structured parsing failed ({e}). Falling back to rule-based parser.")

        if not nodes:
            nodes, edges, clarification_prompts = self._fallback_rule_based_parser(text)

        # Execute Engine 2 Agentic Critic & Self-Repair Loop
        nodes, edges, clarification_prompts, critic_actions = self._critic_and_repair_loop(
            nodes, edges, clarification_prompts or [], text
        )
        self.last_critic_actions = critic_actions

        # Update active session topology
        self.active_topology_nodes = nodes
        self.active_topology_edges = edges
        self.active_clarification_prompts = clarification_prompts

        res = self.format_topology_response(text, nodes, edges, clarification_prompts)
        res["critic_actions"] = critic_actions
        return res

    def _critic_and_repair_loop(
        self,
        nodes: List[NetworkNode],
        edges: List[NetworkEdge],
        prompts: List[ClarificationPrompt],
        raw_text: str
    ) -> tuple[List[NetworkNode], List[NetworkEdge], List[ClarificationPrompt], List[str]]:
        """
        Engine 2 Agentic Critic & Self-Repair Loop:
        Reflects over extracted topology to guarantee schema validity, graph connectivity,
        and NIST SP 800-171 Rev 3 boundary consistency.
        """
        critic_actions: List[str] = []
        text_lower = raw_text.lower()
        node_map = {n.id: n for n in nodes}
        subnet_nodes = [n for n in nodes if n.type == "subnet"]
        firewall_nodes = [n for n in nodes if n.type == "firewall"]

        # Pass 1: Prune invalid or dangling edges
        valid_edges: List[NetworkEdge] = []
        for e in edges:
            if e.source in node_map and e.target in node_map:
                valid_edges.append(e)
            else:
                critic_actions.append(f"Pruned dangling edge: {e.source} -> {e.target}")
        edges = valid_edges

        # Pass 2: Connect isolated orphan nodes
        connected_node_ids = set()
        for e in edges:
            connected_node_ids.add(e.source)
            connected_node_ids.add(e.target)

        for n in nodes:
            if n.type == "subnet":
                continue
            if n.id not in connected_node_ids:
                # Find best target subnet
                target_sub = None
                n_name_lower = n.name.lower()
                if "wifi" in n_name_lower or "wireless" in n_name_lower or "laptop" in n_name_lower:
                    for s in subnet_nodes:
                        if "wifi" in s.name.lower() or "wireless" in s.name.lower():
                            target_sub = s
                            break
                if not target_sub and subnet_nodes:
                    target_sub = subnet_nodes[0]

                if target_sub:
                    edges.append(NetworkEdge(
                        source=n.id,
                        target=target_sub.id,
                        relationship="MEMBER_OF",
                        confidence=0.92
                    ))
                    connected_node_ids.add(n.id)
                    critic_actions.append(f"Healed orphan asset: Connected '{n.name}' to subnet '{target_sub.name}'")
                elif firewall_nodes:
                    edges.append(NetworkEdge(
                        source=firewall_nodes[0].id,
                        target=n.id,
                        relationship="PROTECTS",
                        confidence=0.90
                    ))
                    connected_node_ids.add(n.id)
                    critic_actions.append(f"Healed orphan asset: Linked '{n.name}' to perimeter gateway '{firewall_nodes[0].name}'")

        # Pass 3: Enforce firewall security attributes & protection edges
        for fw in firewall_nodes:
            if not fw.has_firewall_or_mfa:
                fw.has_firewall_or_mfa = True
                critic_actions.append(f"Auto-verified boundary protection flags on firewall '{fw.name}'")
            for sub in subnet_nodes:
                has_prot = any(
                    (e.source == fw.id and e.target == sub.id) or (e.target == fw.id and e.source == sub.id)
                    for e in edges
                )
                if not has_prot:
                    edges.append(NetworkEdge(
                        source=fw.id,
                        target=sub.id,
                        relationship="PROTECTS",
                        confidence=0.95
                    ))
                    critic_actions.append(f"Created boundary protection edge: '{fw.name}' PROTECTS '{sub.name}'")

        # Pass 4: CUI Asset Assessment & Targeted Clarifications
        cui_keywords = ["cui", "controlled unclassified", "sensitive", "patient", "payroll", "tax", "confidential", "ehr"]
        for n in nodes:
            if any(k in n.name.lower() for k in cui_keywords) or any(k in text_lower and n.id in text_lower for k in cui_keywords):
                if not n.stores_cui:
                    n.stores_cui = True
                    critic_actions.append(f"Flagged compliance-critical CUI storage on '{n.name}'")

            if n.stores_cui and not n.has_firewall_or_mfa:
                has_prompt = any(cp.node_id == n.id and cp.property_in_question == "has_firewall_or_mfa" for cp in prompts)
                if not has_prompt:
                    prompts.append(ClarificationPrompt(
                        node_id=n.id,
                        question=f"Is data at rest on '{n.name}' protected with FIPS-validated volume encryption (e.g., BitLocker, LUKS, or AES-256)?",
                        property_in_question="has_firewall_or_mfa",
                        suggested_options=["Encrypted (AES-256)", "Unencrypted / Unknown"]
                    ))
                    critic_actions.append(f"Generated precision encryption clarification for '{n.name}'")

        # Pass 5: Guest Network Boundary Quarantine
        cui_node_ids = {n.id for n in nodes if n.stores_cui}
        sanitized_edges: List[NetworkEdge] = []
        for e in edges:
            src_node = node_map.get(e.source)
            tgt_node = node_map.get(e.target)
            is_guest = (src_node and "guest" in src_node.name.lower()) or (tgt_node and "guest" in tgt_node.name.lower())
            accesses_cui = (e.source in cui_node_ids) or (e.target in cui_node_ids)

            if is_guest and accesses_cui and "allow guest" not in text_lower:
                critic_actions.append(f"Quarantined unsafe link: Severed direct connection from Guest Wi-Fi to CUI storage '{e.target}'")
            else:
                sanitized_edges.append(e)
        edges = sanitized_edges

        return nodes, edges, prompts, critic_actions


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

    def conversational_copilot(
        self,
        message: str,
        history: Optional[List[Any]] = None,
        current_nodes: Optional[List[Dict[str, Any]]] = None,
        current_edges: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Unified Cyber Clinic Copilot:
        Acts as both a knowledgeable compliance assistant and an interactive topology builder.
        - Answers general questions in plain English (CUI, MFA, NIST 800-171, best practices).
        - Incrementally extracts/updates network nodes and edges when infrastructure is discussed.
        - Runs the Critic & Self-Repair loop on updated state.
        """
        # Restore from active session if current_nodes not provided
        if current_nodes is not None:
            self.active_topology_nodes = [NetworkNode(**n) for n in current_nodes]
        if current_edges is not None:
            self.active_topology_edges = [NetworkEdge(**e) for e in current_edges]

        nodes = self.active_topology_nodes
        edges = self.active_topology_edges

        # Format existing topology for context
        topo_summary = "Current Active Network Topology:\n"
        if not nodes:
            topo_summary += "(No devices currently mapped.)\n"
        else:
            for n in nodes:
                cui_flag = " [STORES CUI]" if n.stores_cui else ""
                sec_flag = " [MFA/ENCRYPTION CONFIRMED]" if n.has_firewall_or_mfa else ""
                topo_summary += f"- {n.id}: '{n.name}' (Type: {n.type}, IP/Subnet: {n.ip_or_subnet}){cui_flag}{sec_flag}\n"
            for e in edges:
                enc_flag = " [ENCRYPTED]" if e.is_encrypted else ""
                topo_summary += f"  * Connection: {e.source} --[{e.relationship}]--> {e.target}{enc_flag}\n"

        history_summary = ""
        if history:
            for h in history[-4:]:
                role = getattr(h, 'role', h.get('role', 'user') if isinstance(h, dict) else 'user')
                content = getattr(h, 'content', h.get('content', '') if isinstance(h, dict) else '')
                history_summary += f"{role.capitalize()}: {content}\n"

        system_instruction = """You are GaRC Cyber Clinic Copilot, an approachable, expert cybersecurity advisor for small businesses and defense subcontractors adhering to NIST SP 800-171 Rev 3.

You have two simultaneous roles:
1. EDUCATOR / ADVISOR: Explain cybersecurity concepts, NIST requirements (CUI, MFA, VLANs, backups, access control) in clear, reassuring, plain English with markdown formatting.
2. TOPOLOGY BUILDER: Whenever the user describes or modifies equipment, network setup, remote workers, or servers, extract structured actions to update the live network graph.

Allowed mutation actions:
- "ADD_NODE": { "id": "snake_case", "name": "Human Name", "type": "device"|"server"|"storage"|"data_asset"|"firewall"|"subnet"|"cloud_service", "ip_or_subnet": "...", "stores_cui": bool, "has_firewall_or_mfa": bool, "subnet_id": "optional_subnet_id" }
- "UPDATE_NODE": { "node_id": "existing_id", "updates": { ... } }
- "DELETE_NODE": { "node_id": "existing_id" }
- "ADD_EDGE": { "source": "src_id", "target": "tgt_id", "relationship": "MEMBER_OF"|"ACCESSES"|"STORES"|"PROTECTS"|"CONNECTS_TO", "is_encrypted": bool }
- "CLEAR": {}

Always output "kg_traces" to link your answer to specific NIST SP 800-171 controls (e.g., 03.01.01, 03.05.03) and network asset nodes.
"""

        schema_description = """{
  "reply": "Clear, friendly markdown explanation answering the user's question or summarizing changes made.",
  "actions_taken": ["Added 2x MacBook laptops", "Connected laptops to Wi-Fi subnet"],
  "topology_mutations": [
    {
      "action": "ADD_NODE",
      "node": {
        "id": "dev_macbooks",
        "name": "2x Remote MacBooks",
        "type": "device",
        "stores_cui": false,
        "has_firewall_or_mfa": false
      }
    }
  ],
  "suggested_followups": [
    "Do these MacBooks have FileVault disk encryption enabled?",
    "How do these remote laptops connect back to the office?"
  ],
  "kg_traces": [
    {
      "id": "03.01.01",
      "label": "03.01.01 Authorized Access Control",
      "type": "control",
      "family": "03.01",
      "status": "MET"
    },
    {
      "id": "dev_macbooks",
      "label": "Remote MacBooks",
      "type": "node",
      "status": "NEEDS_INFO"
    }
  ]
}"""

        prompt = f"""{topo_summary}

Recent Conversation:
{history_summary}

User: {message}

Respond with helpful cyber clinic guidance, network topology mutations, and KG traces."""

        llm = get_llm_provider()
        payload = {}
        try:
            payload = llm.generate_structured_json(prompt, schema_description=schema_description, system_instruction=system_instruction)
        except Exception as e:
            logger.debug(f"Copilot LLM call failed or provider offline: {e}. Switching to CPRT fallback engine.")

        # Fallback handling if LLM returns empty or fails
        if not payload or not isinstance(payload, dict) or "reply" not in payload or not payload.get("reply"):
            payload = self._copilot_fallback(message, nodes, edges)

        reply = payload.get("reply", "I've reviewed your network configuration.")
        actions_taken = payload.get("actions_taken", [])
        mutations = payload.get("topology_mutations", [])
        followups = payload.get("suggested_followups", [
            "What security controls should we focus on next?",
            "How do we isolate guest Wi-Fi from our office data?"
        ])
        raw_traces = payload.get("kg_traces", [])

        topology_updated = False
        if mutations:
            for m in mutations:
                act = m.get("action", "").upper()
                if act == "ADD_NODE" and "node" in m:
                    n_data = m["node"]
                    sub_id = n_data.pop("subnet_id", None)
                    new_n = NetworkNode(**n_data)
                    self.active_topology_nodes = [n for n in self.active_topology_nodes if n.id != new_n.id]
                    self.active_topology_nodes.append(new_n)
                    if sub_id and any(s.id == sub_id for s in self.active_topology_nodes):
                        self.active_topology_edges.append(NetworkEdge(source=new_n.id, target=sub_id, relationship="MEMBER_OF"))
                    topology_updated = True
                elif act == "UPDATE_NODE" and "node_id" in m:
                    nid = m["node_id"]
                    upds = m.get("updates", {})
                    for idx, n in enumerate(self.active_topology_nodes):
                        if n.id == nid:
                            curr = n.model_dump()
                            curr.update(upds)
                            self.active_topology_nodes[idx] = NetworkNode(**curr)
                            break
                    topology_updated = True
                elif act == "DELETE_NODE" and "node_id" in m:
                    nid = m["node_id"]
                    self.active_topology_nodes = [n for n in self.active_topology_nodes if n.id != nid]
                    self.active_topology_edges = [e for e in self.active_topology_edges if e.source != nid and e.target != nid]
                    topology_updated = True
                elif act == "ADD_EDGE" and "source" in m and "target" in m:
                    self.active_topology_edges.append(NetworkEdge(
                        source=m["source"],
                        target=m["target"],
                        relationship=m.get("relationship", "CONNECTS_TO"),
                        is_encrypted=m.get("is_encrypted", False)
                    ))
                    topology_updated = True
                elif act == "CLEAR":
                    self.active_topology_nodes = []
                    self.active_topology_edges = []
                    self.active_clarification_prompts = []
                    topology_updated = True

        if topology_updated:
            # Run critic & self-repair loop on the mutated topology
            repaired_nodes, repaired_edges, repaired_prompts, critic_notes = self._critic_and_repair_loop(
                self.active_topology_nodes,
                self.active_topology_edges,
                self.active_clarification_prompts,
                message
            )
            self.active_topology_nodes = repaired_nodes
            self.active_topology_edges = repaired_edges
            self.active_clarification_prompts = repaired_prompts
            for cn in critic_notes:
                if cn not in actions_taken:
                    actions_taken.append(cn)

        # Extract and enrich complete KG traces linking controls and nodes
        kg_traces = self._extract_kg_traces(reply, raw_traces, self.active_topology_nodes, self.active_topology_edges)

        topo_result = self.format_topology_response("Copilot Update", self.active_topology_nodes, self.active_topology_edges, self.active_clarification_prompts)

        return {
            "reply": reply,
            "actions_taken": actions_taken,
            "topology_updated": topology_updated,
            "topology": topo_result,
            "suggested_followups": followups,
            "kg_traces": kg_traces
        }

    def _extract_kg_traces(self, reply_text: str, explicit_traces: List[Dict[str, Any]], active_nodes: List[NetworkNode], active_edges: List[NetworkEdge]) -> List[Dict[str, Any]]:
        """Extracts and deduplicates KG traces (NIST controls, graph nodes, and edges) for UI tracing."""
        traces = []
        seen_ids = set()

        for t in (explicit_traces or []):
            tid = t.get("id")
            if tid and tid not in seen_ids:
                traces.append(t)
                seen_ids.add(tid)

        # Regex detect NIST SP 800-171 Rev 3 controls
        control_matches = re.findall(r'\b(?:0?3\.\d{1,2}\.\d{1,2}|AC-\d+|IA-\d+|MP-\d+|SC-\d+|SI-\d+)\b', reply_text, re.IGNORECASE)
        control_family_map = {
            "03.01": ("03.01", "Access Control"),
            "3.1": ("03.01", "Access Control"),
            "AC": ("03.01", "Access Control"),
            "03.05": ("03.05", "Identification & Authentication"),
            "3.5": ("03.05", "Identification & Authentication"),
            "IA": ("03.05", "Identification & Authentication"),
            "03.08": ("03.08", "Media Protection"),
            "3.8": ("03.08", "Media Protection"),
            "MP": ("03.08", "Media Protection"),
            "03.13": ("03.13", "System & Comms Protection"),
            "3.13": ("03.13", "System & Comms Protection"),
            "SC": ("03.13", "System & Comms Protection"),
            "03.14": ("03.14", "System & Info Integrity"),
            "3.14": ("03.14", "System & Info Integrity"),
            "SI": ("03.14", "System & Info Integrity"),
        }

        for cm in control_matches:
            cid = cm.strip()
            # Normalize to 03.xx.xx format if needed
            normalized_cid = cid
            if re.match(r'^3\.\d+\.\d+$', cid):
                parts = cid.split('.')
                normalized_cid = f"03.{int(parts[1]):02d}.{int(parts[2]):02d}"

            if normalized_cid not in seen_ids:
                fam = "03.01"
                fam_label = "Access Control"
                for prefix, (f_code, f_name) in control_family_map.items():
                    if cid.upper().startswith(prefix) or normalized_cid.startswith(prefix):
                        fam = f_code
                        fam_label = f_name
                        break
                traces.append({
                    "id": normalized_cid,
                    "label": f"NIST {normalized_cid} ({fam_label})",
                    "type": "control",
                    "family": fam,
                    "status": "ACTIVE"
                })
                seen_ids.add(normalized_cid)

        # Detect active topology assets mentioned in text
        text_lower = reply_text.lower()
        for node in active_nodes:
            if node.id not in seen_ids:
                if node.name.lower() in text_lower or node.id.lower() in text_lower or (node.stores_cui and "cui" in text_lower and node.type in ["storage", "data_asset"]):
                    traces.append({
                        "id": node.id,
                        "label": node.name,
                        "type": "node",
                        "family": None,
                        "status": "MET" if node.has_firewall_or_mfa else "NEEDS_INFO"
                    })
                    seen_ids.add(node.id)

        return traces[:7]

    def _copilot_fallback(self, message: str, nodes: List[NetworkNode], edges: List[NetworkEdge]) -> Dict[str, Any]:
        """High-fidelity CPRT KG-backed fallback for Cyber Clinic Copilot when offline or LLM provider unavailable."""
        msg_lower = message.lower()
        mutations: List[Dict[str, Any]] = []
        actions: List[str] = []
        kg_traces: List[Dict[str, Any]] = []
        followups: List[str] = []
        reply: str = ""

        # Check if user is asking about network map, topology, assets, or what Copilot sees
        is_map_query = any(w in msg_lower for w in [
            "see", "map", "network", "topology", "device", "asset", "hardware",
            "setup", "posture", "review", "look at", "inspect", "show", "current",
            "diagram", "graph", "what do you see", "view", "inventory", "canvas",
            "what is here", "what's here", "tell me about my", "audit my"
        ])

        # Check if message is a greeting or introductory inquiry
        is_greeting = (
            any(msg_lower.strip().startswith(g) for g in ["hi", "hello", "hey", "howdy", "greetings", "good morning", "good afternoon"])
            or msg_lower.strip() in ["help", "who are you", "what can you do", "who made you"]
        )

        is_hardware_action = (
            any(w in msg_lower for w in ["install", "added", "add ", "bought", "deploy", "setup", "synology", "nas", "macbook"])
            and not any(q in msg_lower for q in ["what is", "why do", "how do", "how should", "explain", "why does", "what do you see", "can you see"])
        )

        if is_hardware_action:
            extracted_items = []
            if "macbook" in msg_lower or "laptop" in msg_lower or "workstation" in msg_lower or "pc" in msg_lower:
                node_id = f"dev_laptop_{len(nodes) + 1}"
                mutations.append({
                    "action": "ADD_NODE",
                    "node": {
                        "id": node_id,
                        "name": "Staff Workstation / Laptop",
                        "type": "device",
                        "ip_or_subnet": "192.168.1.x",
                        "stores_cui": "cui" in msg_lower or "contract" in msg_lower,
                        "has_firewall_or_mfa": "mfa" in msg_lower or "encrypted" in msg_lower
                    }
                })
                extracted_items.append("Staff Workstation Laptop")
                kg_traces.append({"id": node_id, "label": "Staff Workstation", "type": "node", "status": "NEEDS_INFO"})

            if "nas" in msg_lower or "synology" in msg_lower or "storage" in msg_lower or "server" in msg_lower:
                node_id = f"storage_nas_{len(nodes) + 1}"
                mutations.append({
                    "action": "ADD_NODE",
                    "node": {
                        "id": node_id,
                        "name": "Synology / Office NAS",
                        "type": "storage",
                        "ip_or_subnet": "192.168.1.50",
                        "stores_cui": True,
                        "has_firewall_or_mfa": "mfa" in msg_lower or "encrypted" in msg_lower
                    }
                })
                extracted_items.append("Synology Office NAS (CUI Storage)")
                kg_traces.append({"id": node_id, "label": "Synology NAS", "type": "node", "status": "NEEDS_INFO"})
                kg_traces.append({"id": "03.08.03", "label": "03.08.03 Media Encryption", "type": "control", "family": "03.08", "status": "ACTIVE"})

            if "firewall" in msg_lower or "router" in msg_lower or "gateway" in msg_lower or "pfsense" in msg_lower:
                node_id = f"fw_gateway_{len(nodes) + 1}"
                mutations.append({
                    "action": "ADD_NODE",
                    "node": {
                        "id": node_id,
                        "name": "Perimeter Security Gateway",
                        "type": "firewall",
                        "ip_or_subnet": "192.168.1.1",
                        "has_firewall_or_mfa": True
                    }
                })
                extracted_items.append("Perimeter Security Gateway")
                kg_traces.append({"id": node_id, "label": "Perimeter Security Gateway", "type": "node", "status": "MET"})
                kg_traces.append({"id": "03.13.01", "label": "03.13.01 Boundary Protection", "type": "control", "family": "03.13", "status": "MET"})

            if extracted_items:
                reply = (
                    f"Got it! I've added **{', '.join(extracted_items)}** to your live network map.\n\n"
                    "Our Critic agent has verified the connections and subnets. You can see the updated topology on the canvas."
                )
                actions = [f"Added {item}" for item in extracted_items]
            else:
                reply = "I've noted the hardware change and verified your topology on the canvas."

            followups = [
                "Which subnet should this device connect to?",
                "Simulate: Enable encryption across new storage",
                "Run an audit to check our updated score"
            ]

        elif is_map_query:
            # Full structured visibility into active network map
            if not nodes:
                reply = (
                    "### 🗺️ Network Map Analysis: Empty Canvas\n\n"
                    "I am actively monitoring your canvas, but **no devices or subnets are currently mapped**.\n\n"
                    "- **Quick Start**: Select a small business template above (*Small Healthcare Clinic*, *Local Law / CPA Practice*, etc.) to load a realistic architecture.\n"
                    "- **Natural Language**: Or tell me what hardware you use (*'We have 6 Dell laptops, a Synology NAS with client files, and guest Wi-Fi'*), and I will build your topology automatically!"
                )
                kg_traces = [
                    {"id": "03.01.01", "label": "03.01 Access Control", "type": "control", "family": "03.01", "status": "ACTIVE"},
                    {"id": "03.13.01", "label": "03.13 Boundary Protection", "type": "control", "family": "03.13", "status": "ACTIVE"}
                ]
                followups = [
                    "Load Small Clinic Template",
                    "We have 5 laptops and a Synology NAS",
                    "What is CUI and does my business have it?"
                ]
            else:
                subnets = [n for n in nodes if n.type == "subnet"]
                firewalls = [n for n in nodes if n.type == "firewall" or "firewall" in n.name.lower() or "gateway" in n.name.lower()]
                storages = [n for n in nodes if n.type in ["storage", "server", "data_asset"]]
                endpoints = [n for n in nodes if n.type in ["device", "workstation", "laptop", "user"]]
                cui_nodes = [n for n in nodes if n.stores_cui]
                unencrypted_cui = [n for n in cui_nodes if not n.has_firewall_or_mfa]

                device_lines = []
                for n in nodes[:8]:
                    flags = []
                    if n.stores_cui:
                        flags.append("📁 CUI")
                    if n.has_firewall_or_mfa:
                        flags.append("🔒 MFA/Encrypted")
                    flag_str = f" ({', '.join(flags)})" if flags else ""
                    device_lines.append(f"- **{n.name}** (`{n.type}` · `{n.ip_or_subnet}`){flag_str}")

                extra_count = len(nodes) - 8
                if extra_count > 0:
                    device_lines.append(f"- *...and {extra_count} more asset(s)*")

                cui_status = (
                    f"⚠️ **{len(unencrypted_cui)} of {len(cui_nodes)} CUI asset(s) lack confirmed volume encryption** (NIST 03.08.03)"
                    if unencrypted_cui else
                    f"✅ All {len(cui_nodes)} CUI asset(s) have confirmed encryption"
                    if cui_nodes else "ℹ️ No assets currently designated as CUI repositories"
                )

                fw_status = (
                    f"✅ **Boundary Gateway Active**: {firewalls[0].name} (NIST 03.13.01)"
                    if firewalls else
                    "🚨 **Missing Boundary Firewall**: No dedicated security gateway detected (NIST 03.13.01)"
                )

                reply = (
                    f"### 🗺️ Live Network Map Inspection\n\n"
                    f"I can see **{len(nodes)} assets** and **{len(edges)} connections** active on your canvas:\n\n"
                    + "\n".join(device_lines) + "\n\n"
                    f"**Security & NIST SP 800-171 Rev 3 Observations:**\n"
                    f"- {fw_status}\n"
                    f"- {cui_status}\n"
                    f"- 🌐 **Subnets & Segmentation**: {len(subnets)} subnet zone(s) mapped (`{', '.join(s.name for s in subnets)}`)\n"
                    f"- 💻 **Workstations / Endpoints**: {len(endpoints)} user device(s) connected\n\n"
                    f"*Click any trace tag below to highlight that asset or control directly in the canvas!*"
                )

                kg_traces = []
                if firewalls:
                    kg_traces.append({"id": firewalls[0].id, "label": firewalls[0].name, "type": "node", "status": "MET"})
                    kg_traces.append({"id": "03.13.01", "label": "03.13.01 Boundary Protection", "type": "control", "family": "03.13", "status": "MET"})
                else:
                    kg_traces.append({"id": "03.13.01", "label": "03.13.01 Boundary Protection", "type": "control", "family": "03.13", "status": "UNMET"})

                if cui_nodes:
                    for cn in cui_nodes[:2]:
                        kg_traces.append({"id": cn.id, "label": cn.name, "type": "node", "status": "MET" if cn.has_firewall_or_mfa else "NEEDS_INFO"})
                    kg_traces.append({"id": "03.08.03", "label": "03.08.03 Media Encryption", "type": "control", "family": "03.08", "status": "ACTIVE"})

                kg_traces.append({"id": "03.01.01", "label": "03.01.01 Authorized Access Control", "type": "control", "family": "03.01", "status": "ACTIVE"})

                followups = [
                    "Simulate: Enable encryption across CUI storage",
                    "How do we isolate Guest Wi-Fi from our office LAN?",
                    "What are the top 3 compliance fixes for this network?"
                ]

        elif is_greeting:
            asset_summary = f"{len(nodes)} assets and {len(edges)} connections" if nodes else "an empty canvas"
            reply = (
                f"### Hello! I'm your GaRC Cyber Clinic Copilot 👋\n\n"
                f"I am actively monitoring your **live network map** ({asset_summary} currently detected).\n\n"
                f"Here is how I can assist you:\n"
                f"- **🔍 Inspect Your Map**: Ask *'What do you see in my network map?'* or click **Inspect Active Network Map** above.\n"
                f"- **➕ Add / Update Equipment**: Say *'Add 4 MacBooks and a Synology NAS with contracts'* and I'll update the diagram.\n"
                f"- **🛡️ Compliance Guidance**: Ask about *CUI*, *MFA*, *BitLocker*, *Guest Wi-Fi*, or *NIST SP 800-171 Rev 3* requirements.\n"
                f"- **⚡ What-If Sandbox**: Test one-click remediations (encryption, MFA, VLAN segmentation) to preview your score delta."
            )
            kg_traces = [
                {"id": "03.01.01", "label": "03.01 Access Control", "type": "control", "family": "03.01", "status": "ACTIVE"},
                {"id": "03.05.03", "label": "03.05 Multi-Factor Auth", "type": "control", "family": "03.05", "status": "ACTIVE"},
                {"id": "03.13.01", "label": "03.13 Boundary Protection", "type": "control", "family": "03.13", "status": "ACTIVE"}
            ]
            followups = [
                "What do you see in my network map?",
                "What is CUI and does my business have it?",
                "Simulate: Enable encryption on all storage"
            ]

        elif "cui" in msg_lower or "unclassified" in msg_lower:
            cui_nodes = [n for n in nodes if n.stores_cui]
            cui_note = (
                f"In your active map, **{', '.join(n.name for n in cui_nodes)}** {'is' if len(cui_nodes)==1 else 'are'} designated as CUI repositories."
                if cui_nodes else
                "In your active map, no assets are currently marked as storing CUI."
            )
            reply = (
                "### Controlled Unclassified Information (CUI) & Scoping\n\n"
                "**CUI** is sensitive government-created or owned information requiring safeguarding under federal contracts (DFARS 252.204-7012 and NIST SP 800-171 Rev 3).\n\n"
                f"**Your Active Topology**: {cui_note}\n\n"
                "**Key Requirements for Small Businesses:**\n"
                "- **Access Limitation (NIST 03.01.01)**: Only personnel with a verified 'need-to-know' and active background checks may access CUI repositories.\n"
                "- **At-Rest Volume Encryption (NIST 03.08.03)**: Any drive, NAS volume, or laptop storing CUI must be encrypted with FIPS-validated AES-256 (BitLocker, FileVault, or LUKS).\n"
                "- **Network Isolation (NIST 03.13.01)**: CUI repositories must sit on a segmented subnet with zero direct routes from untrusted guest networks."
            )
            kg_traces = [
                {"id": "03.01.01", "label": "03.01.01 Authorized Access Control", "type": "control", "family": "03.01", "status": "MET"},
                {"id": "03.08.03", "label": "03.08.03 Cryptographic Media Protection", "type": "control", "family": "03.08", "status": "NEEDS_INFO"},
                {"id": "03.13.01", "label": "03.13.01 Boundary Protection", "type": "control", "family": "03.13", "status": "ACTIVE"}
            ]
            followups = [
                "Which assets in our topology store CUI?",
                "Simulate: Enable AES-256 encryption on CUI storage",
                "How do we isolate CUI from guest Wi-Fi?"
            ]

        elif "mfa" in msg_lower or "two factor" in msg_lower or "2fa" in msg_lower or "authenticat" in msg_lower:
            reply = (
                "### Multi-Factor Authentication (MFA) Requirements\n\n"
                "Under **NIST SP 800-171 Rev 3 (Control 03.05.03)**, MFA is non-negotiable for defense contractors and cyber clinic clients:\n\n"
                "1. **Remote Sessions**: All VPN logins, web portals, and remote desktop sessions connecting into the organizational network.\n"
                "2. **Privileged Roles**: Administrative consoles, domain controllers, cloud dashboards (e.g., Microsoft 365 Admin, AWS Console).\n\n"
                "💡 **Clinic Recommendation**: Prefer authenticator apps (TOTP) or FIDO2 hardware tokens (e.g., YubiKey) over SMS text codes, which are vulnerable to SIM-swapping."
            )
            kg_traces = [
                {"id": "03.05.03", "label": "03.05.03 Multi-Factor Authentication", "type": "control", "family": "03.05", "status": "MET"},
                {"id": "03.01.02", "label": "03.01.02 Transaction & Function Separation", "type": "control", "family": "03.01", "status": "ACTIVE"}
            ]
            followups = [
                "Simulate: Enforce MFA across all endpoints",
                "Do office workstations need MFA for local Windows login?",
                "What free MFA tools can small non-profits deploy?"
            ]

        elif "vlan" in msg_lower or "segment" in msg_lower or "guest" in msg_lower or "wifi" in msg_lower:
            reply = (
                "### Network Segmentation & Guest Wi-Fi Isolation\n\n"
                "Under **NIST SP 800-171 Rev 3 (Control 03.13.01 & 03.13.05)**, visitor and guest devices must never share a broadcast domain with internal business systems.\n\n"
                "**Standard 3-Zone Architecture:**\n"
                "1. **Office / Corporate LAN** (`192.168.1.0/24`): Staff PCs and authorized printers.\n"
                "2. **Secure CUI / Server Enclave** (`192.168.10.0/24`): Restricted behind stateful firewall inspection.\n"
                "3. **Guest Wi-Fi VLAN** (`192.168.99.0/24`): Client isolation enabled, internet-only access."
            )
            kg_traces = [
                {"id": "03.13.01", "label": "03.13.01 Boundary Protection & Firewalls", "type": "control", "family": "03.13", "status": "MET"},
                {"id": "03.13.05", "label": "03.13.05 Network Subnet Segmentation", "type": "control", "family": "03.13", "status": "ACTIVE"}
            ]
            followups = [
                "Simulate: Isolate Guest Wi-Fi VLAN",
                "Can an unmanaged switch support VLAN isolation?",
                "How do we configure guest isolation on Ubiquiti / pfSense?"
            ]

        elif "firewall" in msg_lower or "pfsense" in msg_lower or "fortinet" in msg_lower or "router" in msg_lower:
            reply = (
                "### Boundary Defense & Perimeter Firewalls\n\n"
                "**Control 03.13.01** requires managed perimeter security gateways at all external network connections:\n\n"
                "- **Default-Deny Inbound**: All unsolicited inbound ports (e.g., RDP 3389, SMB 445) must be blocked.\n"
                "- **Stateful Inspection**: Monitored outbound sessions with DMZ isolation for public-facing servers.\n"
                "- **Encrypted Management**: Web GUI access restricted to dedicated admin subnets over TLS 1.3."
            )
            kg_traces = [
                {"id": "03.13.01", "label": "03.13.01 Boundary Protection", "type": "control", "family": "03.13", "status": "MET"},
                {"id": "03.13.06", "label": "03.13.06 Connection Deny by Default", "type": "control", "family": "03.13", "status": "ACTIVE"}
            ]
            followups = [
                "Simulate: Deploy Perimeter Firewall Gateway",
                "Is a consumer router sufficient for NIST 800-171?",
                "Which ports should we strictly block on our firewall?"
            ]

        elif "backup" in msg_lower or "ransomware" in msg_lower or "recover" in msg_lower:
            reply = (
                "### Media Protection & Immutable Backups\n\n"
                "Under **NIST SP 800-171 Rev 3 (Control 03.08.01 & 03.08.03)**:\n\n"
                "- **The 3-2-1 Backup Rule**: Maintain 3 copies of data, across 2 different media types, with 1 copy stored off-site or in immutable cloud storage.\n"
                "- **Air-Gapped / Ransomware Resilient**: Ensure backup credentials are separated from standard domain admin accounts so attackers cannot delete recovery snapshots.\n"
                "- **Restoration Drills**: Test bare-metal restoration at least semi-annually."
            )
            kg_traces = [
                {"id": "03.08.01", "label": "03.08.01 Media Storage Protection", "type": "control", "family": "03.08", "status": "MET"},
                {"id": "03.08.03", "label": "03.08.03 Media Sanitation & Cryptography", "type": "control", "family": "03.08", "status": "ACTIVE"},
                {"id": "03.14.01", "label": "03.14.01 Flaw Remediation & Resilience", "type": "control", "family": "03.14", "status": "MET"}
            ]
            followups = [
                "How should we protect our NAS backups from ransomware?",
                "What cloud backup services are FedRAMP Moderate certified?",
                "Simulate: Enable encryption on all backup drives"
            ]

        elif "sprs" in msg_lower or "cmmc" in msg_lower or "score" in msg_lower or "audit" in msg_lower:
            reply = (
                "### NIST SP 800-171 Scoring & CMMC Assessment\n\n"
                "Department of Defense suppliers must submit a **Supplier Performance Risk System (SPRS)** score:\n\n"
                "- **Scoring Scale**: Ranges from **-203 to +110**.\n"
                "- **110 Maximum**: Achieving a +110 indicates complete implementation of all 110 requirements.\n"
                "- **Weighted Deductions**: Missing basic controls (e.g., lack of MFA, unsegmented Wi-Fi) results in severe 5-point and 3-point deductions.\n\n"
                "Run the **NIST SP 800-171 Audit** in the right panel to calculate your live score!"
            )
            kg_traces = [
                {"id": "03.01.01", "label": "03.01 Access Control", "type": "control", "family": "03.01", "status": "ACTIVE"},
                {"id": "03.05.01", "label": "03.05 Identification & Auth", "type": "control", "family": "03.05", "status": "ACTIVE"},
                {"id": "03.13.01", "label": "03.13 System & Comms", "type": "control", "family": "03.13", "status": "ACTIVE"}
            ]
            followups = [
                "Run an audit on our current network topology",
                "What are the top 3 highest impact fixes to raise our score?",
                "How does CMMC Level 2 map to NIST 800-171?"
            ]

        else:
            # Intelligent general response that references active topology and NEVER repeats welcome text
            asset_info = f"Your network currently has **{len(nodes)} mapped assets** and **{len(edges)} connections**." if nodes else "Your canvas is currently empty."
            reply = (
                f"### Cyber Clinic Guidance\n\n"
                f"Regarding **\"{message.strip()}\"**:\n\n"
                f"Under **NIST SP 800-171 Rev 3**, security controls work in synergy across Access Control (03.01), Identification (03.05), Media Protection (03.08), and Communications Protection (03.13).\n\n"
                f"**Active Topology Context**: {asset_info}\n\n"
                f"- **Recommendations**:\n"
                f"  1. Ensure all CUI repositories are encrypted with FIPS-validated AES-256 (03.08.03).\n"
                f"  2. Enforce Multi-Factor Authentication (MFA) across all administrative consoles and remote users (03.05.03).\n"
                f"  3. Maintain strict boundary separation between guest/visitor wireless and internal production assets (03.13.01).\n\n"
                f"Would you like me to inspect your network map, add new hardware, or simulate a security remediation?"
            )
            kg_traces = [
                {"id": "03.01.01", "label": "03.01 Access Control", "type": "control", "family": "03.01", "status": "ACTIVE"},
                {"id": "03.05.03", "label": "03.05 Multi-Factor Auth", "type": "control", "family": "03.05", "status": "ACTIVE"},
                {"id": "03.13.01", "label": "03.13 Boundary Protection", "type": "control", "family": "03.13", "status": "ACTIVE"}
            ]
            followups = [
                "What do you see in my network map?",
                "Simulate: Enable encryption on CUI storage",
                "How do we configure MFA for remote workers?"
            ]

        return {
            "reply": reply,
            "actions_taken": actions,
            "topology_mutations": mutations,
            "suggested_followups": followups,
            "kg_traces": kg_traces
        }

    def simulate_what_if_remediation(self, fix_type: str, target_node_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Interactive "What-If" Remediation Sandbox:
        Applies a simulated cybersecurity control fix to the active topology,
        triggers the multi-family NIST SP 800-171 audit, and calculates the before/after score delta.
        """
        from app.engine_graphrag.xai_reasoner import xai_reasoner

        # Snapshot current state before first simulation so user can revert
        if not self.what_if_backup_nodes:
            self.what_if_backup_nodes = copy.deepcopy(self.active_topology_nodes)
            self.what_if_backup_edges = copy.deepcopy(self.active_topology_edges)

        # Baseline score before applying this fix
        score_before = xai_reasoner.latest_audit_result.get("overall_score_pct", 0.0) if xai_reasoner.latest_audit_result else 0.0

        fix_type_upper = fix_type.upper()
        fix_title = ""
        description = ""

        if "ENCRYPT" in fix_type_upper or "VOLUME" in fix_type_upper:
            fix_title = "Simulated: Full-Disk / Volume Encryption Enabled"
            description = "Configured FIPS-compliant AES-256 volume encryption across all sensitive storage pools."
            for n in self.active_topology_nodes:
                if n.stores_cui or (target_node_id and n.id == target_node_id) or n.type in ["storage", "server"]:
                    n.has_firewall_or_mfa = True
            for e in self.active_topology_edges:
                e.is_encrypted = True

        elif "MFA" in fix_type_upper or "AUTH" in fix_type_upper:
            fix_title = "Simulated: Multi-Factor Authentication (MFA) Enforced"
            description = "Enforced TOTP/FIDO2 MFA across all user logins, administrative consoles, and remote VPN access."
            for n in self.active_topology_nodes:
                if n.type in ["device", "user", "cloud_service", "server"]:
                    n.has_firewall_or_mfa = True

        elif "SEGMENT" in fix_type_upper or "GUEST" in fix_type_upper or "WIFI" in fix_type_upper:
            fix_title = "Simulated: Guest Wi-Fi Isolated & Segmented"
            description = "Quarantined guest traffic into a dedicated VLAN with strict ACLs blocking access to internal office LAN."
            # Ensure guest subnet exists
            has_guest_sub = any("guest" in n.name.lower() and n.type == "subnet" for n in self.active_topology_nodes)
            if not has_guest_sub:
                guest_sub = NetworkNode(
                    id="subnet_guest_vlan",
                    name="Isolated Guest Wi-Fi VLAN",
                    type="subnet",
                    ip_or_subnet="192.168.99.0/24",
                    confidence=1.0
                )
                self.active_topology_nodes.append(guest_sub)
                # Sever direct edges from guest devices to CUI or private servers
                cui_ids = {n.id for n in self.active_topology_nodes if n.stores_cui}
                self.active_topology_edges = [
                    e for e in self.active_topology_edges
                    if not (e.target in cui_ids and "guest" in e.source.lower())
                ]

        elif "FIREWALL" in fix_type_upper or "PERIMETER" in fix_type_upper or "GATEWAY" in fix_type_upper:
            fix_title = "Simulated: Stateful Perimeter Firewall Deployed"
            description = "Installed perimeter boundary firewall with default-deny inbound rule sets."
            has_fw = any(n.type == "firewall" for n in self.active_topology_nodes)
            if not has_fw:
                fw = NetworkNode(
                    id="fw_perimeter_gateway",
                    name="Perimeter Security Gateway (pfSense)",
                    type="firewall",
                    ip_or_subnet="192.168.1.1",
                    has_firewall_or_mfa=True,
                    confidence=1.0
                )
                self.active_topology_nodes.append(fw)
                subnets = [n for n in self.active_topology_nodes if n.type == "subnet"]
                for s in subnets:
                    self.active_topology_edges.append(NetworkEdge(source=fw.id, target=s.id, relationship="PROTECTS"))
            else:
                for n in self.active_topology_nodes:
                    if n.type == "firewall":
                        n.has_firewall_or_mfa = True

        if fix_type not in self.active_what_if_fixes:
            self.active_what_if_fixes.append(fix_type)

        # Run re-audit
        new_audit = xai_reasoner.run_parallel_topology_audit(self.active_topology_nodes, self.active_topology_edges)
        score_after = new_audit.get("overall_score_pct", 0.0)
        score_delta = round(score_after - score_before, 1)

        topo_res = self.format_topology_response("What-If Simulation", self.active_topology_nodes, self.active_topology_edges, self.active_clarification_prompts)

        return {
            "success": True,
            "fix_title": fix_title or f"Simulated {fix_type}",
            "description": description or "Applied security fix simulation to active topology.",
            "score_before": score_before,
            "score_after": score_after,
            "score_delta": score_delta,
            "active_fixes": self.active_what_if_fixes,
            "audit_result": new_audit,
            "topology": topo_res
        }

    def revert_what_if_remediation(self) -> Dict[str, Any]:
        """Reverts active what-if simulations back to original baseline topology."""
        from app.engine_graphrag.xai_reasoner import xai_reasoner

        if self.what_if_backup_nodes:
            self.active_topology_nodes = copy.deepcopy(self.what_if_backup_nodes)
            self.active_topology_edges = copy.deepcopy(self.what_if_backup_edges or [])
            self.what_if_backup_nodes = None
            self.what_if_backup_edges = None

        self.active_what_if_fixes = []
        new_audit = xai_reasoner.run_parallel_topology_audit(self.active_topology_nodes, self.active_topology_edges)
        topo_res = self.format_topology_response("Reverted Baseline", self.active_topology_nodes, self.active_topology_edges, self.active_clarification_prompts)

        return {
            "success": True,
            "message": "Reverted all What-If simulations to original topology baseline.",
            "audit_result": new_audit,
            "topology": topo_res
        }

topology_parser = TopologyParser()


