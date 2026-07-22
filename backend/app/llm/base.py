from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseLLMProvider(ABC):
    @abstractmethod
    def generate_text(self, prompt: str, system_instruction: str = "") -> str:
        """Generate plain text from prompt."""
        pass

    @abstractmethod
    def generate_structured_json(self, prompt: str, schema_description: str, system_instruction: str = "") -> Dict[str, Any]:
        """Generate structured JSON payload from prompt."""
        pass
