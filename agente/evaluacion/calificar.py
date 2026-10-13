# -*- coding: utf-8 -*-
"""Califica respuestas.json contra la verdad de referencia de casos.json.

Es una primera pasada automatica: numeros por coincidencia de cifra, excepciones
por senales en el texto. Los casos marcados REVISAR conviene leerlos a mano.
"""
import os, re, json, argparse
from collections import defaultdict

SPD = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("--entrada", default="respuestas.json")
a = ap.parse_args()

res = json.load(open(os.path.join(SPD, a.entrada), encoding="utf8"))


def numeros(texto):
    # Q941,600.00 | 13,178 | 13178 | 151 -> floats
    return {float(m.replace(",", "")) for m in re.findall(r"\d[\d,]*(?:\.\d+)?", texto)}


def calificar(c):
    e, r = c["esperado"], c.get("respuesta") or ""
    if r.startswith("[error del modelo]") or r.startswith("[EXCEPCION]"):
        return "ERROR"
    if e["tipo"] in ("numero", "conteo"):
        return "OK" if any(abs(n - e["valor"]) < 0.01 for n in numeros(r)) else "REVISAR"
    bajo = r.lower()
    return "OK" if any(s in bajo for s in e["senales"]) else "REVISAR"


por_cat = defaultdict(lambda: [0, 0])
for c in res:
    v = calificar(c)
    por_cat[c["categoria"]][1] += 1
    por_cat[c["categoria"]][0] += v == "OK"
    print(f"[{c['n']:02d}] {v:7s} | {c['pregunta'][:55]:55s} | esperado: {c['nota']}")
    if v != "OK":
        print(f"        -> {c['respuesta'][:200].replace(chr(10), ' ')}")

print()
ok = sum(v[0] for v in por_cat.values()); tot = sum(v[1] for v in por_cat.values())
for cat, (o, t) in por_cat.items():
    print(f"  {o}/{t}  {cat}")
print(f"\n  {ok}/{tot} OK automaticos")
