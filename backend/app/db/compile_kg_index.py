import os
import json
import logging
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("garc.compile_kg")

CPRT_FILE_PATH = os.path.join(os.path.dirname(__file__), "cprt_SP_800_171_3_0_0_07-21-2026.json")
OUTPUT_KG_PATH = os.path.join(os.path.dirname(__file__), "nist_800_171_graph_index.json")

FAMILY_METADATA = {
    "03.01": {"name": "Access Control", "assets": ["device", "server", "user", "cloud_service"]},
    "03.02": {"name": "Awareness and Training", "assets": ["user"]},
    "03.03": {"name": "Audit and Accountability", "assets": ["server", "firewall", "device"]},
    "03.04": {"name": "Configuration Management", "assets": ["device", "server", "storage"]},
    "03.05": {"name": "Identification and Authentication", "assets": ["user", "device", "firewall", "cloud_service"]},
    "03.06": {"name": "Incident Response", "assets": ["user", "server"]},
    "03.07": {"name": "Maintenance", "assets": ["device", "server"]},
    "03.08": {"name": "Media Protection", "assets": ["storage", "device"]},
    "03.09": {"name": "Personnel Security", "assets": ["user"]},
    "03.10": {"name": "Physical Protection", "assets": ["server", "storage", "firewall"]},
    "03.11": {"name": "Risk Assessment", "assets": ["user", "server"]},
    "03.12": {"name": "Security Assessment and Monitoring", "assets": ["firewall", "server", "device"]},
    "03.13": {"name": "System and Communications Protection", "assets": ["firewall", "storage", "cloud_service", "subnet"]},
    "03.14": {"name": "System and Information Integrity", "assets": ["device", "server", "firewall"]},
    "03.15": {"name": "Planning", "assets": ["user", "server"]},
    "03.16": {"name": "System and Services Acquisition", "assets": ["cloud_service", "server"]},
    "03.17": {"name": "Supply Chain Risk Management", "assets": ["cloud_service", "storage"]}
}

