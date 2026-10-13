"""Sesion de conversacion: identidad + historial acotado."""
from __future__ import annotations

from dataclasses import dataclass, field

from agent.prompts import sistema
from settings import settings


@dataclass
class Sesion:
    usuario: str
    usuario_id: int | None
    rol: str
    mensajes: list[dict] = field(default_factory=list)

    def __post_init__(self):
        if not self.mensajes:
            self.mensajes = [{"role": "system", "content": sistema(self.usuario, self.rol)}]

    def agregar(self, mensaje: dict) -> None:
        self.mensajes.append(mensaje)
        self._recortar()

    def _recortar(self) -> None:
        """Conserva el system prompt y los ultimos N mensajes.

        Corta solo en un mensaje 'user' para no dejar tool_calls huerfanos,
        que hacen fallar la API.
        """
        limite = settings.MAX_MENSAJES_HISTORIAL
        cuerpo = self.mensajes[1:]
        if len(cuerpo) <= limite:
            return
        exceso = len(cuerpo) - limite
        corte = exceso
        while corte < len(cuerpo) and cuerpo[corte].get("role") != "user":
            corte += 1
        self.mensajes = [self.mensajes[0]] + cuerpo[corte:]

    def reiniciar(self) -> None:
        self.mensajes = [{"role": "system", "content": sistema(self.usuario, self.rol)}]
