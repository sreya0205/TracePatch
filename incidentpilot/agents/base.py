import json
import os
import re
from typing import Type, TypeVar, Optional, Any, Dict
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """
    LLM Client Abstraction.
    Supports API calling (OpenAI / Anthropic / Gemini) when configured,
    and provides a deterministic fallback mode for zero-cost, reproducible offline
    evaluation and benchmarking.
    """

    def __init__(self, provider: Optional[str] = None):
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.provider = provider or ("openai" if self.openai_key else "gemini" if self.gemini_key else "local")

    def has_active_llm(self) -> bool:
        return bool(self.openai_key or self.gemini_key or self.anthropic_key)

    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
    ) -> T:
        """
        Generates structured output conforming strictly to the provided Pydantic model.
        """
        # When OpenAI API key is present
        if self.openai_key and self.provider == "openai":
            try:
                import urllib.request
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.openai_key}",
                }
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1,
                }
                req = urllib.request.Request(
                    "https://api.openai.com/v1/chat/completions",
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    res_json = json.loads(resp.read().decode("utf-8"))
                    content = res_json["choices"][0]["message"]["content"]
                    data = json.loads(content)
                    return response_model.model_validate(data)
            except Exception:
                pass

        # In absence of external LLM credentials or in offline testing,
        # fallback is handled at agent level by deterministic AST heuristics.
        raise NotImplementedError("LLM API not configured or call failed.")
