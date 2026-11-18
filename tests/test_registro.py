"""Pruebas del registro con correo verificado y del restablecer contraseña.

Los correos no se mandan: quedan en correo.BANDEJA_PRUEBAS (CORREO_MODO=memoria).
"""
import re
import unittest

from _comun import TestClient, correo, webapp

CLAVE = "clave-nueva-12345"


def _token(mensaje, ruta):
    m = re.search(re.escape(webapp.APP_URL) + ruta + r"#t=([A-Za-z0-9_\-]+)", mensaje["text"])
    assert m, mensaje["text"]
    return m.group(1)


class Base(unittest.TestCase):
    def setUp(self):
        webapp._intentos.clear()
        correo.BANDEJA_PRUEBAS.clear()
        with webapp.db._lock:
            webapp.db.conn.execute("DELETE FROM email_tokens")
            webapp.db.conn.commit()
        self.c = TestClient(webapp.app)

    def alta(self, email, c=None):
        return (c or self.c).post("/api/auth/register", json={"email": email})

    def ultimo(self):
        return correo.BANDEJA_PRUEBAS[-1]


class Alta(Base):
    def test_flujo_completo_y_entra_directo(self):
        r = self.alta("Nueva.Persona@Ejemplo.com")
        self.assertEqual(r.status_code, 200)
        msg = self.ultimo()
        self.assertEqual(msg["to"], "nueva.persona@ejemplo.com")
        token = _token(msg, "/create-account")
        self.assertNotIn("?", msg["text"].split("#t=")[0].split("/create-account")[1])
        v = self.c.post("/api/auth/link", json={"token": token, "purpose": "signup"}).json()
        self.assertEqual(v, {"valid": True, "email": "nueva.persona@ejemplo.com", "username": ""})
        r = self.c.post("/api/auth/register/complete",
                        json={"token": token, "username": "nueva", "password": CLAVE})
        self.assertEqual(r.status_code, 200, r.text)
        yo = self.c.get("/api/auth/me")
        self.assertEqual(yo.status_code, 200)
        self.assertEqual(yo.json()["username"], "nueva")
        self.assertEqual(yo.json()["role"], "user")
        # entra directo: también con su contraseña desde otro aparato
        otro = TestClient(webapp.app)
        self.assertEqual(otro.post("/api/auth/login", json={"login": "nueva", "password": CLAVE}).status_code, 200)

    def test_el_enlace_sirve_una_sola_vez(self):
        self.alta("una.vez@ejemplo.com")
        token = _token(self.ultimo(), "/create-account")
        ok = self.c.post("/api/auth/register/complete", json={"token": token, "username": "unavez", "password": CLAVE})
        self.assertEqual(ok.status_code, 200)
        otra = TestClient(webapp.app).post("/api/auth/register/complete",
                                           json={"token": token, "username": "unavez2", "password": CLAVE})
        self.assertEqual(otra.status_code, 400)
        self.assertIsNone(webapp.db.find_user("unavez2"))

    def test_enlace_caducado(self):
        self.alta("tarde@ejemplo.com")
        token = _token(self.ultimo(), "/create-account")
        with webapp.db._lock:
            webapp.db.conn.execute("UPDATE email_tokens SET expires_at = '2000-01-01 00:00:00'")
            webapp.db.conn.commit()
        r = self.c.post("/api/auth/register/complete", json={"token": token, "username": "tarde", "password": CLAVE})
        self.assertEqual(r.status_code, 400)

    def test_token_inventado(self):
        r = self.c.post("/api/auth/register/complete",
                        json={"token": "x" * 43, "username": "intruso", "password": CLAVE})
        self.assertEqual(r.status_code, 400)
        self.assertIsNone(webapp.db.find_user("intruso"))

    def test_usuario_ocupado_no_gasta_el_enlace(self):
        webapp.db.create_user(username="ocupado", password=CLAVE)
        self.alta("libre@ejemplo.com")
        token = _token(self.ultimo(), "/create-account")
        r = self.c.post("/api/auth/register/complete", json={"token": token, "username": "OCUPADO", "password": CLAVE})
        self.assertEqual(r.status_code, 400)
        r = self.c.post("/api/auth/register/complete", json={"token": token, "username": "libre1", "password": CLAVE})
        self.assertEqual(r.status_code, 200)

    def test_no_se_puede_pedir_ser_admin(self):
        self.alta("listillo@ejemplo.com")
        token = _token(self.ultimo(), "/create-account")
        self.c.post("/api/auth/register/complete",
                    json={"token": token, "username": "listillo", "password": CLAVE, "role": "admin"})
        self.assertEqual(webapp.db.find_user("listillo")["role"], "user")

    def test_correo_con_cuenta_misma_respuesta_y_enlace_de_clave(self):
        webapp.db.create_user(username="yaesta", password=CLAVE, email="ya.esta@ejemplo.com")
        nueva = self.alta("nadie.aqui@ejemplo.com")
        existe = self.alta("YA.ESTA@ejemplo.com")
        self.assertEqual(nueva.status_code, existe.status_code)
        self.assertEqual(nueva.json(), existe.json())
        self.assertEqual(len(correo.BANDEJA_PRUEBAS), 2)
        self.assertIn("/reset-password#t=", self.ultimo()["text"])      # no un alta duplicada

    def test_los_enlaces_usan_app_url_y_no_el_host(self):
        self.c.post("/api/auth/register", json={"email": "host@ejemplo.com"},
                    headers={"host": "malo.example", "x-forwarded-host": "malo.example"})
        self.assertNotIn("malo.example", self.ultimo()["text"])
        self.assertIn(webapp.APP_URL + "/create-account#t=", self.ultimo()["text"])

    def test_tres_correos_por_hora_a_la_misma_direccion(self):
        for _ in range(webapp.MAX_CORREOS_HORA_POR_CORREO + 2):
            webapp._intentos.clear()
            self.assertEqual(self.alta("pesado@ejemplo.com").status_code, 200)
        self.assertEqual(len(correo.BANDEJA_PRUEBAS), webapp.MAX_CORREOS_HORA_POR_CORREO)

    def test_tope_por_ip(self):
        for i in range(webapp.TOPES["alta"][0]):
            self.assertEqual(self.alta(f"ip{i}@ejemplo.com").status_code, 200)
        self.assertEqual(self.alta("ipx@ejemplo.com").status_code, 429)

    def test_tope_diario_global(self):
        viejo = webapp.MAX_CORREOS_DIA
        webapp.MAX_CORREOS_DIA = 2
        try:
            self.assertEqual(self.alta("d1@ejemplo.com").status_code, 200)
            self.assertEqual(self.alta("d2@ejemplo.com").status_code, 200)
            self.assertEqual(self.alta("d3@ejemplo.com").status_code, 503)
        finally:
            webapp.MAX_CORREOS_DIA = viejo

    def test_las_altas_no_gastan_el_cupo_de_restablecer(self):
        webapp.db.create_user(username="cupo", password=CLAVE, email="cupo@ejemplo.com") \
            if not webapp.db.find_user("cupo") else None
        viejo = webapp.MAX_ALTAS_DIA
        webapp.MAX_ALTAS_DIA = 1
        try:
            self.assertEqual(self.alta("a1@ejemplo.com").status_code, 200)
            self.assertEqual(self.alta("a2@ejemplo.com").status_code, 503)      # cupo de altas lleno
            self.assertEqual(self.alta("cupo@ejemplo.com").status_code, 200)    # restablecer sigue
            self.assertIn("/reset-password#t=", self.ultimo()["text"])
            self.assertIn("Your username is cupo.", self.ultimo()["text"])
        finally:
            webapp.MAX_ALTAS_DIA = viejo

    def test_cinco_al_dia_por_direccion(self):
        for _ in range(4):
            webapp._intentos.clear()
            self.alta("diario@ejemplo.com")
        with webapp.db._lock:                     # los de "hace dos horas" no cuentan por hora
            webapp.db.conn.execute("UPDATE email_tokens SET created_at = ?",
                                   (webapp.db._ahora(-7200),))
            webapp.db.conn.commit()
        for _ in range(4):
            webapp._intentos.clear()
            self.alta("diario@ejemplo.com")
        self.assertEqual(len(correo.BANDEJA_PRUEBAS), webapp.MAX_CORREOS_DIA_POR_CORREO)

    def test_memoria_y_consola_no_valen_en_produccion(self):
        import os
        os.environ["COOKIE_SEGURA"] = "1"
        try:
            self.assertFalse(correo.disponible())
            os.environ["CORREO_MODO"] = "consola"
            self.assertFalse(correo.disponible())
        finally:
            os.environ.pop("COOKIE_SEGURA")
            os.environ["CORREO_MODO"] = "memoria"

    def test_entrar_sin_distinguir_mayusculas(self):
        self.alta("Mayus@Ejemplo.com")
        token = _token(self.ultimo(), "/create-account")
        self.c.post("/api/auth/register/complete", json={"token": token, "username": "Mayus.Cula", "password": CLAVE})
        for login in ("mayus.cula", "MAYUS.CULA", "MAYUS@ejemplo.COM"):
            webapp._intentos.clear()
            r = TestClient(webapp.app).post("/api/auth/login", json={"login": login, "password": CLAVE})
            self.assertEqual(r.status_code, 200, login)

    def test_correo_invalido(self):
        for malo in ("sin-arroba", "a@b", "x" * 250 + "@ejemplo.com", "a b@ejemplo.com"):
            webapp._intentos.clear()
            self.assertEqual(self.alta(malo).status_code, 400, malo)

    def test_sin_servicio_de_correo_el_registro_se_apaga(self):
        viejo = webapp.APP_URL
        webapp.APP_URL = ""
        try:
            self.assertEqual(self.alta("x@ejemplo.com").status_code, 503)
        finally:
            webapp.APP_URL = viejo

    def test_fallo_de_brevo_da_503(self):
        original = correo.enviar

        def roto(*a, **k):
            raise correo.CorreoNoDisponible("caído")
        correo.enviar = roto
        try:
            self.assertEqual(self.alta("caido@ejemplo.com").status_code, 503)
        finally:
            correo.enviar = original

    def test_paginas_de_cuenta(self):
        for ruta in ("/signup", "/create-account", "/forgot-password", "/reset-password"):
            r = self.c.get(ruta)
            self.assertEqual(r.status_code, 200, ruta)
            self.assertIn("api/auth/register", r.text)


