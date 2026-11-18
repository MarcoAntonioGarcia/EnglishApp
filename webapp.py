"""
webapp.py — App web LOCAL del Lector de Idiomas (FastAPI).

Corre en tu máquina, se abre en el navegador (http://localhost:8080). Reutiliza toda
la lógica de core.py. La voz de lectura la pone el navegador (Web Speech API, gratis);
el servidor solo genera audio para el export a Anki.

Ejecutar:
    export GEMINI_API_KEY="tu_api_key"      # opcional (sin ella, IA en modo simulado)
    python webapp.py
    # luego abre http://localhost:8080
"""

# Copyright (C) 2026 Marco Antonio Garcia
#
# Este archivo es parte de este proyecto, software libre bajo la GNU Affero
# General Public License v3 o posterior. Se distribuye SIN NINGUNA GARANTÍA.
# Ver el archivo LICENSE para los términos completos.

from __future__ import annotations

import glob
import html as html_mod
import logging
import hashlib
import hmac
import ipaddress
import os
import re
import secrets
import tempfile
import threading
import time
from collections import OrderedDict

import uvicorn
from fastapi import (Body, Depends, FastAPI, File, HTTPException, Request,
                     Response, UploadFile)
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

import catalog
import core
import correo

# La documentación automática de FastAPI (/docs, /openapi.json) lista todos los
# endpoints, los del admin incluidos. En producción no se sirve; en local se
# activa con DOCS=1.
_DOCS = os.environ.get("DOCS", "") == "1"
app = FastAPI(title="Daily English Habit",
              docs_url="/docs" if _DOCS else None,
              redoc_url=None,
              openapi_url="/openapi.json" if _DOCS else None)
db = core.DatabaseManager()
core.ensure_sample_wav()

STATIC_DIR = os.path.join(core.BASE_DIR, "static")
os.makedirs(core.LIBRARY_DIR, exist_ok=True)


# --------------------------------------------------------------------------- #
# Frontend
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Sesión: quién está usando la app
# --------------------------------------------------------------------------- #
COOKIE = "sesion"
DIAS_DE_SESION = 30

# En producción la cookie tiene que ir SOLO por HTTPS. En local se sirve por
# HTTP plano, así que el valor se toma del entorno y hay que activarlo al
# desplegar: COOKIE_SEGURA=1
COOKIE_SEGURA = os.environ.get("COOKIE_SEGURA", "") == "1"

# Intentos de login fallidos por IP. En memoria a propósito: para 5-20 usuarios
# no merece una tabla, y reiniciar el proceso no es un agujero porque quien
# controla el proceso ya ha ganado.
# (accion, tope, ventana en segundos)
#   login: 10 fallos por cuarto de hora, contra la fuerza bruta.
#   registro: 5 altas por hora. El registro esta abierto a proposito, pero sin
#   tope un bot llena la tabla de usuarios y el panel de aprobaciones de basura.
#   login_cuenta: 20 fallos por cuarto de hora contra UNA cuenta, vengan de la
#   IP que vengan. Es el tope que de verdad frena la fuerza bruta: el de IP se
#   esquiva cambiando de IP; este no.
#   login_dispositivo: el mismo tope, aparte, para quien entra desde un aparato
#   donde ya entró bien antes (cookie 'dispositivo'). Así un desconocido que
#   machaca tu cuenta no te deja fuera a ti: tus intentos no cuentan con los suyos.
#   alta / olvido: 5 peticiones de correo por hora y por IP (cada una gasta un
#   envío del cupo gratuito de Brevo).
#   enlace: 30 usos de enlaces por cuarto de hora y por IP.
TOPES = {"login": (10, 15 * 60), "login_cuenta": (20, 15 * 60),
         "login_dispositivo": (20, 15 * 60), "alta": (5, 60 * 60),
         "olvido": (5, 60 * 60), "enlace": (30, 15 * 60)}
# Claves vigiladas, de la más vieja a la más nueva. Con tope: sin él, un bot que
# prueba nombres inventados haría crecer el diccionario hasta agotar la memoria.
_intentos: "OrderedDict[tuple[str, str], list[float]]" = OrderedDict()
_MAX_CLAVES_INTENTOS = 20000
# Los endpoints sync corren en varios hilos a la vez: sin candado, una ráfaga
# simultánea pasaría la comprobación antes de que se anotara ningún fallo.
_candado_intentos = threading.Lock()

# De qué cabecera sale la IP del cliente. Detrás del proxy de Render,
# client.host es la IP del PROXY, la misma para todos: un tope por IP sería
# entonces un tope para todo el mundo (10 fallos de un desconocido dejarían
# fuera a todos). Render va detrás de Cloudflare, que pone True-Client-IP con la
# IP real y la sobrescribe si el cliente la manda. X-Forwarded-For NO sirve: el
# proxy de Render la deja pasar tal cual llega y cualquiera puede inventarla.
# En local va vacía y se usa client.host.
IP_DE_CABECERA = os.environ.get("IP_DE_CABECERA", "").strip().lower()


def _agrupar_ip(valor: str) -> str | None:
    """La IP como clave del tope. Una IPv6 se agrupa por su /64: cada conexión
    doméstica recibe millones de direcciones y, si no, cada una contaría aparte."""
    try:
        ip = ipaddress.ip_address(valor.strip())
    except ValueError:
        return None
    if ip.version == 6:
        if ip.ipv4_mapped:
            return str(ip.ipv4_mapped)
        return str(ipaddress.ip_network(f"{ip}/64", strict=False))
    return str(ip)


def _ip(peticion: Request) -> str:
    if IP_DE_CABECERA:
        agrupada = _agrupar_ip(peticion.headers.get(IP_DE_CABECERA) or "")
        if agrupada:
            return agrupada
    socket = peticion.client.host if peticion.client else ""
    return _agrupar_ip(socket) or socket or "?"


def _clave_intento(accion: str, quien: str) -> tuple[str, str]:
    # se guarda un hash: el login tecleado puede ser largo y no hace falta tenerlo
    return accion, hashlib.sha256(quien.encode("utf-8")).hexdigest()[:32]


def _reservar_intento(accion: str, quien: str) -> float | None:
    """Comprueba el tope y apunta el intento en un solo paso, bajo el candado.
    Devuelve la marca apuntada, o None si ya no quedan intentos. Hacerlo en dos
    pasos dejaba que una ráfaga simultánea pasara entera la comprobación."""
    tope, ventana = TOPES[accion]
    clave = _clave_intento(accion, quien)
    ahora = time.time()
    with _candado_intentos:
        recientes = [t for t in _intentos.get(clave, []) if ahora - t < ventana]
        if len(recientes) >= tope:
            _intentos[clave] = recientes
            return None
        recientes.append(ahora)
        _intentos[clave] = recientes
        _intentos.move_to_end(clave)
        while len(_intentos) > _MAX_CLAVES_INTENTOS:
            _intentos.popitem(last=False)
        return ahora


def _devolver_intento(accion: str, quien: str, marca: float) -> None:
    """Quita SOLO la marca de este intento (el que salió bien), no las demás."""
    clave = _clave_intento(accion, quien)
    with _candado_intentos:
        lista = _intentos.get(clave)
        if lista and marca in lista:
            lista.remove(marca)


def _olvidar_intentos(accion: str, quien: str) -> None:
    with _candado_intentos:
        _intentos.pop(_clave_intento(accion, quien), None)


# Cookie de "dispositivo conocido" (patrón de OWASP contra el bloqueo de
# cuentas). Va firmada con un secreto del servidor: no se puede fabricar.
# En Render, SECRETO_APP lo genera el propio Render (render.yaml). Sin él, se
# inventa uno al arrancar y las cookies valen hasta el siguiente reinicio.
COOKIE_DISPOSITIVO = "dispositivo"
DIAS_DISPOSITIVO = 180
_SECRETO = (os.environ.get("SECRETO_APP") or "").encode("utf-8") or secrets.token_bytes(32)


def _firma_dispositivo(uid: int, emitida: int) -> str:
    return hmac.new(_SECRETO, f"dispositivo:{uid}:{emitida}".encode(), hashlib.sha256).hexdigest()


def _cookie_dispositivo(uid: int) -> str:
    emitida = int(time.time())
    return f"{uid}.{emitida}.{_firma_dispositivo(uid, emitida)}"


def _dispositivo_conocido(valor: str, uid: int) -> bool:
    try:
        cuenta, emitida, firma = valor.split(".")
        cuenta, emitida = int(cuenta), int(emitida)
    except (ValueError, AttributeError):
        return False
    if cuenta != uid or time.time() - emitida > DIAS_DISPOSITIVO * 86400:
        return False
    return hmac.compare_digest(firma, _firma_dispositivo(uid, emitida))


# --------------------------------------------------------------------------- #
# Límites de tamaño y cabeceras de seguridad
# --------------------------------------------------------------------------- #
# Sin tope, una subida de 1 GB se carga entera en la memoria (512 MB en el plan
# gratuito) y tumba la app para todos. Cada ruta tiene el suyo; el resto, 1 MB,
# que sobra para cualquier JSON de la app.
LIMITE_CUERPO = 1 * 1024 * 1024
# (tope, quién puede usarlo). Se decide con la sesión ANTES de leer el cuerpo:
# FastAPI lee el formulario entero antes de comprobar quién llama, así que sin
# esto cualquiera sin cuenta podría hacer subir 60 MB al servidor para nada.
LIMITES_POR_RUTA = {
    "/api/upload": (60 * 1024 * 1024, "admin"),           # libros
    "/api/writing/extract": (10 * 1024 * 1024, "user"),   # foto o documento de una redacción
}


def _limite_de(scope) -> int:
    tope, quien = LIMITES_POR_RUTA.get(scope.get("path", ""), (LIMITE_CUERPO, "user"))
    usuario = (scope.get("state") or {}).get("usuario") or {}
    if not usuario or (quien == "admin" and usuario.get("role") != "admin"):
        return LIMITE_CUERPO
    return tope
MAX_TEXTO_IA = 3000          # una palabra, una frase o una selección del libro
MAX_REDACCION = 10000        # una redacción para «Check my writing»
MAX_ITEMS_ANKI = 2000

