"""Loop del agente: mensaje -> LLM -> herramientas -> LLM -> respuesta."""
from __future__ import annotations

import json

from agent.llm import Claude, LLMError
from agent.session import Sesion
from settings import settings
from tools import ejecutar, esquemas_para
from tools.base import Contexto


class Agente:
    def __init__(self, llm: Claude, ctx: Contexto, sesion: Sesion,
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
                resp = self.llm.chat(self.sesion.sistema, self.sesion.mensajes,
                                     herramientas)
            except LLMError as exc:
                return f"[error del modelo] {exc}"

            if resp.stop_reason == "refusal":
                return "No puedo ayudarte con esa consulta."

            # El contenido completo (thinking incluido) vuelve al historial tal
            # cual: la API lo necesita para continuar despues de un tool_use.
            self.sesion.agregar({"role": "assistant", "content": resp.content})

            llamadas = [b for b in resp.content if b.type == "tool_use"]
            texto_resp = "".join(b.text for b in resp.content if b.type == "text").strip()

            if resp.stop_reason == "max_tokens" and not llamadas:
                return (texto_resp + "\n[respuesta cortada por max_tokens]").strip()
            if resp.stop_reason != "tool_use" or not llamadas:
                return texto_resp or "(sin respuesta)"

            # Todos los resultados van en un solo mensaje 'user'.
            resultados = []
            for llamada in llamadas:
                args = llamada.input if isinstance(llamada.input, dict) else {}
                resultado = ejecutar(llamada.name, args, self.ctx)
                if self.on_tool:
                    self.on_tool(llamada.name, args, resultado)
                resultados.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": llamada.id,
                        "content": json.dumps(resultado, ensure_ascii=False, default=str),
                        **({"is_error": True}
                           if isinstance(resultado, dict) and "error" in resultado else {}),
                    }
                )
            self.sesion.agregar({"role": "user", "content": resultados})

        return (
            "Me enrede consultando el sistema y llegue al limite de pasos. "
            "¿Puedes reformular la pregunta con mas detalle?"
        )
