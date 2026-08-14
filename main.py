"""
Lector de Idiomas — MVP (escritorio, estrictamente local).

App ejecutable con las 4 clases principales + servicios:
    - DatabaseManager  -> persistencia SQLite: libros y posición (real)
    - EpubParser       -> parseo EPUB con ebooklib + BeautifulSoup (real)
    - AudioPlayer      -> reproducción de voz vía QtMultimedia (real)
    - AppWindow        -> UI de dos paneles + orquestación (real)
    - LLMClient        -> traducción / gramática / ejemplos vía Gemini (real)
    - VocabWorker + AnkiExporter -> vocabulario efímero de sesión -> .apkg (real)

Ver ARCHITECTURE.md, SCHEMA.sql y TTS_FLOW.md para el diseño completo.

Requisitos:
    pip install -r requirements.txt
    (PyQt6, ebooklib, beautifulsoup4, pyttsx3, google-genai, genanki)

Servicios de IA (todo con degradación elegante — la app nunca se cae):
    - Voz (TTS): pyttsx3, usa las voces del sistema operativo. Gratis y offline.
      Corre en un SUBPROCESO (en macOS, dentro de un hilo produce audio vacío).
      Si falla, cae a un audio de respaldo (assets/sample.wav).
    - Texto (LLM): Google Gemini (free tier), SDK google-genai. Requiere la
      variable de entorno GEMINI_API_KEY. Sin ella, funciona en modo simulado.
          export GEMINI_API_KEY="tu_api_key"
      Consíguela gratis en: https://aistudio.google.com/apikey
      Modelo por defecto: gemini-2.5-flash (override con GEMINI_MODEL).
      Alternativa ligera si topas límites: gemini-flash-lite-latest.

Vocabulario:
    Efímero por sesión (en memoria; NO se guarda en la DB). Selecciona una palabra
    en el visor, pulsa "➕ Vocabulario" y al terminar exporta un .apkg para Anki
    (tarjeta: palabra + audio / traducción + oración de ejemplo + audio).

Ejecutar:
    python main.py
"""

# Copyright (C) 2026 Marco Antonio Garcia
#
# Este archivo es parte de este proyecto, software libre bajo la GNU Affero
# General Public License v3 o posterior. Se distribuye SIN NINGUNA GARANTÍA.
# Ver el archivo LICENSE para los términos completos.

from __future__ import annotations

import hashlib
import html
import os
import re
import sqlite3
import subprocess
import sys
import time
import wave

from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

# --------------------------------------------------------------------------- #
# Rutas
# --------------------------------------------------------------------------- #
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "SCHEMA.sql")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
SAMPLE_WAV = os.path.join(ASSETS_DIR, "sample.wav")
TTS_CACHE_DIR = os.path.join(ASSETS_DIR, "tts_cache")

# Modelo Gemini (override con la variable de entorno GEMINI_MODEL).
# gemini-2.5-flash: buena calidad y con cuota en el free tier.
# Alternativa más ligera si topas límites: gemini-flash-lite-latest.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


