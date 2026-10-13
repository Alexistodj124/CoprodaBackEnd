"""Cliente minimo de OpenRouter (API compatible con OpenAI chat/completions)."""
from __future__ import annotations

import json

import requests

from settings import settings


class LLMError(RuntimeError):
    pass


class OpenRouter:
    def __init__(self, api_key: str | None = None, modelo: str | None = None):
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.modelo = modelo or settings.MODELO
        self.base_url = settings.OPENROUTER_BASE_URL.rstrip("/")
        if not self.api_key:
            raise LLMError(
                "Falta OPENROUTER_API_KEY. Copia .env.example a .env y ponla ahi."
            )

    def chat(self, mensajes: list[dict], herramientas: list[dict] | None = None) -> dict:
        payload = {
            "model": self.modelo,
            "messages": mensajes,
            "max_tokens": settings.MAX_TOKENS,
        }
        # temperature esta removido en Opus 5 / Sonnet 5 / Fable 5: solo se manda
        # si esta configurada explicitamente.
        if settings.TEMPERATURA is not None:
            payload["temperature"] = settings.TEMPERATURA
        if herramientas:
            payload["tools"] = herramientas
            payload["tool_choice"] = "auto"

        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "X-Title": "Coproda Agente",
                },
                data=json.dumps(payload),
                timeout=settings.TIMEOUT_LLM,
            )
        except requests.RequestException as exc:
            raise LLMError(f"No se pudo contactar OpenRouter: {exc}") from exc

        if resp.status_code >= 400:
            raise LLMError(f"OpenRouter {resp.status_code}: {resp.text[:400]}")

        datos = resp.json()
        if "choices" not in datos:
            raise LLMError(f"Respuesta inesperada de OpenRouter: {str(datos)[:400]}")
        return datos
