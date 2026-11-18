"""Preparación común de las pruebas: base SQLite TEMPORAL y sin red.

Se importa antes que webapp: fija el entorno para que nada toque database.db
ni la base de producción, y para que los correos queden en una bandeja en
memoria en vez de mandarse.
"""
import atexit
import os
import shutil
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TMP = tempfile.mkdtemp(prefix="lira-pruebas-")
atexit.register(shutil.rmtree, _TMP, True)
os.environ["APP_DB_PATH"] = os.path.join(_TMP, "pruebas.db")
os.environ.pop("DATABASE_URL", None)          # jamás Postgres en las pruebas
os.environ["TTS_SERVIDOR"] = "0"
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("IP_DE_CABECERA", None)
os.environ.pop("BREVO_API_KEY", None)
os.environ["CORREO_MODO"] = "memoria"
os.environ["APP_URL"] = "https://app.ejemplo.test"
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from fastapi.testclient import TestClient  # noqa: E402,F401

import correo  # noqa: E402,F401
import webapp  # noqa: E402,F401
