"""Herramientas de contexto: fecha y quien pregunta."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from tools.base import Contexto, herramienta

TODOS = ("vendedor", "admin")


@herramienta(
    nombre="fecha_hoy",
    descripcion=(
        "Devuelve la fecha y hora actual mas rangos utiles (hoy, ayer, esta semana, "
        "este mes, mes pasado). USALA SIEMPRE antes de resolver frases como 'hoy', "
        "'esta semana' o 'este mes'; no adivines la fecha."
    ),
    roles=TODOS,
)
def fecha_hoy(ctx: Contexto) -> dict:
    hoy = date.today()
    lunes = hoy - timedelta(days=hoy.weekday())
    primero_mes = hoy.replace(day=1)
    fin_mes_pasado = primero_mes - timedelta(days=1)
    return {
        "ahora": datetime.now().isoformat(timespec="seconds"),
        "hoy": hoy.isoformat(),
        "ayer": (hoy - timedelta(days=1)).isoformat(),
        "semana_actual": {"desde": lunes.isoformat(), "hasta": hoy.isoformat()},
        "mes_actual": {"desde": primero_mes.isoformat(), "hasta": hoy.isoformat()},
        "mes_pasado": {
            "desde": fin_mes_pasado.replace(day=1).isoformat(),
            "hasta": fin_mes_pasado.isoformat(),
        },
        "ultimos_30_dias": {
            "desde": (hoy - timedelta(days=30)).isoformat(),
            "hasta": hoy.isoformat(),
        },
    }


@herramienta(
    nombre="quien_soy",
    descripcion=(
        "Identidad del usuario actual: nombre, rol y alcance de datos que puede ver. "
        "Usala si el usuario pregunta '¿que puedo consultar?' o '¿quien soy?'."
    ),
    roles=TODOS,
)
def quien_soy(ctx: Contexto) -> dict:
    return {
        "usuario": ctx.usuario,
        "usuario_id": ctx.usuario_id,
        "rol": ctx.rol,
        "alcance": (
            "todos los clientes y ordenes"
            if ctx.ve_todo
            else "solo los clientes y ordenes asignados a este usuario"
        ),
        "solo_lectura": True,
    }
