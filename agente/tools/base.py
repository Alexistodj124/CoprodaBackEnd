"""Registro de herramientas (function calling) y contexto de ejecucion."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any, Callable

from backend.client import CoprodaClient

REGISTRO: dict[str, "Herramienta"] = {}


@dataclass
class Contexto:
    """Identidad y alcance del usuario que hace la consulta."""

    api: CoprodaClient
    usuario_id: int | None
    usuario: str
    rol: str  # vendedor | admin

    @property
    def ve_todo(self) -> bool:
        """Solo admin ve la cartera completa; el vendedor ve la suya."""
        return self.rol == "admin"


@dataclass
class Herramienta:
    nombre: str
    descripcion: str
    parametros: dict
    roles: set[str]
    fn: Callable

    def esquema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.nombre,
                "description": self.descripcion,
                "parameters": self.parametros,
            },
        }


def herramienta(nombre: str, descripcion: str, parametros: dict | None = None,
                roles: tuple[str, ...] = ("admin",)):
    def deco(fn):
        REGISTRO[nombre] = Herramienta(
            nombre=nombre,
            descripcion=descripcion,
            parametros=parametros or {"type": "object", "properties": {}},
            roles=set(roles),
            fn=fn,
        )
        return fn

    return deco


def esquemas_para(rol: str) -> list[dict]:
    return [h.esquema() for h in REGISTRO.values() if rol in h.roles]


def ejecutar(nombre: str, argumentos: dict, ctx: Contexto) -> Any:
    h = REGISTRO.get(nombre)
    if h is None:
        return {"error": f"Herramienta desconocida: {nombre}"}
    if ctx.rol not in h.roles:
        return {"error": f"Tu rol ({ctx.rol}) no tiene acceso a {nombre}."}
    try:
        return h.fn(ctx, **(argumentos or {}))
    except TypeError as exc:
        return {"error": f"Argumentos invalidos para {nombre}: {exc}"}
    except Exception as exc:  # noqa: BLE001 - el error vuelve al modelo, no revienta el REPL
        return {"error": f"{type(exc).__name__}: {exc}"}


# ---------------------------------------------------------------- utilidades
def normalizar(texto: str) -> str:
    """minusculas y sin acentos, para busquedas tolerantes."""
    if not texto:
        return ""
    sin_acentos = unicodedata.normalize("NFKD", str(texto))
    sin_acentos = "".join(c for c in sin_acentos if not unicodedata.combining(c))
    return sin_acentos.lower().strip()


def coincide(texto: str, consulta: str) -> bool:
    return normalizar(consulta) in normalizar(texto)


def q(valor) -> str:
    """Formatea quetzales."""
    return f"Q{float(valor or 0):,.2f}"
