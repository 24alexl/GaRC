import json
import re
import logging
import httpx
from typing import Dict, Any
from app.config import settings
from app.llm.base import BaseLLMProvider

logger = logging.getLogger("garc.llm.openrouter")

class OpenRouterProvider(BaseLLMProvider):
    _global_auth_failed: bool = False

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = settings.OPENROUTER_MODEL
        self.base_url = settings.OPENROUTER_BASE_URL.rstrip("/")

        if not self.api_key or "your_" in self.api_key:
            logger.warning("OPENROUTER_API_KEY not set or is placeholder in .env. Operating in resilient fallback mode.")

    @property
    def is_available(self) -> bool:
        return bool(self.api_key and "your_" not in self.api_key and not OpenRouterProvider._global_auth_failed)

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

    def generate_text(self, prompt: str, system_instruction: str = "", max_tokens: int = 1500, response_format: dict = None) -> str:
        if not self.is_available:
            return ""

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
            "temperature": 0.1,
            "max_tokens": max_tokens
        }
        if response_format:
            payload["response_format"] = response_format

        try:
            with httpx.Client(timeout=httpx.Timeout(12.0, connect=4.0)) as client:
                res = client.post(url, json=payload, headers=headers)
                if res.status_code in (401, 403):
                    OpenRouterProvider._global_auth_failed = True
                    logger.warning(
                        "OpenRouter authentication failed (401/403 Unauthorized). "
                        "Entering resilient local CPRT/heuristic fallback mode."
                    )
                    return ""
                if res.status_code == 400 and response_format:
                    # Retry without response_format if model does not support native JSON mode
                    payload.pop("response_format", None)
                    res = client.post(url, json=payload, headers=headers)
                res.raise_for_status()
                data = res.json()
                raw_content = data["choices"][0]["message"]["content"]
                return self._sanitize_output(raw_content)
        except Exception as e:
            if not OpenRouterProvider._global_auth_failed:
                logger.warning(f"OpenRouter API request failed: {e}. Falling back to local heuristic/CPRT engine.")
            return ""

    def _try_parse_resilient_json(self, text: str) -> Dict[str, Any]:
        """Resiliently parses JSON even if output was truncated mid-string or mid-array."""
        if not text or not text.strip():
            return {}
        cleaned = text.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        # 1. Try standard parse
        try:
            return json.loads(cleaned)
        except Exception:
            pass

        # 2. Resilient truncation repair: balance quotes, arrays, and objects
        try:
            # Remove trailing dangling commas
            cleaned_sub = re.sub(r',\s*([\]}])', r'\1', cleaned)
            # Find candidate boundaries backwards
            for end_pos in range(len(cleaned_sub), max(0, len(cleaned_sub) - 400), -5):
                candidate = cleaned_sub[:end_pos].rstrip().rstrip(',')
                quote_count = candidate.count('"') - candidate.count(r'\"')
                if quote_count % 2 != 0:
                    candidate += '"'
                open_brackets = candidate.count('[') - candidate.count(']')
                open_braces = candidate.count('{') - candidate.count('}')
                candidate += ']' * max(0, open_brackets)
                candidate += '}' * max(0, open_braces)
                try:
                    return json.loads(candidate)
                except Exception:
                    continue
        except Exception as repair_err:
            logger.debug(f"JSON repair attempt failed: {repair_err}")

        return {}

    def generate_structured_json(self, prompt: str, schema_description: str, system_instruction: str = "") -> Dict[str, Any]:
        if not self.is_available:
            return {}

        full_prompt = f"""
{system_instruction}

Respond strictly with valid, complete JSON conforming to this schema:
{schema_description}

Input content:
{prompt}
"""
        raw_text = self.generate_text(full_prompt, max_tokens=1000, response_format={"type": "json_object"})
        if not raw_text:
            return {}

        parsed = self._try_parse_resilient_json(raw_text)
        if not parsed and len(raw_text) > 0:
            logger.debug(f"Failed to parse structured JSON from OpenRouter output: {raw_text[:120]}")
        return parsed
