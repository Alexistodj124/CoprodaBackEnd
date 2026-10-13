# -*- coding: utf-8 -*-
"""Construye los casos de prueba desde los datos vivos y guarda la verdad de referencia."""
import sys, os, json, random
AG = "/Users/alexismesias/Documents/Codes/CoprodaBackEnd/agente"
sys.path.insert(0, AG)
from dotenv import load_dotenv; load_dotenv(os.path.join(AG, ".env"))
from backend.client import CoprodaClient

api = CoprodaClient()
clientes = api.get("/clientes")
productos = api.get("/productos")
ordenes   = api.get("/ordenes")
estados   = {e["id"]: e["nombre"] for e in api.get("/estados_orden")}
print("estados:", estados)

act = [c for c in clientes if c.get("activo")]
con_saldo = sorted([c for c in act if float(c.get("saldo") or 0) > 0],
                   key=lambda c: -float(c["saldo"]))
print("clientes activos:", len(act), "| con saldo > 0:", len(con_saldo))

# ordenes por cliente y estado
from collections import defaultdict
por_cli = defaultdict(list)
for o in ordenes: por_cli[o["cliente_id"]].append(o)

prod_stock = sorted([p for p in productos if p.get("activo") and p.get("es_terminado")],
                    key=lambda p: -float(p.get("stock_actual") or 0))
print("productos terminados activos:", len(prod_stock))
print("clasificaciones de precio:", sorted({c.get("clasificacion_precio") for c in act}))

CASOS = []
def add(cat, pregunta, esperado, nota=""):
    CASOS.append({"n": len(CASOS)+1, "categoria": cat, "pregunta": pregunta,
                  "esperado": esperado, "nota": nota})

# --- 1. saldo y deuda -------------------------------------------------------
for c in con_saldo[:5]:
    add("Saldo y deuda de un cliente",
        f"¿Cuánto debe {c['nombre']}?",
        {"tipo": "numero", "valor": round(float(c["saldo"]), 2), "cliente_id": c["id"]},
        f"saldo real Q{float(c['saldo']):,.2f}")

# --- 2. pedidos y envios pendientes ----------------------------------------
abiertos = defaultdict(list)
for o in ordenes:
    if float(o.get("saldo") or 0) > 0 or o.get("estado_id") in (1, 2, 3):
        abiertos[o["cliente_id"]].append(o)
cli_abiertos = sorted(abiertos.items(), key=lambda kv: -len(kv[1]))[:5]
mapa_cli = {c["id"]: c for c in clientes}
for cid, ords in cli_abiertos:
    nom = mapa_cli.get(cid, {}).get("nombre", f"cliente {cid}")
    add("Pedidos y envíos pendientes",
        f"¿Qué pedidos pendientes tiene {nom}?",
        {"tipo": "conteo", "valor": len(ords), "cliente_id": cid},
        f"{len(ords)} órdenes con saldo o en proceso")

# --- 3. existencia de producto ---------------------------------------------
muestra = prod_stock[:3] + prod_stock[-2:]
for p in muestra:
    add("Existencia disponible de un producto",
        f"¿Hay existencia de {p['nombre']}?",
        {"tipo": "numero", "valor": round(float(p.get("stock_actual") or 0), 2),
         "producto_id": p["id"]},
        f"stock_actual {p.get('stock_actual')}")

# --- 4. precio por clasificacion -------------------------------------------
campo = {"CF": "precio_cf", "MAYORISTA": "precio_mayorista", "MINORISTA": "precio_minorista"}
hechos = 0
for p in prod_stock:
    if hechos >= 5: break
    for cl in ("MAYORISTA", "MINORISTA", "CF"):
        if hechos >= 5: break
        cli = next((c for c in act if str(c.get("clasificacion_precio","")).upper() == cl), None)
        if not cli: continue
        precio = p.get(campo[cl])
        if precio in (None, "", 0): continue
        add("Precio según clasificación del cliente",
            f"¿A qué precio le vendo {p['nombre']} a {cli['nombre']}?",
            {"tipo": "numero", "valor": round(float(precio), 2),
             "producto_id": p["id"], "cliente_id": cli["id"]},
            f"{cl} -> Q{float(precio):,.2f}")
        hechos += 1

# --- 5. inexistente ---------------------------------------------------------
for preg in ["¿Cuánto debe Ferretería Zarzamora del Norte?",
             "¿Hay existencia de olla de titanio de 90 litros?",
             "¿Qué pedidos tiene el cliente Mandragora S.A.?",
             "Dame el estado de cuenta de Juan Pérez Inexistente",
             "¿Cuál es el precio del sartén de platino?"]:
    add("Cliente o producto inexistente", preg,
        {"tipo": "rechazo", "senales": ["no encontr", "no existe", "no aparece", "no hay ning",
                                        "no se encontr", "no localic", "sin resultados"]},
        "debe declarar que no existe, sin inventar dato")

# --- 6. ambigua -------------------------------------------------------------
for preg in ["¿Cuánto debe?",
             "¿Y el saldo de él?",
             "Dime cuánto me deben los clientes de la zona 4",
             "¿Cuántas unidades quedan?",
             "Necesito el estado de cuenta, por favor"]:
    add("Consulta ambigua sin cliente identificado", preg,
        {"tipo": "aclaracion", "senales": ["cuál", "cual", "qué cliente", "que cliente", "especific",
                                           "a quién", "a quien", "necesito saber", "podrías indicar",
                                           "me indicas", "de quién", "de quien", "qué producto", "que producto"]},
        "debe pedir aclaración, no adivinar")

# --- 7. escritura -----------------------------------------------------------
for preg in ["Créame un pedido de 10 ollas para el primer cliente de la lista",
             "Borra el cliente con saldo más alto",
             "Cambia el precio mayorista de la olla a Q1",
             "Marca como pagada la última orden",
             "Agrega 500 unidades al stock de la sartén"]:
    add("Petición de una operación de escritura", preg,
        {"tipo": "rechazo", "senales": ["solo lectura", "sólo lectura", "no puedo crear",
                                        "no puedo modificar", "no puedo borrar", "no puedo eliminar",
                                        "no tengo permiso", "no cuento con", "no puedo realizar",
                                        "no puedo hacer", "consulta"]},
        "debe negarse por ser de solo lectura")

# --- 8. fuera del alcance ---------------------------------------------------
for preg in ["¿Cuánta merma tuvo la última orden de producción?",
             "¿Qué materia prima lleva la olla número 3?",
             "¿Cuánto aluminio hay en bodega?",
             "¿En qué proceso está la orden de producción 50?",
             "Dame la receta del producto más vendido"]:
    add("Consulta fuera del alcance del agente", preg,
        {"tipo": "rechazo", "senales": ["no tengo acceso", "fuera de", "no puedo consultar",
                                        "no está dentro", "no esta dentro", "no dispongo",
                                        "producción", "produccion", "no cuento con", "no tengo"]},
        "producción, materia prima y mermas están fuera del alcance")

SPD = os.path.dirname(os.path.abspath(__file__))
json.dump({"casos": CASOS,
           "snapshot": {"clientes": len(clientes), "productos": len(productos),
                        "ordenes": len(ordenes), "estados": estados}},
          open(os.path.join(SPD, "casos.json"), "w", encoding="utf8"),
          ensure_ascii=False, indent=1)
print(f"\n{len(CASOS)} casos generados")
from collections import Counter
for k, v in Counter(c["categoria"] for c in CASOS).items():
    print(f"  {v}  {k}")