# Política de contenido: la página solo carga lo suyo, no se puede meter en un
# iframe ajeno (clickjacking) y no habla con otros dominios. 'unsafe-inline' se
# queda mientras el JavaScript y el CSS vivan dentro del HTML.
CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; "
       "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
       "media-src 'self' blob: data:; connect-src 'self'; font-src 'self' data:; "
       "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


class _CuerpoDemasiadoGrande(Exception):
    pass


class SeguridadMiddleware:
    """Corta los cuerpos demasiado grandes y añade las cabeceras de seguridad.

    El tope se mira dos veces: por Content-Length (rechazo inmediato, sin leer
    nada) y contando lo que llega, porque una subida 'chunked' no lo declara.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limite = _limite_de(scope)
        empezada = False
        excedido = False        # el cuerpo pasó del tope mientras se leía
        tapada = False          # ya se mandó el 413 en lugar de la respuesta

        async def enviar(mensaje):
            nonlocal empezada, tapada
            # FastAPI convierte cualquier fallo al leer el cuerpo en un 400
            # genérico. Si fue por el tope, se responde 413 con un mensaje claro.
            if excedido and not empezada and mensaje["type"] == "http.response.start":
                tapada = True
                await rechazar()
                return
            if tapada:
                return
            if mensaje["type"] == "http.response.start":
                empezada = True
                cabeceras = list(mensaje.get("headers", []))
                extra = [
                    (b"content-security-policy", CSP.encode()),
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"same-origin"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                ]
                if COOKIE_SEGURA:
                    extra.append((b"strict-transport-security",
                                  b"max-age=31536000; includeSubDomains"))
                mensaje = {**mensaje, "headers": cabeceras + extra}
            await send(mensaje)

        async def rechazar():
            nonlocal empezada
            empezada = True
            cuerpo = '{"detail":"El archivo o el texto es demasiado grande."}'.encode()
            await send({"type": "http.response.start", "status": 413,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"content-length", str(len(cuerpo)).encode()),
                                    (b"content-security-policy", CSP.encode()),
                                    (b"x-content-type-options", b"nosniff"),
                                    (b"x-frame-options", b"DENY")]})
            await send({"type": "http.response.body", "body": cuerpo})

        for nombre, valor in scope.get("headers", []):
            if nombre == b"content-length":
                try:
                    if int(valor) > limite:
                        return await rechazar()
                except ValueError:
                    return await rechazar()

        recibido = 0

        async def recibir():
            nonlocal recibido, excedido
            mensaje = await receive()
            if mensaje["type"] == "http.request":
                recibido += len(mensaje.get("body", b""))
                if recibido > limite:
                    excedido = True
                    raise _CuerpoDemasiadoGrande()
            return mensaje

        try:
            await self.app(scope, recibir, enviar)
        except _CuerpoDemasiadoGrande:
            if not empezada:
                await rechazar()


class SesionMiddleware:
    """Resuelve la sesión UNA vez por petición, antes de nada.

    Tiene que ser middleware ASGI puro y no BaseHTTPMiddleware ni una
    dependencia: FastAPI ejecuta dependencias y endpoints sync en hilos del
    pool, cada uno con su COPIA del contexto, así que una variable de contexto
    fijada en una dependencia no llega al endpoint. Se comprobó midiéndolo: la
    key del usuario no llegaba y core caía en la del fichero local, con lo que
    todos habrían gastado la cuota del admin.

    Aquí sí funciona porque este código corre en la misma tarea que envuelve al
    endpoint, y el hilo del pool hereda una copia de ESTE contexto.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        usuario = db.user_for_token(Request(scope).cookies.get(COOKIE, ""))
        scope.setdefault("state", {})["usuario"] = usuario
        # la IA de esta petición usa la key de ESTE usuario. Si no tiene, cadena
        # vacía: que no herede la de nadie.
        token = core.usar_api_key((usuario or {}).get("gemini_api_key") or "")
        try:
            await self.app(scope, receive, send)
        finally:
            core.soltar_api_key(token)


# La última que se añade es la más externa. La sesión va por fuera para que los
# topes de tamaño sepan quién llama antes de leer nada del cuerpo.
app.add_middleware(SeguridadMiddleware)
app.add_middleware(SesionMiddleware)


def usuario_de_la_peticion(peticion: Request) -> dict | None:
    """La fila del usuario logueado, o None. No lanza: sirve para decidir qué
    página servir. La consulta ya la hizo el middleware."""
    return peticion.scope.get("state", {}).get("usuario")


def current_user(peticion: Request) -> int:
    """El id de quien hace la petición. 401 si no hay sesión válida.

    Es de donde sale el user_id de los 46 endpoints: cambiar esta función es lo
    único que hizo falta para que la app pasara de un usuario a muchos.
    """
    u = usuario_de_la_peticion(peticion)
    if not u:
        raise HTTPException(401, "Please sign in.")
    return u["id"]


def current_admin(peticion: Request) -> int:
    """Como current_user, pero además exige ser admin. 404 si no lo es: no hay
    por qué confirmarle a nadie que el panel existe."""
    u = usuario_de_la_peticion(peticion)
    if not u:
        raise HTTPException(401, "Please sign in.")
    if u.get("role") != "admin":
        raise HTTPException(404, "No encontrado")
    return u["id"]


def _poner_cookie(respuesta: Response, token: str) -> None:
    respuesta.set_cookie(
        COOKIE, token,
        max_age=DIAS_DE_SESION * 24 * 3600,
        httponly=True,        # que el JavaScript de la página no pueda leerla
        samesite="lax",       # no viaja en peticiones cross-site: frena el CSRF
        secure=COOKIE_SEGURA,
        path="/",
    )


# --------------------------------------------------------------------------- #
# Alta, entrada y salida
# --------------------------------------------------------------------------- #
# Registro público con correo verificado. El admin puede seguir creando cuentas
# a mano en /admin (POST /api/admin/users).
#
# El orden importa: primero se pide SOLO el correo y se manda un enlace; el
# usuario y la contraseña se eligen DESPUÉS, al abrir ese enlace. Si se pidiera
# la contraseña antes, alguien podría dar de alta el correo de otra persona con
# una contraseña suya y esperar a que la víctima pulse "confirmar"
# (pre-secuestro de cuentas). Así, la contraseña la pone quien lee ese buzón.
#
# El token va en el FRAGMENTO del enlace (#t=...), que el navegador no manda al
# servidor: no queda en los logs de Render ni en ningún proxy.
APP_NOMBRE = os.environ.get("APP_NOMBRE", "Daily English Habit").strip() or "Daily English Habit"
# La dirección pública de la app, para los enlaces de los correos. Se fija en la
# configuración, NUNCA se saca de la cabecera Host de la petición: si no,
# cualquiera podría pedir un enlace de restablecer para tu correo con un Host
# suyo, y el enlace que recibirías llevaría tu token a su servidor.
APP_URL = os.environ.get("APP_URL", "").strip().rstrip("/")
MINUTOS_ENLACE_ALTA = 60
MINUTOS_ENLACE_CLAVE = 30
MAX_CORREOS_HORA_POR_CORREO = 3
MAX_CORREOS_DIA_POR_CORREO = 5      # nadie recibe más de 5 al día sin pedirlos
# Por debajo de los ~300 diarios del plan gratuito de Brevo. Las altas tienen
# su propio cupo, más bajo: un bot que pide altas de correos inventados no
# puede gastar los envíos que necesitan las cuentas que ya existen para
# restablecer su contraseña.
MAX_CORREOS_DIA = int(os.environ.get("MAX_CORREOS_DIA", "250"))
MAX_ALTAS_DIA = int(os.environ.get("MAX_ALTAS_DIA", "150"))
RESPUESTA_GENERICA = ("If that address can receive email, we've sent you a link. "
                      "Check your inbox (and the spam folder).")


def _registro_disponible() -> bool:
    return bool(APP_URL) and correo.disponible()


def _plantilla(titulo: str, parrafo: str, boton: str, enlace: str, pie: str) -> tuple[str, str]:
    texto = f"{titulo}\n\n{parrafo}\n\n{boton}: {enlace}\n\n{pie}\n"
    html = (
        '<div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:480px;'
        'margin:0 auto;padding:24px;color:#111">'
        f'<h2 style="margin:0 0 12px">{titulo}</h2>'
        f'<p style="line-height:1.5">{parrafo}</p>'
        f'<p style="margin:24px 0"><a href="{enlace}" style="background:#0e7c86;color:#fff;'
        f'padding:12px 18px;border-radius:8px;text-decoration:none;font-weight:600">{boton}</a></p>'
        f'<p style="color:#555;font-size:13px;line-height:1.5">{pie}</p></div>')
    return texto, html


