"""Configuracion del agente conversacional.

Todo se lee de variables de entorno para no dejar secretos en el repo.
Copia .env.example a .env y cargalo con `python-dotenv` (lo hace main.py).
"""
from __future__ import annotations

import os


class Settings:
    # --- OpenRouter ---
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL = os.getenv(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
    )
    # Tool-calling confiable es lo unico que importa aqui: si el modelo elige mal
    # la herramienta o se salta fecha_hoy, la respuesta sale mal aunque suene bien.
    MODELO = os.getenv("OPENROUTER_MODELO", "anthropic/claude-opus-5")
    # Las respuestas son de WhatsApp: cortas. Esto solo evita que se corte a medias.
    MAX_TOKENS = int(os.getenv("OPENROUTER_MAX_TOKENS", "2000"))
    # Opus 5, Sonnet 5 y Fable 5 ya no aceptan temperature. Dejala vacia salvo que
    # uses un modelo viejo (Sonnet 4.6, Haiku 4.5) donde si aplica.
    _temp = os.getenv("OPENROUTER_TEMPERATURA", "").strip()
    TEMPERATURA = float(_temp) if _temp else None
    TIMEOUT_LLM = int(os.getenv("OPENROUTER_TIMEOUT", "90"))

    # --- Backend Coproda (solo lectura) ---
    API_BASE_URL = os.getenv("COPRODA_API_URL", "https://coprodasa.com/api4/coproda")
    TIMEOUT_API = int(os.getenv("COPRODA_API_TIMEOUT", "20"))
    CACHE_TTL = int(os.getenv("COPRODA_CACHE_TTL", "60"))  # segundos

    # --- Loop del agente ---
    MAX_ITERACIONES = int(os.getenv("AGENTE_MAX_ITERACIONES", "6"))
    MAX_MENSAJES_HISTORIAL = int(os.getenv("AGENTE_MAX_HISTORIAL", "20"))
    DEBUG = os.getenv("AGENTE_DEBUG", "0") == "1"

    # --- Roles ---
    # Mapea nombres de permisos del backend -> rol del agente.
    # Ajusta segun los permisos reales en la tabla `permisos`.
    # Nombres reales de la tabla `permisos` (se comparan en minusculas).
    MAPA_PERMISO_ROL = {
        "maestro": "admin",          # usuario admin
        "admin": "admin",
        "administrador": "admin",
        "ventas": "vendedor",        # V00, V01, V02
        "clientesventas": "vendedor",
        "vendedor": "vendedor",
    }
    # Cualquier permiso no mapeado cae en ROL_POR_DEFECTO.
    ROL_POR_DEFECTO = os.getenv("AGENTE_ROL_DEFECTO", "vendedor")
    # Solo para pruebas locales: fuerza un rol sin importar los permisos.
    ROL_OVERRIDE = os.getenv("AGENTE_ROL_OVERRIDE") or None


settings = Settings()
