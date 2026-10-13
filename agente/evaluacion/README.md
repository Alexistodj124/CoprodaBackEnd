# Evaluación del agente (OE3)

Arnés para llenar el Cuadro 5 del informe: 40 casos, 5 por cada una de las 8
categorías, construidos desde los datos vivos de producción con su verdad de
referencia calculada aparte.

## Correrlo

    cd agente
    source .venv/bin/activate          # ver README del agente
    python evaluacion/casos.py         # regenera los casos con los datos de hoy
    python evaluacion/correr.py        # los pasa por el agente (Opus 5)
    python evaluacion/calificar.py     # primera calificación automática

Para un tramo: `python evaluacion/correr.py --desde 1 --hasta 10`.
Guarda todo en `respuestas.json` después de cada caso, así que se puede cortar
y retomar.

`verif_tools.py` prueba las 10 herramientas sin gastar tokens del modelo. Útil
para confirmar que la API responde antes de lanzar la corrida completa.

## Qué se evalúa

Consultas normales (20): saldo y deuda de un cliente, pedidos y envíos
pendientes, existencia de un producto, precio según clasificación.

Casos de excepción (20): cliente o producto inexistente, consulta ambigua sin
cliente identificado, petición de una operación de escritura, consulta fuera
del alcance del agente.

La octava categoría sustituye al "mensaje desde un número no autorizado". Esa
autorización vive en el canal de WhatsApp, que todavía no existe, así que no se
puede probar desde consola. En su lugar se prueba una frontera que sí existe:
producción, materia prima, recetas y mermas están fuera del alcance declarado.

## Criterio

Los casos normales se juzgan comparando la cifra de la respuesta contra el
registro del sistema, leído en el mismo momento. Los de excepción se juzgan por
si el agente declara la falta de información o rechaza la petición, en lugar de
entregar un dato.

## Estado

Corre con `claude-opus-5` usando la suscripción de Claude (Claude Agent SDK,
`AGENTE_BACKEND=suscripcion`). Requiere `claude auth login` una vez. Cada caso
guarda en `respuestas.json` qué modelo contestó (`modelos`).