def _mandar_enlace(email: str, proposito: str, ya_tiene_cuenta: bool = False,
                   usuario: str = "") -> None:
    """Crea el token y manda el correo. 503 si hoy ya no se puede enviar más o
    si Brevo falla; nada (en silencio) si ese correo ya recibió 3 en la hora,
    porque la respuesta a quien lo pide es la misma en todos los casos."""
    if (db.contar_correos(86400) >= MAX_CORREOS_DIA
            or (proposito == "signup" and db.contar_correos(86400, proposito="signup") >= MAX_ALTAS_DIA)):
        raise HTTPException(503, "We can't send more emails today. Please try again tomorrow.")
    if (db.contar_correos(3600, email) >= MAX_CORREOS_HORA_POR_CORREO
            or db.contar_correos(86400, email) >= MAX_CORREOS_DIA_POR_CORREO):
        return
    nota_usuario = (f"Your username is {html_mod.escape(usuario)}." if usuario else "")
    if proposito == "signup":
        token = db.crear_token_correo(email, "signup", MINUTOS_ENLACE_ALTA)
        enlace = f"{APP_URL}/create-account#t={token}"
        asunto = f"Confirm your email for {APP_NOMBRE}"
        texto, html = _plantilla(
            "Confirm your email", f"Open this link to choose your username and password for "
            f"{APP_NOMBRE}. It works once and expires in {MINUTOS_ENLACE_ALTA} minutes.",
            "Create my account", enlace,
            "If you didn't ask for this, ignore this email: nothing will be created.")
    else:
        token = db.crear_token_correo(email, "reset", MINUTOS_ENLACE_CLAVE)
        enlace = f"{APP_URL}/reset-password#t={token}"
        if ya_tiene_cuenta:
            asunto = f"You already have an account on {APP_NOMBRE}"
            texto, html = _plantilla(
                "You already have an account",
                "Someone (hopefully you) tried to sign up with this email, but it already has an "
                f"account. {nota_usuario} If you forgot your password, you can set a new one. "
                f"The link expires in {MINUTOS_ENLACE_CLAVE} minutes.",
                "Set a new password", enlace,
                "If it wasn't you, ignore this email: your account is unchanged.")
        else:
            asunto = f"Reset your {APP_NOMBRE} password"
            texto, html = _plantilla(
                "Reset your password",
                f"{nota_usuario} Open this link to choose a new password. It works once and expires in "
                f"{MINUTOS_ENLACE_CLAVE} minutes. Signing in with the new password will close your "
                "other sessions.",
                "Set a new password", enlace,
                "If you didn't ask for this, ignore this email: your password stays the same.")
    try:
        correo.enviar(email, asunto, texto, html, APP_NOMBRE)
    except correo.CorreoNoDisponible:
        raise HTTPException(503, "We couldn't send the email right now. "
                                 "Please try again in a few minutes.")


def _email_de(payload: dict) -> str:
    email = str(payload.get("email") or "").strip().lower()
    if not core.email_valido(email):
        raise HTTPException(400, "That doesn't look like a valid email address.")
    return email


def _entrar(respuesta: Response, uid: int) -> None:
    _poner_cookie(respuesta, db.create_session(uid, DIAS_DE_SESION))
    respuesta.set_cookie(COOKIE_DISPOSITIVO, _cookie_dispositivo(uid),
                         max_age=DIAS_DISPOSITIVO * 86400, httponly=True,
                         samesite="lax", secure=COOKIE_SEGURA, path="/api/auth/login")


@app.post("/api/auth/register")
def registrarse(peticion: Request, payload: dict = Body(...)) -> dict:
    """Paso 1: solo el correo. La respuesta es la misma tenga cuenta o no."""
    if not _registro_disponible():
        raise HTTPException(503, "Sign-up isn't available right now.")
    if _reservar_intento("alta", _ip(peticion)) is None:
        raise HTTPException(429, "Too many requests. Please try again later.")
    email = _email_de(payload)
    db.purgar_tokens_correo()
    existente = db.find_user_by_email(email)
    if existente is None:
        _mandar_enlace(email, "signup")
    elif existente.get("status") == "active":
        # mismo coste que un alta nueva (un correo), así el tiempo de respuesta
        # tampoco delata qué correos tienen cuenta
        _mandar_enlace(email, "reset", ya_tiene_cuenta=True, usuario=existente.get("username") or "")
    return {"ok": True, "message": RESPUESTA_GENERICA}


@app.post("/api/auth/link")
def ver_enlace(peticion: Request, payload: dict = Body(...)) -> dict:
    """¿Sigue valiendo este enlace? Para avisar antes de rellenar el formulario.
    No lo gasta."""
    if _reservar_intento("enlace", _ip(peticion)) is None:
        raise HTTPException(429, "Too many requests. Please try again later.")
    proposito = payload.get("purpose")
    if proposito not in ("signup", "reset"):
        raise HTTPException(400, "Invalid link.")
    email = db.ver_token_correo(str(payload.get("token") or ""), proposito)
    usuario = ""
    if email and proposito == "reset":     # quien tiene el enlace es el dueño del buzón
        usuario = (db.find_user_by_email(email) or {}).get("username") or ""
    return {"valid": bool(email), "email": email or "", "username": usuario}


@app.post("/api/auth/register/complete")
def completar_alta(peticion: Request, respuesta: Response, payload: dict = Body(...)) -> dict:
    """Paso 2: con el enlace del correo, elige usuario y contraseña. Entra directo."""
    if _reservar_intento("enlace", _ip(peticion)) is None:
        raise HTTPException(429, "Too many requests. Please try again later.")
    token = str(payload.get("token") or "")
    email = db.ver_token_correo(token, "signup")
    if not email:
        raise HTTPException(400, "This link has expired or was already used. "
                                 "Request a new one from the sign-up page.")
    if db.find_user_by_email(email):
        raise HTTPException(400, "There's already an account with this email. "
                                 "Sign in, or reset your password.")
    try:
        uid = db.create_user(
            username=str(payload.get("username") or ""),
            password=str(payload.get("password") or ""),
            email=email, role="user", status="active",
            nombre=str(payload.get("nombre") or ""))
    except ValueError as e:
        raise HTTPException(400, str(e))
    # create_user ya impide dos cuentas con el mismo correo; gastar el enlace
    # (y anular los demás de alta de ese correo) cierra la puerta a reusarlo
    db.gastar_token_correo(token, "signup")
    db.anular_tokens_correo(email, "signup")
    _entrar(respuesta, uid)
    return {"ok": True, "necesita_key": True}


def _mandar_en_segundo_plano(email: str, usuario: str) -> None:
    try:
        _mandar_enlace(email, "reset", usuario=usuario)
    except HTTPException as exc:
        logging.getLogger("correo").error("No se mandó el enlace de restablecer: %s", exc.detail)


@app.post("/api/auth/password/forgot")
def olvide_mi_clave(peticion: Request, payload: dict = Body(...)) -> dict:
    """Manda el enlace de restablecer si hay una cuenta activa con ese correo.

    El envío va en segundo plano y la respuesta es siempre la misma: si se
    esperara a Brevo solo cuando la cuenta existe, el tiempo de respuesta
    diría qué correos están dados de alta.
    """
    if not _registro_disponible():
        raise HTTPException(503, "Password reset isn't available right now.")
    if _reservar_intento("olvido", _ip(peticion)) is None:
        raise HTTPException(429, "Too many requests. Please try again later.")
    email = _email_de(payload)
    db.purgar_tokens_correo()
    fila = db.find_user_by_email(email)
    if fila and fila.get("status") == "active":
        threading.Thread(target=_mandar_en_segundo_plano,
                         args=(email, fila.get("username") or ""), daemon=True).start()
    return {"ok": True, "message": RESPUESTA_GENERICA}


@app.post("/api/auth/password/reset")
def restablecer_clave(peticion: Request, respuesta: Response, payload: dict = Body(...)) -> dict:
    """Con el enlace del correo, pone una contraseña nueva. Cierra todas las
    sesiones abiertas de esa cuenta y abre una nueva aquí."""
    if _reservar_intento("enlace", _ip(peticion)) is None:
        raise HTTPException(429, "Too many requests. Please try again later.")
    token = str(payload.get("token") or "")
    clave = str(payload.get("password") or "")
    caducado = "This link has expired or was already used. Request a new one."
    email = db.ver_token_correo(token, "reset")
    fila = db.find_user_by_email(email) if email else None
    if not fila or fila.get("status") != "active":
        raise HTTPException(400, caducado)
    problema = core.problema_con_la_clave(clave)
    if problema:
        raise HTTPException(400, problema)
    if not db.gastar_token_correo(token, "reset"):
        raise HTTPException(400, caducado)
    db.set_password(fila["id"], clave)          # cierra todas sus sesiones
    db.anular_tokens_correo(email, "reset")
    _olvidar_intentos("login_cuenta", f"id:{fila['id']}")
    _entrar(respuesta, fila["id"])
    return {"ok": True}


@app.post("/api/auth/login")
def login(peticion: Request, respuesta: Response, payload: dict = Body(...)) -> dict:
    ip = _ip(peticion)
    login_pedido = str(payload.get("login") or "").strip()[:200]
    marca_ip = _reservar_intento("login", ip)
    if marca_ip is None:
        raise HTTPException(429, "Too many attempts. Please try again later.")
    fila = db.find_user(login_pedido)
    # La cuenta se identifica por su id: entrar alternando usuario y correo no
    # debe duplicar los intentos permitidos. Desde un aparato donde ya entraste
    # bien, tus intentos van aparte y no los agota quien ataque tu cuenta.
    dispositivo = peticion.cookies.get(COOKIE_DISPOSITIVO, "")
    if fila and _dispositivo_conocido(dispositivo, fila["id"]):
        accion, quien = "login_dispositivo", dispositivo
    else:
        accion = "login_cuenta"
        quien = f"id:{fila['id']}" if fila else "login:" + login_pedido.lower()
    if _reservar_intento(accion, quien) is None:
        raise HTTPException(429, "Too many attempts. Please try again later.")

    clave = str(payload.get("password") or "")
    if len(clave) > core.LONGITUD_MAXIMA_CLAVE:
        clave = ""        # ninguna cuenta puede tenerla: se trata como incorrecta
    # se comprueba la contraseña AUNQUE el usuario no exista, contra un hash de
    # mentira: si no, el tiempo de respuesta delataría qué correos están dados
    # de alta.
    guardado = (fila or {}).get("password_hash") or "scrypt$16384$8$1$00$00"
    correcta = core.verify_password(clave, guardado)

    if not fila or not correcta:
        raise HTTPException(401, "Wrong username, email or password.")
    if fila["status"] == "pending":
        raise HTTPException(403, "Your account is still waiting for approval.")
    if fila["status"] == "blocked":
        raise HTTPException(403, "Your account is blocked.")

    # Entró bien: no cuenta este intento de la IP, pero sí los fallos de antes.
    # Si se borraran, quien tenga una cuenta podría probar 9 claves ajenas,
    # entrar con la suya para limpiar el contador, y repetir sin fin.
    _devolver_intento("login", ip, marca_ip)
    _olvidar_intentos(accion, quien)
    _entrar(respuesta, fila["id"])
    db.purge_expired_sessions()
    return {"ok": True, "role": fila["role"],
            "necesita_key": not (fila.get("gemini_api_key") or "")}


