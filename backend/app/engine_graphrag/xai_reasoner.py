import re
import logging
from typing import Dict, Any
from app.llm.factory import get_llm_provider
from app.engine_graphrag.retriever import graphrag_retriever

logger = logging.getLogger("garc.engine1.reasoner")

class XAIReasoner:
    def answer_query(self, user_query: str) -> Dict[str, Any]:
        """
        Executes Engine 1 GraphRAG pipeline:
        1. Retrieves relevant NIST 800-171 sub-graph paths.
        2. Prompts LLM using Few-Shot demonstration to prevent prompt echoes.
        3. Post-processes response in Python to inject [Trace ID](#trace-ID) hyperlinks cleanly.
        """
        retrieved_data = graphrag_retriever.retrieve_relevant_subgraph(user_query)
        controls = retrieved_data["controls"]
        graph = retrieved_data["graph"]

        from app.engine_topology.parser import topology_parser
        active_nodes = topology_parser.active_topology_nodes
        active_edges = topology_parser.active_topology_edges

        # Intent Classification
        is_audit_intent = bool(re.search(r'\b(audit|assess|check|evaluate|gap|compliance)\b', user_query.lower()))

        # Build clean context prompt with retrieved KG nodes
        context_str = ""
        if active_nodes:
            context_str += "### Active User Network Topology Nodes:\n"
            for n in active_nodes:
                cui_str = " (Stores CUI: Yes)" if n.stores_cui else ""
                sec_str = " (Firewall/MFA: Active)" if n.has_firewall_or_mfa else " (Firewall/MFA: UNPROTECTED)"
                context_str += f"- Node '{n.name}' [Type: {n.type}, IP: {n.ip_or_subnet}]{cui_str}{sec_str}\n"
            context_str += "\n"
        if active_edges:
            context_str += "### Active User Network Topology Connections (Edges):\n"
            for e in active_edges:
                context_str += f"- {e.source} --[{e.relationship}]--> {e.target}\n"
            context_str += "\n"

        context_str += "### Retrieved NIST SP 800-171 Controls Context:\n"
        cited_ids = []
        for ctrl in controls:
            cited_ids.append(ctrl['id'])
            context_str += f"- Control ID: {ctrl['id']} ({ctrl['title']}) - Family: {ctrl['family']}\n"
            context_str += f"  Description: {ctrl['description']}\n"
            if ctrl.get('guidance'):
                context_str += f"  Guidance: {ctrl['guidance']}\n"
            if ctrl.get('objectives'):
                objs = ctrl['objectives'][:2]
                context_str += f"  Objectives: {'; '.join(objs)}\n"
            context_str += "\n"

        if is_audit_intent:
            system_prompt = """You are GaRC, an expert cybersecurity compliance copilot for small businesses adhering to NIST SP 800-171 Rev 3.

You are acting as an auditor's assistant and a CISO's intuition engine. Your job is to "Guide, Don't Prescribe". Do NOT definitively declare a system as "DEFICIENT" or prescribe absolute remediation (e.g., "Install a firewall"). Instead, generate investigative prompts, highlight potential scope traps, and provide actions for the assessor to verify.

### Core Copilot Constraints:
1. **Scope Sensitivity**: Alert the user if an unsegmented asset might accidentally get dragged into federal audit scope.
2. **Shared Responsibility**: Clearly split guidance for On-Premise assets versus Cloud assets (e.g., AWS offloads physical/encryption requirements to the provider; recommend auditing the SOC 2/FedRAMP report).
3. **Anti-Hallucination**: If the topology graph doesn't explicitly confirm a control (like a firewall), gracefully state "Insufficient network details to verify firewall state" instead of assuming it is missing.

If the user's question asks to audit or evaluate their network topology, analyze their specific Active User Network Topology Context (including Nodes and Edges) provided below against the retrieved NIST controls. Trace the connections to spot pattern anomalies.

Write a clear, professional assessment following this exact structure:

## Executive Summary
(Briefly summarize the overarching compliance posture and major pattern anomalies observed in the topology.)

## Applicable NIST SP 800-171 Controls
- **NIST [ID] ([Family])**: [Short Description]

## Copilot Investigations & Flags
(For each flagged control, use one of the following investigative formats based on the anomaly)

🔍 Investigation Flag (NIST [ID] - [Title]):
[Explain the observation from the graph]
Action for Assessor: [What specific question should the human ask their IT team or verify?]

☁️ Cloud Scope Alert (NIST [ID] - [Title]):
[Explain the cloud shared responsibility nuance]
Action for Assessor: [What specific cloud report or setting should be requested?]

⚠️ Network Segmentation Risk (NIST [ID] - [Title]):
[Explain the scope creep risk due to flat networks]
Action for Assessor: [What logical boundaries need to be verified?]
"""
        else:
            system_prompt = """You are GaRC, an expert cybersecurity educational copilot for small businesses adhering to NIST SP 800-171 Rev 3.

The user is asking a general or educational question rather than requesting a full network audit. Provide a helpful, clear, and concise explanation using the retrieved NIST SP 800-171 controls context.

Write your response following this structure:

## Copilot Answer
(Provide a clear, conversational answer to the user's specific question)

## Applicable NIST Controls
(List the most relevant NIST controls that support your answer)

## Small Business Guidance
(Provide practical advice on how a small business can achieve this requirement)
"""

        prompt = f"""User Question: "{user_query}"

Knowledge Graph & Topology Sub-graph Context:
{context_str}

Please generate an expert compliance response for the user's question using the requested format layout based on the intent.
"""
        llm = get_llm_provider()
        llm_response = llm.generate_text(prompt, system_instruction=system_prompt)

        # Python Post-Processing: Inject [Trace ID](#trace-ID) hyperlinks automatically into LLM output
        for ctrl_id in cited_ids:
            if f"#trace-{ctrl_id}" not in llm_response:
                pattern = re.compile(rf'\b(NIST\s+)?({re.escape(ctrl_id)})\b', re.IGNORECASE)
                replacement = f"NIST {ctrl_id} [Trace {ctrl_id}](#trace-{ctrl_id})"
                llm_response, count = pattern.subn(replacement, llm_response)

        return {
            "query": user_query,
            "markdown_response": llm_response,
            "cited_controls": cited_ids,
            "graph": graph
        }

xai_reasoner = XAIReasoner()
