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
    email         TEXT    COLLATE NOCASE,          -- alta por correo (Fase 2)
    -- Key de Gemini PROPIA de cada usuario: la cuota del free tier es por
    -- cuenta, asi que cada uno pone la suya. Es SU credencial: no se escribe
    -- en logs y al mostrarla de vuelta solo se enseñan los ultimos 4 caracteres.
    gemini_api_key TEXT   NOT NULL DEFAULT '',
    created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE (username),
    UNIQUE (email),
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
    -- 1 = lo ve todo el mundo; 0 = privado del admin.
    -- El limite legal de un libro con derechos es DISTRIBUIRLO, no tenerlo: el
    -- admin puede leer su copia y marcarla privada para no servirsela a nadie.
    -- Sirve igual para libros que todavia esta preparando.
    visible       INTEGER NOT NULL DEFAULT 1,
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
    user_id         INTEGER NOT NULL DEFAULT 1,
    book_id         INTEGER NOT NULL,         -- 1:1 con books POR usuario
    chapter_index   INTEGER NOT NULL DEFAULT 0,
    sentence_index  INTEGER NOT NULL DEFAULT 0,
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (user_id, book_id),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- vocabulary: palabras/frases que el usuario guarda mientras lee
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vocabulary (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL DEFAULT 1,
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

-- deck_cards guarda SOLO el contenido de la tarjeta, que es compartido: lo cura
-- el admin y lo ve todo el mundo. El progreso de estudio se fue a card_progress
-- porque es de cada uno: si viviera aqui, aprobar una tarjeta se la aprobaria a
-- todos los usuarios a la vez.
CREATE TABLE IF NOT EXISTS deck_cards (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_id       INTEGER NOT NULL,
    position      INTEGER NOT NULL DEFAULT 0,   -- orden por frecuencia
    front         TEXT    NOT NULL,             -- palabra/frase en el idioma meta (lo que se escucha)
    translation   TEXT    NOT NULL,             -- traducción al español
    note          TEXT,                         -- ejemplo/uso o nota gramatical
    category      TEXT,                         -- situación de uso ("Tiendas", "Restaurante")
    audio_file    TEXT,                         -- nombre del .wav pre-generado (Samantha)
    FOREIGN KEY (deck_id) REFERENCES decks(id) ON DELETE CASCADE,
    UNIQUE (deck_id, front)
);

-- card_progress: el estado SRS (SM-2) de UNA tarjeta para UN usuario.
-- No tener fila aqui significa "tarjeta sin ver": las consultas hacen LEFT JOIN
-- y rellenan con los valores por defecto, asi que un usuario nuevo empieza sin
-- una sola fila y aun asi ve el mazo entero como nuevo.
CREATE TABLE IF NOT EXISTS card_progress (
    user_id       INTEGER NOT NULL DEFAULT 1,
    card_id       INTEGER NOT NULL,
    ease          REAL    NOT NULL DEFAULT 2.5,  -- factor de facilidad
    interval_days INTEGER NOT NULL DEFAULT 0,    -- días hasta el próximo repaso
    reps          INTEGER NOT NULL DEFAULT 0,    -- repasos correctos seguidos
    due           TEXT    NOT NULL DEFAULT (date('now','localtime')),
    PRIMARY KEY (user_id, card_id),
    FOREIGN KEY (card_id) REFERENCES deck_cards(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_cardprog_due ON card_progress (user_id, due);

-- ---------------------------------------------------------------------------
-- study_log: un registro por día con cuántos repasos se hicieron -> rachas.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS study_log (
    user_id  INTEGER NOT NULL DEFAULT 1,
    day      TEXT    NOT NULL,              -- 'YYYY-MM-DD'
    reviews  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day)
);

-- ---------------------------------------------------------------------------
-- activity_log: segundos ACTIVOS por día y módulo (heartbeats con interacción).
-- session_log: segundos con la app ABIERTA/visible por día (para procrastinación).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS activity_log (
    user_id INTEGER NOT NULL DEFAULT 1,
    day     TEXT    NOT NULL,
    module  TEXT    NOT NULL,               -- reading | decks | writing | flashcards | stats | lessons
    seconds INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day, module)
);

CREATE TABLE IF NOT EXISTS session_log (
    user_id      INTEGER NOT NULL DEFAULT 1,
    day          TEXT    NOT NULL,
    open_seconds INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day)
);

