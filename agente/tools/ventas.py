"""Herramientas de ventas / cartera. Rol: vendedor y admin."""
from __future__ import annotations

from collections import defaultdict

from tools.base import Contexto, coincide, herramienta

ROLES = ("vendedor", "admin")


# ----------------------------------------------------------------- helpers
def _clientes_visibles(ctx: Contexto) -> list[dict]:
    clientes = ctx.api.get("/clientes")
    if ctx.ve_todo:
        return clientes
    return [c for c in clientes if c.get("usuario_id") == ctx.usuario_id]


def _ordenes_visibles(ctx: Contexto, desde=None, hasta=None) -> list[dict]:
    params = {}
    if desde:
        params["inicio"] = desde
    if hasta:
        params["fin"] = hasta
    ordenes = ctx.api.get("/ordenes", params=params or None)
    if ctx.ve_todo:
        return ordenes
    ids_mios = {c["id"] for c in _clientes_visibles(ctx)}
    return [
        o for o in ordenes
        if o.get("usuario_id") == ctx.usuario_id or o.get("cliente_id") in ids_mios
    ]


def _mapa_estados(ctx: Contexto) -> dict[int, str]:
    return {e["id"]: e["nombre"] for e in ctx.api.get("/estados_orden")}


def _mapa_clientes(ctx: Contexto) -> dict[int, dict]:
    return {c["id"]: c for c in ctx.api.get("/clientes")}


def _mapa_productos(ctx: Contexto) -> dict[int, dict]:
    return {p["id"]: p for p in ctx.api.get("/productos")}


def _resolver_cliente(ctx: Contexto, referencia) -> dict | None:
    """Acepta id, codigo o parte del nombre."""
    clientes = _clientes_visibles(ctx)
    ref = str(referencia).strip()
    if ref.isdigit():
        for c in clientes:
            if c["id"] == int(ref):
                return c
    for c in clientes:
        if str(c.get("codigo", "")).lower() == ref.lower():
            return c
    candidatos = [c for c in clientes if coincide(c.get("nombre", ""), ref)]
    return candidatos[0] if len(candidatos) == 1 else (candidatos[0] if candidatos else None)


def _resumen_orden(o: dict, estados: dict, clientes: dict) -> dict:
    cli = clientes.get(o.get("cliente_id")) or {}
    return {
        "id": o["id"],
        "codigo": o.get("codigo_orden"),
        "fecha": o.get("fecha"),
        "cliente": cli.get("nombre"),
        "cliente_id": o.get("cliente_id"),
        "estado": estados.get(o.get("estado_id"), o.get("estado_id")),
        "total": o.get("total"),
        "saldo": o.get("saldo"),
    }


# ------------------------------------------------------------------ tools
@herramienta(
    nombre="buscar_cliente",
    descripcion=(
        "Busca clientes por nombre, codigo o id. Devuelve nombre, codigo, telefono, "
        "clasificacion de precio y saldo pendiente. Un vendedor solo ve su cartera."
    ),
    parametros={
        "type": "object",
        "properties": {
            "texto": {"type": "string", "description": "Nombre, codigo o id del cliente"},
            "limite": {"type": "integer", "default": 10},
        },
        "required": ["texto"],
    },
    roles=ROLES,
)
def buscar_cliente(ctx: Contexto, texto: str, limite: int = 10) -> dict:
    clientes = _clientes_visibles(ctx)
    encontrados = [
        c for c in clientes
        if coincide(c.get("nombre", ""), texto)
        or coincide(c.get("codigo", ""), texto)
        or str(c["id"]) == str(texto).strip()
    ]
    return {
        "total_encontrados": len(encontrados),
        "clientes": [
            {
                "id": c["id"],
                "codigo": c.get("codigo"),
                "nombre": c.get("nombre"),
                "telefono": c.get("telefono"),
                "clasificacion_precio": c.get("clasificacion_precio"),
                "saldo": c.get("saldo"),
                "activo": c.get("activo"),
            }
            for c in encontrados[:limite]
        ],
    }


