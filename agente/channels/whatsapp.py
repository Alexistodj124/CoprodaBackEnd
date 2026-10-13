"""Canal WhatsApp Cloud API. Version de PRUEBAS LOCALES (ngrok + numero de prueba).

Mismo Agente que la consola, distinto canal:

    GET  /webhook  verificacion de Meta (hub.verify_token -> hub.challenge)
    POST /webhook  mensajes entrantes:
      1. Verifica X-Hub-Signature-256 con WA_APP_SECRET (si esta configurado).
      2. Responde 200 de inmediato; Meta reintenta si tardamos, y el agente
         puede tardar decenas de segundos. El trabajo va a una cola.
      3. Solo atiende numeros en WA_NUMEROS_PERMITIDOS.
      4. Una Sesion por telefono, todas con el usuario que inicio sesion en la
         CLI al arrancar.
      5. Responde por graph.facebook.com/{version}/{PHONE_NUMBER_ID}/messages.

Pendiente antes de produccion (ver README):
  - Mapeo telefono -> usuario con codigo de un solo uso, en vez de un solo
    usuario para todos los numeros permitidos.
  - Sesiones en Redis/tabla con TTL, rate limit por usuario, log de auditoria.
  - Ventana de 24h: fuera de ella solo se pueden mandar plantillas.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import queue
import re
import threading
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import requests

from agent import Sesion, crear_agente
from backend.client import CoprodaClient
from channels.consola import _login
from settings import settings
from tools.base import Contexto

LIMITE_WHATSAPP = 4096


def _numeros_permitidos() -> set[str]:
    return {re.sub(r"\D", "", n) for n in settings.WA_NUMEROS_PERMITIDOS.split(",") if n.strip()}


def _a_formato_whatsapp(texto: str) -> str:
    """WhatsApp usa *negrita* con un asterisco; el modelo escribe **negrita**."""
    texto = re.sub(r"\*\*(.+?)\*\*", r"*\1*", texto)
    return re.sub(r"^#{1,6}\s*(.+)$", r"*\1*", texto, flags=re.MULTILINE)


def _partir(texto: str, limite: int = LIMITE_WHATSAPP) -> list[str]:
    partes = []
    while len(texto) > limite:
        corte = texto.rfind("\n", 0, limite)
        if corte <= 0:
            corte = limite
        partes.append(texto[:corte])
        texto = texto[corte:].lstrip("\n")
    return partes + [texto] if texto else partes


class ClienteWhatsApp:
    def __init__(self):
        self.url = (f"https://graph.facebook.com/{settings.WA_GRAPH_VERSION}"
                    f"/{settings.WA_PHONE_NUMBER_ID}/messages")
        self._http = requests.Session()
        self._http.headers["Authorization"] = f"Bearer {settings.WA_TOKEN}"

    def _post(self, payload: dict) -> None:
        resp = self._http.post(self.url, json={"messaging_product": "whatsapp", **payload},
                               timeout=20)
        if resp.status_code >= 400:
            print(f"  ! Graph API {resp.status_code}: {resp.text[:300]}")

    def enviar_texto(self, telefono: str, texto: str) -> None:
        for parte in _partir(_a_formato_whatsapp(texto)):
            self._post({"to": telefono, "type": "text", "text": {"body": parte}})

    def marcar_leido(self, message_id: str) -> None:
        self._post({"status": "read", "message_id": message_id})


class CanalWhatsApp:
    def __init__(self, ctx: Contexto):
        self.ctx = ctx
        self.wa = ClienteWhatsApp()
        self.permitidos = _numeros_permitidos()
        self.agentes: dict[str, tuple[Sesion, object]] = {}
        self.cola: queue.Queue[tuple[str, str, str]] = queue.Queue()
        # Meta reintenta entregas; se descartan los message_id ya vistos.
        self._vistos: OrderedDict[str, None] = OrderedDict()
        self._lock = threading.Lock()

    def _ya_visto(self, message_id: str) -> bool:
        with self._lock:
            if message_id in self._vistos:
                return True
            self._vistos[message_id] = None
            if len(self._vistos) > 1000:
                self._vistos.popitem(last=False)
            return False

    def _agente_de(self, telefono: str):
        if telefono not in self.agentes:
            sesion = Sesion(usuario=self.ctx.usuario, usuario_id=self.ctx.usuario_id,
                            rol=self.ctx.rol)
            self.agentes[telefono] = (sesion, crear_agente(self.ctx, sesion, on_tool=self._traza))
        return self.agentes[telefono]

    @staticmethod
    def _traza(nombre, args, resultado):
        if settings.DEBUG:
            recorte = json.dumps(resultado, ensure_ascii=False, default=str)[:300]
            print(f"  · {nombre}({json.dumps(args, ensure_ascii=False)}) -> {recorte}")

    def recibir(self, payload: dict) -> None:
        """Encola los mensajes de texto del webhook; ignora statuses y otros tipos."""
        for entrada in payload.get("entry", []):
            for cambio in entrada.get("changes", []):
                valor = cambio.get("value", {})
                for msg in valor.get("messages", []):
                    telefono, message_id = msg.get("from", ""), msg.get("id", "")
                    if self._ya_visto(message_id):
                        continue
                    if telefono not in self.permitidos:
                        print(f"  ! {telefono} no esta en WA_NUMEROS_PERMITIDOS, ignorado")
                        continue
                    if msg.get("type") != "text":
                        self.wa.enviar_texto(telefono, "Por ahora solo entiendo mensajes de texto.")
                        continue
                    self.cola.put((telefono, message_id, msg["text"]["body"].strip()))

    def trabajar(self) -> None:
        """Un solo hilo: los turnos se procesan en orden y no se pisan las sesiones."""
        while True:
            telefono, message_id, texto = self.cola.get()
            try:
                self.wa.marcar_leido(message_id)
                print(f"\n{telefono} > {texto}")
                if texto.lower() in ("/nuevo", "nuevo"):
                    self.agentes.pop(telefono, None)
                    self.ctx.api.limpiar_cache()
                    respuesta = "Conversacion reiniciada."
                else:
                    _, agente = self._agente_de(telefono)
                    respuesta = agente.responder(texto)
                print(f"Agente > {respuesta}")
                self.wa.enviar_texto(telefono, respuesta)
            except Exception as exc:  # el hilo no puede morir por un mensaje
                print(f"  ! error procesando mensaje: {exc}")
                self.wa.enviar_texto(telefono, "Tuve un problema procesando tu mensaje. Intenta de nuevo.")


def _firma_valida(cuerpo: bytes, firma: str) -> bool:
    if not settings.WA_APP_SECRET:
        return True
    esperado = "sha256=" + hmac.new(settings.WA_APP_SECRET.encode(), cuerpo,
                                    hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, firma or "")


def _handler(canal: CanalWhatsApp):
    class Handler(BaseHTTPRequestHandler):
        def _responder(self, codigo: int, cuerpo: str = "") -> None:
            datos = cuerpo.encode()
            self.send_response(codigo)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)

        def do_GET(self):
            url = urlparse(self.path)
            if url.path != "/webhook":
                return self._responder(200, "ok")
            qs = {k: v[0] for k, v in parse_qs(url.query).items()}
            if (qs.get("hub.mode") == "subscribe"
                    and qs.get("hub.verify_token") == settings.WA_VERIFY_TOKEN):
                print("Webhook verificado por Meta.")
                return self._responder(200, qs.get("hub.challenge", ""))
            return self._responder(403, "verify token invalido")

        def do_POST(self):
            if urlparse(self.path).path != "/webhook":
                return self._responder(404)
            cuerpo = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if not _firma_valida(cuerpo, self.headers.get("X-Hub-Signature-256", "")):
                print("  ! firma invalida, request descartado")
                return self._responder(401)
            self._responder(200, "ok")
            try:
                canal.recibir(json.loads(cuerpo or b"{}"))
            except Exception as exc:
                print(f"  ! payload no procesable: {exc}")

        def log_message(self, *args):  # silencia el log por request de http.server
            pass

    return Handler


def ejecutar_servidor() -> None:
    faltan = [n for n in ("WA_PHONE_NUMBER_ID", "WA_TOKEN", "WA_VERIFY_TOKEN",
                          "WA_NUMEROS_PERMITIDOS") if not getattr(settings, n)]
    if faltan:
        raise SystemExit(f"Faltan en el .env: {', '.join(faltan)}")
    if not settings.WA_APP_SECRET:
        print("Aviso: sin WA_APP_SECRET no se verifica la firma de Meta. Solo para pruebas.")

    api = CoprodaClient()
    ctx = _login(api)
    canal = CanalWhatsApp(ctx)
    threading.Thread(target=canal.trabajar, daemon=True).start()

    servidor = ThreadingHTTPServer(("0.0.0.0", settings.WA_PORT), _handler(canal))
    print(f"Webhook escuchando en http://localhost:{settings.WA_PORT}/webhook")
    print(f"Numeros permitidos: {', '.join(sorted(canal.permitidos))}")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nHasta luego.")
