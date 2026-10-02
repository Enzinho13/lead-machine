import os
import json
import time
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIService:
    def __init__(self, model_name: str = 'gemini-3.8-flash'):
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logger.warning("GEMINI_API_KEY environment variable not set. API calls will fail if not authenticated otherwise.")
        
        # Initialize the new SDK client
        self.client = genai.Client(api_key=api_key)
        self.default_model = model_name

    def _retry_with_backoff(self, func, max_retries=3):
        retries = 0
        base_delay = 1.0
        while True:
            try:
                return func()
            except Exception as e:
                retries += 1
                if retries >= max_retries:
                    logger.error(f"Failed after {max_retries} attempts. Last error: {e}")
                    raise
                delay = base_delay * (2 ** (retries - 1))
                logger.warning(f"Attempt {retries} failed: {e}. Retrying in {delay} seconds...")
                time.sleep(delay)

    def generate_text(self, prompt: str, model: Optional[str] = None, temperature: float = 0.7, timeout: int = 30) -> str:
        model_to_use = model or self.default_model
        
        def _call_api():
            config = types.GenerateContentConfig(
                temperature=temperature,
            )
            # using new SDK models.generate_content
            response = self.client.models.generate_content(
                model=model_to_use,
                contents=prompt,
                config=config
            )
            if not response.text:
                return ""
            return response.text

        try:
            return self._retry_with_backoff(_call_api)
        except Exception as e:
            logger.error(f"Error generating text: {e}")
            raise

    def generate_structured(self, prompt: str, schema_hint: Optional[Dict] = None, model: Optional[str] = None, temperature: float = 0.1, timeout: int = 30) -> Dict[str, Any]:
        model_to_use = model or self.default_model
        
        full_prompt = prompt
        if schema_hint:
            full_prompt += f"\n\nPlease respond with valid JSON matching this schema:\n{json.dumps(schema_hint)}"
        else:
            full_prompt += "\n\nPlease respond with valid JSON."
            
        def _call_api():
            config = types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="application/json"
            )
            response = self.client.models.generate_content(
                model=model_to_use,
                contents=full_prompt,
                config=config
            )
            return response.text or "{}"
            
        try:
            text_response = self._retry_with_backoff(_call_api)
            text_response = text_response.strip()
            if text_response.startswith('```json'):
                text_response = text_response[7:]
            elif text_response.startswith('```'):
                text_response = text_response[3:]
            if text_response.endswith('```'):
                text_response = text_response[:-3]
            text_response = text_response.strip()
            
            return json.loads(text_response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}. Raw response: {text_response}")
            raise
        except Exception as e:
            logger.error(f"Error generating structured content: {e}")
            raise

# Module-level singleton
ai = AIService()
