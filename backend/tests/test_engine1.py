from app.engine_graphrag.retriever import graphrag_retriever
from app.engine_graphrag.xai_reasoner import xai_reasoner

def test_graphrag_retriever():
    query = "How do I protect CUI stored on NAS?"
    res = graphrag_retriever.retrieve_relevant_subgraph(query)
    assert "controls" in res
    assert "graph" in res
    assert len(res["graph"]["nodes"]) > 0
    assert len(res["graph"]["edges"]) > 0

def test_xai_reasoner():
    query = "Where is MFA required under NIST 800-171?"
    res = xai_reasoner.answer_query(query)
    assert "markdown_response" in res
    assert "cited_controls" in res
    assert len(res["cited_controls"]) > 0