@herramienta(
    nombre="estado_cuenta_cliente",
    descripcion=(
        "Estado de cuenta de un cliente: saldo total y el listado de ordenes que "
        "todavia tienen saldo pendiente. Acepta id, codigo o nombre."
    ),
    parametros={
        "type": "object",
        "properties": {
            "cliente": {"type": "string", "description": "id, codigo o nombre del cliente"}
        },
        "required": ["cliente"],
    },
    roles=ROLES,
)
def estado_cuenta_cliente(ctx: Contexto, cliente: str) -> dict:
    cli = _resolver_cliente(ctx, cliente)
    if not cli:
        return {"error": f"No encontre ningun cliente que coincida con '{cliente}'."}
    estados = _mapa_estados(ctx)
    clientes = _mapa_clientes(ctx)
    ordenes = [
        o for o in _ordenes_visibles(ctx)
        if o.get("cliente_id") == cli["id"] and float(o.get("saldo") or 0) > 0
    ]
    ordenes.sort(key=lambda o: o.get("fecha") or "")
    return {
        "cliente": {"id": cli["id"], "codigo": cli.get("codigo"), "nombre": cli.get("nombre")},
        "saldo_registrado": cli.get("saldo"),
        "total_pendiente_en_ordenes": round(
            sum(float(o.get("saldo") or 0) for o in ordenes), 2
        ),
        "ordenes_pendientes": [_resumen_orden(o, estados, clientes) for o in ordenes],
    }


@herramienta(
    nombre="listar_ordenes",
    descripcion=(
        "Lista ordenes de venta con filtros. Sirve para 'ordenes de esta semana', "
        "'pedidos del cliente X', 'que esta pendiente de pago'. Devuelve un resumen, "
        "no el detalle de items (para eso usa detalle_orden)."
    ),
    parametros={
        "type": "object",
        "properties": {
            "desde": {"type": "string", "description": "Fecha inicial YYYY-MM-DD"},
            "hasta": {"type": "string", "description": "Fecha final YYYY-MM-DD"},
            "cliente": {"type": "string", "description": "id, codigo o nombre del cliente"},
            "estado": {"type": "string", "description": "Nombre del estado, ej. 'pendiente'"},
            "solo_con_saldo": {"type": "boolean", "default": False},
            "limite": {"type": "integer", "default": 25},
        },
    },
    roles=ROLES,
)
def listar_ordenes(ctx: Contexto, desde=None, hasta=None, cliente=None, estado=None,
                   solo_con_saldo: bool = False, limite: int = 25) -> dict:
    ordenes = _ordenes_visibles(ctx, desde, hasta)
    estados = _mapa_estados(ctx)
    clientes = _mapa_clientes(ctx)

    if cliente:
        cli = _resolver_cliente(ctx, cliente)
        if not cli:
            return {"error": f"No encontre ningun cliente que coincida con '{cliente}'."}
        ordenes = [o for o in ordenes if o.get("cliente_id") == cli["id"]]
    if estado:
        ids = [i for i, n in estados.items() if coincide(n, estado)]
        ordenes = [o for o in ordenes if o.get("estado_id") in ids]
    if solo_con_saldo:
        ordenes = [o for o in ordenes if float(o.get("saldo") or 0) > 0]

    ordenes.sort(key=lambda o: (o.get("fecha") or "", o["id"]), reverse=True)
    return {
        "total_encontradas": len(ordenes),
        "mostrando": min(limite, len(ordenes)),
        "monto_total": round(sum(float(o.get("total") or 0) for o in ordenes), 2),
        "saldo_total": round(sum(float(o.get("saldo") or 0) for o in ordenes), 2),
        "ordenes": [_resumen_orden(o, estados, clientes) for o in ordenes[:limite]],
    }


@herramienta(
    nombre="detalle_orden",
    descripcion="Detalle completo de una orden de venta, con sus productos, cantidades y precios.",
    parametros={
        "type": "object",
        "properties": {
            "orden": {"type": "string", "description": "id o codigo de la orden"}
        },
        "required": ["orden"],
    },
    roles=ROLES,
)
def detalle_orden(ctx: Contexto, orden: str) -> dict:
    ref = str(orden).strip()
    encontrada = None
    if ref.isdigit():
        try:
            encontrada = ctx.api.get(f"/ordenes/{int(ref)}")
        except Exception:
            encontrada = None
    if encontrada is None:
        for o in _ordenes_visibles(ctx):
            if str(o.get("codigo_orden", "")).lower() == ref.lower():
                encontrada = o
                break
    if encontrada is None:
        return {"error": f"No encontre la orden '{orden}'."}

    if not ctx.ve_todo:
        ids_mios = {c["id"] for c in _clientes_visibles(ctx)}
        if (encontrada.get("usuario_id") != ctx.usuario_id
                and encontrada.get("cliente_id") not in ids_mios):
            return {"error": "Esa orden no pertenece a tu cartera."}

    estados = _mapa_estados(ctx)
    clientes = _mapa_clientes(ctx)
    productos = _mapa_productos(ctx)
    base = _resumen_orden(encontrada, estados, clientes)
    base["fecha_envio"] = encontrada.get("fecha_envio")
    base["fecha_pago"] = encontrada.get("fecha_pago")
    base["items"] = [
        {
            "producto": (productos.get(i["producto_id"]) or {}).get("nombre"),
            "codigo": (productos.get(i["producto_id"]) or {}).get("codigo"),
            "cantidad": i.get("cantidad"),
            "precio": i.get("precio"),
            "subtotal": round(float(i.get("precio") or 0) * int(i.get("cantidad") or 0), 2),
        }
        for i in encontrada.get("items", [])
    ]
    return base


