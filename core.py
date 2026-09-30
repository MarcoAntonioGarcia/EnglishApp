"""
core.py — Lógica de negocio del Lector de Idiomas, SIN framework de UI.

Reutilizable tanto por la app web (webapp.py) como, más adelante, por la de escritorio.
No importa PyQt ni FastAPI: solo persistencia, parseo, IA y export.

Piezas:
    - DatabaseManager  -> SQLite (libros, capítulos, oraciones, estado, caché LLM)
    - PdfConverter     -> PDF -> EPUB (Calibre si existe; si no, pdfminer + ebooklib)
    - EpubParser       -> EPUB -> {libro, capítulos, oraciones}
    - ingest()         -> normaliza cualquier archivo a EPUB y lo importa a la DB
    - llm_generate()   -> Gemini (traducción / gramática / ejemplos)
    - synthesize()     -> pyttsx3 -> .wav (para el audio del export a Anki)
    - AnkiExporter     -> .apkg con audio embebido

La unidad atómica del diseño es la ORACIÓN. Ver ARCHITECTURE.md / SCHEMA.sql.
"""

# Copyright (C) 2026 Marco Antonio Garcia
#
# Este archivo es parte de este proyecto, software libre bajo la GNU Affero
# General Public License v3 o posterior. Se distribuye SIN NINGUNA GARANTÍA.
# Ver el archivo LICENSE para los términos completos.

from __future__ import annotations

import datetime
import hashlib
import html
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "SCHEMA.sql")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
SAMPLE_WAV = os.path.join(ASSETS_DIR, "sample.wav")
TTS_CACHE_DIR = os.path.join(ASSETS_DIR, "tts_cache")
LIBRARY_DIR = os.path.join(BASE_DIR, "library")           # archivos subidos
CONVERTED_DIR = os.path.join(ASSETS_DIR, "converted")     # EPUBs generados desde PDF
PIPER_DIR = os.path.join(ASSETS_DIR, "piper")             # modelos de voz neural (Piper)

# Cuenta del administrador. Mientras no exista login (Fase 1) TODO el contenido
# personal pertenece a este usuario: es el unico que hay.
ADMIN_USER_ID = 1
ADMIN_USERNAME = "marco.garcia"

# Voces neurales Piper (más humanas). value 'piper:<modelo>'. Solo se listan las
# que tengan su .onnx descargado en assets/piper/.
_PIPER_MODELS = {
    "en_US-amy-medium": {"display": "Amy · voz neural", "accent": "🇺🇸 femenina"},
    "en_US-ryan-high": {"display": "Ryan · voz neural", "accent": "🇺🇸 masculina"},
}

# Modelo Gemini. gemini-flash-lite-latest: cuota diaria del free tier mucho mayor
# (gemini-2.5-flash solo daba 20 req/día en este proyecto). Buena calidad para traducir.
# Para más calidad puntual: export GEMINI_MODEL="gemini-2.5-flash".
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")

# Modelo para las tareas POCO frecuentes pero exigentes (evaluar y reescribir
# redacciones): unas pocas llamadas al día, pero necesitan JSON largo y válido.
# La cuota del free tier es POR MODELO, así que usar uno distinto aquí no gasta
# la del lector: son dos bolsas diarias separadas, no una compartida.
GEMINI_MODEL_QUALITY = os.environ.get("GEMINI_MODEL_QUALITY", "gemini-2.5-flash")

# Tope GLOBAL de repasos al día. Lo que no entra NO se pierde: se queda vencido
# y sale mañana con prioridad, porque los repasos se sirven del más atrasado al
# más reciente. Un tope alto agota; uno bajo deja crecer el atraso.
DEFAULT_REVIEW_LIMIT = 20

# Respaldo cuando el modelo elegido está saturado (503) o sin cuota (429).
# Sólo modelos con cuota real en el free tier: gemini-2.0-* devuelve
# 'limit: 0' (ya no está disponible) y sólo servía para gastar reintentos.
GEMINI_FALLBACKS = ("gemini-2.5-flash", "gemini-flash-latest", "gemini-flash-lite-latest")

# Páginas de PDF que se agrupan en un "capítulo" al convertir a EPUB.
PDF_PAGES_PER_CHAPTER = int(os.environ.get("PDF_PAGES_PER_CHAPTER", "8"))

# --------------------------------------------------------------------------- #
# Configuración local (API key de Gemini). Se guarda SOLO en la máquina del
# usuario, en config.local.json (permisos 600, en .gitignore). NUNCA se
# hardcodea ni se registra en logs. Precedencia: variable de entorno > archivo.
# --------------------------------------------------------------------------- #
CONFIG_PATH = os.path.join(BASE_DIR, "config.local.json")


def _read_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh) or {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def get_api_key() -> str | None:
    """Devuelve la API key: primero la variable de entorno, luego el archivo local."""
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key.strip() or None
    key = _read_config().get("gemini_api_key")
    return key.strip() if key else None


def set_api_key(key: str) -> None:
    """Guarda la API key en el archivo local (permisos 600) y la activa en el proceso."""
    key = (key or "").strip()
    cfg = _read_config()
    if key:
        cfg["gemini_api_key"] = key
        os.environ["GEMINI_API_KEY"] = key       # activa sin reiniciar
    else:
        cfg.pop("gemini_api_key", None)
        os.environ.pop("GEMINI_API_KEY", None)
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh)
    try:
        os.chmod(CONFIG_PATH, 0o600)             # solo el dueño puede leerlo
    except OSError:
        pass


def ai_status() -> dict:
    """Estado para el frontend. Devuelve la key ENMASCARADA (nunca completa)."""
    key = get_api_key()
    masked = ("…" + key[-4:]) if key and len(key) >= 4 else ("set" if key else "")
    return {"enabled": bool(key), "key_masked": masked, "model": GEMINI_MODEL,
            "from_env": bool(os.environ.get("GEMINI_API_KEY")) and not _read_config().get("gemini_api_key")}


