import json
import logging
from typing import Dict, Any
from google import genai
from app.config import settings
from app.llm.base import BaseLLMProvider

logger = logging.getLogger("garc.llm.gemini")

class GeminiProvider(BaseLLMProvider):
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("GEMINI_API_KEY not configured. Gemini Provider using intelligent fallback execution.")

    def generate_text(self, prompt: str, system_instruction: str = "") -> str:
        if not self.client:
            return f"[Gemini Provider Simulation Mode]\n\nPrompt: {prompt[:100]}...\n(Set GEMINI_API_KEY in .env to enable live Gemini model responses)."
        
        try:
            full_prompt = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=full_prompt,
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return f"Error executing Gemini prompt: {e}"

    def generate_structured_json(self, prompt: str, schema_description: str, system_instruction: str = "") -> Dict[str, Any]:
        full_prompt = f"""
{system_instruction}

Please extract structured JSON according to this schema format:
{schema_description}

Input:
{prompt}

Output ONLY valid JSON inside ```json``` tags.
"""
        raw_text = self.generate_text(full_prompt)
        try:
            cleaned = raw_text
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0].strip()
            return json.loads(cleaned)
        except Exception as e:
            logger.warning(f"Failed to parse LLM structured JSON output ({e}). Returning empty object.")
            return {}
