# Lector de Idiomas — MVP

App **web local** para leer libros (PDF o EPUB) y aprender idiomas: lectura asistida
por voz (oración por oración) y ayuda con IA (traducción, gramática y ejemplos),
más exportación de vocabulario a Anki.

Corre en tu máquina y se abre en el navegador. Tu libro, tu base de datos, tu equipo.

> Hay **dos versiones** del mismo proyecto:
> - **Web (activa):** `webapp.py` + `core.py` + `static/` → se abre en el navegador.
> - **Escritorio (previa):** `main.py` (PyQt6) → ventana nativa. Se retomará después.

---

## Instalación

> Instalación paso a paso (y qué necesita cada persona): **[SETUP.md](SETUP.md)**


Requiere **Python 3.10+**.

```bash
pip install -r requirements.txt
```

## Ejecutar (versión web)

```bash
export GEMINI_API_KEY="tu_api_key"     # opcional; sin ella la IA va en modo simulado
python webapp.py
```

Luego abre **http://localhost:8080** en tu navegador.

Usa **📖 Subir libro (PDF/EPUB)** para cargar tus libros. Si subes un **PDF**, se convierte
automáticamente a EPUB (con `pdfminer.six`, o con Calibre si lo tienes instalado). Si ya
es EPUB, se salta ese paso.

## Ejecutar (versión escritorio, opcional)

```bash
python main.py
```

---

## Qué hace

| Función | Cómo |
|---|---|
| **Cargar EPUB** | Botón "📖 Cargar EPUB" → extrae capítulos y oraciones, los guarda en SQLite. |
| **Leer en voz alta** | Botón "▶ Leer" → resalta la oración actual, la reproduce y avanza sola (también entre capítulos). |
| **Saltar** | Clic en cualquier oración → salta ahí y recalcula el audio. |
| **Traducir / Gramática / Ejemplos** | Botones que consultan la IA sobre la oración actual. |
| **Vocabulario → Anki** | Selecciona una palabra → "➕ Vocabulario" (traducción + audios). Al terminar, "⬇ Exportar a Anki (.apkg)". |
| **Autoguardado** | La posición (libro, capítulo, oración) se guarda en cada avance, pausa, salto y al cerrar. Al reabrir, retomas donde ibas. |

### Vocabulario efímero → Anki

El vocabulario **no se guarda en la base de datos**: vive solo durante la sesión de
lectura y se descarta al cerrar. Lo único persistente es el libro y tu posición.

1. Selecciona una palabra en el visor y pulsa **➕ Vocabulario**.
2. En segundo plano se generan la **traducción** (Gemini) y el **audio** de la palabra
   y de la oración de ejemplo (pyttsx3). Aparece en la lista "Vocabulario (sesión)".
3. Cuando termines, **⬇ Exportar a Anki (.apkg)** crea un archivo que arrastras a Anki:
   trae las tarjetas **y los audios embebidos** (nada que copiar a mano).

Cada tarjeta: frente = palabra + audio · reverso = traducción + oración de ejemplo + audio.

---

## Costos: todo puede ser gratis

| Componente | Servicio | Costo |
|---|---|---|
| Interfaz, EPUB, base de datos | PyQt6 · ebooklib · SQLite | Gratis |
| **Voz de lectura (TTS)** | **Web Speech API** del navegador (voz del sistema) | Gratis · **0 API keys** |
| **Voz para Anki** | `pyttsx3` en el servidor (genera los .wav del export) | Gratis · **0 API keys** |
| **Texto (LLM)** | Google Gemini (free tier), modelo `gemini-2.5-flash` | Gratis* · **1 API key** |

\* El free tier de Gemini se renueva por minuto/día; para lectura personal alcanza de sobra.
En total solo necesitas **una** API key (Gemini). La voz no requiere ninguna.
Si topas límites de cuota, cambia a un modelo más ligero:
`export GEMINI_MODEL="gemini-flash-lite-latest"`.

### Activar la IA real (Gemini)

Sin API key, la traducción funciona en **modo simulado** (la app no se cae; solo verás
texto de ejemplo). Para IA real:

1. Consigue una API key gratis en <https://aistudio.google.com/apikey>
2. Expórtala antes de ejecutar:

   ```bash
   export GEMINI_API_KEY="tu_api_key"     # macOS / Linux
   ```

3. (Opcional) Cambia el modelo: `export GEMINI_MODEL="gemini-2.0-flash"`

La voz (`pyttsx3`) **no necesita API key** ni internet.

---

## Arquitectura

- `main.py` — la app completa (4 clases + `LLMClient`).
- `SCHEMA.sql` — esquema SQLite (la oración es la unidad atómica).
- `ARCHITECTURE.md` — diseño y responsabilidades de cada clase.
- `TTS_FLOW.md` — el ciclo asíncrono de voz + IA (sin congelar la UI).
- `database.db` — (se genera) tu biblioteca y progreso.
- `assets/tts_cache/` — (se genera) audios cacheados por oración.

### Degradación elegante
- Si `pyttsx3` no puede generar audio → usa `assets/sample.wav` de respaldo (no rompe la lectura).
- Si no hay `GEMINI_API_KEY` o falla la red → la IA responde en modo simulado / con el error, sin tumbar la app.

---

## Portabilidad a Postgres (futuro servidor en línea)

El esquema (`SCHEMA.sql`) usa tipos estándar (INTEGER, TEXT, REAL) y es fácil de migrar.
Al pasar a Postgres solo hay que ajustar:
- `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL`/`GENERATED ... AS IDENTITY`.
- `date('now')` / `datetime('now')` → `CURRENT_DATE` / `now()`.
- `INSERT OR IGNORE` → `INSERT ... ON CONFLICT DO NOTHING`; `INSERT OR REPLACE` → `ON CONFLICT ... DO UPDATE`.
- El acceso a datos está **aislado en `DatabaseManager`** (core.py): al migrar, solo cambia esa clase (p.ej. a SQLAlchemy o `psycopg`), no el resto de la app.

## Límites conocidos del MVP
- El segmentador de oraciones es una regex ligera; con textos muy complejos puede fallar
  algún corte. Se cambia fácil (solo `EpubParser._split_sentences`).
- El texto se muestra en **plano** (sin negritas/cursivas/imágenes), a propósito, para el
  modelo "oración por oración".
- Solo EPUB (por diseño; nada de PDF).

---

## Licencia y avisos

Copyright (C) 2026 Marco Antonio Garcia

Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo los
términos de la **GNU Affero General Public License**, versión 3 o posterior,
publicada por la Free Software Foundation. El texto completo está en
[LICENSE](LICENSE).

Se distribuye con la esperanza de que sea útil, pero **SIN NINGUNA GARANTÍA**;
ni siquiera la garantía implícita de comerciabilidad o idoneidad para un fin
determinado. Consulta las secciones 15 y 16 de la licencia.

En resumen, lo que puedes hacer: clonarlo, ejecutarlo, estudiarlo y modificarlo
libremente. La única condición aparece si **distribuyes** tu versión o la
ofreces como servicio en red: entonces debes publicar también tu código bajo
esta misma licencia.

### Responsabilidad sobre los archivos que subes

La app es un **lector de propósito general**, como cualquier otro lector de
EPUB o PDF. No incluye ni distribuye libros.

Cada persona es la única responsable de los archivos que carga en su propia
instalación y de tener los derechos necesarios para usarlos. Los autores de
este software no alojan, comparten ni distribuyen ningún contenido subido por
los usuarios: todo se queda en el ordenador de cada uno, en una base de datos
local.

El catálogo integrado descarga únicamente obras de **dominio público** desde
[Project Gutenberg](https://www.gutenberg.org/).

### Contenido propio y de terceros

- Los mazos de estudio, las lecciones y el código son obra original de este
  proyecto y se publican bajo la misma licencia AGPL-3.0.
- Los textos del catálogo son de dominio público (Project Gutenberg).
- Las respuestas generadas por IA provienen de la API de Google Gemini y están
  sujetas a los términos de Google. Cada usuario emplea su propia clave.

### Dependencias

Este proyecto usa librerías de terceros con sus propias licencias, entre ellas
**EbookLib** (AGPL-3.0), que es la razón por la que este proyecto también es
AGPL-3.0. Consulta cada paquete en `requirements.txt` para sus términos.
