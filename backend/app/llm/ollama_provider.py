import json
import logging
import httpx
from typing import Dict, Any
from app.config import settings
from app.llm.base import BaseLLMProvider

logger = logging.getLogger("garc.llm.ollama")

class OllamaProvider(BaseLLMProvider):
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL

    def generate_text(self, prompt: str, system_instruction: str = "") -> str:
        try:
            url = f"{self.base_url}/api/generate"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": system_instruction,
                "stream": False
            }
            with httpx.Client(timeout=60.0) as client:
                res = client.post(url, json=payload)
                res.raise_for_status()
                return res.json().get("response", "")
        except Exception as e:
            logger.error(f"Ollama connection error to {self.base_url}: {e}")
            return f"[Ollama Connection Error]: Ensure Ollama is running at {self.base_url} with model {self.model}."

    def generate_structured_json(self, prompt: str, schema_description: str, system_instruction: str = "") -> Dict[str, Any]:
        full_prompt = f"""
{system_instruction}

Respond STRICTLY with valid JSON following this structure:
{schema_description}

Input text:
{prompt}
"""
        raw = self.generate_text(full_prompt)
        try:
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()
            return json.loads(raw)
        except Exception:
            return {}