class Restablecer(Base):
    def setUp(self):
        super().setUp()
        if not webapp.db.find_user("olvidona"):
            webapp.db.create_user(username="olvidona", password="clave-vieja-123", email="olvidona@ejemplo.com")
        else:
            webapp.db.set_password(webapp.db.find_user("olvidona")["id"], "clave-vieja-123")

    def _pedir(self):
        r = self.c.post("/api/auth/password/forgot", json={"email": "olvidona@ejemplo.com"})
        self.assertEqual(r.status_code, 200)
        import time
        for _ in range(50):                    # el envío va en segundo plano
            if correo.BANDEJA_PRUEBAS:
                break
            time.sleep(0.05)
        return _token(self.ultimo(), "/reset-password")

    def test_flujo_y_cierra_las_demas_sesiones(self):
        vieja = TestClient(webapp.app)
        self.assertEqual(vieja.post("/api/auth/login", json={"login": "olvidona", "password": "clave-vieja-123"}).status_code, 200)
        token = self._pedir()
        r = self.c.post("/api/auth/password/reset", json={"token": token, "password": CLAVE})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(vieja.get("/api/auth/me").status_code, 401)   # sesión anterior cerrada
        self.assertEqual(self.c.get("/api/auth/me").status_code, 200)
        nuevo = TestClient(webapp.app)
        self.assertEqual(nuevo.post("/api/auth/login", json={"login": "olvidona", "password": CLAVE}).status_code, 200)
        self.assertEqual(TestClient(webapp.app).post("/api/auth/password/reset",
                                                     json={"token": token, "password": "otra-clave-999"}).status_code, 400)

    def test_el_enlace_dice_el_usuario(self):
        token = self._pedir()
        self.assertIn("Your username is olvidona.", self.ultimo()["text"])
        d = self.c.post("/api/auth/link", json={"token": token, "purpose": "reset"}).json()
        self.assertEqual(d["username"], "olvidona")

    def test_misma_respuesta_exista_o_no(self):
        a = self.c.post("/api/auth/password/forgot", json={"email": "olvidona@ejemplo.com"})
        b = self.c.post("/api/auth/password/forgot", json={"email": "no.existe@ejemplo.com"})
        self.assertEqual((a.status_code, a.json()), (b.status_code, b.json()))

    def test_clave_corta_no_gasta_el_enlace(self):
        token = self._pedir()
        self.assertEqual(self.c.post("/api/auth/password/reset", json={"token": token, "password": "corta"}).status_code, 400)
        self.assertEqual(self.c.post("/api/auth/password/reset", json={"token": token, "password": CLAVE}).status_code, 200)

    def test_un_enlace_de_alta_no_sirve_para_restablecer(self):
        self.alta("otra.cosa@ejemplo.com")
        token = _token(self.ultimo(), "/create-account")
        r = self.c.post("/api/auth/password/reset", json={"token": token, "password": CLAVE})
        self.assertEqual(r.status_code, 400)

    def test_cuenta_bloqueada_no_recibe_enlace(self):
        uid = webapp.db.find_user("olvidona")["id"]
        webapp.db.set_user_status(uid, "blocked")
        try:
            self.c.post("/api/auth/password/forgot", json={"email": "olvidona@ejemplo.com"})
            import time
            time.sleep(0.3)
            self.assertEqual(correo.BANDEJA_PRUEBAS, [])
        finally:
            webapp.db.set_user_status(uid, "active")

    def test_el_token_no_se_guarda_en_claro(self):
        token = self._pedir()
        with webapp.db._lock:
            filas = [r["token_hash"] for r in webapp.db.conn.execute("SELECT token_hash FROM email_tokens")]
        self.assertNotIn(token, filas)


if __name__ == "__main__":
    unittest.main()
