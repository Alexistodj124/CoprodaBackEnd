"""Canal de consola: REPL para probar el agente sin WhatsApp."""
from __future__ import annotations

import getpass
import json

from agent import Sesion, crear_agente
from backend.client import BackendError, CoprodaClient
from settings import settings
from tools.base import Contexto, REGISTRO

AYUDA = """
Comandos:
  /salir        terminar
  /nuevo        borrar el historial de la conversacion
  /tools        ver las herramientas disponibles para tu rol
  /debug        activar/desactivar el detalle de llamadas a herramientas
  /ayuda        este mensaje
"""


def _rol_desde_permisos(permisos: list[str]) -> str:
    if settings.ROL_OVERRIDE:
        return settings.ROL_OVERRIDE
    for p in permisos or []:
        rol = settings.MAPA_PERMISO_ROL.get(str(p).strip().lower())
        if rol == "admin":
            return "admin"
    for p in permisos or []:
        rol = settings.MAPA_PERMISO_ROL.get(str(p).strip().lower())
        if rol:
            return rol
    return settings.ROL_POR_DEFECTO


def _login(api: CoprodaClient) -> Contexto:
    print("=== Agente Coproda (solo lectura) ===")
    while True:
        usuario = input("Usuario: ").strip()
        contrasena = getpass.getpass("Contrasena: ")
        try:
            datos = api.login(usuario, contrasena)
        except BackendError as exc:
            print(f"  {exc}\n")
            continue
        if not datos.get("activo", True):
            print("  Ese usuario esta inactivo.\n")
            continue
        rol = _rol_desde_permisos(datos.get("permisos", []))
        print(f"\nHola {datos['usuario']}. Rol: {rol}. Escribe /ayuda para ver comandos.\n")
        return Contexto(
            api=api, usuario_id=datos.get("id"), usuario=datos["usuario"], rol=rol
        )


def ejecutar_repl() -> None:
    api = CoprodaClient()
    ctx = _login(api)
    sesion = Sesion(usuario=ctx.usuario, usuario_id=ctx.usuario_id, rol=ctx.rol)
    debug = {"on": settings.DEBUG}

    def traza(nombre, args, resultado):
        if not debug["on"]:
            return
        recorte = json.dumps(resultado, ensure_ascii=False, default=str)[:300]
        print(f"  · {nombre}({json.dumps(args, ensure_ascii=False)}) -> {recorte}")

    agente = crear_agente(ctx, sesion, on_tool=traza)

    while True:
        try:
            texto = input("\nTu > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego.")
            return
        if not texto:
            continue
        if texto in ("/salir", "/exit", "/q"):
            print("Hasta luego.")
            return
        if texto == "/ayuda":
            print(AYUDA)
            continue
        if texto == "/nuevo":
            sesion.reiniciar()
            api.limpiar_cache()
            print("Conversacion reiniciada.")
            continue
        if texto == "/tools":
            for h in REGISTRO.values():
                if ctx.rol in h.roles:
                    print(f"  - {h.nombre}: {h.descripcion.splitlines()[0]}")
            continue
        if texto == "/debug":
            debug["on"] = not debug["on"]
            print(f"Debug {'activado' if debug['on'] else 'desactivado'}.")
            continue

        print("\nAgente > ", end="", flush=True)
        print(agente.responder(texto))
