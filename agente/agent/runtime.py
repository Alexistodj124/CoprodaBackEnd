"""Loop del agente: mensaje -> LLM -> herramientas -> LLM -> respuesta."""
from __future__ import annotations

import json

from agent.llm import LLMError, OpenRouter
from agent.session import Sesion
from settings import settings
from tools import ejecutar, esquemas_para
from tools.base import Contexto


class Agente:
    def __init__(self, llm: OpenRouter, ctx: Contexto, sesion: Sesion,
                 on_tool=None):
        self.llm = llm
        self.ctx = ctx
        self.sesion = sesion
        self.on_tool = on_tool  # callback(nombre, args, resultado) para debug/log

    def responder(self, texto: str) -> str:
        self.sesion.agregar({"role": "user", "content": texto})
        herramientas = esquemas_para(self.ctx.rol)

        for _ in range(settings.MAX_ITERACIONES):
            try:
                datos = self.llm.chat(self.sesion.mensajes, herramientas)
            except LLMError as exc:
                return f"[error del modelo] {exc}"

            mensaje = datos["choices"][0]["message"]
            llamadas = mensaje.get("tool_calls") or []

            # El historial necesita el mensaje del asistente tal cual vino.
            self.sesion.agregar(
                {
                    "role": "assistant",
                    "content": mensaje.get("content") or "",
                    **({"tool_calls": llamadas} if llamadas else {}),
                }
            )

            if not llamadas:
                return (mensaje.get("content") or "").strip() or "(sin respuesta)"

            for llamada in llamadas:
                nombre = llamada["function"]["name"]
                try:
                    args = json.loads(llamada["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                resultado = ejecutar(nombre, args, self.ctx)
                if self.on_tool:
                    self.on_tool(nombre, args, resultado)
                self.sesion.agregar(
                    {
                        "role": "tool",
                        "tool_call_id": llamada["id"],
                        "name": nombre,
                        "content": json.dumps(resultado, ensure_ascii=False, default=str),
                    }
                )

        return (
            "Me enrede consultando el sistema y llegue al limite de pasos. "
            "¿Puedes reformular la pregunta con mas detalle?"
        )
