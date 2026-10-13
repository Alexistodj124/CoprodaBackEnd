# -*- coding: utf-8 -*-
"""Corre los casos contra el agente y guarda respuestas + llamadas a herramientas."""
import sys, os, json, time, argparse
AG = "/Users/alexismesias/Documents/Codes/CoprodaBackEnd/agente"
sys.path.insert(0, AG)
from dotenv import load_dotenv; load_dotenv(os.path.join(AG, ".env"))
from agent import Agente, OpenRouter, Sesion
from backend.client import CoprodaClient
from tools.base import Contexto
from settings import settings

SPD = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("--desde", type=int, default=1)
ap.add_argument("--hasta", type=int, default=999)
ap.add_argument("--salida", default="respuestas.json")
a = ap.parse_args()

casos = json.load(open(os.path.join(SPD, "casos.json"), encoding="utf8"))["casos"]
casos = [c for c in casos if a.desde <= c["n"] <= a.hasta]
print(f"modelo: {settings.MODELO} | casos: {len(casos)}")

api = CoprodaClient()
ctx = Contexto(api=api, usuario_id=None, usuario="evaluacion", rol="admin")
out = []
t0 = time.time()
for c in casos:
    sesion = Sesion(usuario=ctx.usuario, usuario_id=ctx.usuario_id, rol=ctx.rol)
    llamadas = []
    ag = Agente(OpenRouter(), ctx, sesion,
                on_tool=lambda n, ar, r: llamadas.append({"tool": n, "args": ar}))
    t = time.time()
    try:
        resp = ag.responder(c["pregunta"])
    except Exception as exc:
        resp = f"[EXCEPCION] {type(exc).__name__}: {exc}"
    dt = round(time.time() - t, 1)
    out.append({**c, "respuesta": resp, "herramientas": llamadas, "segundos": dt})
    print(f"[{c['n']:02d}] {dt:5.1f}s {len(llamadas)}t | {c['pregunta'][:52]}")
    print(f"     -> {resp[:150].replace(chr(10),' ')}")
    json.dump(out, open(os.path.join(SPD, a.salida), "w", encoding="utf8"),
              ensure_ascii=False, indent=1)
print(f"\ntotal {round(time.time()-t0,1)}s -> {a.salida}")
