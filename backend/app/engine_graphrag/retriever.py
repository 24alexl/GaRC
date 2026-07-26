import logging
from typing import List, Dict, Any
from app.db.neo4j_client import neo4j_client
from app.db.seed_nist_800_171 import NIST_CONTROLS_DATA

logger = logging.getLogger("garc.engine1.retriever")

class GraphRAGRetriever:
    def retrieve_relevant_subgraph(self, query: str) -> Dict[str, Any]:
        """
        Executes semantic scoring across NIST 800-171 controls and 
        returns direct multi-hop graph paths (User Query -> NIST Controls -> Objectives) for XAI visualization.
        """
        query_lower = query.lower()
        audit_intent_keywords = ["audit", "topology", "evaluate", "assess", "compliance status", "my network", "my setup", "devices", "infrastructure"]
        is_audit_intent = any(kw in query_lower for kw in audit_intent_keywords)

        keywords = [k.lower() for k in query.split() if len(k) > 2]
        
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
            # Import active topology to evaluate specific gaps
            from app.engine_topology.parser import topology_parser
            active_nodes = topology_parser.active_topology_nodes

            # Semantic keyword relevance scoring across title, description, guidance, and objectives
            scored_controls = []
            for ctrl in NIST_CONTROLS_DATA:
                fam_name = ctrl.get("family", ctrl.get("family_name", "Security Requirements"))
                ctrl_title = ctrl.get("title", f"NIST {ctrl.get('id', '')}")
                ctrl_desc = ctrl.get("description", "")
                ctrl_guidance = ctrl.get("small_biz_guidance", "")
                objs = ctrl.get("objectives", ctrl.get("assessment_objectives", []))
                objs_str = " ".join(objs)
                ctrl_id = ctrl.get("id", "")

                score = 0

                # 1. Standard keyword match scoring
                for kw in keywords:
                    if kw in ctrl_title.lower():
                        score += 5
                    if kw in ctrl_desc.lower():
                        score += 3
                    if kw in ctrl_guidance.lower():
                        score += 2
                    if kw in objs_str.lower():
                        score += 2
                    if kw in fam_name.lower():
                        score += 1

                # 2. Intent-Based Boost: Active Topology Risk Mapping
                if is_audit_intent:
                    score += 2 # Base audit intent boost
                    if active_nodes:
                        has_cui = any(n.stores_cui for n in active_nodes)
                        missing_sec = any(not n.has_firewall_or_mfa for n in active_nodes)
                        
                        # Boost Access Control, MFA, Boundary Defense for unauthenticated/unprotected nodes
                        if missing_sec and ctrl_id in ["03.01.01", "03.05.03", "03.13.01", "03.14.02"]:
                            score += 15
                        # Boost Media Protection / Encryption for CUI storage
                        if has_cui and ctrl_id in ["03.08.07", "03.13.16", "03.08.01"]:
                            score += 15

                if score > 0 or len(keywords) == 0:
                    scored_controls.append((score, {
                        "id": ctrl["id"],
                        "title": ctrl_title,
                        "description": ctrl_desc,
                        "guidance": ctrl_guidance,
                        "family": fam_name,
                        "objectives": objs
                    }))

            # Sort controls by relevance score descending
            scored_controls.sort(key=lambda x: x[0], reverse=True)
            # Return all relevant controls (Score >= 10) for comprehensive auditing
            records = [item[1] for item in scored_controls if item[0] >= 10]

            if not records:
                records = [
                    {
                        "id": ctrl["id"],
                        "title": ctrl.get("title", f"NIST {ctrl.get('id', '')}"),
                        "description": ctrl.get("description", ""),
                        "guidance": ctrl.get("small_biz_guidance", ""),
                        "family": ctrl.get("family", ctrl.get("family_name", "Security Requirements")),
                        "objectives": ctrl.get("objectives", ctrl.get("assessment_objectives", []))
                    }
                    for ctrl in NIST_CONTROLS_DATA[:3]
                ]

        # Formulate clean nodes and edges for Cytoscape.js multi-hop reasoning visualization (NO Family clutter)
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

        # Limit UI rendering to top 5 most critical controls to prevent visual spaghetti
        for item in records[:5]:
            ctrl_id = f"Ctrl_{item['id']}"

            # Direct Control Node (Clean Label)
            nodes.append({
                "data": {
                    "id": ctrl_id,
                    "label": f"NIST {item['id']}\n({item['family']})",
                    "type": "control",
                    "description": item["description"],
                    "guidance": item["guidance"]
                }
            })

            # Direct Query -> Control Edge
            edges.append({
                "data": {
                    "source": "User_Query",
                    "target": ctrl_id,
                    "label": "MATCHES_REQUIREMENT"
                }
            })

            # Objective Nodes directly linked to Control
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
