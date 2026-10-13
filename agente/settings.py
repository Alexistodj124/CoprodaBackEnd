"""Configuracion del agente conversacional.

Todo se lee de variables de entorno para no dejar secretos en el repo.
Copia .env.example a .env y cargalo con `python-dotenv` (lo hace main.py).
"""
from __future__ import annotations

import os


class Settings:
    # --- Modelo ---
    # "suscripcion": Claude Agent SDK sobre la sesion de Claude Code (`claude auth
    #                login`), sin API key. Solo para pruebas locales.
    # "api":         Messages API con ANTHROPIC_API_KEY.
    BACKEND = os.getenv("AGENTE_BACKEND", "suscripcion").strip().lower()
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    # Tool-calling confiable es lo unico que importa aqui: si el modelo elige mal
    # la herramienta o se salta fecha_hoy, la respuesta sale mal aunque suene bien.
    MODELO = os.getenv("AGENTE_MODELO", "claude-opus-5")
    # Opus 5 piensa por defecto y max_tokens cubre pensamiento + respuesta, asi
    # que hay que dejar holgura aunque la respuesta de WhatsApp sea corta.
    MAX_TOKENS = int(os.getenv("AGENTE_MAX_TOKENS", "16000"))
    # low | medium | high | xhigh | max. Vacio = default del modelo (high en Opus 5).
    EFFORT = os.getenv("AGENTE_EFFORT", "").strip() or None
    TIMEOUT_LLM = int(os.getenv("AGENTE_TIMEOUT_LLM", "120"))

    # --- Backend Coproda (solo lectura) ---
    API_BASE_URL = os.getenv("COPRODA_API_URL", "https://coprodasa.com/api4/coproda")
    TIMEOUT_API = int(os.getenv("COPRODA_API_TIMEOUT", "20"))
    CACHE_TTL = int(os.getenv("COPRODA_CACHE_TTL", "60"))  # segundos

    # --- Loop del agente ---
    MAX_ITERACIONES = int(os.getenv("AGENTE_MAX_ITERACIONES", "6"))
    MAX_MENSAJES_HISTORIAL = int(os.getenv("AGENTE_MAX_HISTORIAL", "20"))
    DEBUG = os.getenv("AGENTE_DEBUG", "0") == "1"

    # --- WhatsApp Cloud API (channels/whatsapp.py) ---
    WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID", "")
    WA_TOKEN = os.getenv("WA_TOKEN", "")
    WA_VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN", "")
    # Vacio = no se verifica X-Hub-Signature-256. Solo aceptable en pruebas.
    WA_APP_SECRET = os.getenv("WA_APP_SECRET", "")
    # Telefonos (con codigo de pais, sin +) separados por coma.
    WA_NUMEROS_PERMITIDOS = os.getenv("WA_NUMEROS_PERMITIDOS", "")
    WA_GRAPH_VERSION = os.getenv("WA_GRAPH_VERSION", "v25.0")
    WA_PORT = int(os.getenv("WA_PORT", "8000"))

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
