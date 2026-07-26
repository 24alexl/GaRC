import os
import json
import logging
from typing import Dict, Any, List
from app.db.neo4j_client import neo4j_client

logger = logging.getLogger("garc.seed")

KG_INDEX_FILE_PATH = os.path.join(os.path.dirname(__file__), "nist_800_171_graph_index.json")

def load_graph_index() -> Dict[str, Any]:
    """Loads the pre-compiled GraphRAG Knowledge Graph Index."""
    if not os.path.exists(KG_INDEX_FILE_PATH):
        logger.error(f"Graph index JSON file missing at {KG_INDEX_FILE_PATH}")
        return {"nodes": [], "edges": []}

    with open(KG_INDEX_FILE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

# Load compiled Knowledge Graph dataset
KG_INDEX = load_graph_index()

# Filter controls for easy in-memory access
NIST_CONTROLS_DATA = [n for n in KG_INDEX.get("nodes", []) if n.get("type") == "control"]
PARSED_FAMILIES = {n["code"]: {"name": n["label"], "assets": n["mapped_assets"]} for n in KG_INDEX.get("nodes", []) if n.get("type") == "family"}

def seed_database():
    logger.info(f"Starting NIST SP 800-171 Rev 3 GraphRAG Knowledge Graph seeding ({len(NIST_CONTROLS_DATA)} Controls, {len(KG_INDEX.get('edges', []))} Edges)...")

    if neo4j_client.mock_mode or not neo4j_client.driver:
        logger.info(f"Neo4j client operating in mock mode. Loaded {len(NIST_CONTROLS_DATA)} controls directly from GraphRAG Index.")
        return {"status": "mock_seeded", "count": len(NIST_CONTROLS_DATA)}

    # Clear existing NIST framework nodes
    clear_query = "MATCH (c:NISTControl) DETACH DELETE c"
    neo4j_client.execute_write(clear_query)

    for item in NIST_CONTROLS_DATA:
        cypher = """
        MERGE (fam:ControlFamily {name: $family_name, id: $family_id})
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

    logger.info(f"Successfully seeded {len(NIST_CONTROLS_DATA)} NIST 800-171 Rev 3 controls into Neo4j database.")
    return {"status": "seeded", "count": len(NIST_CONTROLS_DATA)}

if __name__ == "__main__":
    seed_database()
