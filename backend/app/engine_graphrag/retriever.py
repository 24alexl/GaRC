import logging
from typing import List, Dict, Any
from app.db.neo4j_client import neo4j_client
from app.db.seed_nist_800_171 import NIST_CONTROLS_DATA

logger = logging.getLogger("garc.engine1.retriever")

class GraphRAGRetriever:
    def retrieve_relevant_subgraph(self, query: str) -> Dict[str, Any]:
        """
        Executes multi-hop Cypher queries across NIST 800-171 controls and 
        returns the graph paths, nodes, and relationships for XAI visualization.
        """
        keywords = [k.lower() for k in query.split() if len(k) > 3]
        
        if not neo4j_client.mock_mode and neo4j_client.driver:
            cypher = """
            MATCH (c:NISTControl)-[:BELONGS_TO]->(fam:ControlFamily)
            OPTIONAL MATCH (c)-[:HAS_OBJECTIVE]->(obj:AssessmentObjective)
            RETURN c.id AS id, c.title AS title, c.description AS description, 
                   c.small_biz_guidance AS guidance, fam.name AS family, 
                   collect(obj.text) AS objectives
            LIMIT 10
            """
            records = neo4j_client.query(cypher)
        else:
            # Filter from in-memory seed dataset for demo/mock mode
            records = []
            for ctrl in NIST_CONTROLS_DATA:
                match = any(kw in ctrl["title"].lower() or kw in ctrl["description"].lower() or kw in ctrl["family"].lower() for kw in keywords)
                if match or len(keywords) == 0:
                    records.append({
                        "id": ctrl["id"],
                        "title": ctrl["title"],
                        "description": ctrl["description"],
                        "guidance": ctrl.get("small_biz_guidance", ""),
                        "family": ctrl["family"],
                        "objectives": ctrl.get("objectives", ctrl.get("assessment_objectives", []))
                    })
            if not records:
                records = [
                    {
                        "id": ctrl["id"],
                        "title": ctrl["title"],
                        "description": ctrl["description"],
                        "guidance": ctrl.get("small_biz_guidance", ""),
                        "family": ctrl["family"],
                        "objectives": ctrl.get("objectives", ctrl.get("assessment_objectives", []))
                    }
                    for ctrl in NIST_CONTROLS_DATA[:3]
                ]

        # Formulate nodes and edges for Cytoscape.js multi-hop reasoning visualization
        nodes = []
        edges = []

        # Add Query context root node
        nodes.append({
            "data": {
                "id": "User_Query",
                "label": "User Requirement Query",
                "type": "query",
                "detail": query
            }
        })

        for item in records:
            fam_id = f"Fam_{item['family'].replace(' ', '_')}"
            ctrl_id = f"Ctrl_{item['id']}"

            # Family Node
            if not any(n["data"]["id"] == fam_id for n in nodes):
                nodes.append({
                    "data": {
                        "id": fam_id,
                        "label": f"Family: {item['family']}",
                        "type": "family"
                    }
                })

            # Control Node
            nodes.append({
                "data": {
                    "id": ctrl_id,
                    "label": f"NIST {item['id']}: {item['title']}",
                    "type": "control",
                    "description": item["description"],
                    "guidance": item["guidance"]
                }
            })

            # Query -> Control Edge
            edges.append({
                "data": {
                    "source": "User_Query",
                    "target": ctrl_id,
                    "label": "MATCHES_REQUIREMENT"
                }
            })

            # Control -> Family Edge
            edges.append({
                "data": {
                    "source": ctrl_id,
                    "target": fam_id,
                    "label": "BELONGS_TO"
                }
            })

            # Objective Nodes
            for idx, obj in enumerate(item.get("objectives", [])[:2]):
                obj_id = f"Obj_{item['id']}_{idx}"
                nodes.append({
                    "data": {
                        "id": obj_id,
                        "label": f"Objective {idx+1}",
                        "type": "objective",
                        "detail": obj
                    }
                })
                edges.append({
                    "data": {
                        "source": ctrl_id,
                        "target": obj_id,
                        "label": "HAS_OBJECTIVE"
                    }
                })

        return {
            "controls": records,
            "graph": {
                "nodes": nodes,
                "edges": edges
            }
        }

graphrag_retriever = GraphRAGRetriever()
