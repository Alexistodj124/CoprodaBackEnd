"""Agente sobre el Claude Agent SDK: usa la sesion de Claude Code (suscripcion).

Mismo contrato que `Agente` (responder(texto) -> str, callback on_tool), pero el
loop LLM <-> herramientas lo corre la CLI de Claude Code autenticada con
`claude auth login`, no la Messages API con API key. Pensado para pruebas
locales.

Aislamiento, para que la evaluacion mida solo a este agente:
  - system prompt propio (reemplaza el de Claude Code),
  - sin herramientas integradas (Bash, Read, WebSearch...),
  - solo el servidor MCP en proceso con las 10 herramientas de Coproda,
  - sin settings, hooks, CLAUDE.md ni skills del usuario.
"""
from __future__ import annotations

import asyncio
import json
import os

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKError,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
    query,
    tool,
)

from agent.session import Sesion
from settings import settings
from tools import REGISTRO, ejecutar
from tools.base import Contexto

SERVIDOR = "coproda"


class AgenteSuscripcion:
    def __init__(self, ctx: Contexto, sesion: Sesion, on_tool=None):
        self.ctx = ctx
        self.sesion = sesion
        self.on_tool = on_tool
        self.ultimo_resultado: ResultMessage | None = None
        # Si hay una API key en el entorno, la CLI la usa en vez de la
        # suscripcion. Se quita para forzar el login de Claude Code.
        os.environ.pop("ANTHROPIC_API_KEY", None)

    def _herramientas(self):
        mcp_tools = []
        for h in REGISTRO.values():
            if self.ctx.rol not in h.roles:
                continue

            def envolver(nombre):
                async def handler(args):
                    resultado = ejecutar(nombre, args or {}, self.ctx)
                    if self.on_tool:
                        self.on_tool(nombre, args or {}, resultado)
                    texto = json.dumps(resultado, ensure_ascii=False, default=str)
                    es_error = isinstance(resultado, dict) and "error" in resultado
                    return {"content": [{"type": "text", "text": texto}],
                            **({"is_error": True} if es_error else {})}
                return handler

            mcp_tools.append(tool(h.nombre, h.descripcion, h.parametros)(envolver(h.nombre)))
        return mcp_tools

    def _opciones(self) -> ClaudeAgentOptions:
        mcp_tools = self._herramientas()
        return ClaudeAgentOptions(
            model=settings.MODELO,
            system_prompt=self.sesion.sistema,
            tools=[],
            mcp_servers={SERVIDOR: create_sdk_mcp_server(SERVIDOR, tools=mcp_tools)},
            strict_mcp_config=True,
            allowed_tools=[f"mcp__{SERVIDOR}__{t.name}" for t in mcp_tools],
            setting_sources=[],
            skills=[],
            max_turns=settings.MAX_ITERACIONES,
            effort=settings.EFFORT,
            resume=self.sesion.sdk_session_id,
        )

    async def _responder(self, texto: str) -> str:
        partes: list[str] = []
        error = None
        resultado = None
        # Se consume el stream completo (sin return adentro) para que el SDK
        # cierre la CLI limpio.
        try:
            async for msg in query(prompt=texto, options=self._opciones()):
                if isinstance(msg, AssistantMessage):
                    if msg.error:
                        error = msg.error
                    # Solo el texto del ultimo mensaje del asistente es la respuesta;
                    # los anteriores son preambulos antes de llamar herramientas.
                    textos = [b.text for b in msg.content if isinstance(b, TextBlock)]
                    if textos:
                        partes = textos
                elif isinstance(msg, ResultMessage):
                    resultado = msg
        except ClaudeSDKError as exc:
            # El SDK lanza al final si el resultado fue error; si ya llego el
            # ResultMessage (p. ej. error_max_turns) se maneja abajo.
            if "Not logged in" in str(exc):
                error = "authentication_failed"
            elif resultado is None:
                return f"[error del modelo] {exc}"

        self.ultimo_resultado = resultado
        if resultado is not None:
            self.sesion.sdk_session_id = resultado.session_id
            if resultado.subtype == "error_max_turns":
                return ("Me enrede consultando el sistema y llegue al limite de pasos. "
                        "¿Puedes reformular la pregunta con mas detalle?")
        if error or (resultado is not None and resultado.is_error):
            if error == "authentication_failed":
                return "[error del modelo] no hay sesion de Claude Code; corre `claude auth login`"
            return f"[error del modelo] {error or resultado.result or resultado.subtype}"
        return "".join(partes).strip() or "(sin respuesta)"

    def responder(self, texto: str) -> str:
        return asyncio.run(self._responder(texto))