@app.post("/api/auth/logout")
def logout(peticion: Request, respuesta: Response) -> dict:
    db.delete_session(peticion.cookies.get(COOKIE, ""))
    respuesta.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def quien_soy(uid: int = Depends(current_user)) -> dict:
    ficha = db.get_user(uid) or {}
    ficha["pasos_para_la_key"] = core.COMO_SACAR_LA_KEY
    return ficha


@app.post("/api/auth/password")
def cambiar_mi_clave(peticion: Request, respuesta: Response,
                     payload: dict = Body(...),
                     uid: int = Depends(current_user)) -> dict:
    """Cambio de contraseña por el propio usuario.

    Pide la actual: con la cookie de alguien bastaría si no, y una sesión robada
    no debería poder dejarte fuera de tu propia cuenta.

    set_password cierra TODAS las sesiones, incluida la de quien la cambia, así
    que se le abre una nueva al momento para que no lo echemos de la app por
    hacer lo correcto.
    """
    fila = db.find_user((db.get_user(uid) or {}).get("username") or "")
    if not fila or not core.verify_password(payload.get("current") or "",
                                           fila["password_hash"] or ""):
        raise HTTPException(403, "La contraseña actual no es correcta.")
    try:
        db.set_password(uid, payload.get("new") or "")
    except ValueError as e:
        raise HTTPException(400, str(e))
    _poner_cookie(respuesta, db.create_session(uid, DIAS_DE_SESION))
    return {"ok": True, "mensaje": "Contraseña cambiada. Se han cerrado las "
                                   "demás sesiones que tuvieras abiertas."}


@app.post("/api/auth/gemini-key")
def guardar_mi_key(payload: dict = Body(...), uid: int = Depends(current_user)) -> dict:
    """Cada usuario guarda SU propia key: la cuota del free tier va por cuenta.

    Se comprueba contra Google antes de guardarla. Mirar el prefijo no servía:
    Google emite claves 'AIza…' y también 'AQ.…', así que una clave buena podía
    quedar rechazada por una suposición nuestra.
    """
    key = (payload.get("key") or "").strip()
    if not key:                       # vaciarla es legítimo: desactiva la IA
        db.set_gemini_key(uid, "")
        return {"ok": True, "tiene_clave_gemini": False}

    estado, mensaje = core.probar_api_key(key)
    if estado == "invalida":
        raise HTTPException(400, mensaje)
    db.set_gemini_key(uid, key)
    core.usar_api_key(key)            # que surta efecto ya, sin volver a entrar
    return {"ok": True, "tiene_clave_gemini": True,
            "aviso": ("Guardada, pero no hemos podido comprobarla contra Google: "
                      + mensaje) if estado == "sin_comprobar" else ""}


# --------------------------------------------------------------------------- #
# Panel de administración
# --------------------------------------------------------------------------- #
@app.post("/api/admin/users")
def admin_crear_usuario(payload: dict = Body(...),
                        uid: int = Depends(current_admin)) -> dict:
    """Crea una cuenta. Solo el admin.

    Nace ACTIVA: si la creas tú, ya has decidido que esa persona entra. La
    contraseña que pongas es temporal y se la pasas por donde quieras; ella la
    cambia luego desde Ajustes.
    """
    try:
        nuevo = db.create_user(
            username=(payload.get("username") or ""),
            password=(payload.get("password") or ""),
            email=(payload.get("email") or ""),
            role="admin" if payload.get("role") == "admin" else "user",
            status="active",
            nombre=(payload.get("nombre") or ""))
    except ValueError as e:
        raise HTTPException(400, str(e))
    ficha = db.get_user(nuevo) or {}
    return {"ok": True, "id": nuevo, "username": ficha.get("username"),
            "mensaje": "Cuenta creada y activa. Pásale el usuario y la "
                       "contraseña; podrá cambiarla desde Ajustes."}


@app.get("/api/admin/users")
def admin_usuarios(uid: int = Depends(current_admin)) -> list[dict]:
    return db.list_users()


@app.get("/api/admin/diagnostico/ip")
def admin_diagnostico_ip(peticion: Request, uid: int = Depends(current_admin)) -> dict:
    """Qué IP ve el servidor para ti. Sirve para comprobar, ya desplegado, que
    el tope de intentos usa tu IP real y no la del proxy de Render."""
    return {"ip_usada": _ip(peticion),
            "ip_del_socket": peticion.client.host if peticion.client else "",
            "cabecera_configurada": IP_DE_CABECERA or "(ninguna)",
            "cabecera_presente": bool(IP_DE_CABECERA and peticion.headers.get(IP_DE_CABECERA))}


@app.post("/api/admin/users/{user_id}/identidad")
def admin_renombrar(user_id: int, payload: dict = Body(...),
                    uid: int = Depends(current_admin)) -> dict:
    """Cambia el usuario de entrada y/o el nombre visible de una cuenta."""
    if not db.get_user(user_id):
        raise HTTPException(404, "No existe ese usuario.")
    try:
        db.set_user_identity(
            user_id,
            username=payload.get("username") if "username" in payload else None,
            nombre=payload.get("nombre") if "nombre" in payload else None)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, **(db.get_user(user_id) or {})}


@app.post("/api/admin/users/{user_id}/status")
def admin_cambiar_estado(user_id: int, payload: dict = Body(...),
                         uid: int = Depends(current_admin)) -> dict:
    estado = payload.get("status") or ""
    if user_id == uid and estado != "active":
        raise HTTPException(400, "No puedes desactivar tu propia cuenta.")
    objetivo = db.get_user(user_id)
    if not objetivo:
        raise HTTPException(404, "No existe ese usuario.")
    # dejar la plataforma sin ningún admin activo la volvería ingobernable
    if (objetivo["role"] == "admin" and estado != "active"
            and db.count_admins() <= 1):
        raise HTTPException(400, "Es el único administrador activo que queda.")
    try:
        if not db.set_user_status(user_id, estado):
            raise HTTPException(404, "No existe ese usuario.")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "status": estado}


@app.post("/api/admin/users/{user_id}/sesiones/cerrar")
def admin_cerrar_sesiones(user_id: int, uid: int = Depends(current_admin)) -> dict:
    """Echa a esa persona de todos sus dispositivos, sin tocar su contraseña.

    Antes la única forma de cerrarle sesión era bloquearla o cambiarle la
    contraseña: las dos hacen más de lo que a veces se quiere.
    """
    if not db.get_user(user_id):
        raise HTTPException(404, "No existe ese usuario.")
    return {"ok": True, "cerradas": db.cerrar_sesiones(user_id)}


@app.post("/api/admin/users/{user_id}/password")
def admin_resetear_clave(user_id: int, payload: dict = Body(...),
                         uid: int = Depends(current_admin)) -> dict:
    """Reset manual de contraseña.

    No hay 'he olvidado mi contraseña' por correo porque enviar correo pide otro
    servicio externo; para un grupo pequeño, que la reponga el admin es más
    simple y no cuesta nada. Cambiarla cierra las sesiones de esa persona.
    """
    if not db.get_user(user_id):
        raise HTTPException(404, "No existe ese usuario.")
    try:
        db.set_password(user_id, payload.get("password") or "")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


def _pagina(nombre: str) -> HTMLResponse:
    with open(os.path.join(STATIC_DIR, nombre), "r", encoding="utf-8") as fh:
        return HTMLResponse(fh.read())


@app.get("/", response_class=HTMLResponse)
def index(peticion: Request) -> HTMLResponse:
    """La app si hay sesión; si no, la pantalla de entrada."""
    return _pagina("index.html" if usuario_de_la_peticion(peticion) else "login.html")


@app.get("/entrar", response_class=HTMLResponse)
def pagina_login() -> HTMLResponse:
    return _pagina("login.html")


@app.get("/signup", response_class=HTMLResponse)
@app.get("/create-account", response_class=HTMLResponse)
@app.get("/forgot-password", response_class=HTMLResponse)
@app.get("/reset-password", response_class=HTMLResponse)
def paginas_de_cuenta() -> HTMLResponse:
    """Una sola página para los cuatro pasos; cada uno se elige por la ruta."""
    return _pagina("account.html")


@app.get("/bienvenida", response_class=HTMLResponse)
def pagina_bienvenida(peticion: Request) -> HTMLResponse:
    """Cómo sacar la clave de Gemini. Se llega aquí al entrar sin tenerla."""
    if not usuario_de_la_peticion(peticion):
        return _pagina("login.html")
    return _pagina("bienvenida.html")


@app.get("/admin", response_class=HTMLResponse)
def pagina_admin(peticion: Request) -> HTMLResponse:
    """Panel de administración. Quien no sea admin ni siquiera ve que existe."""
    u = usuario_de_la_peticion(peticion)
    if not u:
        return _pagina("login.html")
    if u.get("role") != "admin":
        raise HTTPException(404, "No encontrado")
    return _pagina("admin.html")


# --------------------------------------------------------------------------- #
# Biblioteca / carga
# --------------------------------------------------------------------------- #
_SAFE = re.compile(r"[^A-Za-z0-9._ -]")


@app.get("/api/books")
def list_books(uid: int = Depends(current_user)) -> list[dict]:
    return db.list_books(user_id=uid)


@app.post("/api/upload")
async def upload(file: UploadFile = File(...),
                 uid: int = Depends(current_admin)) -> dict:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".pdf", ".epub"):
        raise HTTPException(400, "Solo se aceptan archivos .pdf o .epub")
    safe_name = _SAFE.sub("_", os.path.basename(file.filename or f"libro{ext}"))
    dest = os.path.join(core.LIBRARY_DIR, safe_name)
    with open(dest, "wb") as out:
        out.write(await file.read())
    try:
        book_id = core.ingest(dest, db)  # convierte PDF->EPUB si hace falta
    except Exception as exc:
        raise HTTPException(400, f"No se pudo procesar el archivo: {exc}")
    book = db.get_book(book_id, user_id=uid)
    return {"book_id": book_id, **book}


