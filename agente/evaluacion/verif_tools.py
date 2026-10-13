# -*- coding: utf-8 -*-
"""Verifica la capa de herramientas sin el LLM: confirma la verdad de referencia."""
import sys, os, json
AG="/Users/alexismesias/Documents/Codes/CoprodaBackEnd/agente"
sys.path.insert(0,AG)
from dotenv import load_dotenv; load_dotenv(os.path.join(AG,".env"))
from backend.client import CoprodaClient
from tools.base import Contexto, ejecutar
import tools

api=CoprodaClient()
ctx=Contexto(api=api, usuario_id=None, usuario="evaluacion", rol="admin")
SPD=os.path.dirname(os.path.abspath(__file__))
casos=json.load(open(os.path.join(SPD,"casos.json"),encoding="utf8"))["casos"]

print("=== las 10 herramientas responden? ===")
pruebas=[("fecha_hoy",{}),("quien_soy",{}),("stock_productos",{}),
         ("buscar_cliente",{"texto":"a"}),("buscar_producto",{"texto":"olla"}),
         ("listar_ordenes",{}),("resumen_ventas",{})]
for n,args in pruebas:
    r=ejecutar(n,args,ctx)
    ok = not (isinstance(r,dict) and "error" in r)
    s=json.dumps(r,ensure_ascii=False,default=str)
    print(f"  {'OK ' if ok else 'ERR'} {n:22s} {s[:95]}")

print("\n=== verdad de referencia de los casos normales ===")
for c in casos[:20]:
    e=c["esperado"]
    if e["tipo"]=="numero" and "cliente_id" in e and "producto_id" not in e:
        r=ejecutar("estado_cuenta_cliente",{"cliente":str(e['cliente_id'])},ctx)
        s=json.dumps(r,ensure_ascii=False,default=str)
        print(f"  [{c['n']:02d}] esperado Q{e['valor']:,.2f} | herramienta: {s[:110]}")
