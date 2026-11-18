"""correo.py — envío de los correos de la app (crear cuenta, restablecer contraseña).

Se manda por la API HTTPS de Brevo (plan gratuito, ~300 al día). No por SMTP:
el plan gratuito de Render bloquea los puertos SMTP (25, 465 y 587) desde 2025.

Configuración (variables de entorno, en el panel de Render; nunca en el código):
    BREVO_API_KEY     la clave de la API de Brevo
    CORREO_REMITENTE  el correo verificado en Brevo como remitente
    CORREO_MODO       'memoria' solo para las pruebas: guarda los correos en
                      BANDEJA_PRUEBAS en vez de mandarlos.
                      'consola' solo en local: escribe el correo (con su
                      enlace) en la salida del servidor. Se niega si
                      COOKIE_SEGURA=1, que es producción: allí dejaría enlaces
                      válidos en los logs.

Sin clave (y sin modo memoria) el envío no está disponible y el registro se
desactiva con un aviso, en vez de fingir que mandó algo.
"""
# Copyright (C) 2026 Marco Antonio Garcia
#
# Este archivo es parte de este proyecto, software libre bajo la GNU Affero
# General Public License v3 o posterior. Se distribuye SIN NINGUNA GARANTÍA.
# Ver el archivo LICENSE para los términos completos.

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

URL_BREVO = "https://api.brevo.com/v3/smtp/email"
BANDEJA_PRUEBAS: list[dict] = []
_log = logging.getLogger("correo")


class CorreoNoDisponible(Exception):
    """No hay forma de mandar correos ahora (sin configurar o Brevo falló)."""


def _modo() -> str:
    return os.environ.get("CORREO_MODO", "").strip().lower()


def _en_produccion() -> bool:
    return os.environ.get("COOKIE_SEGURA", "") == "1"


def _consola_permitida() -> bool:
    return _modo() == "consola" and not _en_produccion()


def _memoria_permitida() -> bool:
    # en producción, "memoria" haría creer que el registro funciona sin mandar nada
    return _modo() == "memoria" and not _en_produccion()


def disponible() -> bool:
    if _memoria_permitida() or _consola_permitida():
        return True
    return bool(os.environ.get("BREVO_API_KEY", "").strip()
                and os.environ.get("CORREO_REMITENTE", "").strip())


def enviar(destino: str, asunto: str, texto: str, html: str, nombre_app: str) -> None:
    """Manda un correo. Lanza CorreoNoDisponible si no se pudo.

    El texto y el HTML los arma la app con plantillas fijas: lo único variable
    es el enlace, que ya viene con el token en formato seguro para URL.
    """
    if _memoria_permitida():
        BANDEJA_PRUEBAS.append({"to": destino, "subject": asunto, "text": texto, "html": html})
        return
    if _consola_permitida():
        print(f"\n--- CORREO (modo consola) para {destino}: {asunto}\n{texto}---", flush=True)
        return
    clave = os.environ.get("BREVO_API_KEY", "").strip()
    remitente = os.environ.get("CORREO_REMITENTE", "").strip()
    if not clave or not remitente:
        raise CorreoNoDisponible("el envío de correos no está configurado")
    cuerpo = json.dumps({
        "sender": {"name": nombre_app, "email": remitente},
        "to": [{"email": destino}],
        "subject": asunto,
        "textContent": texto,
        "htmlContent": html,
    }).encode("utf-8")
    peticion = urllib.request.Request(
        URL_BREVO, data=cuerpo, method="POST",
        headers={"api-key": clave, "content-type": "application/json",
                 "accept": "application/json"})
    try:
        with urllib.request.urlopen(peticion, timeout=15) as r:
            if r.status >= 300:
                raise CorreoNoDisponible(f"Brevo respondió {r.status}")
    except urllib.error.HTTPError as exc:
        # solo el código de Brevo (p. ej. 'unauthorized'), nunca su mensaje
        # entero: puede llevar la dirección del destinatario, que es un dato
        # personal y no debe acabar en los logs de Render
        codigo = ""
        try:
            codigo = str(json.loads(exc.read(2000) or b"{}").get("code", ""))[:40]
        except (ValueError, AttributeError, OSError):
            pass
        _log.error("Brevo rechazó el envío: HTTP %s %s", exc.code, codigo)
        raise CorreoNoDisponible(f"Brevo respondió {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        _log.error("No se pudo contactar con Brevo: %s", exc)
        raise CorreoNoDisponible("no se pudo contactar con el servicio de correo") from None