-- ---------------------------------------------------------------------------
-- new_intro: tarjetas NUEVAS introducidas por día y ámbito (candado diario SRS).
-- scope: 'vocab' | 'deck:<id>'
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS new_intro (
    user_id INTEGER NOT NULL DEFAULT 1,
    day     TEXT    NOT NULL,
    scope   TEXT    NOT NULL,
    count   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day, scope)
);

-- ---------------------------------------------------------------------------
-- test_results: resultados del test de diagnóstico de nivel.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS test_results (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL DEFAULT 1,
    level      TEXT,
    correct    INTEGER,
    total      INTEGER,
    created_at TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ---------------------------------------------------------------------------
-- lesson_done: lecciones completadas (progreso de la ruta).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lesson_done (
    user_id    INTEGER NOT NULL DEFAULT 1,
    lesson_id  TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (user_id, lesson_id)
);

-- ---------------------------------------------------------------------------
-- writings: textos del usuario (Writing) — original + corregido + nivel.
-- writing_errors: diario de errores (para práctica dirigida).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS writings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL DEFAULT 1,
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
    user_id     INTEGER NOT NULL DEFAULT 1,
    writing_id  INTEGER,
    original    TEXT,
    correction  TEXT,
    explanation TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (writing_id) REFERENCES writings(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- custom_lessons: lecciones generadas a partir de los errores de UN usuario.
-- Vivia en core._migrate(); se trae aqui para que el esquema este en un solo
-- sitio. Cuesta una llamada a la IA, por eso se guarda.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS custom_lessons (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL DEFAULT 1,
    category    TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    level       TEXT,
    payload     TEXT    NOT NULL,              -- la leccion completa en JSON
    error_count INTEGER NOT NULL DEFAULT 0,
    done        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ---------------------------------------------------------------------------
-- user_settings: preferencias de estudio POR usuario (review_limit,
-- vocab_new_limit...). Sustituye a la tabla global app_settings: un tope de
-- repasos es una decision personal, no de la plataforma.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER NOT NULL DEFAULT 1,
    key     TEXT    NOT NULL,
    value   TEXT    NOT NULL,
    PRIMARY KEY (user_id, key)
);

-- Los indices sobre user_id se crean en la migracion (core._migrate_multiuser),
-- no aqui: este fichero se ejecuta ANTES que las migraciones y en una base
-- antigua la columna todavia no existe. Mismo motivo que idx_vocab_due.

-- ---------------------------------------------------------------------------
-- sessions: una sesion abierta = una fila. Se guarda el SHA-256 del token, no
-- el token: el original solo existe en la cookie del navegador, asi que quien
-- consiga leer esta tabla no puede suplantar a nadie.
-- Tenerlas en la base (y no en una cookie firmada) permite revocarlas: al
-- bloquear a alguien o cambiarle la contrasena, sus sesiones se borran y queda
-- fuera al instante.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT    PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    expires_at TEXT    NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions (user_id);

-- ---------------------------------------------------------------------------
-- chapter_done: capitulos que UN usuario ha terminado.
-- Antes era una columna 'done' en chapters, que es contenido compartido: si
-- alguien marcaba un capitulo como leido, se lo marcaba a todo el mundo. Mismo
-- error que tenia el SRS dentro de deck_cards.
-- No tener fila aqui significa "sin leer".
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chapter_done (
    user_id       INTEGER NOT NULL DEFAULT 1,
    book_id       INTEGER NOT NULL,
    chapter_index INTEGER NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (user_id, book_id, chapter_index),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);