@app.get("/api/catalog")
def get_catalog(uid: int = Depends(current_user)) -> dict:
    """Lecturas gratis y legales (dominio público), clasificadas por nivel y tipo."""
    # El título del EPUB no siempre coincide con el del catálogo ("Aesop's
    # Fables" vs "Aesop's Fables; a new translation"): se compara por prefijo.
    ya = [(b.get("title") or "").strip().lower() for b in db.list_books(user_id=uid)]
    libros = []
    for item in catalog.as_dicts():
        t = item["title"].strip().lower()
        tengo = any(x.startswith(t) or t.startswith(x) for x in ya if x)
        libros.append({**item, "in_library": tengo})
    return {"books": libros,
            "levels": ["A2", "B1", "B2", "C1"],
            "kinds": {"relato": "Relatos cortos", "historia": "Historias",
                      "libro": "Libros completos",
                      "ensayo": "Ensayo y no ficción"},
            "avoid": [{"title": t, "why": w} for t, w in catalog.NOT_RECOMMENDED]}


@app.post("/api/catalog/{key}/add")
def add_from_catalog(key: str, uid: int = Depends(current_admin)) -> dict:
    """Descarga el EPUB de Project Gutenberg y lo añade a tu biblioteca."""
    item = catalog.get(key)
    if not item:
        raise HTTPException(404, "Esa lectura no está en el catálogo")
    safe = _SAFE.sub("_", item["title"])[:60] + ".epub"
    dest = os.path.join(core.LIBRARY_DIR, safe)
    try:
        size = core.download_epub(item["url"], dest)
    except Exception as exc:
        raise HTTPException(502, f"No se pudo descargar de Project Gutenberg: {exc}")
    try:
        book_id = core.ingest(dest, db)
    except Exception as exc:
        if os.path.exists(dest):
            os.remove(dest)   # no dejar basura si el EPUB no se pudo procesar
        raise HTTPException(400, f"Se descargó pero no se pudo procesar: {exc}")
    stats = core.readability(db.book_sample_sentences(book_id))
    return {"book_id": book_id, "title": item["title"], "bytes": size,
            "measured_level": stats["level"], "catalog_level": item["level"]}


@app.get("/api/books/{book_id}")
def get_book(book_id: int, uid: int = Depends(current_user)) -> dict:
    book = db.get_book(book_id, user_id=uid)
    if book is None:
        raise HTTPException(404, "Libro no encontrado")
    return book


@app.delete("/api/books/{book_id}")
def delete_book(book_id: int, uid: int = Depends(current_admin)) -> dict:
    """Borra un libro. El vocabulario guardado leyéndolo se conserva."""
    info = db.delete_book(book_id)
    if info is None:
        raise HTTPException(404, "Libro no encontrado")
    # El archivo solo se borra si vive DENTRO de library/ (es la copia que hizo
    # la app al subirlo). Si lo ingeriste desde otra carpeta, ese archivo es
    # tuyo y no se toca.
    file_removed = False
    try:
        library = os.path.realpath(core.LIBRARY_DIR)
        source = os.path.realpath(info.get("source_path") or "")
        if source.startswith(library + os.sep) and os.path.isfile(source):
            os.remove(source)
            file_removed = True
    except OSError:
        pass
    return {"deleted": book_id, "title": info.get("title"),
            "kept_words": info.get("kept_words", 0), "file_removed": file_removed}


def _exigir_libro(book_id: int, uid: int) -> None:
    """404 si el libro no existe O es privado y no eres el admin.

    404 y no 403 a propósito: confirmar que existe un libro que no puedes abrir
    ya filtra información sobre el catálogo privado.
    """
    if not db.puede_ver_libro(book_id, uid):
        raise HTTPException(404, "Libro no encontrado")


@app.post("/api/books/{book_id}/visibility")
def set_book_visibility(book_id: int, payload: dict = Body(...),
                        uid: int = Depends(current_admin)) -> dict:
    """Publica o esconde un libro. Solo el admin.

    Un libro con derechos de autor se puede LEER pero no distribuir: esconderlo
    deja la copia del admin intacta y lo retira de la biblioteca de los demás.
    """
    if not db.set_book_visible(book_id, bool(payload.get("visible", True))):
        raise HTTPException(404, "Libro no encontrado")
    return {"ok": True, "visible": bool(payload.get("visible", True))}


@app.get("/api/books/{book_id}/toc")
def get_toc(book_id: int, uid: int = Depends(current_user)) -> list[dict]:
    _exigir_libro(book_id, uid)
    return db.get_toc(book_id, user_id=uid)


@app.get("/api/books/{book_id}/stats")
def get_stats(book_id: int, uid: int = Depends(current_user)) -> dict:
    _exigir_libro(book_id, uid)
    return db.get_book_stats(book_id)


@app.get("/api/books/{book_id}/difficulty")
def book_difficulty(book_id: int, uid: int = Depends(current_user)) -> dict:
    """Nivel estimado del libro y cuánto se aleja del tuyo.

    Existe para avisarte ANTES de empezar: leer dos escalones por encima de tu
    nivel no es un reto, es una frustración con pasos extra.
    """
    if db.get_book(book_id, user_id=uid) is None:
        raise HTTPException(404, "Libro no encontrado")
    stats = core.readability(db.book_sample_sentences(book_id))
    yours = (db.last_test(user_id=uid) or {}).get("level") or ""
    gap = core.level_gap(stats["level"], yours) if yours else 0
    if not yours:
        verdict = "Haz el test de nivel para comparar con el tuyo."
    elif gap <= -1:
        verdict = "Por debajo de tu nivel: lectura cómoda, buena para coger ritmo."
    elif gap == 0:
        verdict = "Justo en tu nivel. Ideal."
    elif gap == 1:
        verdict = "Un escalón por encima: te costará, pero es donde se aprende."
    else:
        verdict = ("Dos o más escalones por encima de tu nivel. Vas a parar en cada "
                   "frase; mejor dejarlo para más adelante.")
    return {**stats, "your_level": yours, "gap": gap, "verdict": verdict}


@app.post("/api/books/{book_id}/rename")
def rename_book(book_id: int, payload: dict = Body(...), uid: int = Depends(current_admin)) -> dict:
    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "El título no puede estar vacío")
    db.rename_book(book_id, title)
    return {"ok": True, "title": title}


@app.post("/api/books/{book_id}/index/improve")
def improve_index(book_id: int, uid: int = Depends(current_admin)) -> list[dict]:
    """Usa la IA para leer el inicio de cada sección y ponerle un título descriptivo.
    No reordena el texto (eso rompería la lectura); mejora los nombres del índice."""
    book = db.get_book(book_id, user_id=uid)
    if book is None:
        raise HTTPException(404, "Libro no encontrado")
    lang = "es"  # los títulos del índice, en español (idioma del usuario)
    toc = db.get_toc(book_id, user_id=uid)
    improved = 0
    for c in toc:
        sample = db.get_chapter_sample(book_id, c["index"], n=3)
        if not sample:
            continue
        try:
            title = core.llm_generate(sample[:800], "title", lang, max_tokens=40)
        except core.AIUnavailable as exc:
            # una llamada por capítulo: si la IA cae a mitad, conservamos los
            # títulos ya puestos en vez de tirar todo el trabajo
            if improved == 0:
                raise HTTPException(503, str(exc))
            break
        if title and not core.is_placeholder(title):
            clean = title.strip().splitlines()[0].strip().strip('"').strip()[:80]
            if clean:
                db.set_chapter_title(book_id, c["index"], clean)
                improved += 1
    return db.get_toc(book_id, user_id=uid)


@app.get("/api/books/{book_id}/chapter/{idx}")
def get_chapter(book_id: int, idx: int, uid: int = Depends(current_user)) -> dict:
    _exigir_libro(book_id, uid)
    chapter = db.get_chapter(book_id, idx)
    # sin capítulo, el lector se quedaba en blanco sin decir por qué
    if not chapter.get("sentences") and chapter.get("title") is None:
        raise HTTPException(404, "Ese capítulo no existe")
    return chapter


@app.post("/api/books/{book_id}/chapter/{idx}/done")
def set_chapter_done(book_id: int, idx: int, payload: dict = Body(...), uid: int = Depends(current_user)) -> dict:
    _exigir_libro(book_id, uid)
    db.set_chapter_done(book_id, idx, bool(payload.get("done", True)),
                        user_id=uid)
    return db.get_book(book_id, user_id=uid)


# --------------------------------------------------------------------------- #
# Estado de lectura (autoguardado)
# --------------------------------------------------------------------------- #
@app.get("/api/books/{book_id}/state")
def get_state(book_id: int, uid: int = Depends(current_user)) -> dict:
    _exigir_libro(book_id, uid)
    return db.load_reading_state(book_id, user_id=uid)


@app.post("/api/books/{book_id}/state")
def set_state(book_id: int, payload: dict = Body(...), uid: int = Depends(current_user)) -> dict:
    _exigir_libro(book_id, uid)
    db.save_reading_state(
        book_id,
        int(payload.get("chapter_index", 0)),
        int(payload.get("sentence_index", 0)),
        user_id=uid)
    return {"ok": True}


# --------------------------------------------------------------------------- #
# IA (Gemini) con caché en DB
# --------------------------------------------------------------------------- #
@app.post("/api/llm")
def llm(payload: dict = Body(...), uid: int = Depends(current_user)) -> dict:
    text = str(payload.get("text") or "").strip()
    kind = payload.get("kind", "translation")
    lang = payload.get("target_lang", "es")
    if not text:
        raise HTTPException(400, "Falta 'text'")
    if len(text) > MAX_TEXTO_IA:
        raise HTTPException(413, f"Selecciona menos texto (máximo {MAX_TEXTO_IA} caracteres).")
    # solo los tipos y los idiomas que existen: cualquier otro valor iría tal
    # cual dentro del prompt y llenaría la caché compartida de basura
    if kind not in core.TIPOS_IA or lang not in core.IDIOMAS_IA:
        raise HTTPException(400, "Petición de IA no válida.")
    cached = db.get_cached_translation(text, lang, kind)
    if cached is not None:
        return {"result": cached, "cached": True}
    try:
        result = core.llm_generate(text, kind, lang)
    except core.AIUnavailable as exc:
        # 503 explícito: el lector muestra el aviso en vez de meter el texto
        # del error dentro de la traducción (y nunca se cachea un error).
        raise HTTPException(503, str(exc))
    if not core.is_placeholder(result):
        db.cache_translation(text, result, lang, kind)
    return {"result": result, "cached": False}