# --------------------------------------------------------------------------- #
# 1) DatabaseManager — dueña única de la conexión SQLite
# --------------------------------------------------------------------------- #
class DatabaseManager:
    """Toda la persistencia pasa por aquí. Nadie más toca la DB directamente."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self._apply_schema()

    def _apply_schema(self) -> None:
        """Aplica SCHEMA.sql (idempotente)."""
        if not os.path.exists(SCHEMA_PATH):
            raise FileNotFoundError(f"No se encontró el esquema: {SCHEMA_PATH}")
        with open(SCHEMA_PATH, "r", encoding="utf-8") as fh:
            self.conn.executescript(fh.read())
        self.conn.commit()

    # --- libros --------------------------------------------------------- #
    def list_books(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT id, title, author FROM books ORDER BY added_at DESC"
        ).fetchall()

    def add_book(self, title: str, author: str, language: str, source_path: str) -> int:
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO books (title, author, language, source_path) "
            "VALUES (?, ?, ?, ?)",
            (title, author, language, source_path),
        )
        self.conn.commit()
        if cur.lastrowid:
            return cur.lastrowid
        row = self.conn.execute(
            "SELECT id FROM books WHERE source_path = ?", (source_path,)
        ).fetchone()
        return row["id"]

    def find_book_by_path(self, source_path: str) -> int | None:
        row = self.conn.execute(
            "SELECT id FROM books WHERE source_path = ?", (source_path,)
        ).fetchone()
        return row["id"] if row else None

    def import_book(self, source_path: str, parsed: dict) -> int:
        """Persiste un libro parseado (libro + capítulos + oraciones) en una
        transacción. Si el libro ya fue importado (mismo source_path), lo reemplaza."""
        existing = self.find_book_by_path(source_path)
        try:
            if existing is not None:
                # Reemplaza: al borrar el libro, CASCADE limpia capítulos/oraciones/estado.
                self.conn.execute("DELETE FROM books WHERE id = ?", (existing,))

            cur = self.conn.execute(
                "INSERT INTO books (title, author, language, source_path) VALUES (?, ?, ?, ?)",
                (parsed["title"], parsed.get("author", ""), parsed.get("language", ""), source_path),
            )
            book_id = cur.lastrowid

            for ch_index, chapter in enumerate(parsed["chapters"]):
                cur = self.conn.execute(
                    "INSERT INTO chapters (book_id, chapter_index, title) VALUES (?, ?, ?)",
                    (book_id, ch_index, chapter.get("title")),
                )
                chapter_id = cur.lastrowid
                self.conn.executemany(
                    "INSERT INTO sentences (book_id, chapter_id, sentence_index, content) "
                    "VALUES (?, ?, ?, ?)",
                    [
                        (book_id, chapter_id, s_index, content)
                        for s_index, content in enumerate(chapter["sentences"])
                    ],
                )
            self.conn.commit()
            return book_id
        except Exception:
            self.conn.rollback()
            raise

    def get_chapter_count(self, book_id: int) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM chapters WHERE book_id = ?", (book_id,)
        ).fetchone()
        return row["n"]

    # --- oraciones ------------------------------------------------------ #
    def get_sentences(self, book_id: int, chapter_index: int) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT s.content
            FROM sentences s
            JOIN chapters c ON c.id = s.chapter_id
            WHERE s.book_id = ? AND c.chapter_index = ?
            ORDER BY s.sentence_index
            """,
            (book_id, chapter_index),
        ).fetchall()
        return [r["content"] for r in rows]

    # --- estado de lectura (autoguardado) ------------------------------ #
    def save_reading_state(
        self, book_id: int, chapter_index: int, sentence_index: int
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO reading_state (book_id, chapter_index, sentence_index, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(book_id) DO UPDATE SET
                chapter_index  = excluded.chapter_index,
                sentence_index = excluded.sentence_index,
                updated_at     = excluded.updated_at
            """,
            (book_id, chapter_index, sentence_index),
        )
        self.conn.commit()

    def load_reading_state(self, book_id: int) -> tuple[int, int]:
        row = self.conn.execute(
            "SELECT chapter_index, sentence_index FROM reading_state WHERE book_id = ?",
            (book_id,),
        ).fetchone()
        if row is None:
            return (0, 0)
        return (row["chapter_index"], row["sentence_index"])

    # --- caché de traducciones (LLM) ----------------------------------- #
    def get_cached_translation(
        self, source_text: str, target_lang: str = "es", kind: str = "translation"
    ) -> str | None:
        row = self.conn.execute(
            "SELECT result FROM translations "
            "WHERE source_text = ? AND target_lang = ? AND kind = ?",
            (source_text, target_lang, kind),
        ).fetchone()
        return row["result"] if row else None

    def cache_translation(
        self,
        source_text: str,
        result: str,
        target_lang: str = "es",
        kind: str = "translation",
    ) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO translations (source_text, target_lang, kind, result) "
            "VALUES (?, ?, ?, ?)",
            (source_text, target_lang, kind, result),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()


# --------------------------------------------------------------------------- #
# 2) EpubParser — EPUB -> {libro, capítulos, oraciones} (ebooklib + BeautifulSoup)
# --------------------------------------------------------------------------- #
class EpubParser:
    """Convierte un .epub en {libro, capítulos, oraciones}. No toca la GUI.

    Devuelve:
        {
            "title": str, "author": str, "language": str,
            "chapters": [ {"title": str, "sentences": [str, ...]}, ... ]
        }
    Solo incluye capítulos con al menos una oración.
    """

    # Etiquetas cuyo contenido NO es texto de lectura.
    _DROP_TAGS = ("script", "style", "head", "title", "nav")

    def parse(self, epub_path: str) -> dict:
        # Imports diferidos: la app arranca aunque ebooklib no esté instalado.
        try:
            import ebooklib
            from ebooklib import epub
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Falta 'ebooklib'. Instálalo con: pip install ebooklib"
            ) from exc
        from bs4 import BeautifulSoup

        book = epub.read_epub(epub_path)

        title = self._first_metadata(book, "title") or os.path.basename(epub_path)
        author = self._first_metadata(book, "creator") or ""
        language = self._first_metadata(book, "language") or ""

        # Recorre el spine (orden de lectura real), no el orden físico de los archivos.
        chapters: list[dict] = []
        for spine_id, _ in book.spine:
            item = book.get_item_with_id(spine_id)
            if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue

            soup = BeautifulSoup(item.get_content(), "html.parser")
            for tag in soup(self._DROP_TAGS):
                tag.decompose()

            # El título del capítulo sale del primer encabezado; luego se elimina
            # del cuerpo para que no se duplique dentro de la primera oración.
            heading = soup.find(["h1", "h2", "h3"])
            ch_title = (
                heading.get_text(" ", strip=True)
                if heading
                else f"Capítulo {len(chapters) + 1}"
            )
            if heading:
                heading.decompose()

            text = soup.get_text(" ", strip=True)
            sentences = self._split_sentences(text)
            if not sentences:
                continue

            chapters.append({"title": ch_title, "sentences": sentences})

        if not chapters:
            raise RuntimeError("El EPUB no contiene texto legible que se pueda extraer.")

        return {
            "title": title,
            "author": author,
            "language": language,
            "chapters": chapters,
        }

    @staticmethod
    def _first_metadata(book, name: str) -> str:
        data = book.get_metadata("DC", name)
        return data[0][0].strip() if data and data[0] and data[0][0] else ""

    # Abreviaturas comunes tras las que un punto NO termina oración.
    _ABBREV = {"mr", "mrs", "ms", "dr", "st", "vs", "etc", "e.g", "i.e", "sr", "sra", "dra"}

    @classmethod
    def _split_sentences(cls, text: str) -> list[str]:
        """Segmentador ligero: corta en . ! ? … seguido de espacio y mayúscula/comilla,
        evitando abreviaturas comunes. Suficiente para el MVP; sin dependencias extra."""
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return []

        # Marca fronteras candidatas de oración.
        candidate = re.sub(r'([.!?…])(["»”\')\]]?)\s+(?=[A-ZÁÉÍÓÚÑ¿¡"«])', r"\1\2\n", text)

        sentences: list[str] = []
        pending = ""  # fragmento retenido que terminó en abreviatura (falso corte)
        for piece in candidate.split("\n"):
            piece = piece.strip()
            if not piece:
                continue
            if pending:
                piece = pending + " " + piece
                pending = ""
            last_word = piece.rstrip(".!?…\"»”')]").split(" ")[-1].lower()
            if last_word in cls._ABBREV:
                pending = piece  # retiene: se fusiona con el siguiente fragmento
            else:
                sentences.append(piece)
        if pending:
            sentences.append(pending)
        return sentences


# --------------------------------------------------------------------------- #
# 3) AudioPlayer — reproduce el .wav de una oración (QtMultimedia)
# --------------------------------------------------------------------------- #
class AudioPlayer(QObject):
    finished = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._player = QMediaPlayer()
        self._output = QAudioOutput()
        self._player.setAudioOutput(self._output)
        self._player.mediaStatusChanged.connect(self._on_status)

    def play(self, path: str) -> None:
        self.stop()
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()

    def pause(self) -> None:
        self._player.pause()

    def stop(self) -> None:
        self._player.stop()

    def _on_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.finished.emit()


# --------------------------------------------------------------------------- #
# Servicios de IA (corren SIEMPRE dentro de un worker, nunca en la UI).
# Ver TTS_FLOW.md. Diseñados con degradación elegante: si algo falla, la app
# sigue funcionando (voz -> audio de respaldo; texto -> modo simulado).
# --------------------------------------------------------------------------- #
# Script que corre pyttsx3 en un subproceso (su propio hilo principal). Esto evita el
# bug de macOS donde save_to_file() dentro de un QThread produce audio truncado/vacío.
_TTS_SUBPROCESS = (
    "import sys, pyttsx3;"
    "text=sys.stdin.buffer.read().decode('utf-8'); out=sys.argv[1];"
    "e=pyttsx3.init(); e.save_to_file(text, out); e.runAndWait(); e.stop()"
)


def synthesize(text: str) -> str:
    """TTS con pyttsx3 (voz del sistema, offline y gratis). Devuelve la ruta de un
    .wav. Cachea por hash de texto: la segunda vez es instantánea.

    pyttsx3 se ejecuta en un SUBPROCESO, no en el QThread que llama a esta función:
    en macOS, correrlo en un hilo secundario genera audio vacío. El QThread solo
    espera al subproceso, así que la UI sigue libre. Si algo falla, devuelve el
    audio de respaldo para no romper el ciclo de lectura."""
    os.makedirs(TTS_CACHE_DIR, exist_ok=True)
    key = hashlib.md5(text.encode("utf-8")).hexdigest()
    out_path = os.path.join(TTS_CACHE_DIR, f"{key}.wav")
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path  # cache hit: 0 espera
    try:
        subprocess.run(
            [sys.executable, "-c", _TTS_SUBPROCESS, out_path],
            input=text.encode("utf-8"),
            timeout=30,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path
    except Exception:
        pass  # cae al respaldo
    return SAMPLE_WAV


# Prompts por tipo de tarea del LLM. Se cachean por (texto, idioma, kind).
_LLM_PROMPTS = {
    "translation": (
        "Traduce el siguiente texto al {lang} de forma natural y fiel. "
        "Responde ÚNICAMENTE con la traducción, sin comillas ni explicaciones.\n\nTexto:\n{text}"
    ),
    "grammar": (
        "Explica en {lang}, de forma breve y clara (máximo 4 líneas), la gramática del "
        "siguiente texto: tiempos verbales, estructura y cualquier punto útil para quien "
        "aprende el idioma.\n\nTexto:\n{text}"
    ),
    "example": (
        "A partir del vocabulario o estructura clave del siguiente texto, da 2 ejemplos "
        "nuevos en el idioma original, cada uno con su traducción al {lang}. "
        "Formato: '- ejemplo — traducción'.\n\nTexto:\n{text}"
    ),
}

_LANG_NAMES = {"es": "español", "en": "inglés", "fr": "francés", "de": "alemán"}


def llm_generate(text: str, kind: str = "translation", target_lang: str = "es") -> str:
    """Llama a Gemini para traducir / explicar gramática / dar ejemplos.
    Requiere GEMINI_API_KEY. Sin la clave, devuelve un resultado simulado para que
    la app siga siendo usable. Corre SIEMPRE dentro de LLMWorker."""
    api_key = os.environ.get("GEMINI_API_KEY")
    lang_name = _LANG_NAMES.get(target_lang, target_lang)
    prompt = _LLM_PROMPTS.get(kind, _LLM_PROMPTS["translation"]).format(
        lang=lang_name, text=text
    )

    if not api_key:
        time.sleep(0.3)  # simula un pequeño delay
        return f"[modo simulado — define GEMINI_API_KEY para IA real] ({kind}) {text}"

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return (response.text or "").strip() or "[respuesta vacía del modelo]"
    except Exception as exc:  # red caída, cuota agotada, etc.
        return f"[error de IA: {exc}]"


# --------------------------------------------------------------------------- #
# Workers asíncronos (QThread) — nunca bloquean la UI
# --------------------------------------------------------------------------- #
class TTSWorker(QThread):
    ready = pyqtSignal(int, str)  # (sentence_index, audio_path)

    def __init__(self, index: int, text: str) -> None:
        super().__init__()
        self._index = index
        self._text = text

    def run(self) -> None:
        path = synthesize(self._text)
        self.ready.emit(self._index, path)


class LLMWorker(QThread):
    done = pyqtSignal(str)  # texto resultado

    def __init__(self, text: str, kind: str = "translation", target_lang: str = "es") -> None:
        super().__init__()
        self._text = text
        self._kind = kind
        self._target_lang = target_lang

    def run(self) -> None:
        result = llm_generate(self._text, self._kind, self._target_lang)
        self.done.emit(result)


# --------------------------------------------------------------------------- #
# 5) LLMClient — envuelve el LLM con caché-primero (traducción/gramática/ejemplos)
# --------------------------------------------------------------------------- #
class LLMClient:
    """Coordina caché + LLMWorker. Devuelve por callback (async) o directo (cache hit).
    Mantiene referencias vivas a los workers en curso para que no los recoja el GC."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db
        self._workers: set[LLMWorker] = set()

    def request_async(
        self, text: str, kind: str, on_result, target_lang: str = "es"
    ) -> None:
        cached = self.db.get_cached_translation(text, target_lang, kind)
        if cached is not None:
            on_result(cached)  # 0 delay, 0 tokens
            return

        worker = LLMWorker(text, kind, target_lang)

        def _done(result: str) -> None:
            # No cachear resultados de error/simulados (para reintentar luego con IA real).
            if not result.startswith(("[error de IA:", "[modo simulado")):
                self.db.cache_translation(text, result, target_lang, kind)
            on_result(result)

        worker.done.connect(_done)
        worker.finished.connect(lambda: self._workers.discard(worker))
        self._workers.add(worker)
        worker.start()


# --------------------------------------------------------------------------- #
# VocabWorker — arma una entrada de vocabulario completa (traducción + audios)
# en un solo hilo, sin tocar la DB (la conexión SQLite no es cross-thread).
# --------------------------------------------------------------------------- #
class VocabWorker(QThread):
    ready = pyqtSignal(dict)

    def __init__(self, word: str, example: str, target_lang: str = "es") -> None:
        super().__init__()
        self._word = word
        self._example = example
        self._target_lang = target_lang

    def run(self) -> None:
        translation = llm_generate(self._word, "translation", self._target_lang)
        word_audio = synthesize(self._word)
        example_audio = synthesize(self._example) if self._example else ""
        self.ready.emit(
            {
                "word": self._word,
                "translation": translation,
                "example": self._example,
                "word_audio": word_audio,
                "example_audio": example_audio,
            }
        )


# --------------------------------------------------------------------------- #
# AnkiExporter — construye un .apkg (genanki) con audio embebido
# --------------------------------------------------------------------------- #
class AnkiExporter:
    """Genera un paquete .apkg importable en Anki. Tarjeta:
    frente = palabra + audio; reverso = traducción + oración de ejemplo + audio."""

    # IDs fijos: al reimportar, Anki reconoce el mismo modelo/mazo y no duplica.
    _MODEL_ID = 1738294011
    _DECK_ID = 1738294012

    @classmethod
    def export(cls, items: list[dict], deck_name: str, out_path: str) -> int:
        import genanki  # import diferido

        model = genanki.Model(
            cls._MODEL_ID,
            "AppIdiomas Vocab",
            fields=[
                {"name": "Word"},
                {"name": "Translation"},
                {"name": "Example"},
                {"name": "WordAudio"},
                {"name": "ExampleAudio"},
            ],
            templates=[
                {
                    "name": "Card 1",
                    "qfmt": '<div style="font-size:24px">{{Word}}</div>{{WordAudio}}',
                    "afmt": (
                        '{{FrontSide}}<hr id="answer">'
                        '<div style="font-size:20px;color:#2a6">{{Translation}}</div>'
                        '<br><div style="color:#555">{{Example}}</div>{{ExampleAudio}}'
                    ),
                }
            ],
        )

        deck = genanki.Deck(cls._DECK_ID, deck_name)
        media: set[str] = set()

        for it in items:
            w_snd = cls._sound_field(it.get("word_audio"), media)
            e_snd = cls._sound_field(it.get("example_audio"), media)
            note = genanki.Note(
                model=model,
                fields=[
                    html.escape(it["word"]),
                    html.escape(it["translation"]),
                    html.escape(it.get("example", "")),
                    w_snd,
                    e_snd,
                ],
            )
            deck.add_note(note)

        package = genanki.Package(deck)
        package.media_files = sorted(media)
        package.write_to_file(out_path)
        return len(items)

    @staticmethod
    def _sound_field(path: str | None, media: set[str]) -> str:
        """Devuelve el tag [sound:...] y registra el archivo de audio para empaquetar."""
        if path and os.path.exists(path) and os.path.getsize(path) > 0:
            media.add(path)
            return f"[sound:{os.path.basename(path)}]"
        return ""


# --------------------------------------------------------------------------- #
# 4) AppWindow — UI de dos paneles + orquestación
# --------------------------------------------------------------------------- #
class AppWindow(QMainWindow):
    def __init__(self, db: DatabaseManager) -> None:
        super().__init__()
        self.db = db
        self.audio = AudioPlayer()
        self.llm = LLMClient(db)
        self.parser = EpubParser()

        # --- estado de lectura en memoria (ver TTS_FLOW.md) ---
        self.current_book_id: int | None = None
        self.current_chapter_index = 0
        self.current_sentence_index = 0
        self.chapter_count = 0
        self.sentences: list[str] = []
        self.is_playing = False
        self.prefetch_cache: dict[int, str] = {}
        self._tts_workers: set[TTSWorker] = set()  # referencias vivas (evita GC)
        self._vocab_workers: set[VocabWorker] = set()

        # Vocabulario EFÍMERO de la sesión (en memoria; se descarta al cerrar).
        self.vocab_items: list[dict] = []

        self.setWindowTitle("Lector de Idiomas — MVP")
        self.resize(1100, 700)
        self._build_ui()

        self.audio.finished.connect(self._advance)
        self._refresh_library()

    # ------------------------------------------------------------------ #
    # UI
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Panel izquierdo: biblioteca
        self.library = QListWidget()
        self.library.itemClicked.connect(self._on_book_selected)
        self.btn_load = QPushButton("📖 Cargar EPUB")
        self.btn_load.clicked.connect(self._load_epub)

        # Vocabulario de la sesión (efímero)
        self.vocab_list = QListWidget()
        self.vocab_list.setToolTip("Vocabulario de esta sesión. Se descarta al cerrar.")
        self.btn_export_anki = QPushButton("⬇ Exportar a Anki (.apkg)")
        self.btn_export_anki.clicked.connect(self._export_anki)
        self.btn_clear_vocab = QPushButton("Vaciar")
        self.btn_clear_vocab.clicked.connect(self._clear_vocab)
        vocab_btns = QHBoxLayout()
        vocab_btns.addWidget(self.btn_export_anki)
        vocab_btns.addWidget(self.btn_clear_vocab)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Biblioteca"))
        left_layout.addWidget(self.library)
        left_layout.addWidget(self.btn_load)
        left_layout.addWidget(QLabel("Vocabulario (sesión)"))
        left_layout.addWidget(self.vocab_list)
        left_layout.addLayout(vocab_btns)
        splitter.addWidget(left)

        # Panel derecho: visor + controles + traducción
        self.reader = QTextBrowser()
        self.reader.setOpenExternalLinks(False)
        self.reader.setStyleSheet("font-size: 16px; padding: 12px;")
        self.reader.anchorClicked.connect(self._on_sentence_clicked)

        self.btn_play = QPushButton("▶ Leer")
        self.btn_play.clicked.connect(self._toggle_play)
        self.btn_translate = QPushButton("Traducir")
        self.btn_translate.clicked.connect(lambda: self._ask_llm("translation"))
        self.btn_grammar = QPushButton("Gramática")
        self.btn_grammar.clicked.connect(lambda: self._ask_llm("grammar"))
        self.btn_example = QPushButton("Ejemplos")
        self.btn_example.clicked.connect(lambda: self._ask_llm("example"))
        self.btn_add_vocab = QPushButton("➕ Vocabulario")
        self.btn_add_vocab.setToolTip(
            "Selecciona una palabra en el texto y pulsa aquí para añadirla al mazo de la sesión."
        )
        self.btn_add_vocab.clicked.connect(self._add_vocab)

        controls = QHBoxLayout()
        controls.addWidget(self.btn_play)
        controls.addWidget(self.btn_translate)
        controls.addWidget(self.btn_grammar)
        controls.addWidget(self.btn_example)
        controls.addWidget(self.btn_add_vocab)
        controls.addStretch()

        self.info_panel = QLabel("Selecciona un libro y usa los botones sobre la oración actual.")
        self.info_panel.setWordWrap(True)
        self.info_panel.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.info_panel.setStyleSheet(
            "padding: 10px; background: rgba(0,0,0,0.05); border-radius: 6px;"
        )

        self.chapter_label = QLabel("Visor de lectura")
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(self.chapter_label)
        right_layout.addWidget(self.reader, stretch=1)
        right_layout.addLayout(controls)
        right_layout.addWidget(self.info_panel)
        splitter.addWidget(right)

        splitter.setSizes([280, 820])
        self.setCentralWidget(splitter)

    def _refresh_library(self) -> None:
        self.library.clear()
        books = self.db.list_books()
        if not books:
            # Sin libros aún: crea uno de demo para poder probar el flujo end-to-end.
            self._seed_demo_book()
            books = self.db.list_books()
        for b in books:
            item = QListWidgetItem(f"{b['title']} — {b['author'] or '¿?'}")
            item.setData(Qt.ItemDataRole.UserRole, b["id"])
            self.library.addItem(item)

    def _seed_demo_book(self) -> None:
        """Datos de demo (mientras EpubParser está en mock) para probar la UI."""
        book_id = self.db.add_book("Libro de prueba", "Autor Demo", "en", "demo://sample")
        exists = self.db.conn.execute(
            "SELECT 1 FROM chapters WHERE book_id = ?", (book_id,)
        ).fetchone()
        if exists:
            return
        cur = self.db.conn.execute(
            "INSERT INTO chapters (book_id, chapter_index, title) VALUES (?, 0, ?)",
            (book_id, "Chapter 1"),
        )
        chapter_id = cur.lastrowid
        demo_sentences = [
            "The cat is sleeping on the sofa.",
            "Outside, the rain falls quietly.",
            "She opens the book and starts to read.",
            "Learning a language takes time and patience.",
        ]
        for i, text in enumerate(demo_sentences):
            self.db.conn.execute(
                "INSERT INTO sentences (book_id, chapter_id, sentence_index, content) "
                "VALUES (?, ?, ?, ?)",
                (book_id, chapter_id, i, text),
            )
        self.db.conn.commit()

    # ------------------------------------------------------------------ #
    # Carga de EPUB
    # ------------------------------------------------------------------ #
    def _load_epub(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar EPUB", "", "Libros EPUB (*.epub)"
        )
        if not path:
            return
        try:
            parsed = self.parser.parse(path)
            book_id = self.db.import_book(path, parsed)
        except Exception as exc:  # muestra el error sin tumbar la app
            QMessageBox.critical(self, "Error al cargar EPUB", str(exc))
            return
        self._refresh_library()
        n_ch = len(parsed["chapters"])
        n_sent = sum(len(c["sentences"]) for c in parsed["chapters"])
        QMessageBox.information(
            self,
            "EPUB cargado",
            f"«{parsed['title']}»\n{n_ch} capítulos · {n_sent} oraciones.",
        )
        self._open_book(book_id)

    # ------------------------------------------------------------------ #
    # Carga de libro / capítulo
    # ------------------------------------------------------------------ #
    def _on_book_selected(self, item: QListWidgetItem) -> None:
        self._open_book(item.data(Qt.ItemDataRole.UserRole))

    def _open_book(self, book_id: int) -> None:
        self.current_book_id = book_id
        self.chapter_count = self.db.get_chapter_count(book_id)
        ch, sent = self.db.load_reading_state(book_id)  # restaura posición
        self._load_chapter(ch, sentence_index=sent)

    def _load_chapter(self, chapter_index: int, sentence_index: int = 0) -> None:
        assert self.current_book_id is not None
        self.current_chapter_index = chapter_index
        self.sentences = self.db.get_sentences(self.current_book_id, chapter_index)
        self.current_sentence_index = min(sentence_index, max(len(self.sentences) - 1, 0))
        self.prefetch_cache.clear()
        self.chapter_label.setText(
            f"Capítulo {chapter_index + 1} de {self.chapter_count}"
        )
        self._render()

    def _render(self) -> None:
        """Renderiza las oraciones; resalta la actual como enlaces clicables por índice."""
        parts = []
        for i, s in enumerate(self.sentences):
            safe = html.escape(s)  # el texto del EPUB puede traer &, <, >
            if i == self.current_sentence_index:
                parts.append(
                    f'<a name="cur"></a>'
                    f'<span style="background:#ffe27a;border-radius:4px;">'
                    f'<a href="{i}" style="color:inherit;text-decoration:none;">{safe}</a></span>'
                )
            else:
                parts.append(f'<a href="{i}" style="color:inherit;text-decoration:none;">{safe}</a>')
        self.reader.setHtml(" ".join(parts))
        self.reader.scrollToAnchor("cur")

    # ------------------------------------------------------------------ #
    # Ciclo de lectura asistida (ver TTS_FLOW.md)
    # ------------------------------------------------------------------ #
    def _toggle_play(self) -> None:
        if self.current_book_id is None or not self.sentences:
            return
        if self.is_playing:
            self.audio.pause()
            self.is_playing = False
            self.btn_play.setText("▶ Leer")
            self._save_state()  # guardar al pausar
        else:
            self.is_playing = True
            self.btn_play.setText("⏸ Pausar")
            self._speak_current()

    def _speak_current(self) -> None:
        idx = self.current_sentence_index
        self._render()
        if idx in self.prefetch_cache:
            self.audio.play(self.prefetch_cache[idx])
            self._prefetch(idx + 1)
            return
        self._start_tts(idx)

    def _on_tts_ready(self, index: int, path: str) -> None:
        self.prefetch_cache[index] = path
        if index == self.current_sentence_index and self.is_playing:
            self.audio.play(path)
            self._prefetch(index + 1)

    def _prefetch(self, index: int) -> None:
        if index >= len(self.sentences) or index in self.prefetch_cache:
            return
        self._start_tts(index)

    def _start_tts(self, index: int) -> None:
        """Lanza un TTSWorker manteniendo su referencia viva hasta que termina."""
        worker = TTSWorker(index, self.sentences[index])
        worker.ready.connect(self._on_tts_ready)
        worker.finished.connect(lambda: self._tts_workers.discard(worker))
        self._tts_workers.add(worker)
        worker.start()

    def _advance(self) -> None:
        if not self.is_playing:
            return
        self.current_sentence_index += 1
        if self.current_sentence_index >= len(self.sentences):
            # Fin del capítulo: pasa al siguiente si existe; si no, se detiene.
            if self.current_chapter_index + 1 < self.chapter_count:
                self._load_chapter(self.current_chapter_index + 1, sentence_index=0)
                self._save_state()
                self._speak_current()
                return
            self.current_sentence_index = len(self.sentences) - 1
            self.is_playing = False
            self.btn_play.setText("▶ Leer")
            self._save_state()
            return
        self._save_state()  # autoguardado en cada avance
        self._speak_current()

    def _on_sentence_clicked(self, url) -> None:
        """Salto: clic en una oración -> el estado salta a ese índice."""
        try:
            index = int(url.toString())
        except ValueError:
            return
        self.audio.stop()
        self.current_sentence_index = index
        self.prefetch_cache.clear()  # descartar prefetch obsoleto
        self._save_state()
        if self.is_playing:
            self._speak_current()  # recalcular audio de la nueva posición
        else:
            self._render()

    # ------------------------------------------------------------------ #
    # IA sobre la oración actual (traducción / gramática / ejemplos)
    # ------------------------------------------------------------------ #
    _LLM_LABELS = {"translation": "Traducción", "grammar": "Gramática", "example": "Ejemplos"}

    def _ask_llm(self, kind: str) -> None:
        if not self.sentences:
            return
        text = self.sentences[self.current_sentence_index]
        label = self._LLM_LABELS.get(kind, "Resultado")
        self.info_panel.setText(f"{label}: …")
        self.llm.request_async(
            text, kind, lambda r: self.info_panel.setText(f"{label}: {r}")
        )

    # ------------------------------------------------------------------ #
    # Vocabulario efímero -> Anki
    # ------------------------------------------------------------------ #
    def _add_vocab(self) -> None:
        """Toma la palabra SELECCIONADA en el visor + la oración actual como contexto,
        y lanza un worker que arma traducción + audios. Nada se guarda en la DB."""
        if not self.sentences:
            return
        word = self.reader.textCursor().selectedText().strip()
        if not word:
            self.info_panel.setText(
                "Vocabulario: selecciona primero una palabra en el texto y vuelve a pulsar ➕."
            )
            return
        example = self.sentences[self.current_sentence_index]
        self.info_panel.setText(f"Vocabulario: preparando «{word}»…")

        worker = VocabWorker(word, example)
        worker.ready.connect(self._on_vocab_ready)
        worker.finished.connect(lambda: self._vocab_workers.discard(worker))
        self._vocab_workers.add(worker)
        worker.start()

    def _on_vocab_ready(self, item: dict) -> None:
        self.vocab_items.append(item)
        self.vocab_list.addItem(
            QListWidgetItem(f"{item['word']}  →  {item['translation']}")
        )
        self.info_panel.setText(
            f"Vocabulario: «{item['word']}» añadido ({len(self.vocab_items)} en la sesión)."
        )

    def _clear_vocab(self) -> None:
        self.vocab_items.clear()
        self.vocab_list.clear()
        self.info_panel.setText("Vocabulario: lista vaciada.")

    def _export_anki(self) -> None:
        if not self.vocab_items:
            QMessageBox.information(
                self, "Sin vocabulario", "Aún no has añadido palabras a la sesión."
            )
            return
        default_name = "vocabulario_appidiomas.apkg"
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar a Anki", default_name, "Paquete Anki (*.apkg)"
        )
        if not path:
            return
        if not path.endswith(".apkg"):
            path += ".apkg"
        try:
            deck_name = "AppIdiomas — Vocabulario"
            n = AnkiExporter.export(self.vocab_items, deck_name, path)
        except Exception as exc:
            QMessageBox.critical(self, "Error al exportar", str(exc))
            return
        QMessageBox.information(
            self, "Exportado", f"{n} tarjetas exportadas a:\n{path}\n\nÁbrelo con Anki."
        )

    # ------------------------------------------------------------------ #
    # Estado
    # ------------------------------------------------------------------ #
    def _save_state(self) -> None:
        if self.current_book_id is not None:
            self.db.save_reading_state(
                self.current_book_id,
                self.current_chapter_index,
                self.current_sentence_index,
            )

    def closeEvent(self, event) -> None:
        self._save_state()  # autoguardado al cerrar
        self.db.close()
        super().closeEvent(event)


# --------------------------------------------------------------------------- #
# Audio de respaldo
# --------------------------------------------------------------------------- #
def ensure_sample_wav() -> None:
    """Genera un .wav corto de respaldo (silencio) si no existe. Lo usa el ciclo de
    lectura cuando pyttsx3 no puede producir audio, para no romper el flujo."""
    if os.path.exists(SAMPLE_WAV) and os.path.getsize(SAMPLE_WAV) > 0:
        return
    os.makedirs(ASSETS_DIR, exist_ok=True)
    framerate = 22050
    duration_s = 0.4
    silence = b"\x00\x00" * int(framerate * duration_s)  # 16-bit mono
    with wave.open(SAMPLE_WAV, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(silence)


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #
def main() -> None:
    os.makedirs(ASSETS_DIR, exist_ok=True)
    os.makedirs(TTS_CACHE_DIR, exist_ok=True)
    ensure_sample_wav()
    db = DatabaseManager()
    app = QApplication(sys.argv)
    window = AppWindow(db)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
