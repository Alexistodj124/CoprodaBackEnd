# Agente conversacional Coproda — Ventas

Asistente de **solo lectura** para vendedores. Habla en lenguaje natural,
consulta la API de Coproda con *function calling* vía OpenRouter, y contesta
con datos reales.

**Alcance:** clientes, cartera y saldos, órdenes de venta, precios, y
existencias de producto **terminado y agranel**.
**Fuera de alcance:** producción, procesos, materia prima, recetas y mermas.

Hoy corre en consola. El canal de WhatsApp es fase 2 y ya está previsto en
`channels/whatsapp.py`.

## Cómo correrlo

```bash
cd agente
pip install -r requirements.txt
cp .env.example .env      # pon tu OPENROUTER_API_KEY
python main.py
```

Apunta a la API de producción, `https://coprodasa.com/api4/coproda`. Para
pegarle a un backend local, cambiá `COPRODA_API_URL` en el `.env`.

Como la API es de producción y el agente solo hace GET, se puede probar sin
riesgo de tocar datos.

Comandos del REPL: `/ayuda`, `/tools`, `/debug`, `/nuevo`, `/salir`.
`/debug` imprime cada llamada a herramienta con sus argumentos y su resultado:
es lo más útil para afinar prompts y descripciones.

## Modelo

Por defecto `anthropic/claude-opus-5` vía OpenRouter.

Lo único que decide si este agente sirve es la disciplina de tool-calling: elegir
la herramienta correcta, encadenar `fecha_hoy` antes de un rango de fechas,
preguntar cuando hay dos clientes que coinciden, y no inventar un saldo cuando la
herramienta devolvió vacío. Ahí es donde se nota el modelo, no en la redacción.

Costo real de este agente: el prefijo estable (system prompt + los 10 esquemas)
son ~1,840 tokens, y una consulta típica son 2 llamadas al modelo (elegir
herramienta, redactar respuesta), unas 3 si encadena. Eso da ~6,000 tokens de
entrada y ~250 de salida por consulta.

| Modelo | $/1M in-out | Por consulta | 1,500 consultas/mes |
|---|---|---|---|
| `anthropic/claude-opus-5` | $5 / $25 | ~Q0.28 | ~Q420 |
| `anthropic/claude-sonnet-5` | $2 / $10 | ~Q0.11 | ~Q170 |
| `anthropic/claude-haiku-4.5` | $1 / $5 | ~Q0.06 | ~Q85 |

Precios de OpenRouter a jun-2026; sumale la comisión de OpenRouter al recargar
saldo. Cambiar de modelo es una variable en el `.env`, así que se puede medir con
tráfico real antes de decidir.

**`temperature` no se manda.** Opus 5, Sonnet 5 y Fable 5 ya no lo aceptan.
`OPENROUTER_TEMPERATURA` queda vacía por defecto y solo se llena si bajás a un
modelo viejo (Sonnet 4.6, Haiku 4.5) que sí lo admite.

## Cómo está armado

```
agente/
├── main.py                 punto de entrada
├── settings.py             configuración por variables de entorno
├── backend/client.py       cliente HTTP: SOLO GET + whitelist de rutas
├── tools/                  herramientas que ve el modelo
│   ├── base.py             registro, contexto, control de roles
│   ├── contexto.py         fecha_hoy, quien_soy
│   ├── ventas.py           clientes, órdenes, cartera, precios, resúmenes
│   └── inventario.py       stock de terminado y agranel
├── agent/
│   ├── llm.py              cliente OpenRouter
│   ├── prompts.py          system prompt
│   ├── session.py          historial acotado por usuario
│   └── runtime.py          loop LLM ⇄ herramientas
└── channels/
    ├── consola.py          REPL (lo que se usa hoy)
    └── whatsapp.py         webhook Cloud API (pendiente)
```

La idea de fondo: **el modelo nunca toca la base ni arma URLs**. Solo puede
llamar funciones Python declaradas en `tools/`, y esas funciones solo pueden
hacer GET a rutas de la whitelist. Cambiar de consola a WhatsApp es cambiar el
archivo de `channels/`; el resto no se mueve.

## Tres capas de seguridad

1. **Verbo**: `CoprodaClient` no tiene `post`/`put`/`delete`. Escribir es
   imposible por construcción, no por convención en un prompt.
2. **Ruta**: la whitelist en `backend/client.py` tiene 9 rutas GET. Todo lo
   demás se rechaza aunque una herramienta lo pida.
3. **Rol**: cada herramienta declara qué roles la ven, y `tools.base.ejecutar`
   vuelve a verificar antes de correr.

Encima va el alcance por usuario: un vendedor solo ve los clientes con
`usuario_id` igual al suyo y las órdenes de esos clientes. `admin` ve todo.

## Herramientas

**Contexto**
- `fecha_hoy` — hoy, ayer, semana, mes, mes pasado. El modelo no sabe qué día es;
  sin esto inventa fechas.
- `quien_soy` — usuario, rol y alcance.

**Clientes y cartera**
- `buscar_cliente` — por nombre, código o id.
- `estado_cuenta_cliente` — saldo y órdenes pendientes de pago.

**Órdenes**
- `listar_ordenes` — filtra por fecha, cliente, estado, solo con saldo.
- `detalle_orden` — items, cantidades, precios, subtotales.
- `resumen_ventas` — totales por cliente, estado, producto o mes.