# --------------------------------------------------------------------------- #
# DatabaseManager
# --------------------------------------------------------------------------- #
class DatabaseManager:
    """Persistencia SQLite, segura entre hilos (uvicorn corre endpoints sync en un
    threadpool). Conexión compartida con check_same_thread=False + un Lock."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self._lock = threading.Lock()
        self._apply_schema()

    def _apply_schema(self) -> None:
        if not os.path.exists(SCHEMA_PATH):
            raise FileNotFoundError(f"No se encontró el esquema: {SCHEMA_PATH}")
        with open(SCHEMA_PATH, "r", encoding="utf-8") as fh:
            script = fh.read()
        with self._lock:
            self.conn.executescript(script)
            self.conn.commit()
        self._migrate()
        self._migrate_multiuser()
        self._migrate_deck_progress()

    def _migrate(self) -> None:
        """Añade columnas nuevas a DBs ya existentes (SQLite no tiene ADD COLUMN IF NOT EXISTS)."""
        # 'due' se añade SIN default (SQLite no permite ADD COLUMN con default no
        # constante como date('now')); se rellena con un UPDATE justo después.
        cols = {
            "example": "TEXT",
            "lang": "TEXT NOT NULL DEFAULT 'en'",
            "ease": "REAL NOT NULL DEFAULT 2.5",
            "interval_days": "INTEGER NOT NULL DEFAULT 0",
            "reps": "INTEGER NOT NULL DEFAULT 0",
            "due": "TEXT",
        }
        with self._lock:
            # La plataforma pasa a ser multiusuario. En esta fase solo existe el
            # admin y todo lo ya guardado es suyo. Se siembra aqui y no en
            # SCHEMA.sql porque ese fichero es DDL puro.
            self.conn.execute(
                "INSERT OR IGNORE INTO users (id, username, role, status) "
                "VALUES (?, ?, 'admin', 'active')", (ADMIN_USER_ID, ADMIN_USERNAME))
            existing = {r["name"] for r in self.conn.execute("PRAGMA table_info(vocabulary)")}
            for name, decl in cols.items():
                if name not in existing:
                    try:
                        self.conn.execute(f"ALTER TABLE vocabulary ADD COLUMN {name} {decl}")
                    except sqlite3.OperationalError:
                        pass
            self.conn.execute("UPDATE vocabulary SET due = date('now','localtime') WHERE due IS NULL")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_vocab_due ON vocabulary (due)")
            # 'done' en chapters (capítulos completados)
            chcols = {r["name"] for r in self.conn.execute("PRAGMA table_info(chapters)")}
            if "done" not in chcols:
                try:
                    self.conn.execute("ALTER TABLE chapters ADD COLUMN done INTEGER NOT NULL DEFAULT 0")
                except sqlite3.OperationalError:
                    pass
            # writings: el upgrade vivía en 'corrected' y pisaba la corrección y el
            # nivel evaluado. Ahora tiene columnas propias.
            # Ejemplo corto y a tu nivel para estudiar. La frase del libro se
            # conserva en 'example': sirve de recuerdo de dónde encontraste la
            # palabra, pero 25 palabras es demasiado para una flashcard.
            vcols = {r["name"] for r in self.conn.execute("PRAGMA table_info(vocabulary)")}
            if "simple_example" not in vcols:
                try:
                    self.conn.execute("ALTER TABLE vocabulary ADD COLUMN simple_example TEXT")
                except sqlite3.OperationalError:
                    pass
            # traducciones que quedaron guardadas con el texto de relleno de la
            # IA (cuando no había API key). Se vacían para poder reintentarlas:
            # la palabra y su ejemplo se conservan.
            self.conn.execute(
                "UPDATE vocabulary SET translation='' WHERE translation LIKE '[modo simulado%' "
                "OR translation LIKE '[IA sin configurar%' OR translation LIKE '[error de IA%' "
                "OR translation LIKE '[respuesta vacía%'"
            )
            self.conn.execute(
                "DELETE FROM translations WHERE result LIKE '[modo simulado%' "
                "OR result LIKE '[IA sin configurar%' OR result LIKE '[error de IA%'"
            )
            # Los libros guardan la ruta ABSOLUTA de su .epub. Si mueves la
            # carpeta del proyecto, esas rutas apuntan al sitio viejo: volver a
            # subir un libro crearía un duplicado y borrarlo no eliminaría el
            # archivo. Se rehacen solas cuando el fichero está en library/.
            for row in self.conn.execute("SELECT id, source_path FROM books").fetchall():
                ruta = row["source_path"] or ""
                if ruta and not os.path.exists(ruta):
                    candidato = os.path.join(LIBRARY_DIR, os.path.basename(ruta))
                    if os.path.isfile(candidato):
                        try:
                            self.conn.execute("UPDATE books SET source_path=? WHERE id=?",
                                              (candidato, row["id"]))
                        except sqlite3.IntegrityError:
                            pass          # ya había otra fila con esa ruta
            # Tope de tarjetas NUEVAS por mazo. No todos los mazos merecen el
            # mismo ritmo: 10 nuevas al día en un mazo de 34 tarjetas lo agota
            # en tres días y luego solo genera repasos.
            kcols = {r["name"] for r in self.conn.execute("PRAGMA table_info(decks)")}
            if "new_limit" not in kcols:
                try:
                    self.conn.execute(
                        "ALTER TABLE decks ADD COLUMN new_limit INTEGER NOT NULL DEFAULT 10")
                except sqlite3.OperationalError:
                    pass
            # 'category' en deck_cards: la situación de uso ("Tiendas",
            # "Restaurante"). Estaba metida en 'note', que es el campo del
            # EJEMPLO, así que la tarjeta mostraba "Tiendas" donde debía ir una
            # frase de uso — y sin ejemplo no se puede construir el cloze.
            # (category ya vive en SCHEMA.sql; el ALTER se queda para las bases
            # creadas antes de que estuviera alli)
            dcols = {r["name"] for r in self.conn.execute("PRAGMA table_info(deck_cards)")}
            if "category" not in dcols:
                try:
                    self.conn.execute("ALTER TABLE deck_cards ADD COLUMN category TEXT")
                except sqlite3.OperationalError:
                    pass
            # una nota sin '—' y de pocas palabras no es un ejemplo: es la
            # categoría mal colocada. Se mueve a su sitio y se vacía la nota.
            self.conn.execute(
                "UPDATE deck_cards SET category = note, note = '' "
                "WHERE IFNULL(note,'') != '' AND note NOT LIKE '%—%' "
                "AND length(note) - length(replace(note,' ','')) < 2"
            )
            # mini-lección y marca de revisado POR error. La lección general
            # cubre 12 errores de UNA categoría: el resto se quedaba sin nada.
            for col, decl in (("lesson", "TEXT"), ("reviewed", "INTEGER NOT NULL DEFAULT 0")):
                ecols2 = {r["name"] for r in self.conn.execute(
                    "PRAGMA table_info(writing_errors)")}
                if col not in ecols2:
                    try:
                        self.conn.execute(
                            f"ALTER TABLE writing_errors ADD COLUMN {col} {decl}")
                    except sqlite3.OperationalError:
                        pass
            # tipo gramatical de cada error, para poder agrupar por patrón
            ecols = {r["name"] for r in self.conn.execute("PRAGMA table_info(writing_errors)")}
            if "category" not in ecols:
                try:
                    self.conn.execute("ALTER TABLE writing_errors ADD COLUMN category TEXT")
                except sqlite3.OperationalError:
                    pass
            wcols = {r["name"] for r in self.conn.execute("PRAGMA table_info(writings)")}
            for name in ("assessment", "upgraded", "upgrade_level"):
                if name not in wcols:
                    try:
                        self.conn.execute(f"ALTER TABLE writings ADD COLUMN {name} TEXT")
                    except sqlite3.OperationalError:
                        pass
            # limpia lo que ese bug dejó escrito: mensajes de error guardados como
            # si fueran la corrección, y un 'level' que era el nivel OBJETIVO del
            # upgrade, no el evaluado. El texto original nunca se tocó.
            self.conn.execute(
                "UPDATE writings SET corrected=NULL, level=NULL "
                "WHERE corrected LIKE '[error de IA:%' OR corrected LIKE '[define GEMINI_API_KEY%'"
            )
            self.conn.commit()

    # Tablas con id propio: basta con añadir la columna. Todo lo que ya hay
    # dentro es del admin, que hasta ahora era el único usuario.
    # ALTER deja user_id en la ÚLTIMA posición, mientras que en una base recién
    # creada va en la segunda. Da igual: no hay ni un INSERT posicional ni un
    # acceso row[0] en el código — todo va por nombre con sqlite3.Row.
    _MU_ALTER = ("vocabulary", "test_results", "writings", "writing_errors",
                 "custom_lessons")

    # Tablas cuya PRIMARY KEY tiene que pasar a incluir user_id: "una fila por
    # día" o "una fila por lección" deja de ser único en cuanto hay dos
    # usuarios, y el segundo pisaría las filas del primero. SQLite no permite
    # cambiar una PK con ALTER, así que hay que reconstruirlas.
    _MU_REBUILD = {
        "reading_state": ("book_id", "chapter_index", "sentence_index", "updated_at"),
        "study_log":     ("day", "reviews"),
        "activity_log":  ("day", "module", "seconds"),
        "session_log":   ("day", "open_seconds"),
        "new_intro":     ("day", "scope", "count"),
        "lesson_done":   ("lesson_id", "created_at"),
    }

    _MU_INDICES = (
        "CREATE INDEX IF NOT EXISTS idx_vocab_user     ON vocabulary     (user_id)",
        "CREATE INDEX IF NOT EXISTS idx_writings_user  ON writings       (user_id)",
        "CREATE INDEX IF NOT EXISTS idx_werrors_user   ON writing_errors (user_id)",
        "CREATE INDEX IF NOT EXISTS idx_tests_user     ON test_results   (user_id)",
        "CREATE INDEX IF NOT EXISTS idx_customles_user ON custom_lessons (user_id)",
    )

    def _ddl_de(self, tabla: str) -> str:
        """El CREATE TABLE de una tabla, leído de SCHEMA.sql.

        El esquema vive en un solo sitio: copiarlo aquí sería garantizar que un
        día deje de coincidir con el de una base recién creada."""
        with open(SCHEMA_PATH, "r", encoding="utf-8") as fh:
            m = re.search(
                r"CREATE TABLE IF NOT EXISTS %s\s*\(.*?\n\);" % re.escape(tabla),
                fh.read(), re.S)
        if not m:
            raise RuntimeError(f"SCHEMA.sql no define la tabla {tabla}")
        return m.group(0)

    def _rebuild(self, tabla: str, columnas: tuple, con_user_id: bool = True) -> None:
        """Recrea la tabla con la forma que dicta SCHEMA.sql y le pasa los datos.

        Procedimiento estándar de SQLite para cambiar una PRIMARY KEY: renombrar
        la vieja, crear la nueva, copiar, borrar."""
        viejo = f"{tabla}__pre_mu"
        cols = ", ".join(columnas)
        self.conn.execute(f"ALTER TABLE {tabla} RENAME TO {viejo}")
        self.conn.execute(self._ddl_de(tabla))
        if con_user_id:
            self.conn.execute(
                f"INSERT INTO {tabla} (user_id, {cols}) SELECT ?, {cols} FROM {viejo}",
                (ADMIN_USER_ID,))
        else:
            self.conn.execute(
                f"INSERT INTO {tabla} ({cols}) SELECT {cols} FROM {viejo}")
        self.conn.execute(f"DROP TABLE {viejo}")

    def _migrate_multiuser(self) -> None:
        """Fase 1 del paso a multiusuario: user_id en las tablas personales.

        Todo lo ya guardado pasa a ser del admin, que hasta ahora era el único
        usuario. El CONTENIDO (books, chapters, sentences, decks y el texto de
        deck_cards) no lleva user_id: lo cura el admin y lo comparten todos.

        Todavía no hay login. user_id va con DEFAULT 1, así que las consultas
        que aún no filtran siguen dando lo mismo mientras se migra el código.
        """
        with self._lock:
            hecho = "user_id" in {
                r["name"] for r in self.conn.execute("PRAGMA table_info(vocabulary)")}
            if not hecho:
                # foreign_keys no se puede cambiar dentro de una transacción:
                # hay que apagarlo antes del BEGIN y encenderlo tras el COMMIT.
                self.conn.execute("PRAGMA foreign_keys = OFF")
                previo = self.conn.isolation_level
                self.conn.isolation_level = None
                try:
                    self.conn.execute("BEGIN")
                    for tabla in self._MU_ALTER:
                        self.conn.execute(
                            f"ALTER TABLE {tabla} ADD COLUMN "
                            f"user_id INTEGER NOT NULL DEFAULT {ADMIN_USER_ID}")
                    for tabla, columnas in self._MU_REBUILD.items():
                        self._rebuild(tabla, columnas)
                    # app_settings era global, pero un tope de repasos es una
                    # decisión personal: se convierte en user_settings.
                    if self.conn.execute(
                            "SELECT 1 FROM sqlite_master "
                            "WHERE type='table' AND name='app_settings'").fetchone():
                        self.conn.execute(
                            "INSERT INTO user_settings (user_id, key, value) "
                            "SELECT ?, key, value FROM app_settings", (ADMIN_USER_ID,))
                        self.conn.execute("DROP TABLE app_settings")
                    # users gana email y gemini_api_key. Se reconstruye en vez de
                    # un ALTER porque UNIQUE(email) es restricción de tabla y
                    # ALTER no puede añadirla: una base migrada tiene que quedar
                    # idéntica a una recién creada, o acabarán divergiendo.
                    self._rebuild("users",
                                  ("id", "username", "password_hash", "role",
                                   "status", "created_at"), con_user_id=False)
                    self.conn.execute("COMMIT")
                except Exception:
                    self.conn.execute("ROLLBACK")
                    raise
                finally:
                    self.conn.isolation_level = previo
                    self.conn.execute("PRAGMA foreign_keys = ON")
                rotas = self.conn.execute("PRAGMA foreign_key_check").fetchall()
                if rotas:
                    raise RuntimeError(
                        f"la migración multiusuario dejó {len(rotas)} referencias rotas")
            # Baratos e idempotentes, se aseguran en cada arranque: en una base
            # recién creada el bloque de arriba no llega a ejecutarse.
            for sql in self._MU_INDICES:
                self.conn.execute(sql)
            self.conn.commit()

    # Columnas de una tarjeta tal y como las espera el frontend: el contenido
    # es de deck_cards y el progreso del usuario sale de card_progress. No
    # tener fila alli significa "sin ver", asi que el LEFT JOIN se rellena con
    # los valores iniciales del SM-2.
    _CARD_COLS = ("c.id, c.front, c.translation, c.note, c.category, c.audio_file, "
                  "COALESCE(p.reps,0) AS reps, COALESCE(p.ease,2.5) AS ease, "
                  "COALESCE(p.interval_days,0) AS interval_days")
    _CARD_FROM = ("FROM deck_cards c "
                  "LEFT JOIN card_progress p ON p.card_id = c.id AND p.user_id = ?")
    _CARD_DUE = "COALESCE(p.due, date('now','localtime'))"

    def _migrate_deck_progress(self) -> None:
        """Fase 1, paso 3: el progreso SRS sale de deck_cards a card_progress.

        El contenido de una tarjeta es compartido, pero haberla aprobado es
        personal. Mientras ambos vivieran en la misma fila, el repaso de uno
        era el repaso de todos.

        card_progress se crea DESPUES de reconstruir deck_cards: al renombrar
        una tabla, SQLite reescribe las claves ajenas que apuntan a ella, y si
        card_progress existiera ya acabaria apuntando a la copia vieja.
        """
        with self._lock:
            cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(deck_cards)")}
            if "ease" not in cols:
                return
            self.conn.execute("PRAGMA foreign_keys = OFF")
            previo = self.conn.isolation_level
            self.conn.isolation_level = None
            try:
                self.conn.execute("BEGIN")
                # SCHEMA.sql corre al arrancar y ya ha creado card_progress
                # apuntando a deck_cards. Si se queda ahí durante el renombrado,
                # SQLite reescribe esa clave ajena para que siga al nombre viejo
                # y acaba apuntando a la copia que vamos a borrar. Se tira y se
                # vuelve a crear después; solo puede estar vacía, porque el
                # guard de arriba garantiza que el reparto aún no se hizo.
                n = self.conn.execute(
                    "SELECT COUNT(*) n FROM card_progress").fetchone()["n"] \
                    if self.conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' "
                        "AND name='card_progress'").fetchone() else 0
                if n:
                    raise RuntimeError(
                        f"card_progress ya tiene {n} filas antes de repartir "
                        "deck_cards: migración inesperada, no se toca nada")
                self.conn.execute("DROP TABLE IF EXISTS card_progress")
                self.conn.execute("ALTER TABLE deck_cards RENAME TO deck_cards__pre_sp")
                self.conn.execute(self._ddl_de("deck_cards"))
                self.conn.execute(
                    "INSERT INTO deck_cards (id, deck_id, position, front, translation, "
                    "note, category, audio_file) SELECT id, deck_id, position, front, "
                    "translation, note, category, audio_file FROM deck_cards__pre_sp")
                self.conn.execute(self._ddl_de("card_progress"))
                # se copia el estado de TODAS las tarjetas, no solo las
                # estudiadas: asi el admin conserva exactamente lo que tenia.
                self.conn.execute(
                    "INSERT INTO card_progress "
                    "(user_id, card_id, ease, interval_days, reps, due) "
                    "SELECT ?, id, ease, interval_days, reps, due FROM deck_cards__pre_sp",
                    (ADMIN_USER_ID,))
                self.conn.execute("DROP TABLE deck_cards__pre_sp")
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.execute("ROLLBACK")
                raise
            finally:
                self.conn.isolation_level = previo
                self.conn.execute("PRAGMA foreign_keys = ON")
            rotas = self.conn.execute("PRAGMA foreign_key_check").fetchall()
            if rotas:
                raise RuntimeError(
                    f"partir deck_cards dejo {len(rotas)} referencias rotas")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_cardprog_due "
                              "ON card_progress (user_id, due)")
            self.conn.commit()

    # --- libros -------------------------------------------------------- #
    def list_books(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT id, title, author FROM books ORDER BY added_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def find_book_by_path(self, source_path: str) -> int | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT id FROM books WHERE source_path = ?", (source_path,)
            ).fetchone()
        return row["id"] if row else None

    def import_book(self, source_path: str, parsed: dict) -> int:
        with self._lock:
            existing = self.conn.execute(
                "SELECT id FROM books WHERE source_path = ?", (source_path,)
            ).fetchone()
            try:
                if existing is not None:
                    self.conn.execute("DELETE FROM books WHERE id = ?", (existing["id"],))
                cur = self.conn.execute(
                    "INSERT INTO books (title, author, language, source_path) "
                    "VALUES (?, ?, ?, ?)",
                    (parsed["title"], parsed.get("author", ""),
                     parsed.get("language", ""), source_path),
                )
                book_id = cur.lastrowid
                for ch_index, chapter in enumerate(parsed["chapters"]):
                    cur = self.conn.execute(
                        "INSERT INTO chapters (book_id, chapter_index, title) "
                        "VALUES (?, ?, ?)",
                        (book_id, ch_index, chapter.get("title")),
                    )
                    chapter_id = cur.lastrowid
                    self.conn.executemany(
                        "INSERT INTO sentences (book_id, chapter_id, sentence_index, content) "
                        "VALUES (?, ?, ?, ?)",
                        [(book_id, chapter_id, i, c)
                         for i, c in enumerate(chapter["sentences"])],
                    )
                self.conn.commit()
                return book_id
            except Exception:
                self.conn.rollback()
                raise

    def get_book(self, book_id: int) -> dict | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT id, title, author, language FROM books WHERE id = ?", (book_id,)
            ).fetchone()
            if row is None:
                return None
            n = self.conn.execute(
                "SELECT COUNT(*) AS n FROM chapters WHERE book_id = ?", (book_id,)
            ).fetchone()["n"]
            done = self.conn.execute(
                "SELECT COUNT(*) AS n FROM chapters WHERE book_id = ? AND COALESCE(done,0)=1",
                (book_id,)).fetchone()["n"]
        d = dict(row)
        d["chapter_count"] = n
        d["chapters_done"] = done
        return d

    def rename_book(self, book_id: int, title: str) -> None:
        with self._lock:
            self.conn.execute("UPDATE books SET title = ? WHERE id = ?", (title, book_id))
            self.conn.commit()

    def book_sample_sentences(self, book_id: int, n: int = 3000) -> list[str]:
        """Muestra del CENTRO del libro, para medir dificultad.

        El principio de un EPUB suele ser portadilla, índice, créditos y listas
        de ilustraciones en mayúsculas: medir ahí da un nivel falso. El centro
        es prosa real.
        """
        with self._lock:
            total = self.conn.execute(
                "SELECT COUNT(*) n FROM sentences WHERE book_id = ?", (book_id,)
            ).fetchone()["n"]
            offset = total // 5 if total > 200 else 0   # salta el primer 20 %
            rows = self.conn.execute(
                "SELECT content FROM sentences WHERE book_id = ? "
                "ORDER BY id LIMIT ? OFFSET ?", (book_id, n, offset),
            ).fetchall()
        # descarta líneas que son claramente maquetación (TODO EN MAYÚSCULAS)
        out = [r["content"] for r in rows]
        prosa = [s for s in out if not (s.isupper() and len(s.split()) > 2)]
        return prosa or out

    def get_book_stats(self, book_id: int) -> dict:
        """Conteo de oraciones por capítulo -> para el % de avance del libro."""
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT c.chapter_index AS idx, COUNT(s.id) AS n
                FROM chapters c LEFT JOIN sentences s ON s.chapter_id = c.id
                WHERE c.book_id = ?
                GROUP BY c.chapter_index ORDER BY c.chapter_index
                """,
                (book_id,),
            ).fetchall()
        counts = [r["n"] for r in rows]
        return {"counts": counts, "total": sum(counts)}

    def get_toc(self, book_id: int) -> list[dict]:
        """Índice: lista de capítulos/secciones (índice + título + completado)."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT chapter_index, title, COALESCE(done,0) done FROM chapters "
                "WHERE book_id = ? ORDER BY chapter_index",
                (book_id,),
            ).fetchall()
        return [{"index": r["chapter_index"], "title": r["title"],
                 "done": bool(r["done"])} for r in rows]

    def set_chapter_done(self, book_id: int, chapter_index: int, done: bool) -> None:
        with self._lock:
            self.conn.execute(
                "UPDATE chapters SET done = ? WHERE book_id = ? AND chapter_index = ?",
                (1 if done else 0, book_id, chapter_index))
            self.conn.commit()

    def set_chapter_title(self, book_id: int, chapter_index: int, title: str) -> None:
        with self._lock:
            self.conn.execute(
                "UPDATE chapters SET title = ? WHERE book_id = ? AND chapter_index = ?",
                (title, book_id, chapter_index),
            )
            self.conn.commit()

    def delete_book(self, book_id: int) -> dict | None:
        """Borra un libro con sus capítulos, frases y posición de lectura.

        El vocabulario que guardaste leyéndolo NO se borra: solo se desvincula.
        Esas palabras las aprendiste tú y siguen en tus repasos. Devuelve los
        datos del libro borrado, o None si no existía.
        """
        with self._lock:
            row = self.conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
            if not row:
                return None
            info = dict(row)
            info["kept_words"] = self.conn.execute(
                "SELECT COUNT(*) n FROM vocabulary WHERE book_id = ?", (book_id,)
            ).fetchone()["n"]
            self.conn.execute("UPDATE vocabulary SET book_id = NULL WHERE book_id = ?", (book_id,))
            for table in ("sentences", "chapters", "reading_state"):
                self.conn.execute(f"DELETE FROM {table} WHERE book_id = ?", (book_id,))
            self.conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
            self.conn.commit()
        return info

    def get_chapter_sample(self, book_id: int, chapter_index: int, n: int = 3) -> str:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT s.content FROM sentences s
                JOIN chapters c ON c.id = s.chapter_id
                WHERE s.book_id = ? AND c.chapter_index = ?
                ORDER BY s.sentence_index LIMIT ?
                """,
                (book_id, chapter_index, n),
            ).fetchall()
        return " ".join(r["content"] for r in rows)

    def get_chapter(self, book_id: int, chapter_index: int) -> dict:
        with self._lock:
            title_row = self.conn.execute(
                "SELECT title FROM chapters WHERE book_id = ? AND chapter_index = ?",
                (book_id, chapter_index),
            ).fetchone()
            rows = self.conn.execute(
                """
                SELECT s.content FROM sentences s
                JOIN chapters c ON c.id = s.chapter_id
                WHERE s.book_id = ? AND c.chapter_index = ?
                ORDER BY s.sentence_index
                """,
                (book_id, chapter_index),
            ).fetchall()
        return {
            "title": title_row["title"] if title_row else None,
            "sentences": [r["content"] for r in rows],
        }

    # --- estado de lectura -------------------------------------------- #
    def save_reading_state(self, book_id: int, chapter_index: int, sentence_index: int,
                           user_id: int = ADMIN_USER_ID) -> None:
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO reading_state (user_id, book_id, chapter_index, sentence_index, updated_at)
                VALUES (?, ?, ?, ?, datetime('now','localtime'))
                ON CONFLICT(user_id, book_id) DO UPDATE SET
                    chapter_index  = excluded.chapter_index,
                    sentence_index = excluded.sentence_index,
                    updated_at     = excluded.updated_at
                """,
                (user_id, book_id, chapter_index, sentence_index),
            )
            self.conn.commit()

    def load_reading_state(self, book_id: int, user_id: int = ADMIN_USER_ID) -> dict:
        with self._lock:
            row = self.conn.execute(
                "SELECT chapter_index, sentence_index FROM reading_state "
                "WHERE user_id = ? AND book_id = ?",
                (user_id, book_id),
            ).fetchone()
        if row is None:
            return {"chapter_index": 0, "sentence_index": 0}
        return {"chapter_index": row["chapter_index"], "sentence_index": row["sentence_index"]}

    # --- caché LLM ----------------------------------------------------- #
    def get_cached_translation(self, source_text: str, target_lang: str, kind: str) -> str | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT result FROM translations "
                "WHERE source_text = ? AND target_lang = ? AND kind = ?",
                (source_text, target_lang, kind),
            ).fetchone()
        return row["result"] if row else None

    def cache_translation(self, source_text: str, result: str, target_lang: str, kind: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO translations (source_text, target_lang, kind, result) "
                "VALUES (?, ?, ?, ?)",
                (source_text, target_lang, kind, result),
            )
            self.conn.commit()

    # --- vocabulario + repetición espaciada (SM-2) --------------------- #
    def add_vocab(self, term, translation, example="", lang="en", book_id=None,
                  simple_example="") -> int:
        with self._lock:
            ex = self.conn.execute(
                "SELECT id FROM vocabulary WHERE term = ? AND IFNULL(book_id,0) = IFNULL(?,0)",
                (term, book_id),
            ).fetchone()
            if ex:
                return ex["id"]
            cur = self.conn.execute(
                "INSERT INTO vocabulary (book_id, term, translation, example, lang, "
                "simple_example, due) VALUES (?, ?, ?, ?, ?, ?, date('now','localtime'))",
                (book_id, term, translation, example, lang, simple_example),
            )
            self.conn.commit()
            return cur.lastrowid

    def list_vocab(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT id, term, translation, example, simple_example, lang, reps, due, "
                "(due <= date('now','localtime')) AS is_due FROM vocabulary ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def due_vocab(self, new_limit: int = 20, ahead: bool = False) -> list[dict]:
        """Con ahead=True devuelve también las que aún no tocan, las más
        próximas primero: si quieres estudiar hoy, la app no debe impedírtelo."""
        cols = ("id, term, translation, example, simple_example, lang, "
                "reps, ease, interval_days")
        budget = self.review_budget_left()   # fuera del lock: no es reentrante
        with self._lock:
            reviews = self.conn.execute(
                f"SELECT {cols} FROM vocabulary WHERE reps >= 1 AND due <= date('now','localtime') "
                "ORDER BY due, created_at LIMIT ?", (budget,)
            ).fetchall()
            rem = max(0, new_limit - self._new_intro_today_locked("vocab"))
            new = self.conn.execute(
                f"SELECT {cols} FROM vocabulary WHERE reps = 0 AND due <= date('now','localtime') "
                "ORDER BY created_at LIMIT ?", (rem,)
            ).fetchall()
            extra = []
            if ahead and not reviews and not new:
                # PRIMERO las palabras que acabas de guardar y que el candado
                # diario dejó fuera: vencen HOY, no mañana. Buscar solo en el
                # futuro las escondía justo cuando querías estudiarlas.
                extra = self.conn.execute(
                    f"SELECT {cols} FROM vocabulary WHERE reps = 0 "
                    "AND due <= date('now','localtime') ORDER BY created_at LIMIT 20"
                ).fetchall()
                if not extra:   # nada nuevo pendiente: adelanta lo de días futuros
                    extra = self.conn.execute(
                        f"SELECT {cols} FROM vocabulary WHERE due > date('now','localtime') "
                        "ORDER BY due, created_at LIMIT 20"
                    ).fetchall()
        return [dict(r) for r in list(reviews) + list(new) + list(extra)]

    def grade_vocab(self, vid: int, grade: str) -> None:
        with self._lock:
            row = self.conn.execute(
                "SELECT ease, interval_days, reps FROM vocabulary WHERE id = ?", (vid,)
            ).fetchone()
            if not row:
                return
            ease, interval, reps = _sm2(row["ease"], row["interval_days"], row["reps"], grade)
            self.conn.execute(
                "UPDATE vocabulary SET ease=?, interval_days=?, reps=?, "
                "due=date('now','localtime','+' || ? || ' days') WHERE id=?",
                (ease, interval, reps, interval, vid),
            )
            if row["reps"] == 0 and reps >= 1:  # tarjeta nueva introducida hoy
                self._bump_new_intro_locked("vocab")
            self._log_review_locked()
            self.conn.commit()

    def _bump_new_intro_locked(self, scope, user_id: int = ADMIN_USER_ID) -> None:
        self.conn.execute(
            "INSERT INTO new_intro (user_id, day, scope, count) "
            "VALUES (?, date('now','localtime'), ?, 1) "
            "ON CONFLICT(user_id, day, scope) DO UPDATE SET count = count + 1",
            (user_id, scope))

    def _new_intro_today_locked(self, scope, user_id: int = ADMIN_USER_ID) -> int:
        r = self.conn.execute(
            "SELECT count FROM new_intro "
            "WHERE user_id = ? AND day = date('now','localtime') AND scope = ?",
            (user_id, scope)
        ).fetchone()
        return r["count"] if r else 0

    def _log_review_locked(self, user_id: int = ADMIN_USER_ID) -> None:
        """Registra un repaso hoy (para las rachas). Requiere el lock ya tomado."""
        self.conn.execute(
            "INSERT INTO study_log (user_id, day, reviews) "
            "VALUES (?, date('now','localtime'), 1) "
            "ON CONFLICT(user_id, day) DO UPDATE SET reviews = reviews + 1", (user_id,)
        )

    def get_streak(self, user_id: int = ADMIN_USER_ID) -> dict:
        with self._lock:
            rows = [r["day"] for r in self.conn.execute(
                "SELECT day FROM study_log WHERE user_id = ? AND reviews > 0 "
                "ORDER BY day DESC", (user_id,)
            )]
            total = self.conn.execute(
                "SELECT COALESCE(SUM(reviews),0) n FROM study_log"
            ).fetchone()["n"]
            today_reviews = self.conn.execute(
                "SELECT COALESCE(reviews,0) n FROM study_log WHERE day=date('now','localtime')"
            ).fetchone()
            today_reviews = today_reviews["n"] if today_reviews else 0
            today_min = self.conn.execute(
                "SELECT COALESCE(SUM(seconds),0) n FROM activity_log WHERE day=date('now','localtime')"
            ).fetchone()["n"]
        s = set(rows)
        today = datetime.date.today()
        yday = today - datetime.timedelta(days=1)
        studied_today = today.isoformat() in s
        extra = {"total_reviews": total, "today_reviews": today_reviews,
                 "today_min": round(today_min / 60)}
        if not studied_today and yday.isoformat() not in s:
            return {"current": 0, "today": studied_today, **extra}
        d = today if studied_today else yday
        streak = 0
        while d.isoformat() in s:
            streak += 1
            d -= datetime.timedelta(days=1)
        return {"current": streak, "today": studied_today, **extra}

    def new_vocab(self, limit: int = 10) -> list[dict]:
        """Palabras SIN VER, saltándose el candado diario (a petición tuya)."""
        cols = ("id, term, translation, example, simple_example, lang, "
                "reps, ease, interval_days")
        with self._lock:
            rows = self.conn.execute(
                f"SELECT {cols} FROM vocabulary WHERE reps = 0 ORDER BY created_at LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def set_simple_example(self, vid: int, text: str) -> None:
        with self._lock:
            self.conn.execute("UPDATE vocabulary SET simple_example=? WHERE id=?", (text, vid))
            self.conn.commit()

    def delete_vocab(self, vid: int) -> bool:
        """False si esa palabra no existía (para que la API responda 404)."""
        with self._lock:
            cur = self.conn.execute("DELETE FROM vocabulary WHERE id = ?", (vid,))
            self.conn.commit()
            return cur.rowcount > 0

    def vocab_stats(self) -> dict:
        with self._lock:
            total = self.conn.execute("SELECT COUNT(*) n FROM vocabulary").fetchone()["n"]
            due = self.conn.execute(
                "SELECT COUNT(*) n FROM vocabulary WHERE due <= date('now','localtime')"
            ).fetchone()["n"]
            new = self.conn.execute(
                "SELECT COUNT(*) n FROM vocabulary WHERE reps = 0"
            ).fetchone()["n"]
            learning = self.conn.execute(
                "SELECT COUNT(*) n FROM vocabulary WHERE reps BETWEEN 1 AND 2"
            ).fetchone()["n"]
            learned = self.conn.execute(
                "SELECT COUNT(*) n FROM vocabulary WHERE reps >= 3"
            ).fetchone()["n"]
            # palabras añadidas por día (últimos 14 días) para la gráfica
            hist = self.conn.execute(
                "SELECT date(created_at) d, COUNT(*) n FROM vocabulary "
                "WHERE created_at >= date('now','localtime','-13 days') GROUP BY date(created_at)"
            ).fetchall()
            # cuántas nuevas llevas hoy: explica por qué Review deja de
            # ofrecerte palabras aunque acabes de guardarlas
            new_today = self._new_intro_today_locked("vocab")
        return {
            "total": total, "due": due, "new": new,
            "learning": learning, "learned": learned,
            "new_today": new_today, "new_limit": 20,
            "history": {r["d"]: r["n"] for r in hist},
        }

    # --- decks de aprendizaje (estáticos) ------------------------------ #
    def ensure_deck(self, key, name, description, lang="en", sort_order=0) -> int:
        with self._lock:
            row = self.conn.execute("SELECT id FROM decks WHERE key = ?", (key,)).fetchone()
            if row:
                return row["id"]
            cur = self.conn.execute(
                "INSERT INTO decks (key, name, description, lang, sort_order) VALUES (?,?,?,?,?)",
                (key, name, description, lang, sort_order),
            )
            self.conn.commit()
            return cur.lastrowid

    def add_deck_card(self, deck_id, position, front, translation, note, audio_file,
                      category="") -> None:
        with self._lock:
            self.conn.execute(
                # sin estado SRS: el progreso es de cada usuario y vive en
                # card_progress, así que volver a sembrar contenido no puede
                # tocarlo. OR IGNORE respeta las tarjetas que ya existen.
                "INSERT OR IGNORE INTO deck_cards "
                "(deck_id, position, front, translation, note, audio_file, category) "
                "VALUES (?,?,?,?,?,?,?)",
                (deck_id, position, front, translation, note, audio_file, category),
            )
            self.conn.commit()

    def deck_card_count(self, deck_id) -> int:
        with self._lock:
            return self.conn.execute(
                "SELECT COUNT(*) n FROM deck_cards WHERE deck_id = ?", (deck_id,)
            ).fetchone()["n"]

    # --- ajustes de estudio -------------------------------------------- #
    # Un tope de repasos es una decisión personal, así que los ajustes van por
    # usuario. Mientras no haya login (Fase 1) el único que hay es el admin.
    def get_setting(self, key: str, default: str = "",
                    user_id: int = ADMIN_USER_ID) -> str:
        with self._lock:
            row = self.conn.execute(
                "SELECT value FROM user_settings WHERE user_id = ? AND key = ?",
                (user_id, key)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str,
                    user_id: int = ADMIN_USER_ID) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO user_settings (user_id, key, value) VALUES (?,?,?) "
                "ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value",
                (user_id, key, str(value)))
            self.conn.commit()

    def review_budget_left(self, user_id: int = ADMIN_USER_ID) -> int:
        """Repasos que aún caben hoy según el tope GLOBAL del usuario.

        El tope es global, no por mazo: con 6 mazos, un tope de 20 en cada uno
        serían 120 al día, que es justo el problema que se quiere evitar.
        """
        cap = int(self.get_setting("review_limit", str(DEFAULT_REVIEW_LIMIT),
                                   user_id) or 0)
        if cap <= 0:
            return 10 ** 6            # 0 = sin tope
        return max(0, cap - self.reviews_today(user_id))

    def reviews_today(self, user_id: int = ADMIN_USER_ID) -> int:
        with self._lock:
            row = self.conn.execute(
                "SELECT COALESCE(reviews,0) n FROM study_log "
                "WHERE user_id = ? AND day = date('now','localtime')", (user_id,)
            ).fetchone()
        return row["n"] if row else 0

    def review_backlog(self, user_id: int = ADMIN_USER_ID) -> dict:
        """Repasos vencidos: los de hoy y los que arrastras de días anteriores."""
        with self._lock:
            hoy = self.conn.execute(
                "SELECT COUNT(*) n FROM card_progress "
                "WHERE user_id = ? AND reps>0 AND due<=date('now','localtime')", (user_id,)
            ).fetchone()["n"]
            hoy += self.conn.execute(
                "SELECT COUNT(*) n FROM vocabulary "
                "WHERE user_id = ? AND reps>0 AND due<=date('now','localtime')", (user_id,)
            ).fetchone()["n"]
            atras = self.conn.execute(
                "SELECT COUNT(*) n FROM card_progress "
                "WHERE user_id = ? AND reps>0 AND due<date('now','localtime')", (user_id,)
            ).fetchone()["n"]
        return {"due": hoy, "overdue": atras}

    def set_deck_new_limit(self, deck_id: int, limit: int,
                           user_id: int = ADMIN_USER_ID) -> None:
        """El tope de tarjetas nuevas es el ritmo de estudio de cada uno, no una
        propiedad del mazo: se guarda como ajuste del usuario. decks.new_limit
        se queda como el valor por defecto que fija el admin con el contenido."""
        self.set_setting(f"deck_new_limit:{deck_id}", max(0, int(limit)), user_id)

    def _deck_new_limit_locked(self, deck_id: int, user_id: int) -> int:
        """El tope del usuario si lo cambió; si no, el que trae el mazo."""
        row = self.conn.execute(
            "SELECT value FROM user_settings WHERE user_id = ? AND key = ?",
            (user_id, f"deck_new_limit:{deck_id}")).fetchone()
        if row:
            return max(0, int(row["value"]))
        d = self.conn.execute(
            "SELECT new_limit FROM decks WHERE id = ?", (deck_id,)).fetchone()
        return d["new_limit"] if d else 10

    def list_decks(self, user_id: int = ADMIN_USER_ID) -> list[dict]:
        with self._lock:
            decks = self.conn.execute(
                "SELECT id, key, name, description, lang "
                "FROM decks ORDER BY sort_order, id"
            ).fetchall()
            out = []
            for d in decks:
                total = self.conn.execute(
                    "SELECT COUNT(*) n FROM deck_cards WHERE deck_id = ?", (d["id"],)
                ).fetchone()["n"]
                due = self.conn.execute(
                    f"SELECT COUNT(*) n {self._CARD_FROM} "
                    f"WHERE c.deck_id = ? AND {self._CARD_DUE} <= date('now','localtime')",
                    (user_id, d["id"]),
                ).fetchone()["n"]
                unseen = self.conn.execute(
                    f"SELECT COUNT(*) n {self._CARD_FROM} "
                    "WHERE c.deck_id = ? AND COALESCE(p.reps,0) = 0",
                    (user_id, d["id"]),
                ).fetchone()["n"]
                # cuántas nuevas has empezado hoy: explica por qué "Review" deja
                # de ofrecer tarjetas nuevas aunque queden sin ver
                new_today = self._new_intro_today_locked("deck:" + str(d["id"]), user_id)
                out.append({**dict(d),
                            "new_limit": self._deck_new_limit_locked(d["id"], user_id),
                            "total": total, "due": due,
                            "unseen": unseen, "new_today": new_today})
        return out

    def deck_due_cards(self, deck_id, new_limit=None, ahead: bool = False,
                       user_id: int = ADMIN_USER_ID) -> list[dict]:
        """Repaso inteligente (SRS): repasos que tocan hoy + máx `new_limit` NUEVAS
        (descontando las nuevas ya introducidas hoy = candado diario).
        Con ahead=True, si no queda nada pendiente devuelve las siguientes."""
        budget = self.review_budget_left(user_id)  # fuera del lock: no es reentrante
        with self._lock:
            # ORDER BY due: primero lo más atrasado. Con tope, servir en otro
            # orden dejaría tarjetas viejas sin salir nunca.
            reviews = self.conn.execute(
                f"SELECT {self._CARD_COLS} {self._CARD_FROM} "
                "WHERE c.deck_id = ? AND COALESCE(p.reps,0) >= 1 "
                f"AND {self._CARD_DUE} <= date('now','localtime') "
                f"ORDER BY {self._CARD_DUE}, c.position LIMIT ?",
                (user_id, deck_id, budget),
            ).fetchall()
            if new_limit is None:
                new_limit = self._deck_new_limit_locked(deck_id, user_id)
            rem = max(0, new_limit
                      - self._new_intro_today_locked("deck:" + str(deck_id), user_id))
            new = self.conn.execute(
                f"SELECT {self._CARD_COLS} {self._CARD_FROM} "
                "WHERE c.deck_id = ? AND COALESCE(p.reps,0) = 0 "
                "ORDER BY c.position LIMIT ?", (user_id, deck_id, rem),
            ).fetchall()
            extra = []
            if ahead and not reviews and not new:
                extra = self.conn.execute(
                    f"SELECT {self._CARD_COLS} {self._CARD_FROM} "
                    f"WHERE c.deck_id = ? AND {self._CARD_DUE} > date('now','localtime') "
                    f"ORDER BY {self._CARD_DUE}, c.position LIMIT 20",
                    (user_id, deck_id),
                ).fetchall()
        return [dict(r) for r in list(reviews) + list(new) + list(extra)]

    def cards_without_example(self, deck_id=None) -> list[dict]:
        """Tarjetas cuyo 'note' no es un ejemplo (vacío o sin el separador '—')."""
        sql = ("SELECT id, deck_id, front, translation FROM deck_cards "
               "WHERE IFNULL(note,'') NOT LIKE '%—%'")
        args: list = []
        if deck_id is not None:
            sql += " AND deck_id = ?"
            args.append(deck_id)
        sql += " ORDER BY deck_id, position"
        with self._lock:
            return [dict(r) for r in self.conn.execute(sql, args)]

    def set_card_note(self, card_id, note) -> None:
        with self._lock:
            self.conn.execute("UPDATE deck_cards SET note=? WHERE id=?", (note, card_id))
            self.conn.commit()

    def deck_new_cards(self, deck_id, limit=10,
                       user_id: int = ADMIN_USER_ID) -> list[dict]:
        """Tarjetas SIN VER de un mazo, saltándose el candado diario.

        El candado existe para que no te satures, pero es tuyo: si hoy quieres
        aprender más, la app no debe escondértelas sin explicación.
        """
        with self._lock:
            rows = self.conn.execute(
                f"SELECT {self._CARD_COLS} {self._CARD_FROM} "
                "WHERE c.deck_id = ? AND COALESCE(p.reps,0) = 0 "
                "ORDER BY c.position LIMIT ?", (user_id, deck_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def deck_study_cards(self, deck_id, user_id: int = ADMIN_USER_ID) -> list[dict]:
        """TODAS las tarjetas del mazo (sin límite diario), las pendientes primero."""
        with self._lock:
            rows = self.conn.execute(
                f"SELECT {self._CARD_COLS} {self._CARD_FROM} WHERE c.deck_id = ? "
                f"ORDER BY ({self._CARD_DUE} <= date('now','localtime')) DESC, c.position",
                (user_id, deck_id),
            ).fetchall()
        return [dict(r) for r in rows]

    def grade_deck_card(self, card_id, grade, user_id: int = ADMIN_USER_ID) -> None:
        with self._lock:
            row = self.conn.execute(
                "SELECT c.deck_id, COALESCE(p.ease,2.5) AS ease, "
                "COALESCE(p.interval_days,0) AS interval_days, "
                "COALESCE(p.reps,0) AS reps "
                f"{self._CARD_FROM} WHERE c.id = ?", (user_id, card_id)
            ).fetchone()
            if not row:
                return
            ease, interval, reps = _sm2(row["ease"], row["interval_days"], row["reps"], grade)
            self.conn.execute(
                "INSERT INTO card_progress "
                "(user_id, card_id, ease, interval_days, reps, due) "
                "VALUES (?, ?, ?, ?, ?, date('now','localtime','+' || ? || ' days')) "
                "ON CONFLICT(user_id, card_id) DO UPDATE SET "
                "ease = excluded.ease, interval_days = excluded.interval_days, "
                "reps = excluded.reps, due = excluded.due",
                (user_id, card_id, ease, interval, reps, interval),
            )
            if row["reps"] == 0 and reps >= 1:
                self._bump_new_intro_locked("deck:" + str(row["deck_id"]), user_id)
            self._log_review_locked(user_id)
            self.conn.commit()

    # --- writings (Writing) + diario de errores ------------------------ #
    def save_writing(self, title, original, corrected, level, assessment="") -> int:
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO writings (title, original, corrected, level, assessment) "
                "VALUES (?,?,?,?,?)",
                (title, original, corrected, level, assessment),
            )
            self.conn.commit()
            return cur.lastrowid

    def add_writing_error(self, writing_id, original, correction, explanation,
                          category="other") -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO writing_errors (writing_id, original, correction, explanation, "
                "category) VALUES (?,?,?,?,?)",
                (writing_id, original, correction, explanation, category),
            )
            self.conn.commit()

    def save_writing_upgrade(self, wid, upgraded, upgrade_level) -> None:
        """Guarda la reescritura en SUS columnas. No toca 'corrected' ni 'level':
        el nivel de la tabla es el TUYO, no el objetivo del upgrade."""
        with self._lock:
            self.conn.execute(
                "UPDATE writings SET upgraded=?, upgrade_level=? WHERE id=?",
                (upgraded, upgrade_level, wid),
            )
            self.conn.commit()

    def list_writings(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT id, title, level, upgrade_level, created_at, "
                "substr(original,1,80) AS preview "
                "FROM writings ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_writing(self, wid) -> dict | None:
        with self._lock:
            row = self.conn.execute("SELECT * FROM writings WHERE id=?", (wid,)).fetchone()
        return dict(row) if row else None

    def delete_writing(self, wid) -> bool:
        """Borra un escrito y los errores de su diario. False si no existía."""
        with self._lock:
            cur = self.conn.execute("DELETE FROM writings WHERE id=?", (wid,))
            self.conn.execute("DELETE FROM writing_errors WHERE writing_id=?", (wid,))
            self.conn.commit()
            return cur.rowcount > 0

    def list_writing_errors(self, limit=100, category="") -> list[dict]:
        sql = ("SELECT id, original, correction, explanation, category, created_at, "
               "reviewed, (lesson IS NOT NULL) AS has_lesson FROM writing_errors ")
        args: list = []
        if category:
            sql += "WHERE category = ? "
            args.append(category)
        sql += "ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            rows = self.conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]

    # --- lecciones generadas desde tus errores -------------------------- #
    def save_custom_lesson(self, category, title, level, payload, error_count) -> int:
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO custom_lessons (category,title,level,payload,error_count) "
                "VALUES (?,?,?,?,?)",
                (category, title, level, json.dumps(payload, ensure_ascii=False), error_count))
            self.conn.commit()
            return cur.lastrowid

    def list_custom_lessons(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT id, category, title, level, error_count, done, created_at "
                "FROM custom_lessons ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def get_custom_lesson(self, lid) -> dict | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM custom_lessons WHERE id = ?", (lid,)).fetchone()
        if not row:
            return None
        out = dict(row)
        out["payload"] = json.loads(out["payload"])
        return out

    def set_custom_lesson_done(self, lid, done=True) -> bool:
        with self._lock:
            cur = self.conn.execute("UPDATE custom_lessons SET done=? WHERE id=?",
                                    (1 if done else 0, lid))
            self.conn.commit()
            return cur.rowcount > 0

    def delete_custom_lesson(self, lid) -> bool:
        with self._lock:
            cur = self.conn.execute("DELETE FROM custom_lessons WHERE id=?", (lid,))
            self.conn.commit()
            return cur.rowcount > 0

    def errors_by_category(self, category: str, limit: int = 12) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT original, correction, explanation FROM writing_errors "
                "WHERE COALESCE(NULLIF(category,''),'unclassified') = ? "
                "ORDER BY created_at DESC LIMIT ?", (category, limit)).fetchall()
        return [dict(r) for r in rows]

    def get_writing_error(self, eid) -> dict | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM writing_errors WHERE id = ?", (eid,)).fetchone()
        if not row:
            return None
        out = dict(row)
        if out.get("lesson"):
            out["lesson"] = json.loads(out["lesson"])
        return out

    def set_error_lesson(self, eid, lesson) -> None:
        with self._lock:
            self.conn.execute("UPDATE writing_errors SET lesson=? WHERE id=?",
                              (json.dumps(lesson, ensure_ascii=False), eid))
            self.conn.commit()

    def set_error_reviewed(self, eid, reviewed=True) -> bool:
        with self._lock:
            cur = self.conn.execute("UPDATE writing_errors SET reviewed=? WHERE id=?",
                                    (1 if reviewed else 0, eid))
            self.conn.commit()
            return cur.rowcount > 0

    def writing_error_summary(self) -> list[dict]:
        """Tus errores agrupados por tipo, del más repetido al menos.

        Es lo que convierte el diario en algo accionable: no "24 errores
        sueltos" sino "8 de preposiciones", que sí se puede estudiar.
        """
        with self._lock:
            rows = self.conn.execute(
                "SELECT COALESCE(NULLIF(category,''),'unclassified') AS category, "
                "COUNT(*) AS n, MAX(created_at) AS last_seen "
                "FROM writing_errors GROUP BY 1 ORDER BY n DESC, last_seen DESC"
            ).fetchall()
        # los porcentajes se calculan SOLO sobre lo clasificado: si no, los
        # errores antiguos dominan el diagnóstico y apuntan al sitio equivocado
        total = sum(r["n"] for r in rows if r["category"] != "unclassified") or 1
        out = [{"category": r["category"],
                "label": ERROR_CATEGORIES.get(r["category"], "Otros"),
                "n": r["n"],
                "pct": 0 if r["category"] == "unclassified" else round(r["n"] * 100 / total),
                "last_seen": r["last_seen"]} for r in rows]
        # sin clasificar siempre al final, por informativo
        out.sort(key=lambda s: (s["category"] == "unclassified", -s["n"]))
        return out

    # --- test de nivel ------------------------------------------------- #
    def save_test_result(self, level, correct, total) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO test_results (level, correct, total) VALUES (?,?,?)",
                (level, correct, total))
            self.conn.commit()

    def last_test(self) -> dict | None:
        with self._lock:
            r = self.conn.execute(
                "SELECT level, correct, total, created_at FROM test_results "
                "ORDER BY created_at DESC LIMIT 1").fetchone()
        return dict(r) if r else None

    # --- lecciones (progreso de la ruta) ------------------------------- #
    def lesson_done_ids(self) -> list[str]:
        with self._lock:
            rows = self.conn.execute("SELECT lesson_id FROM lesson_done").fetchall()
        return [r["lesson_id"] for r in rows]

    def set_lesson_done(self, lesson_id: str, done: bool = True) -> None:
        with self._lock:
            if done:
                self.conn.execute(
                    "INSERT OR IGNORE INTO lesson_done (lesson_id) VALUES (?)", (lesson_id,))
            else:
                self.conn.execute("DELETE FROM lesson_done WHERE lesson_id=?", (lesson_id,))
            self.conn.commit()

    # --- actividad / tiempo (para estadísticas) ------------------------ #
    def log_activity(self, module, active_seconds, open_seconds,
                     user_id: int = ADMIN_USER_ID) -> None:
        with self._lock:
            if active_seconds > 0 and module:
                self.conn.execute(
                    "INSERT INTO activity_log (user_id, day, module, seconds) "
                    "VALUES (?, date('now','localtime'), ?, ?) "
                    "ON CONFLICT(user_id, day, module) DO UPDATE SET seconds = seconds + ?",
                    (user_id, module, int(active_seconds), int(active_seconds)),
                )
            if open_seconds > 0:
                self.conn.execute(
                    "INSERT INTO session_log (user_id, day, open_seconds) "
                    "VALUES (?, date('now','localtime'), ?) "
                    "ON CONFLICT(user_id, day) DO UPDATE SET open_seconds = open_seconds + ?",
                    (user_id, int(open_seconds), int(open_seconds)),
                )
            self.conn.commit()

    def get_full_stats(self, rng: str = "week",
                       user_id: int = ADMIN_USER_ID) -> dict:
        start = "date('now','localtime','-6 days')" if rng == "week" else "date('now','localtime','start of month')"
        with self._lock:
            days = self.conn.execute(
                f"SELECT day, SUM(seconds) s FROM activity_log "
                f"WHERE user_id = ? AND day >= {start} "
                "GROUP BY day ORDER BY day", (user_id,)
            ).fetchall()
            mods = self.conn.execute(
                f"SELECT module, SUM(seconds) s FROM activity_log "
                f"WHERE user_id = ? AND day >= {start} "
                "GROUP BY module", (user_id,)
            ).fetchall()
            open_s = self.conn.execute(
                f"SELECT COALESCE(SUM(open_seconds),0) s FROM session_log "
                f"WHERE user_id = ? AND day >= {start}", (user_id,)
            ).fetchone()["s"]
            active_s = self.conn.execute(
                f"SELECT COALESCE(SUM(seconds),0) s FROM activity_log "
                f"WHERE user_id = ? AND day >= {start}", (user_id,)
            ).fetchone()["s"]
            # decks: el mazo es de todos, pero "aprendidas" es de quien pregunta
            deck_rows = self.conn.execute(
                "SELECT d.name, d.key, COUNT(c.id) total, "
                "SUM(CASE WHEN COALESCE(p.reps,0)>=3 THEN 1 ELSE 0 END) learned "
                "FROM decks d LEFT JOIN deck_cards c ON c.deck_id = d.id "
                "LEFT JOIN card_progress p ON p.card_id = c.id AND p.user_id = ? "
                "GROUP BY d.id ORDER BY d.sort_order", (user_id,)
            ).fetchall()
            writings = self.conn.execute(
                "SELECT COUNT(*) n FROM writings WHERE user_id = ?", (user_id,)
            ).fetchone()["n"]
            heat = self.conn.execute(
                "SELECT day, SUM(seconds) s FROM activity_log WHERE user_id = ? "
                "AND day >= date('now','localtime','-97 days') "
                "GROUP BY day", (user_id,)
            ).fetchall()
        modules = {r["module"]: round(r["s"] / 60) for r in mods}
        per_day = {r["day"]: round(r["s"] / 60) for r in days}
        procrast = max(0, open_s - active_s)
        decks = [{"name": r["name"], "key": r["key"], "total": r["total"],
                  "learned": r["learned"] or 0} for r in deck_rows]
        deck_total = sum(d["total"] for d in decks)
        deck_learned = sum(d["learned"] for d in decks)
        vocab = self.vocab_stats()
        streak = self.get_streak()
        reading = self._reading_progress()
        # área de oportunidad: módulo de práctica con menos minutos
        practice = {m: modules.get(m, 0) for m in ("reading", "decks", "writing", "flashcards")}
        least = min(practice, key=practice.get)
        avg = round(sum(practice.values()) / max(1, len(practice)))
        suggest = max(10, min(60, avg - practice[least])) if avg > practice[least] else 15
        names = {"reading": "Reading", "decks": "Decks", "writing": "Writing", "flashcards": "Flashcards"}
        return {
            "range": rng,
            "per_day": per_day,
            "modules": modules,
            "open_min": round(open_s / 60),
            "active_min": round(active_s / 60),
            "procrastination_min": round(procrast / 60),
            "decks": decks, "deck_total": deck_total, "deck_learned": deck_learned,
            "writings": writings, "reading": reading,
            "vocab": vocab, "streak": streak,
            "opportunity": {"module": least, "name": names[least],
                            "minutes": practice[least], "suggest_min": suggest},
            "heatmap": {r["day"]: round(r["s"] / 60) for r in heat},
        }

    def nav_alerts(self) -> dict:
        """Días sin usar cada módulo de práctica (para el recordatorio del nav)."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT module, MAX(day) last FROM activity_log GROUP BY module"
            ).fetchall()
            any_act = self.conn.execute("SELECT COUNT(*) n FROM activity_log").fetchone()["n"]
        last = {r["module"]: r["last"] for r in rows}
        today = datetime.date.today()
        stale = {}
        for m in ("reading", "decks", "writing", "flashcards"):
            if m not in last:
                stale[m] = 999
            else:
                stale[m] = (today - datetime.date.fromisoformat(last[m])).days
        return {"stale": stale, "has_activity": bool(any_act)}

    def _reading_progress(self) -> list:
        """Progreso por CAPÍTULOS COMPLETADOS (check) por libro."""
        with self._lock:
            books = self.conn.execute("SELECT id, title FROM books").fetchall()
            out = []
            for b in books:
                total = self.conn.execute(
                    "SELECT COUNT(*) n FROM chapters WHERE book_id=?", (b["id"],)
                ).fetchone()["n"] or 1
                done = self.conn.execute(
                    "SELECT COUNT(*) n FROM chapters WHERE book_id=? AND COALESCE(done,0)=1",
                    (b["id"],)).fetchone()["n"]
                out.append({"title": b["title"], "pct": round(done / total * 100),
                            "done": done, "total": total})
        return out


