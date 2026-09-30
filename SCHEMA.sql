-- Esquema SQLite — Lector de Idiomas (MVP)
-- Idempotente: seguro de ejecutar en cada arranque.
-- Principio: la ORACIÓN es la unidad atómica → una fila por oración.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- users: cuentas de la plataforma.
-- Fase 1 (actual): solo existe el admin (id=1) y todo el contenido personal ya
-- guardado se le asigna a el. NO hay login todavia: password_hash esta vacio a
-- proposito y nadie puede autenticarse.
-- Fase 2: login por username/contrasena; el admin da o retira acceso con
-- 'status'. La contrasena nunca se guarda en claro, solo su hash.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL COLLATE NOCASE,   -- login sin distinguir mayusculas
    password_hash TEXT    NOT NULL DEFAULT '',       -- vacio hasta la Fase 2
    role          TEXT    NOT NULL DEFAULT 'user',   -- 'admin' | 'user'
    status        TEXT    NOT NULL DEFAULT 'pending',-- 'pending' | 'active' | 'blocked'
    created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE (username),
    CHECK (role   IN ('admin', 'user')),
    CHECK (status IN ('pending', 'active', 'blocked'))
);

-- ---------------------------------------------------------------------------
-- books: un registro por EPUB importado
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS books (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT    NOT NULL,
    author        TEXT,
    language      TEXT,                       -- código idioma si el EPUB lo declara (ej. 'en')
    source_path   TEXT    NOT NULL,           -- ruta al .epub original
    added_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE (source_path)
);

-- ---------------------------------------------------------------------------
-- chapters: capítulos en orden de lectura (spine del EPUB)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chapters (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id        INTEGER NOT NULL,
    chapter_index  INTEGER NOT NULL,          -- 0-based, orden de lectura
    title          TEXT,                      -- título del capítulo si existe
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    UNIQUE (book_id, chapter_index)
);

-- ---------------------------------------------------------------------------
-- sentences: EL CORAZÓN DE LA APP. Una fila = una oración renderizable.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sentences (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id         INTEGER NOT NULL,
    chapter_id      INTEGER NOT NULL,
    sentence_index  INTEGER NOT NULL,         -- 0-based dentro del capítulo
    content         TEXT    NOT NULL,         -- texto limpio, listo para renderizar
    FOREIGN KEY (book_id)    REFERENCES books(id)    ON DELETE CASCADE,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE,
    UNIQUE (chapter_id, sentence_index)
);

CREATE INDEX IF NOT EXISTS idx_sentences_chapter
    ON sentences (chapter_id, sentence_index);