@herramienta(
    nombre="resumen_ventas",
    descripcion=(
        "Totales de venta en un rango de fechas, agrupados por cliente, estado, "
        "producto o mes. Usalo para '¿cuanto vendi este mes?' o 'top clientes'."
    ),
    parametros={
        "type": "object",
        "properties": {
            "desde": {"type": "string", "description": "YYYY-MM-DD"},
            "hasta": {"type": "string", "description": "YYYY-MM-DD"},
            "agrupar_por": {
                "type": "string",
                "enum": ["cliente", "estado", "producto", "mes"],
                "default": "cliente",
            },
            "limite": {"type": "integer", "default": 10},
        },
        "required": ["desde", "hasta"],
    },
    roles=ROLES,
)
def resumen_ventas(ctx: Contexto, desde: str, hasta: str,
                   agrupar_por: str = "cliente", limite: int = 10) -> dict:
    ordenes = _ordenes_visibles(ctx, desde, hasta)
    estados = _mapa_estados(ctx)
    clientes = _mapa_clientes(ctx)
    productos = _mapa_productos(ctx)

    grupos: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "ordenes": 0, "unidades": 0})
    for o in ordenes:
        total = float(o.get("total") or 0)
        if agrupar_por == "cliente":
            clave = (clientes.get(o.get("cliente_id")) or {}).get("nombre", "(sin cliente)")
        elif agrupar_por == "estado":
            clave = estados.get(o.get("estado_id"), "(sin estado)")
        elif agrupar_por == "mes":
            clave = (o.get("fecha") or "")[:7]
        else:  # producto
            for i in o.get("items", []):
                p = productos.get(i["producto_id"]) or {}
                g = grupos[p.get("nombre", "(desconocido)")]
                g["total"] += float(i.get("precio") or 0) * int(i.get("cantidad") or 0)
                g["unidades"] += int(i.get("cantidad") or 0)
                g["ordenes"] += 1
            continue
        g = grupos[clave]
        g["total"] += total
        g["ordenes"] += 1

    filas = sorted(
        ({"grupo": k, **v} for k, v in grupos.items()),
        key=lambda r: r["total"], reverse=True,
    )
    for f in filas:
        f["total"] = round(f["total"], 2)
        if agrupar_por != "producto":
            f.pop("unidades", None)
    return {
        "rango": {"desde": desde, "hasta": hasta},
        "agrupado_por": agrupar_por,
        "total_general": round(sum(float(o.get("total") or 0) for o in ordenes), 2),
        "ordenes_consideradas": len(ordenes),
        "filas": filas[:limite],
    }


@herramienta(
    nombre="buscar_producto",
    descripcion=(
        "Busca un producto vendible (terminado o agranel) por nombre o codigo y "
        "devuelve sus tres precios (cf, minorista, mayorista) y lo disponible. "
        "Usalo para cotizar: '¿a como esta X?'. Para ver bodega completa o lo que "
        "se esta agotando, usa stock_productos."
    ),
    parametros={
        "type": "object",
        "properties": {
            "texto": {"type": "string"},
            "limite": {"type": "integer", "default": 10},
        },
        "required": ["texto"],
    },
    roles=ROLES,
)
def buscar_producto(ctx: Contexto, texto: str, limite: int = 10) -> dict:
    productos = ctx.api.get(
        "/productos", params={"activo": "true", "es_producto_final": "true"}
    )
    encontrados = [
        p for p in productos
        if coincide(p.get("nombre", ""), texto) or coincide(p.get("codigo", ""), texto)
    ]
    return {
        "total_encontrados": len(encontrados),
        "productos": [
            {
                "id": p["id"],
                "codigo": p.get("codigo"),
                "nombre": p.get("nombre"),
                "tipo": "terminado" if p.get("es_terminado") else "agranel",
                "precio_cf": p.get("precio_cf"),
                "precio_minorista": p.get("precio_minorista"),
                "precio_mayorista": p.get("precio_mayorista"),
                "stock_actual": p.get("stock_actual"),
                "stock_reservado": p.get("stock_reservado"),
                "disponible": round(
                    float(p.get("stock_actual") or 0) - float(p.get("stock_reservado") or 0), 4
                ),
            }
            for p in encontrados[:limite]
        ],
    }
