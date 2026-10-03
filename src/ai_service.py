import os
import json
import time
import logging
from typing import Optional, Dict, Any, Protocol

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AIError(Exception):
    """Base de qualquer falha real da camada de IA (nunca é convertida em "" ou {})."""


class AIConfigError(AIError):
    """Configuração ausente ou inválida (ex.: GEMINI_API_KEY não definida). Não adianta tentar de novo."""


class AIRequestError(AIError):
    """A chamada à API falhou (rede, quota, erro 4xx/5xx) depois de esgotar as tentativas permitidas."""

    def __init__(self, message: str, status_code: Optional[int] = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class AIResponseError(AIError):
    """A API respondeu, mas a resposta é inutilizável (vazia, bloqueada, JSON inválido ou vazio)."""


def _is_retryable(exc: Exception) -> bool:
    """Só vale repetir erros transitórios: timeout/quota (408/429), 5xx e falhas de rede."""
    if isinstance(exc, genai_errors.APIError):
        code = exc.code
        return code in (408, 429) or (isinstance(code, int) and code >= 500)
    return isinstance(exc, (httpx.TransportError, TimeoutError, ConnectionError))


class AIProvider(Protocol):
    def generate_text(self, prompt: str, model: str, temperature: float) -> str:
        ...
    def generate_structured(self, prompt: str, schema: Dict, model: str, temperature: float) -> Dict:
        ...

class GeminiProvider:
    def __init__(self, api_key: Optional[str]):
        self.api_key = api_key
        self._client = None

    @property
    def client(self):
        # Criado sob demanda: a falta da chave vira AIConfigError na chamada, não um crash no import.
        if self._client is None:
            if not self.api_key:
                raise AIConfigError("GEMINI_API_KEY não configurada.")
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _retry_with_backoff(self, func, max_retries=3):
        base_delay = 1.0
        attempt = 0
        while True:
            attempt += 1
            try:
                return func()
            except AIError:
                raise
            except Exception as e:
                retryable = _is_retryable(e)
                status_code = e.code if isinstance(e, genai_errors.APIError) else None
                if not retryable or attempt >= max_retries:
                    raise AIRequestError(
                        f"{type(e).__name__}: {e}", status_code=status_code, retryable=retryable
                    ) from e
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(f"AI tentativa {attempt}/{max_retries} falhou ({type(e).__name__}); nova tentativa em {delay}s")
                time.sleep(delay)

    @staticmethod
    def _extract_text(response) -> str:
        text = (getattr(response, "text", None) or "").strip()
        if not text:
            feedback = getattr(response, "prompt_feedback", None)
            raise AIResponseError(f"Resposta vazia do modelo (prompt_feedback={feedback}).")
        return text

    @staticmethod
    def _parse_json(text: str) -> Dict:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Fallback for older models or unexpected formatting
            cleaned = text.strip()
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            elif cleaned.startswith('```'):
                cleaned = cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            try:
                data = json.loads(cleaned.strip())
            except json.JSONDecodeError as e:
                raise AIResponseError(f"A IA devolveu JSON inválido: {e}") from e
        if not isinstance(data, dict) or not data:
            raise AIResponseError("A IA devolveu JSON vazio ou que não é um objeto.")
        return data

    def generate_text(self, prompt: str, model: str, temperature: float) -> str:
        def _call():
            config = types.GenerateContentConfig(temperature=temperature)
            return self.client.models.generate_content(model=model, contents=prompt, config=config)
        response = self._retry_with_backoff(_call)
        return self._extract_text(response)

    def generate_structured(self, prompt: str, schema: Dict, model: str, temperature: float) -> Dict:
        def _call():
            config = types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="application/json",
                response_schema=schema if schema else None
            )
            return self.client.models.generate_content(model=model, contents=prompt, config=config)

        response = self._retry_with_backoff(_call)
        return self._parse_json(self._extract_text(response))

class AIService:
    """Abstraction layer for AI providers.

    generate_text / generate_structured devolvem sempre uma resposta válida ou levantam
    uma subclasse de AIError (AIConfigError, AIRequestError, AIResponseError).
    """
    def __init__(self, provider_name: str = "gemini", model_name: str = "gemini-3.8-flash", provider: Optional[AIProvider] = None):
        self.default_model = model_name
        self.provider: AIProvider

        if provider is not None:
            self.provider = provider
        elif provider_name == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                logger.warning("GEMINI_API_KEY not found. As chamadas de IA vão falhar com AIConfigError.")
            self.provider = GeminiProvider(api_key)
        else:
            raise ValueError(f"Provider {provider_name} not supported.")

    def generate_text(self, prompt: str, model: Optional[str] = None, temperature: float = 0.7) -> str:
        try:
            return self.provider.generate_text(prompt, model or self.default_model, temperature)
        except Exception as e:
            logger.error(f"AI generate_text error ({type(e).__name__}): {e}")
            raise

    def generate_structured(self, prompt: str, schema_hint: Optional[Dict] = None, model: Optional[str] = None, temperature: float = 0.1) -> Dict[str, Any]:
        try:
            return self.provider.generate_structured(prompt, schema_hint, model or self.default_model, temperature)
        except Exception as e:
            logger.error(f"AI generate_structured error ({type(e).__name__}): {e}")
            raise

# Singleton for global use
ai = AIService()
