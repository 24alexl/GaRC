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

        # Build clean context prompt with retrieved KG nodes
        context_str = ""
        cited_ids = []
        for ctrl in controls[:3]:
            cited_ids.append(ctrl['id'])
            context_str += f"- Control ID: {ctrl['id']} ({ctrl['title']}) - Family: {ctrl['family']}\n"
            context_str += f"  Description: {ctrl['description']}\n"
            if ctrl.get('guidance'):
                context_str += f"  Guidance: {ctrl['guidance']}\n"
            if ctrl.get('objectives'):
                objs = ctrl['objectives'][:2]
                context_str += f"  Objectives: {'; '.join(objs)}\n"
            context_str += "\n"

        system_prompt = """You are GaRC, an expert cybersecurity compliance assistant for small businesses adhering to NIST SP 800-171 Rev 3.

Write a clear, professional response following this exact structure:

## Executive Summary
To protect Controlled Unclassified Information (CUI) on network storage devices, small businesses must enforce access controls, media transport safeguards, and malware protection. Following these guidelines ensures compliance with NIST SP 800-171 Rev 3.

## Applicable NIST SP 800-171 Controls
- **NIST 03.14.02 (Malware Protection)**: Deploy anti-malware protection at system entry and exit points.
- **NIST 03.08.05 (Media Transport)**: Document and secure all transport of system media containing CUI.
- **NIST 03.08.07 (Media Use Restriction)**: Prohibit unauthorized removable media usage across endpoints.

## Knowledge Graph Reasoning Path
1. **Asset Requirement**: Network storage devices processing CUI require cryptographic and malware protection.
2. **Graph Traversal**: Linked NIST Control 03.14.02 and Media Protection objectives.
3. **Compliance Impact**: Protects CUI from malware infection and unauthorized physical exposure.

## Recommended Action Steps
1. Install managed EDR/antivirus protection on storage gateways.
2. Enable BitLocker or AES-256 volume encryption for CUI data at rest.
3. Establish a formal media transport logging procedure.
"""

        prompt = f"""User Question: "{user_query}"

Knowledge Graph Sub-graph Context:
{context_str}

Please generate an expert compliance response for the user's question using the exact 4-section layout.
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