# --------------------------------------------------------------------------- #
# Configuración de IA (API key de Gemini) — guardada localmente, nunca en código
# --------------------------------------------------------------------------- #
@app.get("/api/config")
def get_config(uid: int = Depends(current_user)) -> dict:
    # current_user ya ha puesto la key de este usuario en el contexto, asi que
    # ai_status describe LA SUYA
    return core.ai_status()


@app.post("/api/config")
def set_config(payload: dict = Body(...), uid: int = Depends(current_user)) -> dict:
    """Guarda la key en la ficha del usuario, no en config.local.json.

    Antes habia una sola key para toda la app; ahora la cuota del free tier de
    Google va por cuenta, asi que cada uno guarda la suya.
    """
    key = (payload.get("gemini_api_key") or "").strip()
    if key:
        estado, mensaje = core.probar_api_key(key)
        if estado == "invalida":
            raise HTTPException(400, mensaje)
    db.set_gemini_key(uid, key)
    core.usar_api_key(key)          # que surta efecto ya, sin volver a entrar
    return core.ai_status()


# --------------------------------------------------------------------------- #
# Vocabulario + repetición espaciada (SRS)
# --------------------------------------------------------------------------- #
@app.post("/api/vocab")
def add_vocab(payload: dict = Body(...), uid: int = Depends(current_user)) -> dict:
    term = str(payload.get("term") or "").strip()
    if not term:
        raise HTTPException(400, "Falta 'term'")
    if (len(term) > 200 or len(str(payload.get("translation") or "")) > 2000
            or len(str(payload.get("example") or "")) > MAX_TEXTO_IA):
        raise HTTPException(413, "La palabra o su ejemplo son demasiado largos.")
    # nunca guardar un texto de relleno como si fuera la traducción: mejor
    # vacío (se puede reintentar) que una tarjeta permanentemente errónea
    if core.is_placeholder(payload.get("translation") or ""):
        payload = {**payload, "translation": ""}
    # Ejemplo corto a tu nivel para la flashcard. La frase del libro puede tener
    # 25 palabras y varias estructuras nuevas a la vez; para memorizar hace falta
    # una sola idea nueva por tarjeta. Si la IA falla, la tarjeta usa la frase
    # del libro como hasta ahora: nunca bloquea el guardado.
    simple = ""
    try:
        level = (db.last_test(user_id=uid) or {}).get("level") or "B1"
        simple_pair = core.simple_example(term, level=level)
        if simple_pair["example"]:
            simple = simple_pair["example"]
            if simple_pair["translation"]:
                simple += " — " + simple_pair["translation"]
    except core.AIUnavailable:
        pass
    vid = db.add_vocab(
        term,
        (payload.get("translation") or "").strip(),
        (payload.get("example") or "").strip(),
        payload.get("lang") or "en",
        payload.get("book_id"),
        simple_example=simple,
        user_id=uid)
    return {"id": vid, "simple_example": simple, **db.vocab_stats(user_id=uid)}


@app.get("/api/vocab")
def list_vocab(uid: int = Depends(current_user)) -> list[dict]:
    return db.list_vocab(user_id=uid)


@app.get("/api/vocab/due")
def due_vocab(ahead: bool = False, uid: int = Depends(current_user)) -> list[dict]:
    """ahead=true: si no toca nada hoy, adelanta los próximos repasos."""
    limite = int(db.get_setting("vocab_new_limit", "10", user_id=uid) or 10)
    return _with_cloze(db.due_vocab(new_limit=limite, ahead=ahead, user_id=uid),
                       front_key="term", note_key="simple_example")


@app.post("/api/vocab/backfill-examples")
def backfill_examples(limit: int = 5, uid: int = Depends(current_user)) -> dict:
    """Genera el ejemplo corto de las palabras que se quedaron sin él.

    Existe porque si la IA está caída justo al guardar una palabra, esa tarjeta
    se quedaría con la frase larga del libro para siempre.

    Va de 5 en 5 a propósito: cada palabra es una llamada a la IA con sus
    reintentos, y un lote grande dejaría el servidor bloqueado varios minutos.
    Es seguro llamarlo varias veces: solo toca las que aún no tienen ejemplo.
    """
    level = (db.last_test(user_id=uid) or {}).get("level") or "B1"
    pending = [w for w in db.list_vocab(user_id=uid) if not (w.get("simple_example") or "").strip()]
    done, failed = 0, 0
    for word in pending[:limit]:
        try:
            pair = core.simple_example(word["term"], level=level)
        except core.AIUnavailable:
            failed += 1
            break          # si la IA cae, parar: el resto se reintenta luego
        if pair["example"]:
            text = pair["example"]
            if pair["translation"]:
                text += " — " + pair["translation"]
            db.set_simple_example(word["id"], text, user_id=uid)
            done += 1
    return {"filled": done, "remaining": max(0, len(pending) - done), "ai_failed": failed}


@app.get("/api/vocab/new")
def new_vocab(limit: int = 10, uid: int = Depends(current_user)) -> list[dict]:
    """Palabras sin ver, ignorando el candado diario (a petición tuya)."""
    return _with_cloze(db.new_vocab(limit=limit, user_id=uid), front_key="term", note_key="simple_example")


@app.get("/api/vocab/stats")
def vocab_stats(uid: int = Depends(current_user)) -> dict:
    return db.vocab_stats(user_id=uid)


@app.post("/api/vocab/{vid}/grade")
def grade_vocab(vid: int, payload: dict = Body(...), uid: int = Depends(current_user)) -> dict:
    grade = payload.get("grade", "good")
    if grade not in ("again", "hard", "good", "easy"):
        raise HTTPException(400, "grade inválido")
    if not db.grade_vocab(vid, grade, user_id=uid):
        raise HTTPException(404, "Esa palabra no existe")
    return db.vocab_stats(user_id=uid)


@app.delete("/api/vocab/{vid}")
def delete_vocab(vid: int, uid: int = Depends(current_user)) -> dict:
    if not db.delete_vocab(vid, user_id=uid):
        raise HTTPException(404, "Esa palabra no existe")
    return db.vocab_stats(user_id=uid)


# --------------------------------------------------------------------------- #
# Decks de aprendizaje (estáticos) + repaso SRS
# --------------------------------------------------------------------------- #
def _with_cloze(cards: list[dict], front_key="front", note_key="note") -> list[dict]:
    """Añade a cada tarjeta su ejercicio de hueco, si se puede construir."""
    out = []
    for c in cards:
        cz = core.build_cloze(c.get(front_key) or "", c.get(note_key) or "")
        out.append({**c, "cloze": cz})
    return out


@app.post("/api/study/check")
def study_check(payload: dict = Body(...), uid: int = Depends(current_user)) -> dict:
    """Compara lo que escribiste con las respuestas válidas.

    Se comprueba en el servidor a propósito: duplicar la normalización en el
    navegador es pedir que las dos versiones se separen con el tiempo.
    """
    typed = payload.get("typed") or ""
    accepted = payload.get("accepted") or []
    if isinstance(accepted, str):
        accepted = [accepted]
    return {"correct": core.check_answer(typed, *accepted),
            "normalized": core.normalize_answer(typed)}


@app.get("/api/study/limits")
def get_limits(uid: int = Depends(current_user)) -> dict:
    """Topes de estudio y cuánto llevas hoy."""
    done = db.reviews_today(user_id=uid)
    cap = int(db.get_setting("review_limit", str(core.DEFAULT_REVIEW_LIMIT), user_id=uid) or 0)
    return {"review_limit": cap, "reviews_today": done,
            "review_left": db.review_budget_left(user_id=uid) if cap else None,
            "vocab_new_limit": int(db.get_setting("vocab_new_limit", "10", user_id=uid) or 10),
            "decks": [{"id": d["id"], "name": d["name"], "new_limit": d["new_limit"]}
                      for d in db.list_decks(user_id=uid)],
            "backlog": db.review_backlog(user_id=uid)}


@app.post("/api/study/limits")
def set_limits(payload: dict = Body(...), uid: int = Depends(current_user)) -> dict:
    if "review_limit" in payload:
        db.set_setting("review_limit", max(0, int(payload["review_limit"])), user_id=uid)
    if "vocab_new_limit" in payload:
        db.set_setting("vocab_new_limit", max(0, int(payload["vocab_new_limit"])), user_id=uid)
    for item in (payload.get("decks") or []):
        db.set_deck_new_limit(int(item["id"]), int(item["new_limit"]), user_id=uid)
    return get_limits(uid=uid)


@app.get("/api/decks")
def list_decks(uid: int = Depends(current_user)) -> list[dict]:
    return db.list_decks(user_id=uid)


@app.post("/api/decks/{deck_id}/backfill-examples")
def deck_backfill_examples(deck_id: int, batch: int = 12, uid: int = Depends(current_admin)) -> dict:
    """Genera los ejemplos que faltan en un mazo, en lotes.

    Un lote por llamada a la IA (no una por tarjeta): 123 frases serían 123
    llamadas y varios minutos de servidor bloqueado.
    """
    pending = db.cards_without_example(deck_id)
    if not pending:
        return {"filled": 0, "remaining": 0, "done": True}
    lote = pending[:batch]
    level = (db.last_test(user_id=uid) or {}).get("level") or "B1"
    try:
        ejemplos = core.phrase_examples([c["front"] for c in lote], level=level)
    except core.AIUnavailable as exc:
        raise HTTPException(503, str(exc))
    hechos = 0
    for card in lote:
        texto = ejemplos.get(card["front"])
        if texto and "—" in texto:
            db.set_card_note(card["id"], texto)
            hechos += 1
    quedan = len(db.cards_without_example(deck_id))
    return {"filled": hechos, "remaining": quedan, "done": quedan == 0}


