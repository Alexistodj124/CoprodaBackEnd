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
    sistema: str = ""
    sdk_session_id: str | None = None  # backend "suscripcion": la CLI guarda el historial

    def __post_init__(self):
        # En la API de Anthropic el system prompt va aparte, no en `mensajes`.
        self.sistema = sistema(self.usuario, self.rol)

    def agregar(self, mensaje: dict) -> None:
        self.mensajes.append(mensaje)
        self._recortar()

    @staticmethod
    def _es_turno_usuario(mensaje: dict) -> bool:
        """Un 'user' con texto plano; los tool_result tambien son role 'user'."""
        return mensaje.get("role") == "user" and isinstance(mensaje.get("content"), str)

    def _recortar(self) -> None:
        """Conserva los ultimos N mensajes.

        Corta solo en un turno de usuario con texto para no dejar tool_use /
        tool_result huerfanos, que hacen fallar la API.
        """
        limite = settings.MAX_MENSAJES_HISTORIAL
        if len(self.mensajes) <= limite:
            return
        corte = len(self.mensajes) - limite
        while corte < len(self.mensajes) and not self._es_turno_usuario(self.mensajes[corte]):
            corte += 1
        if corte < len(self.mensajes):  # sin corte valido, mejor no recortar
            self.mensajes = self.mensajes[corte:]

    def reiniciar(self) -> None:
        self.mensajes = []
        self.sdk_session_id = None