# --------------------------------------------------------------------------- #
# SM-2: algoritmo de repetición espaciada (como Anki)
# --------------------------------------------------------------------------- #
# Pasos iniciales, en días. La curva del olvido cae en picado los primeros
# días: repasar pronto y varias veces al principio fija mucho mejor que saltar
# a intervalos largos. Antes era 1→3→8→20 ('easy' empezaba en 4), demasiado
# separado justo donde más se olvida. Pasado el último paso, el intervalo ya
# crece solo multiplicando por 'ease'.
# El primer 0 es un paso el MISMO día: una palabra que ves por primera vez
# vuelve a salir hoy antes de irse a mañana. Verla una sola vez y no repetirla
# hasta el día siguiente es donde más se pierde: la primera consolidación pasa
# en la misma sesión.
_STEPS_GOOD = (0, 1, 2, 4, 7)
_STEPS_EASY = (2, 4, 7, 12)   # 'easy' = ya la sabías: no necesita repaso hoy
# Topes: sin ellos, marcar 'easy' varias veces disparaba el intervalo a más de
# 1000 días (el 'ease' crecía sin límite y además se multiplicaba por 1.3).
# Una tarjeta que no vuelves a ver en 3 años no es aprendizaje, es un olvido
# programado.
_EASE_MAX = 3.0
_INTERVAL_MAX = 365