@app.get("/api/decks/{deck_id}/due")
def deck_due(deck_id: int, new_limit: int | None = None, ahead: bool = False, uid: int = Depends(current_user)) -> list[dict]:
    """new_limit sin valor = usa el tope configurado en el mazo (ajustable en 🎚)."""
    return _with_cloze(db.deck_due_cards(deck_id, new_limit=new_limit, ahead=ahead, user_id=uid))


@app.get("/api/streak")
def streak(uid: int = Depends(current_user)) -> dict:
    return db.get_streak(user_id=uid)


@app.post("/api/activity")
def activity(payload: dict = Body(...), uid: int = Depends(current_user)) -> dict:
    db.log_activity(payload.get("module", ""), int(payload.get("active", 0)),
                    int(payload.get("open", 0)), user_id=uid)
    return {"ok": True}


@app.get("/api/stats/full")
def stats_full(range: str = "week", uid: int = Depends(current_user)) -> dict:
    return db.get_full_stats("month" if range == "month" else "week", user_id=uid)


@app.get("/api/nav-alerts")
def nav_alerts(uid: int = Depends(current_user)) -> dict:
    return db.nav_alerts(user_id=uid)


# --------------------------------------------------------------------------- #
# Test de diagnóstico de nivel (5 versiones equivalentes)
# --------------------------------------------------------------------------- #
@app.get("/api/test/form")
def test_form(uid: int = Depends(current_user)) -> dict:
    return core.get_test_form()


@app.post("/api/test/score")
def test_score(payload: dict = Body(...), uid: int = Depends(current_user)) -> dict:
    form_id = int(payload.get("form_id", 0))
    answers = payload.get("answers") or []
    result = core.score_test(form_id, answers)
    db.save_test_result(result["level"], result["correct"], result["total"], user_id=uid)
    return result


@app.get("/api/test/last")
def test_last(uid: int = Depends(current_user)) -> dict:
    return db.last_test(user_id=uid) or {}


@app.post("/api/test/adaptive")
def test_adaptive(payload: dict = Body(...), uid: int = Depends(current_user)) -> dict:
    answers = payload.get("answers") or []
    result = core.adaptive_next(answers)
    if result.get("done"):
        db.save_test_result(result["level"], result.get("correct", 0), len(answers), user_id=uid)
    return result


# --------------------------------------------------------------------------- #
# Lessons — método contrastivo (Ghio): beginner / mid / advanced
# --------------------------------------------------------------------------- #
@app.get("/api/lessons")
def lessons(level: str = "", uid: int = Depends(current_user)) -> dict:
    items = core.get_lessons(level or None)
    done = set(db.lesson_done_ids(user_id=uid))
    for it in items:
        it["done"] = it["id"] in done
    # checkpoints (mini-tests) por nivel
    cps = []
    for lv in ([level] if level else core._LESSON_LEVELS):
        for cp in core.get_checkpoints(lv):
            cp = dict(cp)
            cp["done"] = cp["id"] in done
            cp["kind"] = "checkpoint"
            cps.append(cp)
    return {"lessons": items, "checkpoints": cps, "levels": core._LESSON_LEVELS}


@app.get("/api/checkpoint/{cp_id}")
def checkpoint_detail(cp_id: str, uid: int = Depends(current_user)) -> dict:
    cp = core.get_checkpoint(cp_id)
    if not cp:
        raise HTTPException(404, "Checkpoint not found")
    cp["done"] = cp_id in set(db.lesson_done_ids(user_id=uid))
    return cp


@app.post("/api/checkpoint/{cp_id}/done")
def checkpoint_done(cp_id: str, payload: dict = Body(default={}), uid: int = Depends(current_user)) -> dict:
    if not core.get_checkpoint(cp_id):
        raise HTTPException(404, "Checkpoint not found")
    done = bool(payload.get("done", True))
    db.set_lesson_done(cp_id, done, user_id=uid)
    return {"ok": True, "done": done}


# NOTA: estas rutas van ANTES de /api/lessons/{lesson_id}. FastAPI resuelve
# por orden de definición: si {lesson_id} va primero, captura "custom" como
# si fuera el id de una lección y devuelve 404.
@app.post("/api/lessons/generate")
def generate_lesson(payload: dict = Body(default={}), uid: int = Depends(current_user)) -> dict:
    """Crea una lección a medida contra tu tipo de error más frecuente."""
    resumen = [s for s in db.writing_error_summary(user_id=uid) if s["category"] != "unclassified"]
    if not resumen:
        raise HTTPException(400, "Aún no hay errores clasificados. Evalúa alguna redacción "
                                 "con «Check my writing» primero.")
    categoria = payload.get("category") or resumen[0]["category"]
    etiqueta = next((s["label"] for s in resumen if s["category"] == categoria), categoria)
    errores = db.errors_by_category(categoria, user_id=uid)
    if not errores:
        raise HTTPException(400, f"No hay errores de tipo «{etiqueta}».")
    nivel = (db.last_test(user_id=uid) or {}).get("level") or "B1"
    try:
        leccion = core.generate_error_lesson(etiqueta, errores, level=nivel)
    except core.AIUnavailable as exc:
        raise HTTPException(503, str(exc))
    lid = db.save_custom_lesson(categoria, leccion.get("title") or etiqueta,
                                nivel, leccion, len(errores), user_id=uid)
    return {"id": lid, "category": categoria, "label": etiqueta,
            "based_on": len(errores), "lesson": leccion}


@app.get("/api/lessons/custom")
def list_custom_lessons(uid: int = Depends(current_user)) -> list[dict]:
    return db.list_custom_lessons(user_id=uid)


@app.get("/api/lessons/custom/{lid}")
def get_custom_lesson(lid: int, uid: int = Depends(current_user)) -> dict:
    row = db.get_custom_lesson(lid, user_id=uid)
    if not row:
        raise HTTPException(404, "Esa lección no existe")
    return row


@app.post("/api/lessons/custom/{lid}/done")
def custom_lesson_done(lid: int, payload: dict = Body(default={}), uid: int = Depends(current_user)) -> dict:
    if not db.set_custom_lesson_done(lid, bool(payload.get("done", True)), user_id=uid):
        raise HTTPException(404, "Esa lección no existe")
    return {"ok": True}


@app.delete("/api/lessons/custom/{lid}")
def delete_custom_lesson(lid: int, uid: int = Depends(current_user)) -> dict:
    if not db.delete_custom_lesson(lid, user_id=uid):
        raise HTTPException(404, "Esa lección no existe")
    return {"deleted": lid}


@app.get("/api/lessons/{lesson_id}")
def lesson_detail(lesson_id: str, uid: int = Depends(current_user)) -> dict:
    ls = core.get_lesson(lesson_id)
    if not ls:
        raise HTTPException(404, "Lesson not found")
    out = dict(ls)
    out["done"] = lesson_id in set(db.lesson_done_ids(user_id=uid))
    return out


@app.post("/api/lessons/{lesson_id}/done")
def lesson_done(lesson_id: str, payload: dict = Body(default={}), uid: int = Depends(current_user)) -> dict:
    if not core.get_lesson(lesson_id):
        raise HTTPException(404, "Lesson not found")
    done = bool(payload.get("done", True))
    db.set_lesson_done(lesson_id, done, user_id=uid)
    return {"ok": True, "done": done}


# --------------------------------------------------------------------------- #
# Writing: extraer texto (incl. foto→OCR), corregir+explicar, upgrade
# --------------------------------------------------------------------------- #
@app.post("/api/writing/extract")
async def writing_extract(file: UploadFile = File(...),
                          uid: int = Depends(current_user)) -> dict:
    data = await file.read()
    try:
        text = core.extract_text_from_upload(file.filename or "", data)
    except core.AIUnavailable as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:
        raise HTTPException(400, str(exc))
    return {"text": text}


@app.post("/api/writing/check")
def writing_check(payload: dict = Body(...), uid: int = Depends(current_user)) -> dict:
    text = str(payload.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "Falta 'text'")
    if len(text) > MAX_REDACCION:
        raise HTTPException(413, f"La redacción es demasiado larga (máximo {MAX_REDACCION} caracteres).")
    try:
        result = core.writing_check(text)
    except core.AIUnavailable as exc:
        # 503: nada que guardar. Sin evaluación real no se inventa un nivel.
        raise HTTPException(503, str(exc))
    # guarda el escrito + los errores en el diario
    title = (payload.get("title") or text[:40]).strip()
    wid = db.save_writing(title, text, result.get("corrected"), result.get("level"),
                          result.get("assessment", ""), user_id=uid)
    for e in result.get("errors", []):
        db.add_writing_error(wid, e.get("original", ""), e.get("correction", ""),
                             e.get("explanation", ""), e.get("category", "other"), user_id=uid)
    result["writing_id"] = wid
    return result


@app.post("/api/writing/upgrade")
def writing_upgrade(payload: dict = Body(...), uid: int = Depends(current_user)) -> dict:
    text = str(payload.get("text") or "").strip()
    level = payload.get("level", "B2")
    if not text:
        raise HTTPException(400, "Falta 'text'")
    if len(text) > MAX_REDACCION:
        raise HTTPException(413, f"La redacción es demasiado larga (máximo {MAX_REDACCION} caracteres).")
    wid = payload.get("writing_id")
    # el upgrade parte del nivel evaluado: primero hay que saber en qué nivel escribes
    record = db.get_writing(int(wid), user_id=uid) if wid else None
    from_level = (record or {}).get("level") or ""
    if not from_level:
        raise HTTPException(
            400, "Primero evalúa tu texto con «Check my writing»: el upgrade parte "
                 "de tu nivel actual."
        )
    allowed = core.next_levels(from_level)
    if not allowed:
        raise HTTPException(400, f"Tu texto ya es {from_level}: no hay nivel superior.")
    if level not in allowed:
        raise HTTPException(
            400, f"Tu texto es {from_level}; el siguiente escalón es {allowed[0]}."
        )
    try:
        upgraded = core.writing_upgrade(text, level, from_level=from_level)
    except core.AIUnavailable as exc:
        raise HTTPException(503, str(exc))
    db.save_writing_upgrade(int(wid), upgraded, level, user_id=uid)
    return {"upgraded": upgraded, "level": level, "from_level": from_level}


