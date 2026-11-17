"""Pruebas de seguridad de la web: topes, sesiones, permisos y cabeceras.

Corren contra una base SQLite TEMPORAL (APP_DB_PATH) y sin red: nunca tocan
database.db ni la base de producción. Ejecutar desde la raíz del repo:

    python3 -m unittest discover -s tests -v
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TMP = tempfile.mkdtemp(prefix="lira-pruebas-")
os.environ["APP_DB_PATH"] = os.path.join(_TMP, "pruebas.db")
os.environ.pop("DATABASE_URL", None)          # jamás Postgres en las pruebas
os.environ["TTS_SERVIDOR"] = "0"
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("IP_DE_CABECERA", None)
sys.path.insert(0, RAIZ)

from fastapi.testclient import TestClient  # noqa: E402

import webapp  # noqa: E402

CLAVE = "clave-de-prueba-123"


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _usuario(nombre, rol="user"):
    if not webapp.db.find_user(nombre):
        webapp.db.create_user(username=nombre, password=CLAVE, role=rol, status="active")
    return webapp.db.find_user(nombre)["id"]


def _cliente(nombre=None, ip=None):
    c = TestClient(webapp.app)
    if nombre:
        cab = {"true-client-ip": ip} if ip else {}
        r = c.post("/api/auth/login", json={"login": nombre, "password": CLAVE}, headers=cab)
        assert r.status_code == 200, r.text
    return c


class Base(unittest.TestCase):
    def setUp(self):
        webapp._intentos.clear()
        self._ip_cab = webapp.IP_DE_CABECERA
        _usuario("admin.prueba", "admin")
        _usuario("ana")
        _usuario("beto")

    def tearDown(self):
        webapp.IP_DE_CABECERA = self._ip_cab
        webapp._intentos.clear()


class Cabeceras(Base):
    def test_cabeceras_de_seguridad(self):
        r = _cliente().get("/entrar")
        self.assertEqual(r.status_code, 200)
        self.assertIn("frame-ancestors 'none'", r.headers["content-security-policy"])
        self.assertEqual(r.headers["x-frame-options"], "DENY")
        self.assertEqual(r.headers["x-content-type-options"], "nosniff")

    def test_documentacion_apagada(self):
        c = _cliente()
        for ruta in ("/docs", "/openapi.json", "/redoc"):
            self.assertEqual(c.get(ruta).status_code, 404, ruta)


class Topes(Base):
    def test_cuerpo_grande_por_content_length(self):
        r = _cliente("ana").post("/api/llm", content=b"x" * (webapp.LIMITE_CUERPO + 1),
                                 headers={"content-type": "application/json"})
        self.assertEqual(r.status_code, 413)

    def test_cuerpo_grande_sin_content_length(self):
        def trozos():
            for _ in range(20):
                yield b"x" * 100_000
        r = _cliente("ana").post("/api/llm", content=trozos(),
                                 headers={"content-type": "application/json"})
        self.assertEqual(r.status_code, 413)

    def test_subida_grande(self):
        grande = b"0" * (webapp.LIMITES_POR_RUTA["/api/writing/extract"][0] + 1)
        r = _cliente("ana").post("/api/writing/extract", files={"file": ("a.txt", grande)})
        self.assertEqual(r.status_code, 413)

    def test_sin_sesion_o_sin_ser_admin_el_tope_es_1mb(self):
        dos_mb = b"0" * (2 * 1024 * 1024)
        for c in (_cliente(), _cliente("ana")):
            r = c.post("/api/upload", files={"file": ("libro.epub", dos_mb)})
            self.assertEqual(r.status_code, 413)
        r = _cliente().post("/api/writing/extract", files={"file": ("a.txt", dos_mb)})
        self.assertEqual(r.status_code, 413)

    def test_subida_normal_sigue_funcionando(self):
        r = _cliente("ana").post("/api/writing/extract", files={"file": ("a.txt", b"Hello world")})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["text"], "Hello world")

    def test_ia_valida_texto_tipo_e_idioma(self):
        c = _cliente("ana")
        self.assertEqual(c.post("/api/llm", json={"text": "a" * (webapp.MAX_TEXTO_IA + 1)}).status_code, 413)
        self.assertEqual(c.post("/api/llm", json={"text": "hi", "kind": "otro"}).status_code, 400)
        self.assertEqual(c.post("/api/llm", json={"text": "hi", "target_lang": "zz"}).status_code, 400)
        self.assertEqual(c.post("/api/llm", json={"text": "hi", "kind": "translation"}).status_code, 200)

    def test_redaccion_demasiado_larga(self):
        r = _cliente("ana").post("/api/writing/check", json={"text": "a" * (webapp.MAX_REDACCION + 1)})
        self.assertEqual(r.status_code, 413)


class Login(Base):
    def _falla(self, c, login, ip):
        return c.post("/api/auth/login", json={"login": login, "password": "mala-clave-000"},
                      headers={"true-client-ip": ip}).status_code

    def test_tope_por_cuenta_aunque_cambie_la_ip(self):
        webapp.IP_DE_CABECERA = "true-client-ip"
        c = _cliente()
        tope = webapp.TOPES["login_cuenta"][0]
        for i in range(tope):
            self.assertEqual(self._falla(c, "ana", f"10.0.{i}.1"), 401)
        r = c.post("/api/auth/login", json={"login": "ana", "password": CLAVE},
                   headers={"true-client-ip": "10.9.9.9"})
        self.assertEqual(r.status_code, 429)

    def test_usuario_y_correo_cuentan_juntos(self):
        uid = webapp.db.find_user("beto")["id"]
        with webapp.db._lock:
            webapp.db.conn.execute("UPDATE users SET email='beto@ejemplo.com' WHERE id=?", (uid,))
            webapp.db.conn.commit()
        webapp.IP_DE_CABECERA = "true-client-ip"
        c = _cliente()
        tope = webapp.TOPES["login_cuenta"][0]
        for i in range(tope):
            self._falla(c, "beto" if i % 2 else "beto@ejemplo.com", f"10.1.{i}.1")
        self.assertEqual(self._falla(c, "beto", "10.1.200.1"), 429)

    def test_entrar_bien_no_borra_los_fallos_de_la_ip(self):
        webapp.IP_DE_CABECERA = "true-client-ip"
        c = _cliente()
        tope = webapp.TOPES["login"][0]
        for i in range(tope - 1):
            self._falla(c, f"nadie{i}", "203.0.113.7")
        _cliente("ana", ip="203.0.113.7")            # entra con SU cuenta desde la misma IP
        self.assertEqual(self._falla(c, "otro", "203.0.113.7"), 401)
        self.assertEqual(self._falla(c, "otro2", "203.0.113.7"), 429)

    def test_sin_cabecera_configurada_no_se_fia_de_ninguna(self):
        webapp.IP_DE_CABECERA = ""
        c = _cliente()
        tope = webapp.TOPES["login"][0]
        for i in range(tope):
            self._falla(c, f"x{i}", f"198.51.100.{i}")   # IPs inventadas: se ignoran
        self.assertEqual(self._falla(c, "y", "198.51.100.250"), 429)

    def test_dispositivo_conocido_no_queda_bloqueado(self):
        """Un atacante agota los intentos de la cuenta; su dueño, desde el aparato
        donde ya había entrado, sigue pudiendo entrar."""
        webapp.IP_DE_CABECERA = "true-client-ip"
        dueno = _cliente("ana", ip="192.0.2.10")
        self.assertIn(webapp.COOKIE_DISPOSITIVO, dueno.cookies)
        atacante = _cliente()
        for i in range(webapp.TOPES["login_cuenta"][0]):
            self._falla(atacante, "ana", f"10.2.{i}.1")
        self.assertEqual(self._falla(atacante, "ana", "10.2.250.1"), 429)
        r = dueno.post("/api/auth/login", json={"login": "ana", "password": CLAVE},
                       headers={"true-client-ip": "192.0.2.10"})
        self.assertEqual(r.status_code, 200)

    def test_cookie_de_dispositivo_falsa_no_sirve(self):
        webapp.IP_DE_CABECERA = "true-client-ip"
        uid = webapp.db.find_user("beto")["id"]
        c = _cliente()
        for i in range(webapp.TOPES["login_cuenta"][0]):
            self._falla(c, "beto", f"10.3.{i}.1")
        c.cookies.set(webapp.COOKIE_DISPOSITIVO, f"{uid}.{int(__import__('time').time())}.{'0' * 64}",
                      path="/api/auth/login")
        r = c.post("/api/auth/login", json={"login": "beto", "password": CLAVE},
                   headers={"true-client-ip": "10.3.250.1"})
        self.assertEqual(r.status_code, 429)

    def test_ipv6_se_agrupa_por_64(self):
        webapp.IP_DE_CABECERA = "true-client-ip"
        c = _cliente()
        tope = webapp.TOPES["login"][0]
        for i in range(tope):
            self._falla(c, f"v6-{i}", f"2001:db8:1:2::{i + 1:x}")
        self.assertEqual(self._falla(c, "v6-x", "2001:db8:1:2:ffff::9"), 429)
        self.assertEqual(self._falla(c, "v6-y", "2001:db8:1:3::1"), 401)   # otra /64

    def test_cabecera_basura_cae_a_la_ip_del_socket(self):
        webapp.IP_DE_CABECERA = "true-client-ip"
        c = _cliente()
        for i in range(webapp.TOPES["login"][0]):
            self._falla(c, f"b{i}", f"no-es-una-ip-{i}")
        self.assertEqual(self._falla(c, "b-x", "otra-basura"), 429)

    def test_diagnostico_de_ip_solo_admin(self):
        webapp.IP_DE_CABECERA = "true-client-ip"
        self.assertEqual(_cliente("ana").get("/api/admin/diagnostico/ip").status_code, 404)
        r = _cliente("admin.prueba").get("/api/admin/diagnostico/ip",
                                         headers={"true-client-ip": "192.0.2.5"})
        self.assertEqual(r.json()["ip_usada"], "192.0.2.5")

    def test_contrasena_demasiado_larga(self):
        with self.assertRaises(ValueError):
            webapp.db.create_user(username="largo", password="a" * 300)
        r = _cliente().post("/api/auth/login", json={"login": "ana", "password": "a" * 5000})
        self.assertEqual(r.status_code, 401)


class Permisos(Base):
    def test_sin_sesion_401(self):
        self.assertEqual(_cliente().get("/api/books").status_code, 401)

    def test_panel_admin_invisible_para_usuarios(self):
        c = _cliente("ana")
        self.assertEqual(c.get("/api/admin/users").status_code, 404)
        self.assertEqual(c.get("/admin").status_code, 404)

    def test_libro_privado_no_se_ve(self):
        with webapp.db._lock:
            cur = webapp.db.conn.execute(
                "INSERT INTO books (title, source_path, visible) VALUES ('Privado', '/nada', 0)")
            webapp.db.conn.commit()
            bid = cur.lastrowid
        self.assertEqual(_cliente("ana").get(f"/api/books/{bid}").status_code, 404)
        self.assertEqual(_cliente("ana").get(f"/api/books/{bid}/toc").status_code, 404)
        self.assertEqual(_cliente("admin.prueba").get(f"/api/books/{bid}").status_code, 200)


class Anki(Base):
    def test_cada_exportacion_tiene_su_fichero_y_se_borra(self):
        rutas = []
        original = webapp.tempfile.mkstemp

        def espia(*a, **k):
            fd, ruta = original(*a, **k)
            if os.path.basename(ruta).startswith("anki-"):    # genanki usa los suyos
                rutas.append(ruta)
            return fd, ruta
        webapp.tempfile.mkstemp = espia
        try:
            c = _cliente("ana")
            for _ in range(2):
                r = c.post("/api/export/anki", json={"items": [{"word": "house", "translation": "casa"}]})
                self.assertEqual(r.status_code, 200)
                self.assertGreater(len(r.content), 0)
        finally:
            webapp.tempfile.mkstemp = original
        self.assertEqual(len(set(rutas)), 2)
        for ruta in rutas:
            self.assertFalse(os.path.exists(ruta), ruta)

    def test_items_que_no_son_objetos(self):
        r = _cliente("ana").post("/api/export/anki", json={"items": ["house", 3]})
        self.assertEqual(r.status_code, 400)

    def test_demasiadas_palabras(self):
        items = [{"word": "w"}] * (webapp.MAX_ITEMS_ANKI + 1)
        r = _cliente("ana").post("/api/export/anki", json={"items": items})
        self.assertEqual(r.status_code, 413)


class Navegador(unittest.TestCase):
    """escapeHtml y mdToHtml del front, ejecutados con node si está instalado."""

    def test_escape_y_enlaces(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node no está instalado")
        with open(os.path.join(RAIZ, "static", "index.html"), encoding="utf-8") as fh:
            html = fh.read()
        esc = next(l for l in html.splitlines() if l.startswith("function escapeHtml("))
        ini = html.index("function mdToHtml(md){")
        fin = html.index("\n}\n", ini) + 2
        js = esc + "\n" + html[ini:fin] + """
const out = {
  esc: escapeHtml(`"><img src=x onerror=alert(1)> '`),
  js: mdToHtml("[pulsa](javascript:alert(1))"),
  attr: mdToHtml('[x](https://a.com/" onmouseover="alert(1))'),
  ok: mdToHtml("[web](https://example.com)"),
};
console.log(JSON.stringify(out));"""
        r = subprocess.run([node, "-e", js], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertNotIn('"', out["esc"])
        self.assertNotIn("<img", out["esc"])
        self.assertNotIn("javascript:", out["js"].lower().replace("pulsa", ""))
        self.assertNotIn("href=\"javascript", out["js"])
        self.assertNotIn('" onmouseover', out["attr"])
        self.assertIn('href="https://example.com"', out["ok"])


if __name__ == "__main__":
    unittest.main()