# --------------------------------------------------------------------------- #
# Cloze: convertir el ejemplo de una tarjeta en un hueco que hay que rellenar.
#
# Por qué: reconocer (ver «because» y recordar «porque») es la forma más débil
# de practicar — genera familiaridad, no lengua usable. Recuperar la palabra
# DENTRO de una frase obliga a elegir la forma correcta, que es justo donde
# fallan las preposiciones y los tiempos verbales.
# --------------------------------------------------------------------------- #
_IRREGULAR_PAST = {
    "run": "ran", "go": "went", "take": "took", "get": "got", "give": "gave",
    "come": "came", "make": "made", "find": "found", "think": "thought",
    "bring": "brought", "buy": "bought", "catch": "caught", "hold": "held",
    "keep": "kept", "leave": "left", "put": "put", "say": "said", "see": "saw",
    "sit": "sat", "stand": "stood", "tell": "told", "break": "broke", "eat": "ate",
    "fall": "fell", "feel": "felt", "grow": "grew", "hear": "heard", "know": "knew",
    "lose": "lost", "meet": "met", "pay": "paid", "send": "sent", "speak": "spoke",
    "spend": "spent", "teach": "taught", "wear": "wore", "write": "wrote",
    "do": "did", "have": "had", "be": "was",
}


def _word_forms(word: str) -> list[str]:
    """Formas flexionadas plausibles de una palabra (sin diccionario)."""
    w = word.lower()
    forms = {w, w + "s", w + "es", w + "ed", w + "ing", w + "d"}
    if w.endswith("e"):
        forms.add(w[:-1] + "ing")
    if w.endswith("y"):
        forms |= {w[:-1] + "ies", w[:-1] + "ied"}
    if len(w) > 2 and w[-1] not in "aeiouy":
        forms |= {w + w[-1] + "ing", w + w[-1] + "ed"}
    if w in _IRREGULAR_PAST:
        forms.add(_IRREGULAR_PAST[w])
    return sorted(forms, key=len, reverse=True)