@app.get("/api/writings")
def list_writings(uid: int = Depends(current_user)) -> list[dict]:
    return db.list_writings(user_id=uid)


@app.get("/api/writings/{wid}")
def get_writing(wid: int, uid: int = Depends(current_user)) -> dict:
    """Detalle completo: original, corrección, evaluación y upgrade (para comparar)."""
    record = db.get_writing(wid, user_id=uid)
    if not record:
        raise HTTPException(404, "No existe ese escrito")
    return record


@app.delete("/api/writings/{wid}")
def delete_writing(wid: int, uid: int = Depends(current_user)) -> dict:
    if not db.delete_writing(wid, user_id=uid):
        raise HTTPException(404, "No existe ese escrito")
    return {"deleted": wid}


@app.get("/api/writing/errors")
def writing_errors(category: str = "", uid: int = Depends(current_user)) -> list[dict]:
    return db.list_writing_errors(category=category, user_id=uid)


@app.post("/api/writing/errors/{eid}/explain")
def explain_error(eid: int, force: bool = False, uid: int = Depends(current_user)) -> dict:
    """Mini-lección para UN error. Se cachea: la segunda vez no gasta IA."""
    err = db.get_writing_error(eid, user_id=uid)
    if not err:
        raise HTTPException(404, "Ese error no existe")
    if err.get("lesson") and not force:
        return {"id": eid, "lesson": err["lesson"], "cached": True}
    nivel = (db.last_test(user_id=uid) or {}).get("level") or "B1"
    try:
        leccion = core.explain_error(err.get("original", ""), err.get("correction", ""),
                                     err.get("explanation", ""), level=nivel)
    except core.AIUnavailable as exc:
        raise HTTPException(503, str(exc))
    db.set_error_lesson(eid, leccion, user_id=uid)
    return {"id": eid, "lesson": leccion, "cached": False}


@app.post("/api/writing/errors/{eid}/reviewed")
def mark_error_reviewed(eid: int, payload: dict = Body(default={}), uid: int = Depends(current_user)) -> dict:
    if not db.set_error_reviewed(eid, bool(payload.get("reviewed", True)), user_id=uid):
        raise HTTPException(404, "Ese error no existe")
    return {"ok": True, "reviewed": bool(payload.get("reviewed", True))}


@app.get("/api/writing/errors/summary")
def writing_error_summary(uid: int = Depends(current_user)) -> list[dict]:
    """Tus errores agrupados por tipo gramatical, del más repetido al menos."""
    return db.writing_error_summary(user_id=uid)


@app.get("/api/writing/progress")
def writing_progress(uid: int = Depends(current_user)) -> dict:
    """Evolución de tu nivel CEFR escrito a lo largo del tiempo."""
    rows = [w for w in db.list_writings(user_id=uid) if w.get("level")]
    rows.reverse()  # del más antiguo al más reciente
    points = [{"date": (w.get("created_at") or "")[:10], "level": w["level"],
               "value": core.CEFR_LEVELS.index(w["level"]) + 1, "title": w.get("title") or ""}
              for w in rows if w["level"] in core.CEFR_LEVELS]
    return {"points": points,
            "current": points[-1]["level"] if points else "",
            "best": max((p["level"] for p in points),
                        key=lambda l: core.CEFR_LEVELS.index(l), default=""),
            "count": len(points)}


@app.get("/api/decks/{deck_id}/new")
def deck_new(deck_id: int, limit: int = 10, uid: int = Depends(current_user)) -> list[dict]:
    """Siguientes tarjetas sin ver, ignorando el candado diario (a petición tuya)."""
    return _with_cloze(db.deck_new_cards(deck_id, limit=limit, user_id=uid))


@app.get("/api/decks/{deck_id}/study")
def deck_study(deck_id: int, uid: int = Depends(current_user)) -> list[dict]:
    # todas las tarjetas, sin límite diario
    cards = db.deck_study_cards(deck_id, user_id=uid)
    if not cards and not any(d["id"] == deck_id for d in db.list_decks(user_id=uid)):
        raise HTTPException(404, "Ese mazo no existe")
    return _with_cloze(cards)


# Si el servidor no tiene voces del sistema pero sí audio pre-generado, lo
# anuncia como una voz. Sin esto el navegador daba por perdido el audio del
# servidor y no volvía a pedirlo, dejando los ficheros pre-generados sin usar.
VOZ_PREGENERADA = {"name": "pregen", "display": "Amy · voz neural",
                   "accent": "🇺🇸 pre-generada", "pregenerada": True}


@app.get("/api/voices")
def voices(lang: str = "en", uid: int = Depends(current_user)) -> list[dict]:
    del_sistema = core.list_voices(lang)
    if del_sistema:
        return del_sistema
    # sin voces del sistema (servidor Linux): se ofrece la pre-generada si la hay
    return [VOZ_PREGENERADA] if core.hay_audio_pregenerado() else []


@app.get("/api/tts")
def tts(text: str, voice: str = "", rate: int = 0, lang: str = "en", uid: int = Depends(current_user)) -> FileResponse:
    """Genera (y cachea) audio para 'text' con la voz/velocidad pedidas. Sirve el .wav.
    Permite cambiar voz y ritmo de los decks dinámicamente sin re-sembrar."""
    text = (text or "").strip()
    if not text:
        raise HTTPException(400, "Falta 'text'")
    path = core.synthesize(text, lang, rate=rate or None, voice=voice or None)
    # synthesize devuelve el fichero de MUESTRA cuando no pudo generar nada --
    # p. ej. en el servidor Linux, donde no existe el `say` de macOS. Servirlo
    # haria que todas las tarjetas sonaran igual sin decir por que, asi que se
    # responde 503 y el navegador usa su propia voz.
    if os.path.realpath(path) == os.path.realpath(core.SAMPLE_WAV):
        # No pudo generarlo. Antes de rendirse: las tarjetas tienen su audio
        # pre-generado con la voz neural, que es mejor que cualquiera del
        # navegador. Las frases de los libros no, y esas sí caen al navegador.
        pre = core.audio_pregenerado(text)
        if pre:
            return FileResponse(pre, media_type="audio/mp4")
        raise HTTPException(503, "Este servidor no puede generar audio; "
                                 "usa la voz del navegador.")
    return FileResponse(path, media_type="audio/wav")


@app.post("/api/decks/cards/{card_id}/grade")
def grade_deck_card(card_id: int, payload: dict = Body(...), uid: int = Depends(current_user)) -> dict:
    grade = payload.get("grade", "good")
    if grade not in ("again", "hard", "good", "easy"):
        raise HTTPException(400, "grade inválido")
    db.grade_deck_card(card_id, grade, user_id=uid)
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Export a Anki (.apkg) — genera audio server-side y lo empaqueta
# --------------------------------------------------------------------------- #
def _barrer_exportaciones_viejas(edad: int = 3600) -> None:
    """Si alguien corta la descarga a medias, Starlette no llega a borrar su
    .apkg. Cada exportación nueva barre los de más de una hora."""
    limite = time.time() - edad
    for ruta in glob.glob(os.path.join(tempfile.gettempdir(), "anki-*.apkg")):
        try:
            if os.path.getmtime(ruta) < limite:
                os.unlink(ruta)
        except OSError:
            pass


@app.post("/api/export/anki")
def export_anki(payload: dict = Body(...), uid: int = Depends(current_user)) -> FileResponse:
    items = payload.get("items") or []
    if not isinstance(items, list) or len(items) > MAX_ITEMS_ANKI:
        raise HTTPException(413, f"Exporta como mucho {MAX_ITEMS_ANKI} palabras a la vez.")
    if not all(isinstance(it, dict) for it in items):
        raise HTTPException(400, "Formato de exportación no válido.")
    _barrer_exportaciones_viejas()
    if not items:
        # sin items -> exporta TODO el vocabulario guardado
        items = [
            {"word": v["term"], "translation": v.get("translation") or "",
             "example": v.get("example") or "", "lang": v.get("lang") or "en"}
            for v in db.list_vocab(user_id=uid)
        ]
    if not items:
        raise HTTPException(400, "No hay vocabulario para exportar")
    deck_name = payload.get("deck_name") or "AppIdiomas — Vocabulario"
    lang = payload.get("lang") or "en"  # idioma original (para la voz correcta)
    enriched = []
    for it in items:
        word = (it.get("word") or "").strip()
        if not word:
            continue
        example = (it.get("example") or "").strip()
        enriched.append({
            "word": word,
            "translation": (it.get("translation") or "").strip(),
            "example": example,
            "word_audio": core.synthesize(word, lang),
            "example_audio": core.synthesize(example, lang) if example else "",
        })
    if not enriched:
        raise HTTPException(400, "No hay vocabulario válido para exportar")
    # Un fichero propio por petición, que se borra al terminar de enviarlo. Con
    # una ruta fija para todos, dos personas exportando a la vez podían
    # descargarse el vocabulario la una de la otra.
    fd, out_path = tempfile.mkstemp(prefix="anki-", suffix=".apkg")
    os.close(fd)
    try:
        core.AnkiExporter.export(enriched, str(deck_name)[:100], out_path)
    except Exception:
        os.unlink(out_path)
        raise
    return FileResponse(
        out_path,
        media_type="application/octet-stream",
        filename="vocabulario_appidiomas.apkg",
        background=BackgroundTask(os.unlink, out_path),
    )


# audio pre-generado de los decks / TTS (para reproducir en el navegador)
os.makedirs(core.TTS_CACHE_DIR, exist_ok=True)
app.mount("/audio", StaticFiles(directory=core.TTS_CACHE_DIR), name="audio")

# static (por si luego servimos css/js como archivos)
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    # En local se escucha solo en el portátil (127.0.0.1), que es lo seguro.
    # En producción hay que escuchar en todas las interfaces y en el puerto que
    # diga el servidor: Render lo pasa en la variable PORT y mata el proceso si
    # no lo usa.
    puerto = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST") or ("0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")
    # proxy_headers=False: la IP la decide _ip(), nunca X-Forwarded-For.
    uvicorn.run(app, host=host, port=puerto, proxy_headers=False)
