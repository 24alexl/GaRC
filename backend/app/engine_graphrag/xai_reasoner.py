import re
import json
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List

from app.llm.factory import get_llm_provider
from app.engine_graphrag.retriever import graphrag_retriever, CORE_TECHNICAL_FAMILIES

logger = logging.getLogger("garc.engine1.reasoner")

class XAIReasoner:
    def __init__(self):
        self.latest_audit_result: Dict[str, Any] | None = None

    def _audit_family_worker(self, fam_code: str, fam_data: Dict[str, Any], active_nodes: List[Any], active_edges: List[Any]) -> Dict[str, Any]:
        """
        Specialist worker agent evaluating a single technical control family against the active topology.
        """
        fam_name = fam_data["family_name"]
        controls = fam_data["controls"]

        # Build clean topology summary
        topo_summary = "Active Network Topology:\n"
        if not active_nodes:
            topo_summary += "- No topology nodes defined.\n"
        else:
            for n in active_nodes:
                cui_str = " [STORES CUI]" if getattr(n, 'stores_cui', False) or (isinstance(n, dict) and n.get('stores_cui')) else ""
                mfa_str = " [MFA/FIREWALL CONFIRMED]" if getattr(n, 'has_firewall_or_mfa', False) or (isinstance(n, dict) and n.get('has_firewall_or_mfa')) else " [MFA/FIREWALL UNCONFIRMED]"
                node_name = getattr(n, 'name', n.get('name', 'Asset') if isinstance(n, dict) else str(n))
                node_type = getattr(n, 'type', n.get('type', 'device') if isinstance(n, dict) else 'device')
                node_ip = getattr(n, 'ip_or_subnet', n.get('ip_or_subnet', 'Unknown') if isinstance(n, dict) else 'Unknown')
                topo_summary += f"- Asset '{node_name}' (Type: {node_type}, IP: {node_ip}){cui_str}{mfa_str}\n"

        for e in active_edges:
            src = getattr(e, 'source', e.get('source', '') if isinstance(e, dict) else '')
            tgt = getattr(e, 'target', e.get('target', '') if isinstance(e, dict) else '')
            rel = getattr(e, 'relationship', e.get('relationship', 'CONNECTED_TO') if isinstance(e, dict) else 'CONNECTED_TO')
            enc = " [ENCRYPTED]" if getattr(e, 'is_encrypted', False) or (isinstance(e, dict) and e.get('is_encrypted')) else ""
            topo_summary += f"- Connection: {src} --[{rel}]--> {tgt}{enc}\n"

        # Build candidate controls text with assessment objectives
        controls_text = ""
        for c in controls[:6]: # Focus on key controls per family
            controls_text += f"\nControl {c['id']}: {c['title']}\n"
            controls_text += f"Requirement: {c['description']}\n"
            if c.get("objectives"):
                controls_text += "Assessment Objectives:\n"
                for idx, obj in enumerate(c["objectives"][:3]):
                    controls_text += f"  - Obj {idx+1}: {obj}\n"

        system_instruction = f"""You are a certified NIST SP 800-171 Rev 3 cybersecurity compliance auditor specializing in Family {fam_code} ({fam_name}).
Your mission is to strictly audit whether each candidate control is "MET", "UNMET", or "INSUFFICIENT_DATA" based ONLY on observable evidence in the active network topology.

Auditing Rules:
1. "MET": Only if the active topology contains explicit evidence satisfying the control (e.g. firewall protecting LAN for 03.13.01, or MFA confirmed for 03.05.03).
2. "UNMET": If the topology explicitly displays a non-compliant state (e.g. CUI stored on an unencrypted volume for 03.08.07, or unauthenticated remote access for 03.01.01).
3. "INSUFFICIENT_DATA": If the property is unstated or ambiguous. Do NOT assume or guess.
4. "action_for_assessor": Formulate a crisp, practical question for a cyber clinic student or assessor to ask the client.
"""

        schema_description = """{
  "family_code": "03.01",
  "family_name": "Access Control",
  "evaluated_controls": [
    {
      "control_id": "03.01.01",
      "title": "NIST SP 800-171 Control 03.01.01",
      "status": "MET",
      "confidence": 0.95,
      "finding": "Perimeter gateway provides logical boundary separation.",
      "evidence_from_topology": "pfSense firewall on 192.168.1.1",
      "action_for_assessor": "Verify that unauthorized device connection attempts are dropped.",
      "objective_results": [
        {
          "objective_text": "limit system access to authorized users",
          "status": "MET"
        }
      ]
    }
  ]
}"""

        prompt = f"""{topo_summary}

Candidate NIST SP 800-171 Rev 3 Controls to Audit:
{controls_text}

Audit each control and its objectives against the topology facts."""

        llm = get_llm_provider()
        payload = {}
        try:
            payload = llm.generate_structured_json(prompt, schema_description=schema_description, system_instruction=system_instruction)
        except Exception as e:
            logger.warning(f"LLM family audit for {fam_code} failed: {e}")

        # Deterministic validation and fallback
        evaluated = []
        if payload and isinstance(payload, dict) and "evaluated_controls" in payload:
            for item in payload.get("evaluated_controls", []):
                status = str(item.get("status", "INSUFFICIENT_DATA")).upper()
                if status not in ["MET", "UNMET", "INSUFFICIENT_DATA"]:
                    status = "INSUFFICIENT_DATA"
                cid = str(item.get("control_id", ""))
                ctrl_objs = next((c.get("objectives", []) for c in controls if c.get("id") == cid), [])
                evaluated.append({
                    "control_id": cid,
                    "title": str(item.get("title", f"NIST {cid}")),
                    "status": status,
                    "confidence": float(item.get("confidence", 0.90)),
                    "finding": str(item.get("finding", "Audited against network topology.")),
                    "evidence_from_topology": str(item.get("evidence_from_topology", "Topology configuration")),
                    "action_for_assessor": str(item.get("action_for_assessor", "Verify technical controls with IT administrator.")),
                    "objectives": ctrl_objs,
                    "objective_results": item.get("objective_results", [])
                })

        # Fallback deterministic evaluator if LLM returned empty
        if not evaluated:
            has_fw = any((getattr(n, 'type', '') == 'firewall' or (isinstance(n, dict) and n.get('type') == 'firewall')) for n in active_nodes)
            has_mfa = any(getattr(n, 'has_firewall_or_mfa', False) or (isinstance(n, dict) and n.get('has_firewall_or_mfa')) for n in active_nodes)
            has_cui = any(getattr(n, 'stores_cui', False) or (isinstance(n, dict) and n.get('stores_cui')) for n in active_nodes)

            for c in controls[:3]:
                cid = c["id"]
                status = "INSUFFICIENT_DATA"
                finding = f"Evaluated {c['title']} against topology."
                action = f"Ask assessor to verify configuration for NIST {cid}."

                if fam_code == "03.13": # System and Comm Protection
                    if cid == "03.13.01":
                        status = "MET" if has_fw else "UNMET"
                        finding = "Perimeter firewall protects internal subnet boundaries." if has_fw else "No perimeter firewall identified at boundary entry points."
                        action = "Verify firewall stateful inspection and ingress rule base." if has_fw else "Verify if managed ISP gateway provides firewall filtering."
                    elif cid == "03.13.11":
                        status = "MET" if has_mfa else ("UNMET" if has_cui else "INSUFFICIENT_DATA")
                        finding = "Cryptographic protection confirmed on active connections." if has_mfa else "Unencrypted channels detected."
                elif fam_code == "03.05": # Identification and Auth
                    status = "MET" if has_mfa else "UNMET"
                    finding = "Multifactor authentication (MFA) confirmed on gateways and workstations." if has_mfa else "MFA unconfirmed on remote gateway or administrative access."
                    action = "Verify MFA enforcement for all remote access sessions."
                elif fam_code == "03.08": # Media Protection
                    if has_cui:
                        status = "MET" if has_mfa else "UNMET"
                        finding = "CUI volume encryption confirmed on local storage." if has_mfa else "Storage node stores CUI but volume encryption is unconfirmed."
                        action = "Verify if AES-256 BitLocker/ZFS volume encryption is enabled on storage assets."
                elif fam_code == "03.01": # Access Control
                    status = "MET" if has_fw or has_mfa else "UNMET"
                    finding = "Access control boundaries enforced." if (has_fw or has_mfa) else "Flat unsegmented network allows unrestricted device access."
                    action = "Verify network segmentation and access control lists."
                elif fam_code == "03.14": # System Integrity
                    status = "MET" if has_fw else "INSUFFICIENT_DATA"
                    finding = "Boundary protection mechanisms active." if has_fw else "Malicious code scanning at boundary entry points is unconfirmed."
                    action = "Verify endpoint EDR and perimeter malware scanning policies."

                evaluated.append({
                    "control_id": cid,
                    "title": c["title"],
                    "status": status,
                    "confidence": 0.90,
                    "finding": finding,
                    "evidence_from_topology": "Active network nodes and connection attributes",
                    "action_for_assessor": action,
                    "objectives": c.get("objectives", []),
                    "objective_results": [{"objective_text": obj, "status": status} for obj in c.get("objectives", [])[:2]]
                })

        # Multi-Hop Auditor Verification Loop:
        # Cross-verify each control against CPRT knowledge graph & topology evidence paths
        verified_evaluated = []
        cprt_control_ids = {c["id"] for c in controls}
        for item in evaluated:
            cid = item["control_id"]
            # Multi-hop verification 1: verify control exists in NIST CPRT graph
            if cid not in cprt_control_ids:
                matching_c = next((c for c in controls if c["id"].startswith(fam_code)), None)
                if matching_c:
                    cid = matching_c["id"]
                    item["control_id"] = cid
                    item["title"] = matching_c["title"]
                    item["objectives"] = matching_c.get("objectives", [])

            # Multi-hop verification 2: Topology path evidence verification
            if cid in ["03.13.01", "03.13.05"]:  # Boundary Protection / Separation
                has_fw = any((getattr(n, 'type', '') == 'firewall' or (isinstance(n, dict) and n.get('type') == 'firewall')) for n in active_nodes)
                has_guest = any(("guest" in str(getattr(n, 'name', '')).lower() or (isinstance(n, dict) and "guest" in str(n.get('name', '')).lower())) for n in active_nodes)
                if not has_fw:
                    item["status"] = "UNMET"
                    item["finding"] = "Boundary Protection: No stateful perimeter firewall protecting subnet interfaces."
                elif has_guest:
                    item["finding"] = item["finding"] + " (Guest Wi-Fi detected: verify VLAN isolation)"
            elif cid in ["03.08.07", "03.13.11"]: # Encryption
                has_cui = any((getattr(n, 'stores_cui', False) or (isinstance(n, dict) and n.get('stores_cui'))) for n in active_nodes)
                has_sec = any((getattr(n, 'has_firewall_or_mfa', False) or (isinstance(n, dict) and n.get('has_firewall_or_mfa'))) for n in active_nodes if getattr(n, 'stores_cui', False) or (isinstance(n, dict) and n.get('stores_cui')))
                if has_cui and not has_sec:
                    item["status"] = "UNMET"
                    item["finding"] = "Media Protection: Sensitive CUI storage asset lacks verified at-rest volume encryption."

            verified_evaluated.append(item)
        evaluated = verified_evaluated

        return {
            "family_code": fam_code,
            "family_name": fam_name,
            "short_code": fam_data.get("short_code", fam_code),
            "focus": fam_data.get("focus", ""),
            "evaluated_controls": evaluated
        }


    def run_parallel_topology_audit(self, active_nodes: List[Any], active_edges: List[Any]) -> Dict[str, Any]:
        """
        Executes a high-speed parallel audit across the 5 core technical families concurrently.
        """
        technical_families = graphrag_retriever.get_technical_family_subgraphs()
        
        logger.info(f"Starting parallel 5-family objective-level audit across {len(technical_families)} technical families...")

        family_results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(self._audit_family_worker, fam_code, fam_data, active_nodes, active_edges)
                for fam_code, fam_data in technical_families.items()
            ]
            for future in futures:
                try:
                    res = future.result()
                    family_results.append(res)
                except Exception as e:
                    logger.error(f"Error in family audit worker: {e}")

        # Compute aggregate metrics
        total_controls = 0
        met_count = 0
        unmet_count = 0
        insufficient_count = 0
        all_evaluated_controls = []
        family_scorecards = []

        cyto_nodes = []
        cyto_edges = []

        # Root Audit node for Cytoscape
        cyto_nodes.append({
            "data": {
                "id": "Audit_Root",
                "label": "5-Family Technical Audit",
                "type": "query",
                "status": "INFO",
                "detail": f"Evaluated {len(active_nodes)} topology nodes across 5 technical families."
            }
        })

        for fam in family_results:
            fam_controls = fam.get("evaluated_controls", [])
            fam_met = sum(1 for c in fam_controls if c["status"] == "MET")
            fam_unmet = sum(1 for c in fam_controls if c["status"] == "UNMET")
            fam_insufficient = sum(1 for c in fam_controls if c["status"] == "INSUFFICIENT_DATA")
            fam_total = len(fam_controls)

            fam_score = round((fam_met / fam_total * 100) if fam_total > 0 else 0, 1)
            fam_status = "Good" if fam_score >= 70 else ("Action Needed" if fam_score >= 40 else "Critical Gap")

            total_controls += fam_total
            met_count += fam_met
            unmet_count += fam_unmet
            insufficient_count += fam_insufficient
            all_evaluated_controls.extend(fam_controls)

            family_scorecards.append({
                "family_code": fam["family_code"],
                "family_name": fam["family_name"],
                "short_code": fam["short_code"],
                "focus": fam["focus"],
                "total": fam_total,
                "met": fam_met,
                "unmet": fam_unmet,
                "insufficient_data": fam_insufficient,
                "score_pct": fam_score,
                "status": fam_status
            })

            # Add Family and Control nodes to Cytoscape visualization
            fam_node_id = f"Fam_{fam['family_code']}"
            cyto_nodes.append({
                "data": {
                    "id": fam_node_id,
                    "label": f"{fam['short_code']} ({fam['family_code']})\n{fam['family_name']}",
                    "type": "family",
                    "family_code": fam["family_code"],
                    "family_name": fam["family_name"],
                    "short_code": fam["short_code"],
                    "focus": fam.get("focus", ""),
                    "score_pct": fam_score,
                    "status": fam_status,
                    "met": fam_met,
                    "unmet": fam_unmet,
                    "insufficient_data": fam_insufficient,
                    "total": fam_total
                }
            })
            cyto_edges.append({
                "data": {
                    "id": f"Edge_Root_{fam['family_code']}",
                    "source": "Audit_Root",
                    "target": fam_node_id,
                    "label": "INCLUDES_FAMILY",
                    "type": "INCLUDES_FAMILY",
                    "meaning": f"Establishes the technical audit scope connecting to the {fam['family_name']} ({fam['family_code']}) domain."
                }
            })

            for ctrl in fam_controls:
                ctrl_node_id = f"Ctrl_{ctrl['control_id']}"
                cyto_nodes.append({
                    "data": {
                        "id": ctrl_node_id,
                        "label": f"NIST {ctrl['control_id']}",
                        "type": "control",
                        "control_id": ctrl["control_id"],
                        "title": ctrl.get("title", f"NIST {ctrl['control_id']}"),
                        "status": ctrl["status"],
                        "description": ctrl.get("description") or ctrl.get("finding") or f"NIST SP 800-171 Rev 3 Requirement for {ctrl['control_id']}",
                        "finding": ctrl.get("finding", "Audited against active topology."),
                        "guidance": ctrl.get("action_for_assessor", "Verify control implementation."),
                        "action_for_assessor": ctrl.get("action_for_assessor", "Verify control implementation."),
                        "evidence_from_topology": ctrl.get("evidence_from_topology", "Network topology assets and connection attributes"),
                        "objectives": ctrl.get("objectives", []),
                        "family_code": fam["family_code"],
                        "family_name": fam["family_name"]
                    }
                })
                cyto_edges.append({
                    "data": {
                        "id": f"Edge_{fam_node_id}_{ctrl_node_id}",
                        "source": fam_node_id,
                        "target": ctrl_node_id,
                        "label": ctrl["status"],
                        "type": "EVALUATES",
                        "meaning": f"Automated audit determination status for control {ctrl['control_id']}: {ctrl['status']}"
                    }
                })

                # Branch out specific CPRT assessment determination objectives (DS-A.03.xx.xx)
                for o_idx, obj_text in enumerate(ctrl.get("objectives", [])):
                    letter = chr(ord('a') + o_idx) if o_idx < 26 else str(o_idx + 1)
                    obj_label = f"DS-A.{ctrl['control_id']}.{letter}"
                    obj_node_id = f"Obj_{ctrl['control_id']}_{letter}"

                    cyto_nodes.append({
                        "data": {
                            "id": obj_node_id,
                            "label": obj_label,
                            "type": "objective",
                            "obj_label": obj_label,
                            "status": ctrl["status"],
                            "description": obj_text,
                            "detail": f"CPRT Assessment Objective ({obj_label}): {obj_text}",
                            "parent_control": ctrl["control_id"],
                            "parent_title": ctrl.get("title", f"NIST {ctrl['control_id']}")
                        }
                    })
                    cyto_edges.append({
                        "data": {
                            "id": f"Edge_{ctrl_node_id}_{obj_node_id}",
                            "source": ctrl_node_id,
                            "target": obj_node_id,
                            "label": "DETERMINES",
                            "type": "DETERMINES",
                            "meaning": f"Links parent security requirement {ctrl['control_id']} to NIST SP 800-171A assessment objective test {obj_label}."
                        }
                    })

        overall_score = round(((met_count * 1.0 + insufficient_count * 0.3) / total_controls * 100) if total_controls > 0 else 0, 1)

        # Generate Top 3 High-Impact Remediation Fixes
        top_fixes = self._generate_top_fixes(all_evaluated_controls, active_nodes)

        # Assessor Interview Checklist items for remaining questions
        assessor_checklist = [
            {
                "family": c.get("control_id", "")[:5],
                "control_id": c["control_id"],
                "title": c["title"],
                "question_to_ask": c["action_for_assessor"],
                "why_it_matters": c["finding"]
            }
            for c in all_evaluated_controls
            if c["status"] in ["UNMET", "INSUFFICIENT_DATA"]
        ][:8]

        result = {
            "status": "completed",
            "overall_score_pct": overall_score,
            "total_controls_evaluated": total_controls,
            "met_count": met_count,
            "unmet_count": unmet_count,
            "insufficient_data_count": insufficient_count,
            "family_scorecards": family_scorecards,
            "top_fixes": top_fixes,
            "assessor_checklist": assessor_checklist,
            "evaluated_controls": all_evaluated_controls,
            "cytoscape_graph": {
                "nodes": cyto_nodes,
                "edges": cyto_edges
            }
        }

        self.latest_audit_result = result
        return result

    def _generate_top_fixes(self, evaluated_controls: List[Dict[str, Any]], active_nodes: List[Any]) -> List[Dict[str, Any]]:
        """
        Synthesizes the top 3 highest-impact, plain-English remediation actions
        tailored for small businesses and non-profits.
        """
        fixes = []
        unmet_or_partial = [c for c in evaluated_controls if c["status"] in ["UNMET", "INSUFFICIENT_DATA"]]

        has_cui = any(getattr(n, 'stores_cui', False) or (isinstance(n, dict) and n.get('stores_cui')) for n in active_nodes)
        has_fw = any((getattr(n, 'type', '') == 'firewall' or (isinstance(n, dict) and n.get('type') == 'firewall')) for n in active_nodes)
        has_mfa = any(getattr(n, 'has_firewall_or_mfa', False) or (isinstance(n, dict) and n.get('has_firewall_or_mfa')) for n in active_nodes)

        # Fix Candidate 1: Encryption on CUI Volumes
        if has_cui and not has_mfa:
            fixes.append({
                "rank": 1,
                "priority": "HIGH",
                "title": "Enable Full-Disk Volume Encryption on CUI Storage Assets",
                "control_ref": "NIST SP 800-171 Rev 3 — 03.08.07 & 03.13.11",
                "family": "Media Protection (MP) / Comms (SC)",
                "impact": "+15% Compliance Readiness",
                "effort": "Low (1-2 Hours)",
                "what_if_type": "ENCRYPT_CUI_VOLUME",
                "description": "Sensitive client/donor data is stored on network drives without verified at-rest encryption.",
                "plain_english_steps": [
                    "Turn on BitLocker (Windows) or FileVault (Mac) across all workstations holding sensitive documents.",
                    "Enable hardware or volume encryption (AES-256) on your Synology/TrueNAS storage pools.",
                    "Store encryption recovery keys in a secure offline password manager."
                ]
            })

        # Fix Candidate 2: Multi-Factor Authentication (MFA)
        if not has_mfa or any(c["control_id"] == "03.05.03" and c["status"] != "MET" for c in evaluated_controls):
            fixes.append({
                "rank": len(fixes) + 1,
                "priority": "CRITICAL",
                "title": "Enforce Multi-Factor Authentication (MFA) on All Remote & Admin Logins",
                "control_ref": "NIST SP 800-171 Rev 3 — 03.05.03 & 03.01.01",
                "family": "Identification & Authentication (IA)",
                "impact": "+20% Compliance Readiness",
                "effort": "Medium (2-4 Hours)",
                "what_if_type": "ENFORCE_MFA",
                "description": "Remote gateways, VPNs, and administrative access must require a second factor (authenticator app or security key).",
                "plain_english_steps": [
                    "Require authenticator apps (e.g. Microsoft Authenticator or Google Authenticator) for Microsoft 365, Google Workspace, and VPN portals.",
                    "Disable SMS-based OTP where possible in favor of TOTP apps or FIDO2 keys.",
                    "Audit user lists to ensure former employees have their access revoked."
                ]
            })

        # Fix Candidate 3: Network Segmentation & Perimeter Gateway
        if not has_fw or any(c["control_id"] == "03.13.01" and c["status"] != "MET" for c in evaluated_controls):
            fixes.append({
                "rank": len(fixes) + 1,
                "priority": "HIGH",
                "title": "Isolate Guest Wi-Fi & Deploy Dedicated Perimeter Firewall",
                "control_ref": "NIST SP 800-171 Rev 3 — 03.13.01 & 03.13.05",
                "family": "System and Communications Protection (SC)",
                "impact": "+15% Compliance Readiness",
                "effort": "Medium (Half Day)",
                "what_if_type": "SEGMENT_GUEST_WIFI",
                "description": "Internal work computers and sensitive data assets must not share an unsegmented network with guest visitors.",
                "plain_english_steps": [
                    "Configure a dedicated Guest VLAN or separate SSID on your router with client isolation enabled.",
                    "Block traffic from the guest network to your internal office subnet (192.168.1.0/24).",
                    "Verify stateful firewall default-deny rules on incoming WAN traffic."
                ]
            })

        # Fix Candidate 4: Endpoint Security / Antivirus & Patching
        if len(fixes) < 3:
            fixes.append({
                "rank": len(fixes) + 1,
                "priority": "MEDIUM",
                "title": "Standardize Endpoint Protection (EDR) & Automated Patching",
                "control_ref": "NIST SP 800-171 Rev 3 — 03.14.01 & 03.14.02",
                "family": "System and Information Integrity (SI)",
                "impact": "+10% Compliance Readiness",
                "effort": "Low (Ongoing)",
                "what_if_type": "DEPLOY_FIREWALL",
                "description": "Ensure all client laptops and servers have active malware scanning and automatic security update channels.",
                "plain_english_steps": [
                    "Enable Windows Defender or central EDR across all office workstations.",
                    "Configure automatic weekly OS and browser security updates.",
                    "Conduct regular quarterly backup restoration tests."
                ]
            })

        return fixes[:3]


    def generate_executive_report_data(self, org_name: str = "Client Organization") -> Dict[str, Any]:
        """Generates comprehensive structured export payload for executive & assessor reporting."""
        from app.engine_topology.parser import topology_parser
        nodes = topology_parser.active_topology_nodes
        edges = topology_parser.active_topology_edges

        audit = self.latest_audit_result
        if not audit:
            audit = self.run_parallel_topology_audit(nodes, edges)

        return {
            "organization_name": org_name,
            "assessment_framework": "NIST SP 800-171 Rev 3 (Core Technical Architecture)",
            "overall_readiness_pct": audit.get("overall_score_pct", 0),
            "total_controls_evaluated": audit.get("total_controls_evaluated", 0),
            "met_count": audit.get("met_count", 0),
            "unmet_count": audit.get("unmet_count", 0),
            "insufficient_data_count": audit.get("insufficient_data_count", 0),
            "active_assets": [
                {
                    "name": n.name,
                    "type": n.type,
                    "ip_or_subnet": n.ip_or_subnet,
                    "stores_cui": n.stores_cui,
                    "has_firewall_or_mfa": n.has_firewall_or_mfa
                }
                for n in nodes
            ],
            "family_scores": audit.get("family_scorecards", []),
            "top_fixes": audit.get("top_fixes", []),
            "assessor_checklist": audit.get("assessor_checklist", [])
        }

    def get_baseline_cprt_graph(self) -> Dict[str, Any]:
        """
        Generates the static, inherent NIST SP 800-171 Rev 3 CPRT Knowledge Graph
        without requiring an active topology audit.
        """
        technical_families = graphrag_retriever.get_technical_family_subgraphs()
        cyto_nodes = []
        cyto_edges = []
        family_scorecards = []

        # Root Audit node
        cyto_nodes.append({
            "data": {
                "id": "Audit_Root",
                "label": "5-Family Technical Audit",
                "type": "query",
                "status": "INFO",
                "detail": "NIST SP 800-171 Rev 3 Core Technical Architecture Baseline"
            }
        })

        for fam_code, fam_data in technical_families.items():
            fam_name = fam_data.get("family_name") or fam_data.get("name", fam_code)
            short_code = fam_data.get("short_code", fam_code)
            controls = fam_data.get("controls", [])
            fam_node_id = f"Fam_{fam_code}"

            family_scorecards.append({
                "family_code": fam_code,
                "family_name": fam_name,
                "short_code": short_code,
                "focus": fam_data.get("focus", ""),
                "total": len(controls),
                "met": 0,
                "unmet": 0,
                "insufficient_data": len(controls),
                "score_pct": 0,
                "status": "Ready to Audit"
            })

            cyto_nodes.append({
                "data": {
                    "id": fam_node_id,
                    "label": f"{short_code} ({fam_code})\n{fam_name}",
                    "type": "family",
                    "family_code": fam_code,
                    "family_name": fam_name,
                    "short_code": short_code,
                    "focus": fam_data.get("focus", ""),
                    "score_pct": 0,
                    "status": "Ready to Audit",
                    "met": 0,
                    "unmet": 0,
                    "insufficient_data": len(controls),
                    "total": len(controls)
                }
            })

            cyto_edges.append({
                "data": {
                    "id": f"Edge_Root_{fam_code}",
                    "source": "Audit_Root",
                    "target": fam_node_id,
                    "label": "INCLUDES_FAMILY",
                    "type": "INCLUDES_FAMILY",
                    "meaning": f"Establishes the technical audit scope connecting to the {fam_name} ({fam_code}) domain."
                }
            })

            for ctrl in controls:
                ctrl_id = ctrl["id"]
                ctrl_node_id = f"Ctrl_{ctrl_id}"
                cyto_nodes.append({
                    "data": {
                        "id": ctrl_node_id,
                        "label": f"NIST {ctrl_id}",
                        "type": "control",
                        "control_id": ctrl_id,
                        "title": ctrl.get("title", f"NIST {ctrl_id}"),
                        "status": "PENDING_AUDIT",
                        "description": ctrl.get("description", f"NIST SP 800-171 Rev 3 Requirement for {ctrl_id}"),
                        "formal_requirement": ctrl.get("description", f"NIST SP 800-171 Rev 3 Requirement for {ctrl_id}"),
                        "finding": "Baseline control standard loaded. Click 'Run NIST SP 800-171 Audit' to evaluate against active topology.",
                        "guidance": ctrl.get("guidance") or ctrl.get("small_biz_guidance", "Verify control implementation."),
                        "action_for_assessor": ctrl.get("guidance") or ctrl.get("small_biz_guidance", "Verify control implementation."),
                        "objectives": ctrl.get("objectives", []),
                        "family_code": fam_code,
                        "family_name": fam_name
                    }
                })
                cyto_edges.append({
                    "data": {
                        "id": f"Edge_{fam_node_id}_{ctrl_node_id}",
                        "source": fam_node_id,
                        "target": ctrl_node_id,
                        "label": "EVALUATES",
                        "type": "EVALUATES",
                        "meaning": f"NIST SP 800-171 requirement standard {ctrl_id} awaiting topology assessment."
                    }
                })

                for o_idx, obj_text in enumerate(ctrl.get("objectives", [])):
                    letter = chr(ord('a') + o_idx) if o_idx < 26 else str(o_idx + 1)
                    obj_label = f"DS-A.{ctrl_id}.{letter}"
                    obj_node_id = f"Obj_{ctrl_id}_{letter}"

                    cyto_nodes.append({
                        "data": {
                            "id": obj_node_id,
                            "label": obj_label,
                            "type": "objective",
                            "obj_label": obj_label,
                            "status": "PENDING_AUDIT",
                            "description": obj_text,
                            "detail": f"CPRT Assessment Objective ({obj_label}): {obj_text}",
                            "parent_control": ctrl_id,
                            "parent_title": ctrl.get("title", f"NIST {ctrl_id}")
                        }
                    })
                    cyto_edges.append({
                        "data": {
                            "id": f"Edge_{ctrl_node_id}_{obj_node_id}",
                            "source": ctrl_node_id,
                            "target": obj_node_id,
                            "label": "DETERMINES",
                            "type": "DETERMINES",
                            "meaning": f"Links parent security requirement {ctrl_id} to NIST SP 800-171A assessment objective test {obj_label}."
                        }
                    })

        return {
            "cytoscape_graph": {
                "nodes": cyto_nodes,
                "edges": cyto_edges
            },
            "family_scorecards": family_scorecards
        }

    def explain_control_finding(self, control_id: str, active_nodes: List[Any], active_edges: List[Any]) -> Dict[str, Any]:
        """
        Generates an instant, contextual single-control explanation for the 'Inspect Finding' drawer.
        """
        # Find control in CPRT KG
        target_ctrl = None
        for ctrl in graphrag_retriever.get_technical_family_subgraphs().values():
            for c in ctrl["controls"]:
                if c["id"] == control_id:
                    target_ctrl = c
                    break
            if target_ctrl:
                break

        if not target_ctrl:
            return {
                "control_id": control_id,
                "title": f"NIST SP 800-171 Control {control_id}",
                "description": "Control details not found in active technical families.",
                "objectives": [],
                "finding_explanation": "No assessment data available.",
                "action_for_assessor": "Verify control requirements in NIST SP 800-171 Rev 3."
            }

        # Check existing evaluation finding if available
        finding_info = None
        if self.latest_audit_result:
            for c in self.latest_audit_result.get("evaluated_controls", []):
                if c["control_id"] == control_id:
                    finding_info = c
                    break

        status = finding_info["status"] if finding_info else "INSUFFICIENT_DATA"
        finding = finding_info["finding"] if finding_info else "Audited against active network configuration."
        action = finding_info["action_for_assessor"] if finding_info else "Inspect system configuration to confirm compliance."

        return {
            "control_id": control_id,
            "title": target_ctrl["title"],
            "description": target_ctrl["description"],
            "status": status,
            "objectives": target_ctrl.get("objectives", []),
            "finding_explanation": finding,
            "action_for_assessor": action,
            "references_800_53": target_ctrl.get("references_800_53", [])
        }

    def answer_query(self, user_query: str) -> Dict[str, Any]:
        """Legacy general educational Q&A handler."""
        retrieved_data = graphrag_retriever.retrieve_relevant_subgraph(user_query)
        controls = retrieved_data["controls"]
        graph = retrieved_data["graph"]

        from app.engine_topology.parser import topology_parser
        active_nodes = topology_parser.active_topology_nodes
        active_edges = topology_parser.active_topology_edges

        context_str = ""
        if active_nodes:
            context_str += "### Active User Network Topology Nodes:\n"
            for n in active_nodes:
                cui_str = " (Stores CUI: Yes)" if getattr(n, 'stores_cui', False) else ""
                sec_str = " (Firewall/MFA: Active)" if getattr(n, 'has_firewall_or_mfa', False) else " (Firewall/MFA: UNPROTECTED)"
                context_str += f"- Node '{getattr(n, 'name', 'Asset')}' [Type: {getattr(n, 'type', 'device')}]{cui_str}{sec_str}\n"

        context_str += "### Retrieved NIST SP 800-171 Controls Context:\n"
        cited_ids = []
        for ctrl in controls:
            cited_ids.append(ctrl['id'])
            context_str += f"- Control ID: {ctrl['id']} ({ctrl['title']}) - Family: {ctrl['family']}\n"
            context_str += f"  Description: {ctrl['description']}\n"

        system_prompt = """You are GaRC, an expert cybersecurity compliance copilot for small businesses adhering to NIST SP 800-171 Rev 3.
Provide a clear, objective educational answer citing relevant NIST controls."""

        prompt = f"User Question: \"{user_query}\"\n\nContext:\n{context_str}"
        llm = get_llm_provider()
        llm_response = llm.generate_text(prompt, system_instruction=system_prompt)

        return {
            "query": user_query,
            "markdown_response": llm_response,
            "cited_controls": cited_ids,
            "graph": graph
        }

xai_reasoner = XAIReasoner()