def _forms_alt(words: list[str]) -> str:
    return "(?:" + "|".join(re.escape(f) for w in words for f in _word_forms(w)) + ")"


def build_cloze(front: str, note: str, min_context: int = 2) -> dict | None:
    """Del ejemplo de una tarjeta saca {sentence con hueco, answer, translation}.

    None si la palabra no aparece en el ejemplo, o si al quitarla no queda
    contexto suficiente: «_____.» no es un ejercicio, es adivinar.
    """
    if not front or not note or "—" not in note:
        return None
    english, spanish = [p.strip() for p in note.split("—", 1)]
    if "," in front:
        # los verbos vienen como "be, was, been": vale cualquiera de las formas
        alts = [p.strip() for p in front.split(",") if p.strip()]
        pattern = re.compile(r"\b" + _forms_alt(alts) + r"\b", re.I)
    else:
        parts = re.findall(r"[A-Za-z']+", front)
        if not parts:
            return None
        # permite hasta 2 palabras intercaladas: "figure out" → "figure it out"
        joined = r"\W+(?:\w+\W+){0,2}".join(_forms_alt([p]) for p in parts)
        pattern = re.compile(r"\b" + joined + r"\b", re.I)
    match = pattern.search(english)
    if not match:
        return None
    rest = english[:match.start()] + english[match.end():]
    if len(re.findall(r"[A-Za-z']+", rest)) < min_context:
        return None
    return {
        "sentence": english[:match.start()] + "_____" + english[match.end():],
        "answer": match.group(0),
        "target": front,
        "translation": spanish,
    }


def normalize_answer(text: str) -> str:
    """Para comparar lo que escribes con la respuesta: ignora mayúsculas,
    puntuación y espacios de más. Un acierto no debe fallar por una coma."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s']", "", (text or "").lower())).strip()


def check_answer(typed: str, *accepted: str) -> bool:
    got = normalize_answer(typed)
    if not got:
        return False
    for ok in accepted:
        if not ok:
            continue
        if got == normalize_answer(ok):
            return True
        # "be, was, been": vale cualquiera de las formas listadas
        if "," in ok and got in {normalize_answer(p) for p in ok.split(",")}:
            return True
    return False


def _syllables(word: str) -> int:
    """Sílabas aproximadas en inglés. No es exacto, pero para promediar sobre
    miles de palabras la aproximación es suficiente y no necesita diccionario."""
    w = re.sub(r"e$", "", word.lower())
    groups = re.findall(r"[aeiouy]+", w)
    return max(1, len(groups))


# Flesch Reading Ease → nivel CEFR aproximado. Los cortes salen de comparar el
# índice con lecturas graduadas: no es una medición oficial, es una señal para
# avisarte ANTES de que empieces un libro que te va a frustrar.
_FLESCH_CEFR = ((80, "A2"), (70, "B1"), (60, "B2"), (50, "C1"), (0, "C2"))


def readability(sentences: list[str]) -> dict:
    """Estima la dificultad de un texto: {flesch, level, words_per_sentence, ...}."""
    sentences = [s for s in sentences if s and s.strip()]
    if not sentences:
        return {"flesch": 0.0, "level": "", "words_per_sentence": 0.0,
                "long_word_pct": 0.0, "sentences": 0}
    words = [w.lower() for s in sentences for w in re.findall(r"[A-Za-z']+", s)]
    if not words:
        return {"flesch": 0.0, "level": "", "words_per_sentence": 0.0,
                "long_word_pct": 0.0, "sentences": len(sentences)}
    wps = len(words) / len(sentences)
    spw = sum(_syllables(w) for w in words) / len(words)
    flesch = 206.835 - 1.015 * wps - 84.6 * spw
    level = next(lv for cut, lv in _FLESCH_CEFR if flesch >= cut)
    return {
        "flesch": round(flesch, 1),
        "level": level,
        "words_per_sentence": round(wps, 1),
        "long_word_pct": round(sum(1 for w in words if len(w) >= 9) / len(words) * 100, 1),
        "sentences": len(sentences),
    }


def level_gap(book_level: str, your_level: str) -> int:
    """Cuántos escalones CEFR separa un libro de tu nivel. Negativo = más fácil."""
    if book_level not in CEFR_LEVELS or your_level not in CEFR_LEVELS:
        return 0
    return CEFR_LEVELS.index(book_level) - CEFR_LEVELS.index(your_level)


def download_epub(url: str, dest_path: str, timeout: int = 60) -> int:
    """Descarga un EPUB. Devuelve los bytes escritos.

    Usa el almacén de certificados de `certifi`: el Python de macOS suele venir
    sin CA configurada y falla el SSL contra cualquier sitio real.
    """
    import ssl
    import urllib.request
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "AppIdiomas/1.0 (lector local)"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        data = resp.read()
    if len(data) < 1000 or not data.startswith(b"PK"):
        raise RuntimeError("La descarga no es un EPUB válido.")
    with open(dest_path, "wb") as fh:
        fh.write(data)
    return len(data)


def _round_half_up(x: float) -> int:
    """round() de Python usa redondeo bancario: round(2.5) == 2. El SM-2 espejo
    del navegador usa Math.round, que da 3. Sin esto los botones prometen un
    intervalo y el servidor programa otro."""
    return int(math.floor(x + 0.5))


def _sm2(ease: float, interval: int, reps: int, grade: str) -> tuple[float, int, int]:
    """Devuelve (ease, interval_días, reps) tras calificar una tarjeta.
    grade: 'again' (fallo) | 'hard' (difícil) | 'good' (bien) | 'easy' (fácil)."""
    if grade == "again":
        return (max(1.3, ease - 0.2), 0, 0)  # vuelve a salir hoy
    if grade == "hard":
        # tras un titubeo no se salta a un intervalo largo: se repite pronto.
        # Si aún estaba aprendiéndose (primeras veces), vuelve HOY.
        if reps < 2:
            nuevo = 0
        elif reps < len(_STEPS_GOOD):
            nuevo = 1
        else:
            nuevo = max(1, _round_half_up(interval * 1.2))
        return (max(1.3, ease - 0.15), nuevo, reps + 1)
    if grade == "easy":
        ease = min(_EASE_MAX, ease + 0.15)
    reps += 1
    steps = _STEPS_EASY if grade == "easy" else _STEPS_GOOD
    if reps <= len(steps):
        interval = steps[reps - 1]
    else:
        interval = _round_half_up(interval * ease * (1.15 if grade == "easy" else 1.0))
    # el suelo es 0, no 1: 0 significa "vuelve hoy" (paso de aprendizaje)
    return (round(ease, 3), max(0, min(_INTERVAL_MAX, interval)), reps)


# --------------------------------------------------------------------------- #
# Segmentador de oraciones (compartido)
# --------------------------------------------------------------------------- #
_ABBREV = {"mr", "mrs", "ms", "dr", "st", "vs", "etc", "e.g", "i.e", "sr", "sra", "dra"}

# Longitud máxima cómoda de una "oración" para leer/escuchar. Las más largas se
# parten en fragmentos más cortos (por ; : — y, si hace falta, por comas).
_MAX_LEN = 140


def _comma_split(s: str, maxlen: int) -> list[str]:
    """Parte una frase larga acumulando fragmentos separados por coma hasta maxlen."""
    frags = re.split(r"(?<=,)\s+", s)
    out: list[str] = []
    buf = ""
    for f in frags:
        if buf and len(buf) + len(f) + 1 > maxlen:
            out.append(buf.strip())
            buf = f
        else:
            buf = (buf + " " + f).strip() if buf else f
    if buf:
        out.append(buf.strip())
    return out


def _soft_split(s: str, maxlen: int = _MAX_LEN) -> list[str]:
    """Acorta una oración larga: primero por ; : —, luego por comas si sigue larga."""
    if len(s) <= maxlen:
        return [s]
    out: list[str] = []
    for part in re.split(r"(?<=[;:—])\s+", s):
        part = part.strip()
        if not part:
            continue
        if len(part) > maxlen:
            out.extend(_comma_split(part, maxlen))
        else:
            out.append(part)
    return [p for p in out if p]


def split_sentences(text: str) -> list[str]:
    """Segmentador ligero: corta en . ! ? … seguido de espacio y mayúscula/comilla,
    evitando abreviaturas comunes. Normaliza saltos y espacios (útil para PDF) y
    acorta las oraciones muy largas para una lectura más cómoda."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    candidate = re.sub(r'([.!?…])(["»”\')\]]?)\s+(?=[A-ZÁÉÍÓÚÑ¿¡"«])', r"\1\2\n", text)
    sentences: list[str] = []
    pending = ""
    for piece in candidate.split("\n"):
        piece = piece.strip()
        if not piece:
            continue
        if pending:
            piece = pending + " " + piece
            pending = ""
        last_word = piece.rstrip(".!?…\"»”')]").split(" ")[-1].lower()
        if last_word in _ABBREV:
            pending = piece
        else:
            sentences.append(piece)
    if pending:
        sentences.append(pending)

    # Segundo pase: acorta las oraciones demasiado largas.
    result: list[str] = []
    for s in sentences:
        result.extend(_soft_split(s))
    return result