def generate_clean_kg():
    """Compiles raw CPRT JSON dataset into a hyper-structured, explicit GraphRAG Knowledge Graph Index."""
    if not os.path.exists(CPRT_FILE_PATH):
        logger.error(f"CPRT file missing at {CPRT_FILE_PATH}")
        return

    with open(CPRT_FILE_PATH, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    elements = raw_data.get("response", {}).get("elements", {}).get("elements", [])
    relationships = raw_data.get("response", {}).get("elements", {}).get("relationships", [])

    nodes = []
    edges = []

    # 1. Family Nodes
    families_map = {}
    for el in elements:
        if el.get("element_type") == "family":
            fid = el.get("element_identifier", "")
            title = el.get("title", "")
            meta = FAMILY_METADATA.get(fid, {"name": title, "assets": ["device", "server"]})
            fam_node_id = f"FAM_{fid}"
            families_map[fid] = {
                "id": fam_node_id,
                "code": fid,
                "type": "family",
                "label": meta["name"],
                "mapped_assets": meta["assets"]
            }
            nodes.append({
                "id": fam_node_id,
                "type": "family",
                "label": meta["name"],
                "code": fid,
                "mapped_assets": meta["assets"]
            })

    # 2. Control Nodes
    controls_map = {}
    for el in elements:
        etype = el.get("element_type")
        eident = el.get("element_identifier", "")
        text = el.get("text", "")

        if etype == "security_requirement":
            parts = eident.replace("SR-", "").split(".")
            if len(parts) >= 3:
                ctrl_id = f"{parts[0]}.{parts[1]}.{parts[2]}"
                fam_id = f"{parts[0]}.{parts[1]}"

                if ctrl_id not in controls_map:
                    fam_info = families_map.get(fam_id, {"label": "Security Controls", "mapped_assets": ["device"]})
                    controls_map[ctrl_id] = {
                        "id": ctrl_id,
                        "type": "control",
                        "label": f"NIST {ctrl_id}",
                        "family_id": f"FAM_{fam_id}",
                        "family_name": fam_info["label"],
                        "title": f"NIST SP 800-171 Control {ctrl_id}",
                        "description": "",
                        "sub_requirements": [],
                        "objectives": [],
                        "references_800_53": [],
                        "small_biz_guidance": f"Implement baseline security configurations and role-based access for {fam_info['label']}.",
                        "mapped_asset_types": fam_info["mapped_assets"]
                    }

                if text:
                    controls_map[ctrl_id]["sub_requirements"].append(text)
                    if not controls_map[ctrl_id]["description"]:
                        controls_map[ctrl_id]["description"] = text

    # 3. Assessment Objective Nodes & Links
    obj_count = 0
    for el in elements:
        if el.get("element_type") == "determination":
            eident = el.get("element_identifier", "")
            text = el.get("text", "")
            if text and "DS-A." in eident:
                clean = eident.replace("DS-A.", "")
                parts = clean.split(".")
                if len(parts) >= 3:
                    ctrl_id = f"{parts[0]}.{parts[1]}.{parts[2]}"
                    if ctrl_id in controls_map:
                        controls_map[ctrl_id]["objectives"].append(text)
                        obj_count += 1
                        obj_node_id = f"OBJ_{clean}"
                        nodes.append({
                            "id": obj_node_id,
                            "type": "objective",
                            "label": f"Objective {clean}",
                            "text": text,
                            "parent_control_id": ctrl_id
                        })
                        edges.append({
                            "source": ctrl_id,
                            "target": obj_node_id,
                            "relationship": "HAS_OBJECTIVE"
                        })

    # 4. 800-53 Cross references
    for rel in relationships:
        if rel.get("relationship_identifier") == "external_reference":
            src = rel.get("source_element_identifier", "")
            dest = rel.get("dest_element_identifier", "")
            if src in controls_map and rel.get("dest_doc_identifier", "").startswith("SP_800_53"):
                if dest not in controls_map[src]["references_800_53"]:
                    controls_map[src]["references_800_53"].append(dest)

    # 5. Build final controls list and relationships
    for cid, cdata in controls_map.items():
        if not cdata["description"]:
            cdata["description"] = " ".join(cdata["sub_requirements"][:2]) or f"NIST SP 800-171 Rev 3 Requirement for {cdata['family_name']}."
        
        nodes.append({
            "id": cdata["id"],
            "type": "control",
            "label": cdata["label"],
            "title": cdata["title"],
            "family": cdata["family_name"],
            "family_id": cdata["family_id"],
            "family_name": cdata["family_name"],
            "description": cdata["description"],
            "small_biz_guidance": cdata["small_biz_guidance"],
            "objectives": cdata["objectives"],
            "mapped_asset_types": cdata["mapped_asset_types"],
            "references_800_53": cdata["references_800_53"]
        })

        # Family Edge
        edges.append({
            "source": cdata["id"],
            "target": cdata["family_id"],
            "relationship": "BELONGS_TO"
        })

        # Asset Edges
        for asset in cdata["mapped_asset_types"]:
            edges.append({
                "source": cdata["id"],
                "target": asset,
                "relationship": "APPLIES_TO_ASSET"
            })

    kg_dataset = {
        "metadata": {
            "title": "NIST SP 800-171 Rev 3 GraphRAG Knowledge Graph Index",
            "version": "3.0.0",
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "control_count": len(controls_map),
            "family_count": len(families_map),
            "objective_count": obj_count
        },
        "nodes": nodes,
        "edges": edges
    }

    with open(OUTPUT_KG_PATH, "w", encoding="utf-8") as f:
        json.dump(kg_dataset, f, indent=2)

    logger.info(f"Successfully compiled GraphRAG Knowledge Graph Index to {OUTPUT_KG_PATH} ({len(nodes)} Nodes, {len(edges)} Edges)!")

if __name__ == "__main__":
    generate_clean_kg()
