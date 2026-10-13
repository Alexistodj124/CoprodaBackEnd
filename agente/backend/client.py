"""Cliente HTTP de solo lectura contra la API de Coproda.

Reglas duras (no se pueden saltar desde el LLM):
  1. Solo se expone el metodo GET. No hay POST/PUT/PATCH/DELETE en esta clase.
  2. La ruta debe hacer match con la whitelist RUTAS_PERMITIDAS.
  3. Respuestas cacheadas unos segundos, porque varios endpoints devuelven
     la tabla completa y el agente los consulta varias veces por turno.
"""
from __future__ import annotations

import re
import time
from typing import Any

import requests

from settings import settings


class BackendError(RuntimeError):
    pass


# Whitelist de rutas GET que el agente puede tocar. Cualquier otra se rechaza.
RUTAS_PERMITIDAS = [
    r"^/clientes$",
    r"^/clientes/\d+$",
    r"^/productos$",
    r"^/productos/\d+$",
    r"^/categorias_producto$",
    r"^/ordenes$",
    r"^/ordenes/\d+$",
    r"^/estados_orden$",
    r"^/tipos_pago$",
]

_PATRONES = [re.compile(p) for p in RUTAS_PERMITIDAS]


def ruta_permitida(path: str) -> bool:
    return any(p.match(path) for p in _PATRONES)


class CoprodaClient:
    def __init__(self, base_url: str | None = None, timeout: int | None = None):
        self.base_url = (base_url or settings.API_BASE_URL).rstrip("/")
        self.timeout = timeout or settings.TIMEOUT_API
        self._http = requests.Session()
        self._cache: dict[str, tuple[float, Any]] = {}

    # -- unico verbo expuesto --------------------------------------------
    def get(self, path: str, params: dict | None = None, cache: bool = True) -> Any:
        if not path.startswith("/"):
            path = "/" + path
        if not ruta_permitida(path):
            raise BackendError(f"Ruta no permitida para el agente: {path}")

        clave = f"{path}?{sorted((params or {}).items())}"
        ahora = time.time()
        if cache and clave in self._cache:
            ts, valor = self._cache[clave]
            if ahora - ts < settings.CACHE_TTL:
                return valor

        try:
            resp = self._http.get(
                self.base_url + path, params=params, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise BackendError(f"No se pudo contactar el backend: {exc}") from exc

        if resp.status_code == 404:
            raise BackendError("Recurso no encontrado")
        if resp.status_code >= 400:
            raise BackendError(f"Backend respondio {resp.status_code}: {resp.text[:200]}")

        datos = resp.json()
        if cache:
            self._cache[clave] = (ahora, datos)
        return datos

    # -- login: unico POST, aislado y fuera del alcance del LLM -----------
    def login(self, usuario: str, contrasena: str) -> dict:
        try:
            resp = self._http.post(
                self.base_url + "/auth/login",
                json={"usuario": usuario, "contrasena": contrasena},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise BackendError(f"No se pudo contactar el backend: {exc}") from exc
        if resp.status_code == 401:
            raise BackendError("Credenciales invalidas")
        if resp.status_code >= 400:
            raise BackendError(f"Login fallo ({resp.status_code}): {resp.text[:200]}")
        return resp.json()

    def limpiar_cache(self) -> None:
        self._cache.clear()