# --------------------------------------------------------------------------- #
# PdfConverter — PDF -> EPUB (gratis)
# --------------------------------------------------------------------------- #
class PdfConverter:
    """Convierte PDF a EPUB. Prefiere Calibre (ebook-convert) si está instalado;
    si no, extrae texto con pdfminer.six y arma el EPUB con ebooklib. Todo gratis."""

    @classmethod
    def to_epub(cls, pdf_path: str) -> str:
        os.makedirs(LIBRARY_DIR, exist_ok=True)
        base = os.path.splitext(os.path.basename(pdf_path))[0]
        out_path = os.path.join(LIBRARY_DIR, f"{base}.epub")

        calibre = shutil.which("ebook-convert")
        if calibre:
            try:
                subprocess.run(
                    [calibre, pdf_path, out_path],
                    check=True, timeout=300,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    return out_path
            except Exception:
                pass  # cae al método Python

        return cls._python_pdf_to_epub(pdf_path, out_path, base)

    @staticmethod
    def _python_pdf_to_epub(pdf_path: str, out_path: str, base: str) -> str:
        from pdfminer.high_level import extract_text
        from ebooklib import epub

        book = epub.EpubBook()
        book.set_identifier(hashlib.md5(pdf_path.encode()).hexdigest())
        book.set_title(base)
        book.set_language("en")

        # pdfminer separa las páginas con form-feed (\x0c). Un solo pase, rápido.
        full = extract_text(pdf_path) or ""
        pages = full.split("\x0c")

        # Agrupa páginas en capítulos.
        epub_chapters = []
        spine = ["nav"]
        toc = []
        group = max(1, PDF_PAGES_PER_CHAPTER)
        idx = 0
        for start in range(0, len(pages), group):
            block = " ".join(pages[start:start + group]).strip()
            if not block:
                continue
            idx += 1
            title = f"Sección {idx}"
            safe = html.escape(block)
            ch = epub.EpubHtml(title=title, file_name=f"sec_{idx}.xhtml", lang="en")
            ch.content = f"<html><body><h2>{title}</h2><p>{safe}</p></body></html>"
            book.add_item(ch)
            epub_chapters.append(ch)
            spine.append(ch)
            toc.append(ch)

        if not epub_chapters:
            raise RuntimeError("No se pudo extraer texto del PDF.")

        book.toc = tuple(toc)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = spine
        epub.write_epub(out_path, book)
        return out_path


# --------------------------------------------------------------------------- #
# EpubParser
# --------------------------------------------------------------------------- #
class EpubParser:
    _DROP_TAGS = ("script", "style", "head", "title", "nav")

    def parse(self, epub_path: str) -> dict:
        import ebooklib
        from ebooklib import epub
        from bs4 import BeautifulSoup

        book = epub.read_epub(epub_path)
        title = self._meta(book, "title") or os.path.basename(epub_path)
        author = self._meta(book, "creator") or ""
        language = self._meta(book, "language") or ""

        # Índice REAL del libro: mapa href-de-archivo -> título del capítulo.
        nav_titles = self._nav_titles(book)

        chapters: list[dict] = []
        for spine_id, _ in book.spine:
            item = book.get_item_with_id(spine_id)
            if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue
            soup = BeautifulSoup(item.get_content(), "html.parser")
            for tag in soup(self._DROP_TAGS):
                tag.decompose()
            heading = soup.find(["h1", "h2", "h3"])
            heading_title = heading.get_text(" ", strip=True) if heading else ""
            if heading:
                heading.decompose()
            text = soup.get_text(" ", strip=True)
            sentences = split_sentences(text)
            if not sentences:
                continue
            # Título: índice del libro > encabezado del documento > primeras palabras.
            ch_title = (
                self._match_nav(nav_titles, item.get_name())
                or heading_title
                or self._first_words(sentences[0])
            )
            chapters.append({"title": ch_title, "sentences": sentences})

        if not chapters:
            raise RuntimeError("El EPUB no contiene texto legible que se pueda extraer.")
        return {"title": title, "author": author, "language": language, "chapters": chapters}

    @staticmethod
    def _meta(book, name: str) -> str:
        data = book.get_metadata("DC", name)
        return data[0][0].strip() if data and data[0] and data[0][0] else ""

    @staticmethod
    def _first_words(sentence: str, n: int = 6) -> str:
        words = sentence.split()
        t = " ".join(words[:n])
        return t + ("…" if len(words) > n else "")

    @classmethod
    def _nav_titles(cls, book) -> dict[str, str]:
        """Recorre el índice del EPUB (book.toc, anidado) y devuelve
        {archivo.xhtml: título}. Toma el primer título por archivo."""
        titles: dict[str, str] = {}

        def add(href, title):
            if not href or not title:
                return
            key = href.split("#")[0]
            titles.setdefault(key, title.strip())
            titles.setdefault(os.path.basename(key), title.strip())

        def walk(items):
            for it in items:
                if isinstance(it, (list, tuple)):
                    # (Section/Link, [hijos]) o lista de hijos
                    if len(it) == 2 and not isinstance(it[0], (list, tuple)):
                        sec, children = it
                        add(getattr(sec, "href", None), getattr(sec, "title", None))
                        walk(children)
                    else:
                        walk(it)
                else:
                    add(getattr(it, "href", None), getattr(it, "title", None))

        try:
            walk(book.toc)
        except Exception:
            pass
        return titles

    @staticmethod
    def _match_nav(nav: dict[str, str], name: str) -> str:
        """Empareja el archivo del spine con una entrada del índice (por ruta o nombre)."""
        if not name:
            return ""
        if name in nav:
            return nav[name]
        base = os.path.basename(name)
        if base in nav:
            return nav[base]
        for href, title in nav.items():
            if href.endswith(name) or name.endswith(href):
                return title
        return ""


# --------------------------------------------------------------------------- #
# ingest — normaliza a EPUB y persiste
# --------------------------------------------------------------------------- #
def ingest(source_path: str, db: DatabaseManager) -> int:
    """Normaliza a EPUB y guarda en la DB. Si es PDF: lo convierte a EPUB en library/
    y DESCARTA el PDF original (nos quedamos solo con el .epub). Si ya es EPUB, se usa
    tal cual. El .epub final es el source_path que identifica al libro. Devuelve book_id."""
    ext = os.path.splitext(source_path)[1].lower()
    if ext == ".pdf":
        epub_path = PdfConverter.to_epub(source_path)
        if os.path.abspath(epub_path) != os.path.abspath(source_path):
            try:
                os.remove(source_path)  # descarta el PDF; conservamos el EPUB
            except OSError:
                pass
        final_path = epub_path
    elif ext == ".epub":
        final_path = source_path
    else:
        raise RuntimeError(f"Formato no soportado: {ext} (usa .pdf o .epub)")
    parsed = EpubParser().parse(final_path)
    return db.import_book(final_path, parsed)


# --------------------------------------------------------------------------- #
# LLM (Gemini) y TTS (pyttsx3) — degradación elegante
# --------------------------------------------------------------------------- #
_LLM_PROMPTS = {
    "translation": (
        "Traduce el siguiente texto al {lang} de forma natural y fiel. "
        "Responde ÚNICAMENTE con la traducción, sin comillas ni explicaciones.\n\nTexto:\n{text}"
    ),
    "grammar": (
        "Explica en {lang}, de forma breve y clara (máximo 4 líneas), la gramática del "
        "siguiente texto: tiempos verbales, estructura y puntos útiles para quien aprende "
        "el idioma.\n\nTexto:\n{text}"
    ),
    "example": (
        "A partir del vocabulario o estructura clave del siguiente texto, da 2 ejemplos "
        "nuevos en el idioma original, cada uno con su traducción al {lang}. "
        "Formato: '- ejemplo — traducción'.\n\nTexto:\n{text}"
    ),
    "lookup": (
        "Para la palabra o expresión «{text}» (en su idioma original), responde en {lang} "
        "de forma concisa con exactamente estas tres partes:\n"
        "Traducción: <traducción breve>\n"
        "Ejemplo: <una frase de ejemplo en el idioma original> — <su traducción>\n"
        "Gramática: <nota corta: categoría o tiempo verbal, si aplica>"
    ),
    "title": (
        "Este es el inicio de una sección de un libro. Dame SOLO un título corto y "
        "descriptivo (máximo 6 palabras) en {lang} que resuma de qué trata. Sin comillas, "
        "sin numeración, sin la palabra 'título'. Si es portada/créditos/índice, dilo "
        "(ej. 'Portada y créditos', 'Índice').\n\nTexto:\n{text}"
    ),
}
_LANG_NAMES = {"es": "español", "en": "inglés", "fr": "francés", "de": "alemán"}


def llm_generate(text: str, kind: str = "translation", target_lang: str = "es",
                 max_tokens: int | None = None) -> str:
    api_key = get_api_key()
    lang_name = _LANG_NAMES.get(target_lang, target_lang)
    prompt = _LLM_PROMPTS.get(kind, _LLM_PROMPTS["translation"]).format(lang=lang_name, text=text)
    if not api_key:
        time.sleep(0.3)
        return f"[IA sin configurar — agrega tu API key en ⚙ Ajustes] ({kind}) {text}"
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key)

    def _call(model):
        kwargs = {}
        # Solo incluir max_output_tokens cuando se pide; pasarlo como None hace que
        # el SDK lo serialice mal y la API responda 400 INVALID_ARGUMENT.
        if max_tokens is not None:
            kwargs["max_output_tokens"] = max_tokens
        # thinking_budget=0 desactiva el "razonamiento". SOLO los modelos 2.5 lo
        # aceptan; en otros (p.ej. flash-lite) provoca 400 INVALID_ARGUMENT. Se
        # decide por el modelo que se va a usar AHORA, no por el principal: la
        # cadena de respaldo puede haber cambiado de modelo.
        if "2.5" in model:
            kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
        config = types.GenerateContentConfig(**kwargs) if kwargs else None
        resp = client.models.generate_content(model=model, contents=prompt, config=config)
        out = (resp.text or "").strip()
        if not out:
            raise RuntimeError("respuesta vacía")
        return out

    # Reintenta y baja por la cadena de modelos. Lanza AIUnavailable si nada
    # responde: antes devolvía el error como si fuera la traducción, y acababas
    # leyendo "[error de IA: 503...]" dentro del lector.
    # attempts=2 (no 3): esto es interactivo — clicas una palabra y esperas. Un
    # reintento absorbe un fallo puntual; más que eso es mejor cambiar de modelo
    # que hacerte esperar.
    return _gemini_retry(_call, attempts=2)


# Ritmo del TTS (palabras/min aprox). Más bajo = más lento y claro. Override: TTS_RATE.
TTS_RATE = int(os.environ.get("TTS_RATE", "150"))
# Ritmo (más lento) y voz para el audio pre-generado de los decks de aprendizaje.
DECK_TTS_RATE = int(os.environ.get("DECK_TTS_RATE", "130"))
DECK_VOICE = os.environ.get("DECK_VOICE", "Samantha")

# Voces preferidas de macOS `say` por idioma (usa la primera disponible).
_SAY_VOICE_PREFS = {
    "en": ["Ava (Premium)", "Samantha", "Allison", "Alex", "Tom", "Evan"],
    "es": ["Paulina", "Mónica", "Juan", "Eddy (Español (México))"],
    "fr": ["Thomas", "Amelie"],
    "de": ["Anna", "Markus"],
}
_say_voice_cache: dict[str, str | None] = {}


def _available_say_voices() -> list[tuple[str, str]]:
    try:
        out = subprocess.run(
            ["say", "-v", "?"], capture_output=True, text=True, timeout=10
        ).stdout
    except Exception:
        return []
    voices = []
    for line in out.splitlines():
        m = re.match(r"^(.*?)\s{2,}([a-z]{2}_[A-Z]{2})", line)
        if m:
            voices.append((m.group(1).strip(), m.group(2)))
    return voices


# Voces "de broma"/personaje de macOS que no queremos ofrecer (por primera palabra).
_NOVELTY = {"albert", "bad", "bahh", "bells", "boing", "bubbles", "cellos", "good",
            "jester", "organ", "superstar", "trinoids", "whisper", "wobble", "zarvox",
            "deranged", "hysterical", "pipe", "bruce", "junior", "ralph", "fred",
            "kathy", "princess", "reed", "rocko", "sandy", "shelley", "grandma",
            "grandpa", "flo", "eddy"}
_ACCENT = {"en-us": "🇺🇸 EE.UU.", "en-gb": "🇬🇧 Británico", "en-au": "🇦🇺 Australiano",
           "en-in": "🇮🇳 Indio", "en-ie": "🇮🇪 Irlandés", "en-za": "🇿🇦 Sudafricano"}


def _piper_voices(lang: str = "en") -> list[dict]:
    if not lang.startswith("en"):
        return []
    out = []
    for model, meta in _PIPER_MODELS.items():
        if os.path.exists(os.path.join(PIPER_DIR, model + ".onnx")):
            out.append({"name": "piper:" + model, "lang": "en_US",
                        "accent": meta["accent"], "display": meta["display"]})
    return out


def list_voices(lang: str = "en") -> list[dict]:
    """Voces disponibles para el idioma: primero las NEURALES (Piper, más humanas),
    luego las de `say` (curadas, sin las de broma), con acento."""
    lang = (lang or "en")[:2]
    out = _piper_voices(lang)  # neurales primero
    say = []
    for name, code in _available_say_voices():
        if not code.lower().startswith(lang):
            continue
        if name.lower().split(" ")[0].split("(")[0] in _NOVELTY:
            continue
        say.append({"name": name, "lang": code,
                    "accent": _ACCENT.get(code.lower().replace("_", "-"), code),
                    "display": name})
    say.sort(key=lambda v: (0 if v["name"] == "Samantha" else 1, v["name"]))
    return out + say


def _pick_say_voice(lang: str) -> str | None:
    """Elige la mejor voz de `say` para el idioma (prioriza voces naturales)."""
    lang = (lang or "en")[:2]
    if lang in _say_voice_cache:
        return _say_voice_cache[lang]
    voices = _available_say_voices()
    names = [n for n, _ in voices]
    chosen = next((p for p in _SAY_VOICE_PREFS.get(lang, []) if p in names), None)
    if not chosen:
        chosen = next((n for n, code in voices if code.startswith(lang)), None)
    _say_voice_cache[lang] = chosen
    return chosen


# --------------------------------------------------------------------------- #
# Writing: extracción de texto (incl. OCR de fotos con Gemini vision) + IA
# --------------------------------------------------------------------------- #
def extract_text_from_upload(filename: str, data: bytes) -> str:
    """Extrae texto de lo que suba el usuario: .txt, .pdf, .docx o imagen (OCR)."""
    ext = os.path.splitext(filename or "")[1].lower()
    if ext == ".txt":
        return data.decode("utf-8", errors="replace")
    if ext == ".pdf":
        import tempfile
        from pdfminer.high_level import extract_text
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(data); tmp = f.name
        try:
            return extract_text(tmp) or ""
        finally:
            try: os.remove(tmp)
            except OSError: pass
    if ext == ".docx":
        import io, docx
        d = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in d.paragraphs)
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".heic", ".gif"):
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext[1:], "image/" + ext[1:])
        return ocr_image(data, mime)
    raise RuntimeError(f"Formato no soportado: {ext}")


def ocr_image(data: bytes, mime: str) -> str:
    """OCR de una foto (incl. manuscrito) con Gemini vision. Requiere GEMINI_API_KEY."""
    api_key = get_api_key()
    if not api_key:
        raise AIUnavailable("Falta la API key de Gemini para leer fotos.")
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key)

    def _call(model):
        resp = client.models.generate_content(
            model=model,
            contents=[
                types.Part.from_bytes(data=data, mime_type=mime),
                "Transcribe exactly all the text written in this image. "
                "Return only the transcription, no comments.",
            ],
        )
        out = (resp.text or "").strip()
        if not out:
            raise RuntimeError("no se leyó texto en la imagen")
        return out

    return _gemini_retry(_call)


def is_placeholder(text: str) -> bool:
    """¿Es un texto de relleno de la IA en vez de contenido real?

    Existe porque una traducción de relleno llegó a guardarse como si fuera
    buena y quedó así para siempre en las flashcards. Cubre también los
    formatos de versiones anteriores, que siguen en la base.
    """
    t = (text or "").strip()
    return t.startswith(("[modo simulado", "[IA sin configurar", "[error de IA",
                         "[error de OCR", "[respuesta vacía", "[define GEMINI_API_KEY"))


class AIUnavailable(RuntimeError):
    """El modelo no respondió (sin API key, sobrecargado o sin cuota).

    Se lanza en vez de devolver el error como si fuera texto: así nunca acaba
    guardado en la base de datos ni mostrado como si fuera tu redacción.
    """


# 503 = modelo saturado, 429 = cuota por minuto. Ambos son temporales y se
# resuelven reintentando; el resto de errores no.
_AI_RETRY_HINTS = ("503", "unavailable", "overloaded", "429", "resource_exhausted",
                   "rate limit", "high demand", "500", "internal", "deadline", "timeout")


def _is_retryable(exc: Exception) -> bool:
    # Un JSON malformado es un fallo de formato del modelo, no un error del
    # usuario: casi siempre sale bien al reintentar o con otro modelo.
    if isinstance(exc, (json.JSONDecodeError, ValueError)):
        return True
    msg = str(exc).lower()
    return any(h in msg for h in _AI_RETRY_HINTS)


def _model_chain(prefer: str = "") -> list[str]:
    """Modelo a usar primero + respaldos, sin repetidos.

    `prefer` permite que cada tarea elija su modelo sin perder la red de
    seguridad: si el preferido cae, se sigue bajando por la cadena.
    """
    chain: list[str] = []
    for m in (prefer or GEMINI_MODEL, GEMINI_MODEL, *GEMINI_FALLBACKS):
        if m and m not in chain:
            chain.append(m)
    return chain


def _gemini_retry(call, attempts: int = 3, prefer: str = ""):
    """Ejecuta `call(model)` reintentando con espera creciente.

    Si un modelo sigue saturado tras sus reintentos, pasa al siguiente de la
    cadena: un 503 en el modelo principal ya no deja la app sin IA.
    """
    last: Exception | None = None
    for model in _model_chain(prefer):
        delay = 1.5
        for i in range(attempts):
            try:
                return call(model)
            except AIUnavailable:
                raise
            except Exception as exc:
                last = exc
                if _is_model_missing(exc):
                    break                      # ese modelo no existe → siguiente
                if not _is_retryable(exc):
                    raise AIUnavailable(_friendly_ai_error(exc)) from exc
                if i < attempts - 1:
                    time.sleep(delay)
                    delay *= 2
    raise AIUnavailable(_friendly_ai_error(last) if last else "La IA no respondió.")


def _is_model_missing(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "404" in msg or "not_found" in msg or "not found" in msg


def _friendly_ai_error(exc: Exception) -> str:
    msg = str(exc)
    low = msg.lower()
    if "503" in low or "unavailable" in low or "overloaded" in low or "high demand" in low:
        return ("El modelo está saturado ahora mismo (503). Ya lo reintenté varias "
                "veces. Espera unos segundos y vuelve a intentarlo.")
    if "429" in low or "resource_exhausted" in low or "quota" in low:
        return ("Se agotó la cuota gratuita por ahora (429). Espera un minuto y "
                "vuelve a intentarlo.")
    if "api key" in low or "permission" in low or "401" in low or "403" in low:
        return "La API key de Gemini no es válida o no tiene permisos."
    return f"La IA falló: {msg}"


def _salvage_json(raw: str) -> dict | None:
    """Último recurso ante un JSON cortado a media frase: cierra comillas,
    llaves y corchetes abiertos y descarta el último campo incompleto."""
    raw = raw.strip()
    start = raw.find("{")
    if start < 0:
        return None
    raw = raw[start:]
    # corta en la última coma de nivel superior que dejó una estructura sana
    for cut in range(len(raw), 0, -1):
        chunk = raw[:cut].rstrip().rstrip(",")
        depth, in_str, esc = 0, False, False
        for ch in chunk:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = not in_str
            elif not in_str:
                depth += 1 if ch in "{[" else -1 if ch in "}]" else 0
        if in_str or depth < 0:
            continue
        try:
            return json.loads(chunk + "}" * depth)
        except Exception:
            continue
    return None


def _gemini_json(prompt: str, max_tokens: int | None = None,
                 schema: dict | None = None, prefer: str = "") -> dict:
    """Llama a Gemini pidiendo JSON y lo parsea. Lanza AIUnavailable si falla.

    Con `schema`, la API obliga al modelo a respetar la estructura en vez de
    confiar en que la respete por su cuenta: es lo que evita los JSON rotos
    en textos largos o con muchas comillas dentro.
    """
    api_key = get_api_key()
    if not api_key:
        raise AIUnavailable("Falta la API key de Gemini (config.local.json o GEMINI_API_KEY).")
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key)
    cfg = types.GenerateContentConfig(response_mime_type="application/json",
                                      max_output_tokens=max_tokens,
                                      response_schema=schema)

    def _call(model):
        resp = client.models.generate_content(model=model, contents=prompt, config=cfg)
        raw = (resp.text or "").strip()
        if not raw:
            raise RuntimeError("respuesta vacía")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            rescued = _salvage_json(raw)
            if rescued:
                return rescued
            raise

    return _gemini_retry(_call, prefer=prefer)