**Producto y existencias**
- `buscar_producto` — los tres precios (cf / minorista / mayorista) y disponible.
- `stock_productos` — bodega de terminado y agranel, con filtro de bajo mínimo.
- `alcanza_para_pedido` — ¿hay suficiente para vender N de X? Cuánto falta.

## Ejemplos de conversación

**Cartera de un cliente**
> **Vendedor:** cuánto me debe la tienda la esquina
> `buscar_cliente("la esquina")` → `estado_cuenta_cliente(1)`
> **Agente:** Tienda La Esquina (C001) debe Q350.00 en 1 orden:
> - C001-1 del 01/09/2026 — total Q500.00, saldo Q350.00

**Cliente ambiguo**
> **Vendedor:** el saldo de don julio
> `buscar_cliente("don julio")` → 2 resultados
> **Agente:** Tengo dos que coinciden:
> - C014 Abarrotería Don Julio
> - C031 Don Julio Mazatenango
> ¿Cuál de los dos?

**Ventas del mes**
> **Vendedor:** cuánto llevo vendido este mes
> `fecha_hoy()` → `resumen_ventas("2026-09-01","2026-09-08","cliente")`
> **Agente:** Del 01/09 al 08/09 llevás Q12,450.00 en 18 órdenes.
> Tus tres más fuertes: Abarrotería Gómez Q3,200.00, Tienda La Esquina Q2,780.00,
> Súper Chapín Q1,940.00.

**Cobranza**
> **Vendedor:** qué pedidos tengo pendientes de pago
> `listar_ordenes(solo_con_saldo=true)`
> **Agente:** Tenés 4 órdenes con saldo, Q6,820.00 en total:
> - C001-1 · Tienda La Esquina · Q350.00
> - C014-3 · Abarrotería Don Julio · Q2,100.00
> …

**Precio**
> **Vendedor:** a cómo está el jabón azul
> `buscar_producto("jabón azul")`
> **Agente:** Jabón azul 250g (T10, terminado):
> - CF Q12.00 · Minorista Q10.00 · Mayorista Q8.50
> Disponible: 80.

**Disponibilidad**
> **Vendedor:** me alcanza para 200 jabones azules de 250?
> `alcanza_para_pedido("Jabón azul 250g", 200)`
> **Agente:** No alcanza. Hay 80 disponibles, te faltarían 120.

**Bodega**
> **Vendedor:** qué se está agotando
> `stock_productos(solo_bajo_minimo=true)`
> **Agente:** 3 productos en o bajo el mínimo:
> - Jabón azul 250g — 40 disponibles (mínimo 50)
> - Detergente agranel — 90 (mínimo 100)
> …

**Detalle de una orden**
> **Vendedor:** qué traía el pedido C001-1
> `detalle_orden("C001-1")`
> **Agente:** C001-1 · Tienda La Esquina · 01/09/2026 · Pendiente
> - Jabón azul 250g — 50 × Q10.00 = Q500.00
> Total Q500.00, saldo Q350.00.

**Le piden escribir** (el agente no puede)
> **Vendedor:** anotale un abono de Q200 a la esquina
> **Agente:** No puedo registrar abonos, solo consultar. Eso se hace en el
> sistema. Si querés, te digo cómo quedó el saldo después de que lo ingresés.

**Fuera de alcance**
> **Vendedor:** cuánta sosa cáustica queda
> **Agente:** No manejo materia prima ni producción, solo ventas. Sí puedo
> decirte existencias de producto terminado y agranel.

**Datos de otro vendedor**
> **Vendedor:** el saldo de Abarrotería Gómez
> `buscar_cliente("gómez")` → 0 resultados (es cartera de otro)
> **Agente:** Ese cliente no aparece en tu cartera. Consultalo con la oficina.

## Agregar una herramienta

```python
@herramienta(
    nombre="ordenes_sin_enviar",
    descripcion="Órdenes pagadas que todavía no tienen fecha de envío.",
    parametros={"type": "object", "properties": {"limite": {"type": "integer"}}},
    roles=("vendedor", "admin"),
)
def ordenes_sin_enviar(ctx, limite=20):
    ordenes = _ordenes_visibles(ctx)
    ...
```

Tres reglas que importan más de lo que parecen:

- **La descripción es el contrato.** Es lo único que el modelo lee para decidir
  si la llama. Escríbela pensando en cómo pregunta un vendedor, no en cómo se
  llama la tabla.
- **Devuelve poco.** Los endpoints de Coproda mandan la tabla completa sin
  paginar. Filtra y agrega en Python; nunca pases un listado crudo al modelo.
- **Devuelve nombres, no ids.** `"estado": "Pendiente"` en vez de
  `"estado_id": 1`. El modelo no sabe qué es el estado 1 y se lo inventa.

## Pendientes antes de producción

- **La API no tiene autenticación.** `/auth/login` valida credenciales pero no
  emite token, y ningún endpoint exige uno. El agente autentica al usuario para
  saber su rol y alcance, pero cualquiera con acceso de red al backend puede
  leerlo o escribirlo directo. Antes de exponer esto fuera de la red interna
  hay que meter tokens en la API.
- **Mapeo teléfono → usuario** para WhatsApp, con verificación por código la
  primera vez. Autenticar solo por número de teléfono no alcanza para datos de
  cartera.
- **Rate limit por usuario** y log de auditoría (quién preguntó qué, qué
  herramientas corrieron, cuántos tokens costó).
