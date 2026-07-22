import logging
from app.config import settings
from app.llm.base import BaseLLMProvider
from app.llm.openrouter_provider import OpenRouterProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.ollama_provider import OllamaProvider

logger = logging.getLogger("garc.llm.factory")

def get_llm_provider() -> BaseLLMProvider:
    provider_name = settings.LLM_PROVIDER.lower()
    if provider_name == "openrouter":
        logger.info("Initializing OpenRouter LLM provider...")
        return OpenRouterProvider()
    elif provider_name == "ollama":
        logger.info("Initializing Ollama local LLM provider...")
        return OllamaProvider()
    else:
        logger.info("Initializing Gemini API LLM provider...")
        return GeminiProvider()