CEFR_LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")

# Estructura que la API obliga a respetar en writing_check. Sin esto, un texto
# largo o con comillas dentro puede salir con el JSON malformado y se pierde
# toda la evaluación.
_STR = {"type": "STRING"}

# Categorías CERRADAS de error. Son la clave de la pestaña "Errors": agrupando
# por frase exacta nunca se repite nada, agrupando por tipo sí se ve el patrón.
ERROR_CATEGORIES = {
    "verb_tense": "Tiempos verbales",
    "agreement": "Concordancia sujeto-verbo",
    "preposition": "Preposiciones",
    "article": "Artículos (a/an/the)",
    "word_order": "Orden de las palabras",
    "vocabulary": "Elección de palabra",
    "plural": "Plurales y contables",
    "pronoun": "Pronombres",
    "spelling": "Ortografía",
    "punctuation": "Puntuación",
    "other": "Otros",
    # errores guardados antes de que existiera la clasificación: se muestran
    # aparte para que no falseen el diagnóstico
    "unclassified": "Sin clasificar (anteriores)",
}

WRITING_CHECK_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "level": {"type": "STRING", "enum": list(CEFR_LEVELS)},
        "assessment": _STR,
        "strengths": {"type": "ARRAY", "items": _STR},
        "to_improve": {"type": "ARRAY", "items": _STR},
        "corrected": _STR,
        "errors": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "original": _STR, "correction": _STR, "explanation": _STR,
                    "category": {"type": "STRING", "enum": list(ERROR_CATEGORIES)},
                },
                "required": ["original", "correction", "explanation", "category"],
            },
        },
    },
    "required": ["level", "assessment", "strengths", "to_improve", "corrected", "errors"],
}


def next_levels(level: str) -> list[str]:
    """El nivel INMEDIATAMENTE superior: A2→B1, B1→B2, y así.

    Uno solo, a propósito: la comparación siempre es contra el escalón siguiente,
    nunca contra tu mismo nivel ni contra uno tan lejano que no sirva de modelo.
    Lista vacía en C2 (no hay a dónde subir).
    """
    if level not in CEFR_LEVELS:
        return []
    return list(CEFR_LEVELS[CEFR_LEVELS.index(level) + 1:][:1])


CARD_EXAMPLE_SCHEMA = {
    "type": "OBJECT",
    "properties": {"example": _STR, "translation": _STR},
    "required": ["example", "translation"],
}


def simple_example(term: str, level: str = "B1", lang_name: str = "español") -> dict:
    """Frase de ejemplo CORTA y al nivel del estudiante para una flashcard.

    Las frases del libro pueden tener 25 palabras y varias estructuras
    desconocidas a la vez: para memorizar hace falta una sola idea nueva por
    tarjeta. Devuelve {'example': ..., 'translation': ...}.
    """
    lvl = level if level in CEFR_LEVELS else "B1"
    prompt = (
        f"Write ONE short example sentence in English using the word or phrase «{term}».\n"
        f"Rules: maximum 10 words; CEFR level {lvl}; everyday situation; the sentence "
        f"must make the meaning of «{term}» obvious from context; use only vocabulary "
        f"a {lvl} learner already knows apart from the target word itself.\n"
        f"Return JSON with 'example' (the English sentence) and 'translation' "
        f"(its natural {lang_name} translation)."
    )
    data = _gemini_json(prompt, max_tokens=512, schema=CARD_EXAMPLE_SCHEMA,
                        prefer=GEMINI_MODEL_QUALITY)
    return {"example": (data.get("example") or "").strip(),
            "translation": (data.get("translation") or "").strip()}


PHRASE_EXAMPLES_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {"phrase": _STR, "english": _STR, "spanish": _STR},
                "required": ["phrase", "english", "spanish"],
            },
        }
    },
    "required": ["items"],
}


def phrase_examples(phrases: list[str], level: str = "B1") -> dict[str, str]:
    """Para cada frase, un mini-diálogo que la muestra EN USO.

    Devuelve {frase: "inglés — español"}, el formato que usan las tarjetas.
    El diálogo incluye la frase literal y la respuesta que oirías: así la
    tarjeta enseña la frase y lo que viene después, y además permite construir
    el cloze (que necesita que la frase aparezca en el ejemplo).
    """
    if not phrases:
        return {}
    lvl = level if level in CEFR_LEVELS else "B1"
    listado = "\n".join(f"- {p}" for p in phrases)
    prompt = (
        "For each English phrase below, write a two-line mini-dialogue that shows it "
        "in a real situation.\n"
        "Rules:\n"
        "- 'english': the phrase EXACTLY as given, then a natural reply someone would "
        "say back. Keep the whole thing under 20 words.\n"
        f"- Use simple CEFR {lvl} vocabulary in the reply.\n"
        "- 'spanish': the natural Spanish translation of the WHOLE exchange.\n"
        "- 'phrase': repeat the original phrase verbatim so I can match it.\n"
        "Return one item per phrase, same order.\n\n" + listado
    )
    data = _gemini_json(prompt, max_tokens=8192, schema=PHRASE_EXAMPLES_SCHEMA,
                        prefer=GEMINI_MODEL_QUALITY)
    out: dict[str, str] = {}
    for item in (data.get("items") or []):
        frase = (item.get("phrase") or "").strip()
        en = (item.get("english") or "").strip()
        es = (item.get("spanish") or "").strip()
        if frase and en and es:
            out[frase] = f"{en} — {es}"
    return out


ERROR_LESSON_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": _STR,
        "desc": _STR,
        "why_it_happens": _STR,
        "explanation": {"type": "ARRAY", "items": _STR},
        "rule": {"type": "ARRAY", "items": _STR},
        "fixes": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {"wrong": _STR, "right": _STR, "why": _STR},
                "required": ["wrong", "right", "why"],
            },
        },
        "examples": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {"en": _STR, "es": _STR},
                "required": ["en", "es"],
            },
        },
        "practice": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {"prompt": _STR, "answer": _STR, "hint": _STR},
                "required": ["prompt", "answer"],
            },
        },
        "watch_out": {"type": "ARRAY", "items": _STR},
    },
    "required": ["title", "desc", "why_it_happens", "explanation", "rule",
                 "fixes", "examples", "practice"],
}


ERROR_MINI_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "rule": _STR,
        "why": _STR,
        "examples": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {"en": _STR, "es": _STR},
                "required": ["en", "es"],
            },
        },
        "drill": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {"prompt": _STR, "answer": _STR},
                "required": ["prompt", "answer"],
            },
        },
        "remember": _STR,
    },
    "required": ["rule", "why", "examples", "drill", "remember"],
}


def explain_error(original: str, correction: str, note: str = "",
                  level: str = "B1") -> dict:
    """Mini-lección para UN error concreto.

    Corta a propósito: la lección general profundiza en un tipo de error, esta
    resuelve el caso que tienes delante. Si fuera igual de larga, nadie la
    leería en una lista de 36.
    """
    if not original or not correction:
        raise AIUnavailable("Ese error no tiene datos suficientes.")
    lvl = level if level in CEFR_LEVELS else "B1"
    prompt = (
        "A Spanish-speaking English student made this mistake:\n"
        f'  wrote:   "{original}"\n'
        f'  correct: "{correction}"\n'
        + (f"  note: {note}\n" if note else "")
        + "\nWrite a SHORT lesson so they never repeat it. Answer IN SPANISH "
        "(except the English examples).\n"
        "Return JSON with:\n"
        '  "rule": one line — the rule that was broken.\n'
        '  "why": 1-2 sentences on why a Spanish speaker makes exactly this mistake '
        "(name the interference with Spanish).\n"
        f'  "examples": 3 short correct English sentences {{"en","es"}} at level {lvl} '
        "using the same pattern.\n"
        '  "drill": 2 quick exercises {"prompt","answer"} — "prompt" in Spanish to '
        'translate, or English with a "_____" gap.\n'
        '  "remember": one memorable line to keep.\n'
        "Be concise: this is a note, not a chapter."
    )
    data = _gemini_json(prompt, max_tokens=2048, schema=ERROR_MINI_SCHEMA,
                        prefer=GEMINI_MODEL_QUALITY)
    if not isinstance(data, dict) or not data.get("rule"):
        raise AIUnavailable("La IA no devolvió una explicación utilizable.")
    for key in ("examples", "drill"):
        if not isinstance(data.get(key), list):
            data[key] = []
    return data


def generate_error_lesson(category_label: str, errors: list[dict],
                          level: str = "B1") -> dict:
    """Crea una lección centrada en NO repetir un tipo de error concreto.

    Se le pasan los errores REALES del estudiante, no ejemplos genéricos: una
    lección sobre preposiciones sirve de poco; una que empiece por «escribiste
    *no related with*» se queda.
    """
    if not errors:
        raise AIUnavailable("No hay errores de ese tipo todavía.")
    lvl = level if level in CEFR_LEVELS else "B1"
    listado = "\n".join(
        f'- escribió: "{e.get("original","")}" · correcto: "{e.get("correction","")}"'
        + (f' · nota: {e.get("explanation","")}' if e.get("explanation") else "")
        for e in errors
    )
    prompt = (
        "You are an English teacher writing a focused remedial lesson for a Spanish-speaking "
        f"student at CEFR level {lvl}. The lesson must attack ONE recurring mistake type: "
        f"«{category_label}».\n\n"
        "These are the student's REAL mistakes:\n" + listado + "\n\n"
        "Write the whole lesson IN SPANISH (except the English examples themselves).\n"
        "Return JSON with:\n"
        '  "title": short title naming the problem.\n'
        '  "desc": one line saying what the student will stop doing wrong.\n'
        '  "why_it_happens": 2-3 sentences explaining WHY a Spanish speaker makes this '
        "mistake — name the interference with Spanish explicitly. This is the key part: "
        "understanding the cause is what stops the mistake repeating.\n"
        '  "explanation": 2-4 paragraphs teaching the rule clearly, from simple to subtle.\n'
        '  "rule": 1-3 short memorable lines (a formula or rule of thumb).\n'
        '  "fixes": for EACH mistake above, {"wrong","right","why"} — "why" in Spanish, '
        "short, saying what the rule says about THAT case.\n"
        '  "examples": 5-8 correct sentences {"en","es"} showing the pattern in everyday '
        f"situations, at level {lvl}.\n"
        '  "practice": 5-8 exercises {"prompt","answer","hint"}. "prompt" is a Spanish '
        'sentence to translate, or an English sentence with a gap marked "_____". '
        '"answer" is the expected English. "hint" is a short nudge in Spanish.\n'
        '  "watch_out": 2-4 traps or exceptions worth remembering.\n'
    )
    data = _gemini_json(prompt, max_tokens=8192, schema=ERROR_LESSON_SCHEMA,
                        prefer=GEMINI_MODEL_QUALITY)
    if not isinstance(data, dict) or not data.get("explanation"):
        raise AIUnavailable("La IA no devolvió una lección utilizable. Reintenta.")
    for key in ("explanation", "rule", "fixes", "examples", "practice", "watch_out"):
        if not isinstance(data.get(key), list):
            data[key] = []
    return data


def writing_check(text: str) -> dict:
    """Evalúa el nivel del texto, lo corrige y explica los errores (en español).

    Devuelve {level, assessment, strengths, to_improve, corrected, errors[]}.
    Lanza AIUnavailable si la IA no responde: sin evaluación real no se guarda
    nada, porque un nivel inventado es peor que ningún nivel.
    """
    prompt = (
        "You are a strict but encouraging English writing examiner for a Spanish speaker.\n"
        "First ASSESS the student's original text, then correct it.\n"
        "Return a JSON object with EXACTLY these keys:\n"
        '  "level": the CEFR level of the ORIGINAL text as written '
        "(A1, A2, B1, B2, C1 or C2). Judge it honestly on range of vocabulary, "
        "grammatical control, sentence complexity and cohesion. Do NOT inflate it: "
        "a short text with basic vocabulary and simple sentences is A1 or A2 even "
        "if it has no mistakes.\n"
        '  "assessment": 2-3 sentences IN SPANISH explaining WHY it is that level, '
        "citing concrete evidence from the text.\n"
        '  "strengths": array of 1-3 short strings IN SPANISH, what the student did well.\n'
        '  "to_improve": array of 1-3 short strings IN SPANISH, the concrete things '
        "that would move this text to the next CEFR level.\n"
        '  "corrected": the full text corrected into natural English, KEEPING the '
        "student's own level and voice (fix mistakes, do not upgrade the level).\n"
        '  "errors": array of the main mistakes, each {"original": "...", '
        '"correction": "...", "explanation": "...", "category": "..."}, where '
        '"explanation" is IN SPANISH, short and clear, and "category" is exactly one of: '
        + ", ".join(ERROR_CATEGORIES) + ". Only real mistakes (max 12).\n\n"
        "Student's text:\n\n" + text
    )
    data = _gemini_json(prompt, max_tokens=8192, schema=WRITING_CHECK_SCHEMA,
                        prefer=GEMINI_MODEL_QUALITY)
    if not isinstance(data, dict) or not data.get("corrected"):
        raise AIUnavailable("La IA devolvió una respuesta que no pude interpretar. Reintenta.")
    level = str(data.get("level") or "").strip().upper()
    data["level"] = level if level in CEFR_LEVELS else ""
    data.setdefault("assessment", "")
    for key in ("strengths", "to_improve", "errors"):
        if not isinstance(data.get(key), list):
            data[key] = []
    data["next_levels"] = next_levels(data["level"])
    return data


def writing_upgrade(text: str, level: str = "B2", from_level: str = "") -> str:
    """Reescribe el texto a un nivel objetivo manteniendo la idea y la voz."""
    lvl = level if level in CEFR_LEVELS else "B2"
    origin = (f"The student currently writes at {from_level}. " if from_level in CEFR_LEVELS else "")
    prompt = (
        f"{origin}Rewrite the following text in natural, correct English at CEFR level {lvl}, "
        "keeping the same meaning and the writer's personal voice but using the richer "
        f"vocabulary, connectors and sentence structures that genuinely characterise {lvl}. "
        "Return ONLY the rewritten text, with no preamble or commentary.\n\n" + text
    )
    out = _plain_gemini(prompt, prefer=GEMINI_MODEL_QUALITY)
    if not out:
        raise AIUnavailable("La IA devolvió una reescritura vacía. Reintenta.")
    return out


def _plain_gemini(prompt: str, prefer: str = "") -> str:
    api_key = get_api_key()
    if not api_key:
        raise AIUnavailable("Falta la API key de Gemini (config.local.json o GEMINI_API_KEY).")
    from google import genai
    client = genai.Client(api_key=api_key)

    def _call(model):
        resp = client.models.generate_content(model=model, contents=prompt)
        out = (resp.text or "").strip()
        if not out:
            raise RuntimeError("respuesta vacía")
        return out

    return _gemini_retry(_call, prefer=prefer)


_TTS_SUBPROCESS = (
    "import sys, pyttsx3;"
    "text=sys.stdin.buffer.read().decode('utf-8'); out=sys.argv[1];"
    "e=pyttsx3.init();"
    "e.setProperty('rate', int(sys.argv[2]));"
    "[e.setProperty('voice', v.id) for v in e.getProperty('voices') if 'en_' in getattr(v,'id','') or 'en-' in getattr(v,'id','')][:1];"
    "e.save_to_file(text, out); e.runAndWait(); e.stop()"
)


