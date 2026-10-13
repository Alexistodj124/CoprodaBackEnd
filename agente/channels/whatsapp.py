"""Canal WhatsApp Cloud API. FASE 2 - todavia no conectado.

Diseno previsto (mismo Agente, distinto canal):

    POST /webhook  (Meta -> nosotros)
      1. Verificar la firma X-Hub-Signature-256 con el APP_SECRET.
      2. Extraer telefono del remitente y el texto del mensaje.
      3. Mapear telefono -> usuario del sistema (tabla nueva `agente_contactos`:
         telefono, usuario_id, rol, activo). Si no esta mapeado, responder
         "no estas autorizado" y salir. NUNCA autenticar por numero solamente
         si el dato es sensible: pedir un codigo de un solo uso la primera vez.
      4. Cargar/crear la Sesion de ese usuario (Redis o tabla, con TTL ~30 min).
      5. respuesta = Agente(...).responder(texto)
      6. POST a graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages

Puntos a resolver antes de encender esto:
  - Rate limit por usuario (ej. 20 mensajes/hora) para no quemar creditos.
  - Ventana de 24h de WhatsApp: fuera de ella solo se pueden mandar plantillas.
  - Log de auditoria: quien pregunto que y que herramientas se ejecutaron.
"""

raise NotImplementedError("Canal WhatsApp pendiente. Por ahora usa channels/consola.py")
