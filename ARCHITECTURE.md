# Arquitectura — Lector de Idiomas (MVP)

App de escritorio **estrictamente local**. Sin cliente-servidor, sin REST, sin microservicios.
Un solo proceso Python, una base SQLite (`database.db`), una ventana PyQt6.

## Principio rector

> **La unidad atómica de la app es la ORACIÓN.**

Todo el sistema (persistencia, TTS, traducción, resaltado, posición de lectura) gira en
torno a la oración como fila individual en la base de datos. Nada trabaja "palabra por
palabra".

---

## Decisiones de costo (premisa: gratis y funcional)

| Función | Servicio | Costo | ¿Corre local? |
|---|---|---|---|
| Voz / lectura en voz alta | **pyttsx3** (voz del SO) | Gratis | Sí (ligero, no es un LLM) |
| Traducción / gramática / ejemplos | **Google Gemini API** (free tier) | Gratis* | No (nube, pero gratis) |
| EPUB / UI / DB | Python + PyQt6 + SQLite | Gratis | Sí |

\* Free tier renovable por minuto/día. Para lectura personal alcanza de sobra.
Contrato estable: si algún día se cambia de proveedor, solo cambia el cuerpo de las
funciones `synthesize()` (TTS) y `translate()` (LLM); el resto queda intacto.

> **TTS ≠ LLM.** El LLM (Gemini) genera *texto* (traducciones, explicaciones).
> El TTS (pyttsx3) genera *voz*. Son dos motores distintos.

---

## Stack

| Capa | Tecnología |
|---|---|
| Lenguaje | Python 3.10+ |
| GUI | PyQt6 (nativa de escritorio) |
| Persistencia | SQLite3 (consultas directas, sin ORM) |
| Parseo EPUB | `ebooklib` + `BeautifulSoup` (`bs4`) |
| Audio | `PyQt6.QtMultimedia` (QMediaPlayer + QAudioOutput) reproduciendo `.wav` |
| TTS (voz) | `pyttsx3` → `save_to_file()` genera el `.wav` (hoy: mock con delay) |
| LLM (texto) | `google-generativeai` (Gemini) (hoy: mock con delay) |

> Prohibido: PDF, PyMuPDF, ORMs pesados, cualquier arquitectura de red propia.

---

## Las 4 clases principales + 1 servicio LLM

### 1. `DatabaseManager`
Dueña única de la conexión SQLite. Nadie más toca la DB directamente.

Responsabilidades:
- Abrir/crear `database.db` y aplicar `SCHEMA.sql` (idempotente).
- CRUD de libros, capítulos y oraciones.
- Leer/escribir `reading_state` (autoguardado).
- CRUD de `vocabulary`.
- Leer/escribir la **caché de traducciones** (`translations`).

No sabe nada de UI, audio ni red. Es pura persistencia.

### 2. `EpubParser`
Convierte un `.epub` en filas de base de datos. **No toca la GUI.**

Flujo:
1. `ebooklib` abre el EPUB y recorre los documentos en orden de lectura (`spine`).
2. `BeautifulSoup` limpia HTML/metadatos → texto plano por capítulo.
3. Segmenta cada capítulo en **oraciones**.
4. Devuelve `{ libro, [capítulos], [oraciones por capítulo] }` que `DatabaseManager`
   persiste en una transacción.

### 3. `AudioPlayer`
Envuelve `QMediaPlayer` + `QAudioOutput`. Reproduce el `.wav` de UNA oración.

Responsabilidades:
- `play(path)`, `pause()`, `stop()`.
- Emitir señal `finished` cuando termina → dispara el avance.
- No decide QUÉ oración suena; solo reproduce lo que le pasan.

### 4. `AppWindow` (QMainWindow)
Orquestador. Contiene la UI y coordina a las demás clases.

Layout — `QSplitter` horizontal:
- **Panel izquierdo:** biblioteca (`QListWidget` de libros).
- **Panel derecho:** visor de lectura (`QTextBrowser`) + controles (play/pausa) +
  panel de traducción.

Coordina el ciclo de lectura asistida (ver `TTS_FLOW.md`) y el autoguardado.

### 5. `LLMClient` (servicio)
Envuelve la llamada a Gemini para **traducir / explicar / dar ejemplos**.
Hoy es un **mock** (delay + texto falso). Siempre pasa por la caché `translations`
antes de llamar a la red → ahorra tokens y elimina delay en repeticiones.

---

## Comunicación entre clases (señales)

PyQt usa el patrón **signal/slot**. Nada bloqueante en el hilo de UI.

```
                 ┌──────────────────────────────┐
                 │          AppWindow           │
                 │  (hilo principal / UI)       │
                 └──────────────────────────────┘
              │        │           ▲           │
     carga/   │  play/ │   finished│    ready  │
     guarda   │  pause │           │  (señales)│
              ▼        ▼           │           ▼
   ┌──────────────┐ ┌───────────┐ │ ┌─────────────┐ ┌─────────────┐
   │DatabaseManager│ │AudioPlayer│ │ │  TTSWorker  │ │  LLMWorker  │
   │  (SQLite)    │ │(QtMultim.)│ │ │ (QThread)   │ │ (QThread)   │
   └──────────────┘ └───────────┘ │ │ pyttsx3     │ │ Gemini      │
                          │        │ └─────────────┘ └─────────────┘
                          └────────┘  ready(path)     translated(text)
```

- **TTS y LLM son asíncronos** (cada uno en su `QThread`) → nunca congelan la UI.
- `AudioPlayer.finished` → `AppWindow` avanza a la siguiente oración.
- Cada avance/salto/pausa → `DatabaseManager.save_reading_state(...)`.

---

## Ciclo de vida del estado de lectura

`reading_state` guarda `(book_id, chapter_index, sentence_index)` y se **autoguarda**:
- al avanzar automáticamente a la siguiente oración,
- al pausar,
- al saltar (clic en una oración anterior/posterior),
- al cerrar la app.

Al reabrir un libro, la app restaura exactamente la última oración.

---

## Estructura de archivos propuesta

```
AppIdiomas/
├── main.py                 # entrypoint: crea DB, levanta AppWindow (4 clases + LLMClient)
├── database.db             # (generado) SQLite local
├── ARCHITECTURE.md         # este documento
├── SCHEMA.sql              # esquema de la base
├── TTS_FLOW.md             # diagrama del ciclo TTS/LLM asíncrono
└── assets/
    └── sample.wav          # audio de prueba para el mock TTS
```

> El primer `main.py` mantiene las 4 clases + `LLMClient` en un único archivo como
> esqueleto ejecutable. Más adelante se puede extraer a paquetes (`db/`, `epub/`,
> `audio/`, `ui/`) sin cambiar la arquitectura.
