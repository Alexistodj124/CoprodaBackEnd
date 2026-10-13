"""Cliente del modelo via el SDK oficial de Anthropic (Messages API)."""
from __future__ import annotations

import anthropic

from settings import settings


class LLMError(RuntimeError):
    pass


class Claude:
    def __init__(self, api_key: str | None = None, modelo: str | None = None):
        self.modelo = modelo or settings.MODELO
        api_key = api_key or settings.ANTHROPIC_API_KEY
        if not api_key:
            raise LLMError(
                "Falta ANTHROPIC_API_KEY. Copia .env.example a .env y ponla ahi."
            )
        self.cliente = anthropic.Anthropic(
            api_key=api_key, timeout=settings.TIMEOUT_LLM
        )

    def chat(self, sistema: str, mensajes: list[dict],
             herramientas: list[dict] | None = None):
        """Una vuelta del modelo. Devuelve el BetaMessage del SDK."""
        params = {
            "model": self.modelo,
            "max_tokens": settings.MAX_TOKENS,
            "system": sistema,
            "messages": mensajes,
            # System prompt + tools no cambian entre vueltas: se cachean.
            "cache_control": {"type": "ephemeral"},
            # Si un clasificador de seguridad rechaza la solicitud, la API la
            # reintenta en el modelo recomendado en vez de devolver el rechazo.
            "betas": ["server-side-fallback-2026-07-01"],
            "fallbacks": "default",
        }
        if settings.EFFORT:
            params["output_config"] = {"effort": settings.EFFORT}
        if herramientas:
            params["tools"] = herramientas

        try:
            return self.cliente.beta.messages.create(**params)
        except anthropic.AuthenticationError as exc:
            raise LLMError("ANTHROPIC_API_KEY invalida.") from exc
        except anthropic.RateLimitError as exc:
            raise LLMError(f"Limite de uso de Anthropic: {exc.message}") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Anthropic {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError(f"No se pudo contactar Anthropic: {exc}") from exc
