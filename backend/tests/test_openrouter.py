from app.llm.openrouter_provider import OpenRouterProvider

def test_openrouter_provider_init():
    provider = OpenRouterProvider()
    assert provider.model is not None
    res = provider.generate_text("Test query")
    assert isinstance(res, str)
    assert len(res) > 0
