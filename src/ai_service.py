import os
import json
import time
import logging
from typing import Optional, Dict, Any, Protocol

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIProvider(Protocol):
    def generate_text(self, prompt: str, model: str, temperature: float) -> str:
        ...
    def generate_structured(self, prompt: str, schema: Dict, model: str, temperature: float) -> Dict:
        ...

class GeminiProvider:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def _retry_with_backoff(self, func, max_retries=3):
        retries = 0
        base_delay = 1.0
        while True:
            try:
                return func()
            except Exception as e:
                retries += 1
                if retries >= max_retries:
                    raise
                delay = base_delay * (2 ** (retries - 1))
                time.sleep(delay)

    def generate_text(self, prompt: str, model: str, temperature: float) -> str:
        def _call():
            config = types.GenerateContentConfig(temperature=temperature)
            response = self.client.models.generate_content(model=model, contents=prompt, config=config)
            return response.text or ""
        return self._retry_with_backoff(_call)

    def generate_structured(self, prompt: str, schema: Dict, model: str, temperature: float) -> Dict:
        def _call():
            config = types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="application/json",
                response_schema=schema if schema else None
            )
            response = self.client.models.generate_content(model=model, contents=prompt, config=config)
            return response.text or "{}"
        
        text = self._retry_with_backoff(_call)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Fallback for older models or unexpected formatting
            text = text.strip()
            if text.startswith('```json'): text = text[7:]
            if text.startswith('```'): text = text[3:]
            if text.endswith('```'): text = text[:-3]
            return json.loads(text.strip())

class AIService:
    """Abstraction layer for AI providers."""
    def __init__(self, provider_name: str = "gemini", model_name: str = "gemini-3.8-flash"):
        self.default_model = model_name
        self.provider: AIProvider

        if provider_name == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                logger.error("GEMINI_API_KEY not found.")
            self.provider = GeminiProvider(api_key)
        else:
            raise ValueError(f"Provider {provider_name} not supported.")

    def generate_text(self, prompt: str, model: Optional[str] = None, temperature: float = 0.7) -> str:
        try:
            return self.provider.generate_text(prompt, model or self.default_model, temperature)
        except Exception as e:
            logger.error(f"AI generate_text error: {e}")
            return ""

    def generate_structured(self, prompt: str, schema_hint: Optional[Dict] = None, model: Optional[str] = None, temperature: float = 0.1) -> Dict[str, Any]:
        try:
            return self.provider.generate_structured(prompt, schema_hint, model or self.default_model, temperature)
        except Exception as e:
            logger.error(f"AI generate_structured error: {e}")
            return {}

# Singleton for global use
ai = AIService()