def synthesize(text: str, lang: str = "en", rate: int | None = None,
               voice: str | None = None) -> str:
    """TTS con `say` (macOS): voz NATIVA del idioma y ritmo configurable → pronunciación
    correcta y natural. `rate` en palabras/min (más bajo = más lento); `voice` fuerza una
    voz concreta (p.ej. 'Samantha'). Fuera de macOS cae a pyttsx3. Cachea por
    (idioma, voz, ritmo, texto)."""
    os.makedirs(TTS_CACHE_DIR, exist_ok=True)
    r = int(rate) if rate else TTS_RATE
    key = hashlib.md5(f"{lang}:{voice or ''}:{r}:{text}".encode("utf-8")).hexdigest()
    out_path = os.path.join(TTS_CACHE_DIR, f"{key}.wav")
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path

    # Motor NEURAL Piper (voz más humana). voice = 'piper:<modelo>'.
    if voice and voice.startswith("piper:"):
        model = os.path.join(PIPER_DIR, voice.split("piper:", 1)[1] + ".onnx")
        if os.path.exists(model):
            # length_scale: >1 = más lento. Mapea el 'rate' (palabras/min) a la escala.
            length_scale = round(max(0.8, min(1.7, 150.0 / max(60, r))), 2)
            try:
                subprocess.run(
                    [sys.executable, "-m", "piper", "-m", model,
                     "--length-scale", str(length_scale), "-f", out_path],
                    input=text.encode("utf-8"), timeout=90, check=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    return out_path
            except Exception:
                pass  # cae a `say`

    if sys.platform == "darwin":
        try:
            cmd = ["say"]
            v = voice or _pick_say_voice(lang)
            if v:
                cmd += ["-v", v]
            cmd += ["-r", str(r),
                    "--file-format=WAVE", "--data-format=LEI16@22050",
                    "-o", out_path, text]
            subprocess.run(cmd, check=True, timeout=60,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                return out_path
        except Exception:
            pass

    try:
        subprocess.run(
            [sys.executable, "-c", _TTS_SUBPROCESS, out_path, str(TTS_RATE)],
            input=text.encode("utf-8"), timeout=30, check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path
    except Exception:
        pass
    return SAMPLE_WAV


# --------------------------------------------------------------------------- #
# AnkiExporter
# --------------------------------------------------------------------------- #
class AnkiExporter:
    _MODEL_ID = 1738294011
    _DECK_ID = 1738294012

    @classmethod
    def export(cls, items: list[dict], deck_name: str, out_path: str) -> int:
        import genanki

        model = genanki.Model(
            cls._MODEL_ID, "AppIdiomas Vocab",
            fields=[{"name": "Word"}, {"name": "Translation"}, {"name": "Example"},
                    {"name": "WordAudio"}, {"name": "ExampleAudio"}],
            templates=[{
                "name": "Card 1",
                "qfmt": '<div style="font-size:24px">{{Word}}</div>{{WordAudio}}',
                "afmt": ('{{FrontSide}}<hr id="answer">'
                         '<div style="font-size:20px;color:#2a6">{{Translation}}</div>'
                         '<br><div style="color:#555">{{Example}}</div>{{ExampleAudio}}'),
            }],
        )
        deck = genanki.Deck(cls._DECK_ID, deck_name)
        media: set[str] = set()
        for it in items:
            w_snd = cls._sound(it.get("word_audio"), media)
            e_snd = cls._sound(it.get("example_audio"), media)
            deck.add_note(genanki.Note(
                model=model,
                fields=[html.escape(it["word"]), html.escape(it["translation"]),
                        html.escape(it.get("example", "")), w_snd, e_snd],
            ))
        pkg = genanki.Package(deck)
        pkg.media_files = sorted(media)
        pkg.write_to_file(out_path)
        return len(items)

    @staticmethod
    def _sound(path: str | None, media: set[str]) -> str:
        if path and os.path.exists(path) and os.path.getsize(path) > 0:
            media.add(path)
            return f"[sound:{os.path.basename(path)}]"
        return ""


from lessons_data import LESSONS  # curso completo (42 lecciones) con bloques temáticos

_LESSON_LEVELS = ["beginner", "mid", "advanced"]


def get_lessons(level: str | None = None) -> list[dict]:
    """Lista ligera de lecciones (sin explanation/pairs/practice) para el índice."""
    out = []
    for ls in LESSONS:
        if level and ls["level"] != level:
            continue
        out.append({"id": ls["id"], "level": ls["level"], "n": ls.get("n", 0),
                    "block": ls.get("block", ""), "title": ls["title"], "desc": ls.get("desc", "")})
    out.sort(key=lambda x: x["n"])
    return out


def get_lesson(lesson_id: str) -> dict | None:
    for ls in LESSONS:
        if ls["id"] == lesson_id:
            return ls
    return None


# --------------------------------------------------------------------------- #
# CHECKPOINTS (mini-tests cada 3 lecciones). Se construyen SOLO del contenido ya
# validado de las lecciones (sus 'practice' es→en): 1 pregunta de opción múltiple
# por ítem, con distractores tomados de otras lecciones. Sin autoría extra =
# cero riesgo de contenido nuevo con errores. Progreso en tabla lesson_done
# (id tipo 'cp-beginner-1').
# --------------------------------------------------------------------------- #
_CP_GROUP = 3  # lecciones por checkpoint


def _level_lessons(level: str) -> list[dict]:
    return sorted([l for l in LESSONS if l["level"] == level], key=lambda x: x.get("n", 0))


def get_checkpoints(level: str) -> list[dict]:
    """Lista de checkpoints de un nivel: uno cada 3 lecciones (el último absorbe el resto)."""
    ls = _level_lessons(level)
    out = []
    k = 0
    i = 0
    while i < len(ls):
        k += 1
        group = ls[i:i + _CP_GROUP]
        # si lo que queda tras este grupo es 1-2 lecciones, únelas a este checkpoint
        rest = len(ls) - (i + _CP_GROUP)
        if 0 < rest < _CP_GROUP:
            group = ls[i:]
            i = len(ls)
        else:
            i += _CP_GROUP
        nums = [g.get("n", 0) for g in group]
        out.append({
            "id": f"cp-{level}-{k}", "level": level, "n": k,
            "title": f"Repaso {k}",
            "desc": f"Mini-test de las lecciones {nums[0]}–{nums[-1]}",
            "after": nums[-1],                      # va después de esta lección (nº)
            "lesson_ids": [g["id"] for g in group],
        })
    return out


def get_checkpoint(cp_id: str) -> dict | None:
    """Arma el mini-test (opción múltiple) desde los 'practice' de sus lecciones."""
    import random
    try:
        _, level, k = cp_id.split("-")
        k = int(k)
    except ValueError:
        return None
    cps = {c["id"]: c for c in get_checkpoints(level)}
    cp = cps.get(cp_id)
    if not cp:
        return None
    lessons = [get_lesson(lid) for lid in cp["lesson_ids"]]
    lessons = [l for l in lessons if l]
    # pool global de respuestas EN (para distractores plausibles del mismo nivel)
    pool = []
    for l in _level_lessons(level):
        for es, en in l.get("practice", []):
            pool.append(en)
    items = []
    for l in lessons:
        for es, en in l.get("practice", []):
            items.append((es, en))
    random.shuffle(items)
    items = items[:6]                                # máximo 6 preguntas por checkpoint
    questions = []
    for es, en in items:
        distractors = [d for d in pool if d != en]
        random.shuffle(distractors)
        opts = [en] + distractors[:3]
        random.shuffle(opts)
        questions.append({"prompt": es, "answer": en, "options": opts})
    return {"id": cp_id, "level": level, "title": cp["title"],
            "desc": cp["desc"], "questions": questions,
            "pass": max(1, round(len(questions) * 0.6))}


# --------------------------------------------------------------------------- #
# Test de diagnóstico de nivel — 5 versiones EQUIVALENTES (10 preguntas,
# 2 por nivel A1..C1). Contenido curado (Claude), estático. q=(pregunta, opciones, idx_correcto, nivel)
# --------------------------------------------------------------------------- #
TEST_FORMS = [
    [  # Form 1
        ("She ___ a student.", ["is", "are", "am", "be"], 0, "A1"),
        ("I have two ___.", ["dog", "dogs", "doges", "dog's"], 1, "A1"),
        ("Yesterday we ___ to the park.", ["go", "went", "gone", "going"], 1, "A2"),
        ("He is ___ than me.", ["tall", "taller", "tallest", "more tall"], 1, "A2"),
        ("If it rains, we ___ stay home.", ["will", "would", "are", "have"], 0, "B1"),
        ("I've lived here ___ 2010.", ["for", "since", "from", "during"], 1, "B1"),
        ("She suggested ___ a break.", ["to take", "taking", "take", "took"], 1, "B2"),
        ("By next year, I ___ here for a decade.", ["will work", "will have worked", "work", "worked"], 1, "B2"),
        ("___ had I arrived when the phone rang.", ["No sooner", "Hardly", "Scarcely", "As soon"], 0, "C1"),
        ("The proposal was turned ___ by the board.", ["down", "off", "up", "over"], 0, "C1"),
    ],
    [  # Form 2
        ("They ___ my friends.", ["is", "am", "are", "be"], 2, "A1"),
        ("This is ___ apple.", ["a", "an", "the", "some"], 1, "A1"),
        ("She ___ TV last night.", ["watch", "watched", "watches", "watching"], 1, "A2"),
        ("It's the ___ movie I've seen.", ["good", "better", "best", "well"], 2, "A2"),
        ("I ___ English for three years.", ["study", "am studying", "have studied", "studied"], 2, "B1"),
        ("You ___ smoke here; it's forbidden.", ["mustn't", "don't have to", "can", "needn't"], 0, "B1"),
        ("I'd rather you ___ now.", ["leave", "left", "to leave", "leaving"], 1, "B2"),
        ("If I ___ known, I would have helped.", ["had", "have", "would", "did"], 0, "B2"),
        ("Not only ___ late, but he also forgot the keys.", ["he was", "was he", "he is", "is he"], 1, "C1"),
        ("'Take after' someone means to ___ them.", ["resemble", "avoid", "dislike", "call"], 0, "C1"),
    ],
    [  # Form 3
        ("I ___ from Mexico.", ["is", "am", "are", "be"], 1, "A1"),
        ("There ___ a book on the table.", ["is", "are", "am", "be"], 0, "A1"),
        ("We didn't ___ the bus.", ["caught", "catch", "catches", "catching"], 1, "A2"),
        ("She sings ___ than him.", ["good", "well", "better", "best"], 2, "A2"),
        ("When I was a child, I ___ play outside.", ["used to", "use to", "am used to", "was used"], 0, "B1"),
        ("The report ___ by Friday.", ["must finish", "must be finished", "must finishing", "finished"], 1, "B1"),
        ("He denied ___ the money.", ["to steal", "stealing", "steal", "stole"], 1, "B2"),
        ("___ you mind opening the window?", ["Would", "Will", "Do", "Are"], 0, "B2"),
        ("It's high time we ___ a decision.", ["make", "made", "making", "to make"], 1, "C1"),
        ("To 'give up' means to ___.", ["quit", "continue", "start", "win"], 0, "C1"),
    ],
    [  # Form 4
        ("My sister ___ tall.", ["are", "is", "am", "be"], 1, "A1"),
        ("How ___ apples do you want?", ["much", "many", "some", "any"], 1, "A1"),
        ("I ___ my keys yesterday.", ["lose", "lost", "losed", "losing"], 1, "A2"),
        ("This box is ___ than that one.", ["heavy", "heavier", "heaviest", "more heavy"], 1, "A2"),
        ("She's the person ___ helped me.", ["who", "which", "whose", "whom"], 0, "B1"),
        ("I'm looking forward ___ you.", ["to see", "to seeing", "seeing", "see"], 1, "B1"),
        ("Had I known, I ___ come.", ["will", "would have", "would", "had"], 1, "B2"),
        ("The house ___ built in 1990.", ["was", "were", "is", "has"], 0, "B2"),
        ("Seldom ___ such talent.", ["I have seen", "have I seen", "I saw", "did I saw"], 1, "C1"),
        ("'Bump into' someone means to ___ them.", ["meet by chance", "avoid", "insult", "help"], 0, "C1"),
    ],
    [  # Form 5
        ("You ___ my teacher.", ["is", "are", "am", "be"], 1, "A1"),
        ("I don't have ___ money.", ["some", "any", "much of", "many"], 1, "A1"),
        ("They ___ to Spain last summer.", ["travel", "traveled", "travels", "traveling"], 1, "A2"),
        ("He runs ___ of all.", ["fast", "faster", "fastest", "more fast"], 2, "A2"),
        ("If I ___ you, I'd apologize.", ["was", "were", "am", "be"], 1, "B1"),
        ("I haven't finished ___.", ["already", "yet", "still", "ever"], 1, "B1"),
        ("She made me ___ it again.", ["do", "to do", "doing", "did"], 0, "B2"),
        ("It's essential that he ___ on time.", ["is", "be", "was", "being"], 1, "B2"),
        ("Under no circumstances ___ leave.", ["you should", "should you", "you will", "will you"], 1, "C1"),
        ("'Look forward to' is followed by the ___.", ["base verb", "-ing form", "to + verb", "past"], 1, "C1"),
    ],
]


def get_test_form(idx: int | None = None) -> dict:
    import random
    if idx is None or not (0 <= idx < len(TEST_FORMS)):
        idx = random.randrange(len(TEST_FORMS))
    qs = [{"q": q, "opts": o, "level": lv} for (q, o, a, lv) in TEST_FORMS[idx]]
    return {"form_id": idx, "questions": qs}


_LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1"]


def _test_pool() -> list:
    pool = []
    for fi, form in enumerate(TEST_FORMS):
        for qi, (q, o, a, lv) in enumerate(form):
            pool.append({"id": fi * 10 + qi, "q": q, "opts": o, "a": a, "level": lv})
    return pool


def adaptive_next(answers: list, max_q: int = 12) -> dict:
    """Test ADAPTATIVO (sin estado en el servidor; el cliente manda el historial).
    answers = [{qid, choice}]. Sube/baja de dificultad según aciertos y converge."""
    import random
    pool = _test_pool()
    byid = {p["id"]: p for p in pool}
    diff = 2  # empieza en B1
    asked = set()
    correct = 0
    for ans in answers:
        p = byid.get(ans.get("qid"))
        asked.add(ans.get("qid"))
        if p:
            hit = ans.get("choice") == p["a"]
            correct += 1 if hit else 0
            diff = max(0, min(4, diff + (1 if hit else -1)))
    n = len(answers)
    if n >= max_q:
        # 'correct' se cuenta de verdad: antes el resultado se guardaba con 0
        # aciertos fijos y el historial mostraba "0 de 12" tras aprobar.
        return {"done": True, "level": _LEVEL_ORDER[diff], "asked": n, "correct": correct}
    order = [diff, diff - 1, diff + 1, diff - 2, diff + 2]
    for d in order:
        if 0 <= d < 5:
            cands = [p for p in pool if p["level"] == _LEVEL_ORDER[d] and p["id"] not in asked]
            if cands:
                q = random.choice(cands)
                return {"done": False, "asked": n + 1, "max": max_q,
                        "question": {"id": q["id"], "q": q["q"], "opts": q["opts"], "level": q["level"]}}
    # se agotaron las preguntas disponibles antes de max_q
    return {"done": True, "level": _LEVEL_ORDER[diff], "asked": n, "correct": correct}


def score_test(form_id: int, answers: list) -> dict:
    form = TEST_FORMS[form_id] if 0 <= form_id < len(TEST_FORMS) else TEST_FORMS[0]
    correct = 0
    for i, (q, o, a, lv) in enumerate(form):
        if i < len(answers) and answers[i] == a:
            correct += 1
    total = len(form)
    level = ("A1" if correct <= 2 else "A2" if correct <= 4 else "B1" if correct <= 6
             else "B2" if correct <= 8 else "C1")
    return {"correct": correct, "total": total, "level": level}


def ensure_sample_wav() -> None:
    """Audio de respaldo (silencio) si no existe."""
    import wave
    if os.path.exists(SAMPLE_WAV) and os.path.getsize(SAMPLE_WAV) > 0:
        return
    os.makedirs(ASSETS_DIR, exist_ok=True)
    with wave.open(SAMPLE_WAV, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        wf.writeframes(b"\x00\x00" * int(22050 * 0.4))
