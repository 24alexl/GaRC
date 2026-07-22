import os
import json
import logging
from typing import Dict, Any, List
from app.db.neo4j_client import neo4j_client

logger = logging.getLogger("garc.seed")

CPRT_FILE_PATH = os.path.join(os.path.dirname(__file__), "cprt_SP_800_171_3_0_0_07-21-2026.json")

# Mapping of Control Family IDs to names & default asset tags
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

def load_cprt_json() -> Dict[str, Any]:
    """Loads and parses the official NIST SP 800-171 Rev 3 CPRT JSON dataset."""
    if not os.path.exists(CPRT_FILE_PATH):
        logger.error(f"CPRT JSON file not found at {CPRT_FILE_PATH}")
        return {"elements": [], "relationships": []}

    with open(CPRT_FILE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    elements_container = data.get("response", {}).get("elements", {})
    return {
        "elements": elements_container.get("elements", []),
        "relationships": elements_container.get("relationships", [])
    }

def process_cprt_dataset():
    """Parses raw CPRT elements into structured NIST 800-171 Knowledge Graph nodes."""
    raw = load_cprt_json()
    elements = raw["elements"]
    relationships = raw["relationships"]

    # 1. Extract Families
    families = {}
    for el in elements:
        if el.get("element_type") == "family":
            fid = el.get("element_identifier", "")
            title = el.get("title", "")
            meta = FAMILY_METADATA.get(fid, {"name": title, "assets": ["device", "server"]})
            families[fid] = {
                "id": fid,
                "name": meta["name"],
                "assets": meta["assets"]
            }

    # 2. Extract Security Requirements & group by Control ID
    controls_map = {}
    for el in elements:
        etype = el.get("element_type")
        eident = el.get("element_identifier", "")
        text = el.get("text", "")

        if etype == "security_requirement":
            # Example identifier: SR-03.01.01 or SR-03.01.01.a
            parts = eident.replace("SR-", "").split(".")
            if len(parts) >= 3:
                ctrl_id = f"{parts[0]}.{parts[1]}.{parts[2]}" # e.g. 03.01.01
                fam_id = f"{parts[0]}.{parts[1]}"           # e.g. 03.01

                if ctrl_id not in controls_map:
                    fam_meta = families.get(fam_id, {"name": "Security Requirements", "assets": ["device"]})
                    controls_map[ctrl_id] = {
                        "id": ctrl_id,
                        "family": fam_meta["name"],
                        "family_id": fam_id,
                        "title": f"Control {ctrl_id}",
                        "description": "",
                        "sub_requirements": [],
                        "objectives": [],
                        "references_800_53": [],
                        "small_biz_guidance": f"Implement baseline security configurations and role-based access for {fam_meta['name']}.",
                        "mapped_asset_types": fam_meta["assets"]
                    }

                if text:
                    controls_map[ctrl_id]["sub_requirements"].append(text)
                    if not controls_map[ctrl_id]["description"]:
                        controls_map[ctrl_id]["description"] = text

    # 3. Extract Determinations (Assessment Objectives)
    for el in elements:
        if el.get("element_type") == "determination":
            eident = el.get("element_identifier", "")
            text = el.get("text", "")
            if text and "DS-A." in eident:
                # e.g. DS-A.03.01.01.c.01 -> ctrl_id 03.01.01
                clean = eident.replace("DS-A.", "")
                parts = clean.split(".")
                if len(parts) >= 3:
                    ctrl_id = f"{parts[0]}.{parts[1]}.{parts[2]}"
                    if ctrl_id in controls_map:
                        controls_map[ctrl_id]["objectives"].append(text)

    # 4. Extract 800-53 External References from Relationships
    for rel in relationships:
        if rel.get("relationship_identifier") == "external_reference":
            src = rel.get("source_element_identifier", "")
            dest = rel.get("dest_element_identifier", "")
            if src in controls_map and rel.get("dest_doc_identifier", "").startswith("SP_800_53"):
                if dest not in controls_map[src]["references_800_53"]:
                    controls_map[src]["references_800_53"].append(dest)

    # Format into list
    controls_list = []
    for cid, cdata in controls_map.items():
        if not cdata["description"]:
            cdata["description"] = " ".join(cdata["sub_requirements"][:2]) or f"NIST SP 800-171 Rev 3 Requirement for {cdata['family']}."
        controls_list.append(cdata)

    return families, controls_list

# Global cached parsed dataset
PARSED_FAMILIES, NIST_CONTROLS_DATA = process_cprt_dataset()

def seed_database():
    logger.info(f"Starting NIST SP 800-171 Rev 3 CPRT Knowledge Graph seeding ({len(NIST_CONTROLS_DATA)} Controls)...")

    if neo4j_client.mock_mode or not neo4j_client.driver:
        logger.info(f"Neo4j client in mock mode. Seeded {len(NIST_CONTROLS_DATA)} CPRT controls in memory.")
        return {"status": "mock_seeded", "count": len(NIST_CONTROLS_DATA)}

    # Clear existing NIST framework nodes
    clear_query = "MATCH (c:NISTControl) DETACH DELETE c"
    neo4j_client.execute_write(clear_query)

    for item in NIST_CONTROLS_DATA:
        cypher = """
        MERGE (fam:ControlFamily {name: $family, id: $family_id})
        CREATE (c:NISTControl {
            id: $id,
            title: $title,
            description: $description,
            small_biz_guidance: $small_biz_guidance,
            mapped_asset_types: $mapped_asset_types,
            references_800_53: $references_800_53
        })
        MERGE (c)-[:BELONGS_TO]->(fam)
        WITH c
        UNWIND $objectives AS obj_text
        CREATE (obj:AssessmentObjective {text: obj_text})
        CREATE (c)-[:HAS_OBJECTIVE]->(obj)
        """
        neo4j_client.execute_write(cypher, item)

    logger.info(f"Successfully seeded {len(NIST_CONTROLS_DATA)} NIST 800-171 Rev 3 CPRT controls into Neo4j.")
    return {"status": "seeded", "count": len(NIST_CONTROLS_DATA)}

if __name__ == "__main__":
    seed_database()
