"""Existencias de producto terminado y agranel.

No cubre materia prima ni componentes: eso es produccion, fuera del alcance
de este agente.

Clasificacion en el modelo Producto:
  TERMINADO -> es_producto_final=True,  es_terminado=True
  AGRANEL   -> es_producto_final=True,  es_terminado=False
  COMPONENTE-> es_producto_final=False              (excluido)
"""
from __future__ import annotations

from tools.base import Contexto, coincide, herramienta

ROLES = ("vendedor", "admin")


def _tipo(producto: dict) -> str:
    if not producto.get("es_producto_final"):
        return "componente"
    return "terminado" if producto.get("es_terminado") else "agranel"


def _fila(producto: dict) -> dict:
    actual = float(producto.get("stock_actual") or 0)
    reservado = float(producto.get("stock_reservado") or 0)
    minimo = float(producto.get("stock_minimo") or 0)
    disponible = round(actual - reservado, 4)
    return {
        "id": producto["id"],
        "codigo": producto.get("codigo"),
        "nombre": producto.get("nombre"),
        "tipo": _tipo(producto),
        "stock_actual": actual,
        "stock_reservado": reservado,
        "disponible": disponible,
        "stock_minimo": minimo,
        "bajo_minimo": disponible <= minimo,
    }


@herramienta(
    nombre="stock_productos",
    descripcion=(
        "Existencias de producto terminado y agranel: stock actual, reservado, "
        "disponible y minimo. Usala para '¿que hay en bodega?', '¿que se esta "
        "agotando?', '¿cuanto queda de X?'. Con solo_bajo_minimo=true devuelve "
        "unicamente lo que ya esta en o bajo el minimo. NO incluye materia prima "
        "ni componentes de produccion."
    ),
    parametros={
        "type": "object",
        "properties": {
            "texto": {"type": "string", "description": "nombre o codigo (opcional)"},
            "tipo": {
                "type": "string",
                "enum": ["todos", "terminado", "agranel"],
                "default": "todos",
            },
            "solo_bajo_minimo": {"type": "boolean", "default": False},
            "limite": {"type": "integer", "default": 25},
        },
    },
    roles=ROLES,
)
def stock_productos(ctx: Contexto, texto=None, tipo: str = "todos",
                    solo_bajo_minimo: bool = False, limite: int = 25) -> dict:
    productos = ctx.api.get("/productos", params={"activo": "true", "es_producto_final": "true"})

    if texto:
        productos = [
            p for p in productos
            if coincide(p.get("nombre", ""), texto) or coincide(p.get("codigo", ""), texto)
        ]

    filas = [_fila(p) for p in productos]
    if tipo in ("terminado", "agranel"):
        filas = [f for f in filas if f["tipo"] == tipo]
    if solo_bajo_minimo:
        filas = [f for f in filas if f["bajo_minimo"]]

    filas.sort(key=lambda f: (not f["bajo_minimo"], f["nombre"] or ""))
    return {
        "tipo_consultado": tipo,
        "total": len(filas),
        "bajo_minimo": sum(1 for f in filas if f["bajo_minimo"]),
        "productos": filas[:limite],
    }


@herramienta(
    nombre="alcanza_para_pedido",
    descripcion=(
        "Revisa si hay existencia suficiente para vender una cantidad de un "
        "producto. Responde cuanto hay disponible y cuanto faltaria."
    ),
    parametros={
        "type": "object",
        "properties": {
            "producto": {"type": "string", "description": "id, codigo o nombre"},
            "cantidad": {"type": "number"},
        },
        "required": ["producto", "cantidad"],
    },
    roles=ROLES,
)
def alcanza_para_pedido(ctx: Contexto, producto: str, cantidad: float) -> dict:
    productos = ctx.api.get("/productos", params={"activo": "true", "es_producto_final": "true"})
    ref = str(producto).strip()
    encontrados = [p for p in productos if str(p["id"]) == ref]
    if not encontrados:
        encontrados = [
            p for p in productos
            if coincide(p.get("codigo", ""), ref) or coincide(p.get("nombre", ""), ref)
        ]
    if not encontrados:
        return {"error": f"No encontre el producto '{producto}'."}
    if len(encontrados) > 1:
        return {
            "ambiguo": True,
            "mensaje": "Varios productos coinciden, pide al usuario que elija.",
            "candidatos": [
                {"id": p["id"], "codigo": p.get("codigo"), "nombre": p.get("nombre")}
                for p in encontrados[:5]
            ],
        }

    fila = _fila(encontrados[0])
    faltante = round(float(cantidad) - fila["disponible"], 4)
    return {
        "producto": fila["nombre"],
        "codigo": fila["codigo"],
        "tipo": fila["tipo"],
        "cantidad_solicitada": cantidad,
        "disponible": fila["disponible"],
        "alcanza": faltante <= 0,
        "faltante": max(faltante, 0),
    }
