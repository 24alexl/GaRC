import json
import re
import logging
import httpx
from typing import Dict, Any
from app.config import settings
from app.llm.base import BaseLLMProvider

logger = logging.getLogger("garc.llm.openrouter")

class OpenRouterProvider(BaseLLMProvider):
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = settings.OPENROUTER_MODEL
        self.base_url = settings.OPENROUTER_BASE_URL.rstrip("/")

        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not set in .env. OpenRouter Provider operating in simulation mode.")

    def _sanitize_output(self, text: str) -> str:
        """Strips Llama/ChatML system tags and deduplicates repeating adjacent lines without cutting off response."""
        if not text:
            return ""

        # Remove ChatML/Llama special tokens
        text = re.sub(r'<\|[^|]+\|>', '', text)

        # Remove adjacent duplicate lines (instead of aborting entire response)
        lines = text.split('\n')
        cleaned_lines = []
        last_line = None

        for line in lines:
            trimmed = line.strip()
            # If line is identical to immediately preceding line, skip duplicate line
            if trimmed and trimmed == last_line:
                continue
            cleaned_lines.append(line)
            if trimmed:
                last_line = trimmed

        return '\n'.join(cleaned_lines).strip()

    def generate_text(self, prompt: str, system_instruction: str = "") -> str:
        if not self.api_key:
            return f"[OpenRouter Simulation Mode]\n\nPrompt: {prompt[:120]}...\n\n(Set OPENROUTER_API_KEY in backend/.env to activate live OpenRouter models)."

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/GaRC",
            "X-Title": "GaRC - GraphRAG Automated Risk & Compliance",
            "Content-Type": "application/json"
        }

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 1500
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                res = client.post(url, json=payload, headers=headers)
                res.raise_for_status()
                data = res.json()
                raw_content = data["choices"][0]["message"]["content"]
                return self._sanitize_output(raw_content)
        except Exception as e:
            logger.error(f"OpenRouter API request failed: {e}")
            return f"[OpenRouter API Error]: {e}"

    def generate_structured_json(self, prompt: str, schema_description: str, system_instruction: str = "") -> Dict[str, Any]:
        full_prompt = f"""
{system_instruction}

Respond strictly with valid JSON conforming to this schema:
{schema_description}

Input content:
{prompt}
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
            logger.warning(f"Failed to parse structured JSON from OpenRouter output: {e}")
            return {}