-- ---------------------------------------------------------------------------
-- reading_state: posición actual por libro (autoguardado).
-- Un solo registro por libro → última posición conocida.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reading_state (
    book_id         INTEGER PRIMARY KEY,      -- 1:1 con books
    chapter_index   INTEGER NOT NULL DEFAULT 0,
    sentence_index  INTEGER NOT NULL DEFAULT 0,
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- vocabulary: palabras/frases que el usuario guarda mientras lee
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vocabulary (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id       INTEGER,                    -- de qué libro salió (opcional)
    sentence_id   INTEGER,                    -- contexto: la oración origen (opcional)
    term          TEXT    NOT NULL,           -- palabra o frase seleccionada
    translation   TEXT,                       -- traducción / nota del usuario
    example       TEXT,                       -- oración de ejemplo (contexto)
    lang          TEXT    NOT NULL DEFAULT 'en', -- idioma original de la palabra
    -- Campos de repetición espaciada (SM-2):
    ease          REAL    NOT NULL DEFAULT 2.5,  -- factor de facilidad
    interval_days INTEGER NOT NULL DEFAULT 0,    -- días hasta el próximo repaso
    reps          INTEGER NOT NULL DEFAULT 0,    -- repasos correctos seguidos
    due           TEXT    NOT NULL DEFAULT (date('now','localtime')), -- fecha del próximo repaso
    created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (book_id)     REFERENCES books(id)     ON DELETE SET NULL,
    FOREIGN KEY (sentence_id) REFERENCES sentences(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_vocab_term ON vocabulary (term);
-- El índice sobre 'due' se crea en la migración (core._migrate), tras garantizar
-- que la columna existe también en bases de datos antiguas.

-- ---------------------------------------------------------------------------
-- translations: CACHÉ de resultados del LLM (Gemini).
-- Antes de llamar a la red, se busca aquí. Ahorra tokens del free tier y
-- elimina el delay en textos ya traducidos.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS translations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_text   TEXT    NOT NULL,           -- texto original (oración o palabra)
    target_lang   TEXT    NOT NULL DEFAULT 'es',
    kind          TEXT    NOT NULL DEFAULT 'translation', -- translation | grammar | example
    result        TEXT    NOT NULL,           -- respuesta del LLM
    created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE (source_text, target_lang, kind)
);

CREATE INDEX IF NOT EXISTS idx_translations_lookup
    ON translations (source_text, target_lang, kind);

-- ---------------------------------------------------------------------------
-- decks / deck_cards: mazos de aprendizaje ESTÁTICOS (tipo Refold), aparte del
-- vocabulario de los libros. Contenido y audio pre-generados y guardados.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT    NOT NULL UNIQUE,        -- 'words' | 'phrases' | 'phrasal'
    name        TEXT    NOT NULL,
    description TEXT,
    lang        TEXT    NOT NULL DEFAULT 'en',
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS deck_cards (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_id       INTEGER NOT NULL,
    position      INTEGER NOT NULL DEFAULT 0,   -- orden por frecuencia
    front         TEXT    NOT NULL,             -- palabra/frase en el idioma meta (lo que se escucha)
    translation   TEXT    NOT NULL,             -- traducción al español
    note          TEXT,                         -- ejemplo/uso o nota gramatical
    audio_file    TEXT,                         -- nombre del .wav pre-generado (Samantha)
    -- SRS (SM-2), por usuario/local:
    ease          REAL    NOT NULL DEFAULT 2.5,
    interval_days INTEGER NOT NULL DEFAULT 0,
    reps          INTEGER NOT NULL DEFAULT 0,
    due           TEXT    NOT NULL DEFAULT (date('now','localtime')),
    FOREIGN KEY (deck_id) REFERENCES decks(id) ON DELETE CASCADE,
    UNIQUE (deck_id, front)
);

CREATE INDEX IF NOT EXISTS idx_deckcards_due ON deck_cards (deck_id, due);

-- ---------------------------------------------------------------------------
-- study_log: un registro por día con cuántos repasos se hicieron -> rachas.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS study_log (
    day      TEXT    PRIMARY KEY,           -- 'YYYY-MM-DD'
    reviews  INTEGER NOT NULL DEFAULT 0
);

-- ---------------------------------------------------------------------------
-- activity_log: segundos ACTIVOS por día y módulo (heartbeats con interacción).
-- session_log: segundos con la app ABIERTA/visible por día (para procrastinación).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS activity_log (
    day     TEXT    NOT NULL,
    module  TEXT    NOT NULL,               -- reading | decks | writing | flashcards | stats | lessons
    seconds INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, module)
);

CREATE TABLE IF NOT EXISTS session_log (
    day          TEXT    PRIMARY KEY,
    open_seconds INTEGER NOT NULL DEFAULT 0
);

-- ---------------------------------------------------------------------------
-- new_intro: tarjetas NUEVAS introducidas por día y ámbito (candado diario SRS).
-- scope: 'vocab' | 'deck:<id>'
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS new_intro (
    day    TEXT    NOT NULL,
    scope  TEXT    NOT NULL,
    count  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, scope)
);

-- ---------------------------------------------------------------------------
-- test_results: resultados del test de diagnóstico de nivel.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS test_results (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    level      TEXT,
    correct    INTEGER,
    total      INTEGER,
    created_at TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ---------------------------------------------------------------------------
-- lesson_done: lecciones completadas (progreso de la ruta).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lesson_done (
    lesson_id  TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ---------------------------------------------------------------------------
-- writings: textos del usuario (Writing) — original + corregido + nivel.
-- writing_errors: diario de errores (para práctica dirigida).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS writings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT,
    original      TEXT    NOT NULL,
    corrected     TEXT,
    level         TEXT,               -- nivel CEFR evaluado del ORIGINAL
    assessment    TEXT,               -- por qué ese nivel (en español)
    upgraded      TEXT,               -- reescritura a nivel superior
    upgrade_level TEXT,               -- nivel objetivo de esa reescritura
    created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS writing_errors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    writing_id  INTEGER,
    original    TEXT,
    correction  TEXT,
    explanation TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (writing_id) REFERENCES writings(id) ON DELETE CASCADE
);
