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

import os
import re
import tempfile

import uvicorn
from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

import catalog
import core

app = FastAPI(title="Lector de Idiomas")
db = core.DatabaseManager()
core.ensure_sample_wav()

STATIC_DIR = os.path.join(core.BASE_DIR, "static")
os.makedirs(core.LIBRARY_DIR, exist_ok=True)


# --------------------------------------------------------------------------- #
# Frontend
# --------------------------------------------------------------------------- #
@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    with open(os.path.join(STATIC_DIR, "index.html"), "r", encoding="utf-8") as fh:
        return HTMLResponse(fh.read())


# --------------------------------------------------------------------------- #
# Biblioteca / carga
# --------------------------------------------------------------------------- #
_SAFE = re.compile(r"[^A-Za-z0-9._ -]")


@app.get("/api/books")
def list_books() -> list[dict]:
    return db.list_books()


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict:
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
    book = db.get_book(book_id)
    return {"book_id": book_id, **book}


@app.get("/api/catalog")
def get_catalog() -> dict:
    """Lecturas gratis y legales (dominio público), clasificadas por nivel y tipo."""
    # El título del EPUB no siempre coincide con el del catálogo ("Aesop's
    # Fables" vs "Aesop's Fables; a new translation"): se compara por prefijo.
    ya = [(b.get("title") or "").strip().lower() for b in db.list_books()]
    libros = []
    for item in catalog.as_dicts():
        t = item["title"].strip().lower()
        tengo = any(x.startswith(t) or t.startswith(x) for x in ya if x)
        libros.append({**item, "in_library": tengo})
    return {"books": libros,
            "levels": ["A2", "B1", "B2"],
            "kinds": {"relato": "Relatos cortos", "historia": "Historias",
                      "libro": "Libros completos"},
            "avoid": [{"title": t, "why": w} for t, w in catalog.NOT_RECOMMENDED]}


@app.post("/api/catalog/{key}/add")
def add_from_catalog(key: str) -> dict:
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
def get_book(book_id: int) -> dict:
    book = db.get_book(book_id)
    if book is None:
        raise HTTPException(404, "Libro no encontrado")
    return book


@app.delete("/api/books/{book_id}")
def delete_book(book_id: int) -> dict:
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


@app.get("/api/books/{book_id}/toc")
def get_toc(book_id: int) -> list[dict]:
    return db.get_toc(book_id)


@app.get("/api/books/{book_id}/stats")
def get_stats(book_id: int) -> dict:
    return db.get_book_stats(book_id)


@app.get("/api/books/{book_id}/difficulty")
def book_difficulty(book_id: int) -> dict:
    """Nivel estimado del libro y cuánto se aleja del tuyo.

    Existe para avisarte ANTES de empezar: leer dos escalones por encima de tu
    nivel no es un reto, es una frustración con pasos extra.
    """
    if db.get_book(book_id) is None:
        raise HTTPException(404, "Libro no encontrado")
    stats = core.readability(db.book_sample_sentences(book_id))
    yours = (db.last_test() or {}).get("level") or ""
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
def rename_book(book_id: int, payload: dict = Body(...)) -> dict:
    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "El título no puede estar vacío")
    db.rename_book(book_id, title)
    return {"ok": True, "title": title}


@app.post("/api/books/{book_id}/index/improve")
def improve_index(book_id: int) -> list[dict]:
    """Usa la IA para leer el inicio de cada sección y ponerle un título descriptivo.
    No reordena el texto (eso rompería la lectura); mejora los nombres del índice."""
    book = db.get_book(book_id)
    if book is None:
        raise HTTPException(404, "Libro no encontrado")
    lang = "es"  # los títulos del índice, en español (idioma del usuario)
    toc = db.get_toc(book_id)
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
    return db.get_toc(book_id)


@app.get("/api/books/{book_id}/chapter/{idx}")
def get_chapter(book_id: int, idx: int) -> dict:
    chapter = db.get_chapter(book_id, idx)
    # sin capítulo, el lector se quedaba en blanco sin decir por qué
    if not chapter.get("sentences") and chapter.get("title") is None:
        raise HTTPException(404, "Ese capítulo no existe")
    return chapter


@app.post("/api/books/{book_id}/chapter/{idx}/done")
def set_chapter_done(book_id: int, idx: int, payload: dict = Body(...)) -> dict:
    db.set_chapter_done(book_id, idx, bool(payload.get("done", True)))
    return db.get_book(book_id)


# --------------------------------------------------------------------------- #
# Estado de lectura (autoguardado)
# --------------------------------------------------------------------------- #
@app.get("/api/books/{book_id}/state")
def get_state(book_id: int) -> dict:
    return db.load_reading_state(book_id)


@app.post("/api/books/{book_id}/state")
def set_state(book_id: int, payload: dict = Body(...)) -> dict:
    db.save_reading_state(
        book_id,
        int(payload.get("chapter_index", 0)),
        int(payload.get("sentence_index", 0)),
    )
    return {"ok": True}


# --------------------------------------------------------------------------- #
# IA (Gemini) con caché en DB
# --------------------------------------------------------------------------- #
@app.post("/api/llm")
def llm(payload: dict = Body(...)) -> dict:
    text = (payload.get("text") or "").strip()
    kind = payload.get("kind", "translation")
    lang = payload.get("target_lang", "es")
    if not text:
        raise HTTPException(400, "Falta 'text'")
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
def get_config() -> dict:
    return core.ai_status()


@app.post("/api/config")
def set_config(payload: dict = Body(...)) -> dict:
    key = (payload.get("gemini_api_key") or "").strip()
    core.set_api_key(key)
    return core.ai_status()


# --------------------------------------------------------------------------- #
# Vocabulario + repetición espaciada (SRS)
# --------------------------------------------------------------------------- #
@app.post("/api/vocab")
def add_vocab(payload: dict = Body(...)) -> dict:
    term = (payload.get("term") or "").strip()
    if not term:
        raise HTTPException(400, "Falta 'term'")
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
        level = (db.last_test() or {}).get("level") or "B1"
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
    )
    return {"id": vid, "simple_example": simple, **db.vocab_stats()}


@app.get("/api/vocab")
def list_vocab() -> list[dict]:
    return db.list_vocab()


@app.get("/api/vocab/due")
def due_vocab(ahead: bool = False) -> list[dict]:
    """ahead=true: si no toca nada hoy, adelanta los próximos repasos."""
    limite = int(db.get_setting("vocab_new_limit", "10") or 10)
    return _with_cloze(db.due_vocab(new_limit=limite, ahead=ahead),
                       front_key="term", note_key="simple_example")


@app.post("/api/vocab/backfill-examples")
def backfill_examples(limit: int = 5) -> dict:
    """Genera el ejemplo corto de las palabras que se quedaron sin él.

    Existe porque si la IA está caída justo al guardar una palabra, esa tarjeta
    se quedaría con la frase larga del libro para siempre.

    Va de 5 en 5 a propósito: cada palabra es una llamada a la IA con sus
    reintentos, y un lote grande dejaría el servidor bloqueado varios minutos.
    Es seguro llamarlo varias veces: solo toca las que aún no tienen ejemplo.
    """
    level = (db.last_test() or {}).get("level") or "B1"
    pending = [w for w in db.list_vocab() if not (w.get("simple_example") or "").strip()]
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
            db.set_simple_example(word["id"], text)
            done += 1
    return {"filled": done, "remaining": max(0, len(pending) - done), "ai_failed": failed}


@app.get("/api/vocab/new")
def new_vocab(limit: int = 10) -> list[dict]:
    """Palabras sin ver, ignorando el candado diario (a petición tuya)."""
    return _with_cloze(db.new_vocab(limit=limit), front_key="term", note_key="simple_example")


@app.get("/api/vocab/stats")
def vocab_stats() -> dict:
    return db.vocab_stats()


@app.post("/api/vocab/{vid}/grade")
def grade_vocab(vid: int, payload: dict = Body(...)) -> dict:
    grade = payload.get("grade", "good")
    if grade not in ("again", "hard", "good", "easy"):
        raise HTTPException(400, "grade inválido")
    db.grade_vocab(vid, grade)
    return db.vocab_stats()


@app.delete("/api/vocab/{vid}")
def delete_vocab(vid: int) -> dict:
    if not db.delete_vocab(vid):
        raise HTTPException(404, "Esa palabra no existe")
    return db.vocab_stats()


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
def study_check(payload: dict = Body(...)) -> dict:
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
def get_limits() -> dict:
    """Topes de estudio y cuánto llevas hoy."""
    done = db.reviews_today()
    cap = int(db.get_setting("review_limit", str(core.DEFAULT_REVIEW_LIMIT)) or 0)
    return {"review_limit": cap, "reviews_today": done,
            "review_left": db.review_budget_left() if cap else None,
            "vocab_new_limit": int(db.get_setting("vocab_new_limit", "10") or 10),
            "decks": [{"id": d["id"], "name": d["name"], "new_limit": d["new_limit"]}
                      for d in db.list_decks()],
            "backlog": db.review_backlog()}


@app.post("/api/study/limits")
def set_limits(payload: dict = Body(...)) -> dict:
    if "review_limit" in payload:
        db.set_setting("review_limit", max(0, int(payload["review_limit"])))
    if "vocab_new_limit" in payload:
        db.set_setting("vocab_new_limit", max(0, int(payload["vocab_new_limit"])))
    for item in (payload.get("decks") or []):
        db.set_deck_new_limit(int(item["id"]), int(item["new_limit"]))
    return get_limits()


@app.get("/api/decks")
def list_decks() -> list[dict]:
    return db.list_decks()


@app.post("/api/decks/{deck_id}/backfill-examples")
def deck_backfill_examples(deck_id: int, batch: int = 12) -> dict:
    """Genera los ejemplos que faltan en un mazo, en lotes.

    Un lote por llamada a la IA (no una por tarjeta): 123 frases serían 123
    llamadas y varios minutos de servidor bloqueado.
    """
    pending = db.cards_without_example(deck_id)
    if not pending:
        return {"filled": 0, "remaining": 0, "done": True}
    lote = pending[:batch]
    level = (db.last_test() or {}).get("level") or "B1"
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
def deck_due(deck_id: int, new_limit: int | None = None, ahead: bool = False) -> list[dict]:
    """new_limit sin valor = usa el tope configurado en el mazo (ajustable en 🎚)."""
    return _with_cloze(db.deck_due_cards(deck_id, new_limit=new_limit, ahead=ahead))


@app.get("/api/streak")
def streak() -> dict:
    return db.get_streak()


@app.post("/api/activity")
def activity(payload: dict = Body(...)) -> dict:
    db.log_activity(payload.get("module", ""), int(payload.get("active", 0)),
                    int(payload.get("open", 0)))
    return {"ok": True}


@app.get("/api/stats/full")
def stats_full(range: str = "week") -> dict:
    return db.get_full_stats("month" if range == "month" else "week")


@app.get("/api/nav-alerts")
def nav_alerts() -> dict:
    return db.nav_alerts()


# --------------------------------------------------------------------------- #
# Test de diagnóstico de nivel (5 versiones equivalentes)
# --------------------------------------------------------------------------- #
@app.get("/api/test/form")
def test_form() -> dict:
    return core.get_test_form()


@app.post("/api/test/score")
def test_score(payload: dict = Body(...)) -> dict:
    form_id = int(payload.get("form_id", 0))
    answers = payload.get("answers") or []
    result = core.score_test(form_id, answers)
    db.save_test_result(result["level"], result["correct"], result["total"])
    return result


@app.get("/api/test/last")
def test_last() -> dict:
    return db.last_test() or {}


@app.post("/api/test/adaptive")
def test_adaptive(payload: dict = Body(...)) -> dict:
    answers = payload.get("answers") or []
    result = core.adaptive_next(answers)
    if result.get("done"):
        db.save_test_result(result["level"], result.get("correct", 0), len(answers))
    return result


# --------------------------------------------------------------------------- #
# Lessons — método contrastivo (Ghio): beginner / mid / advanced
# --------------------------------------------------------------------------- #
@app.get("/api/lessons")
def lessons(level: str = "") -> dict:
    items = core.get_lessons(level or None)
    done = set(db.lesson_done_ids())
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
def checkpoint_detail(cp_id: str) -> dict:
    cp = core.get_checkpoint(cp_id)
    if not cp:
        raise HTTPException(404, "Checkpoint not found")
    cp["done"] = cp_id in set(db.lesson_done_ids())
    return cp


@app.post("/api/checkpoint/{cp_id}/done")
def checkpoint_done(cp_id: str, payload: dict = Body(default={})) -> dict:
    if not core.get_checkpoint(cp_id):
        raise HTTPException(404, "Checkpoint not found")
    done = bool(payload.get("done", True))
    db.set_lesson_done(cp_id, done)
    return {"ok": True, "done": done}


# NOTA: estas rutas van ANTES de /api/lessons/{lesson_id}. FastAPI resuelve
# por orden de definición: si {lesson_id} va primero, captura "custom" como
# si fuera el id de una lección y devuelve 404.
@app.post("/api/lessons/generate")
def generate_lesson(payload: dict = Body(default={})) -> dict:
    """Crea una lección a medida contra tu tipo de error más frecuente."""
    resumen = [s for s in db.writing_error_summary() if s["category"] != "unclassified"]
    if not resumen:
        raise HTTPException(400, "Aún no hay errores clasificados. Evalúa alguna redacción "
                                 "con «Check my writing» primero.")
    categoria = payload.get("category") or resumen[0]["category"]
    etiqueta = next((s["label"] for s in resumen if s["category"] == categoria), categoria)
    errores = db.errors_by_category(categoria)
    if not errores:
        raise HTTPException(400, f"No hay errores de tipo «{etiqueta}».")
    nivel = (db.last_test() or {}).get("level") or "B1"
    try:
        leccion = core.generate_error_lesson(etiqueta, errores, level=nivel)
    except core.AIUnavailable as exc:
        raise HTTPException(503, str(exc))
    lid = db.save_custom_lesson(categoria, leccion.get("title") or etiqueta,
                                nivel, leccion, len(errores))
    return {"id": lid, "category": categoria, "label": etiqueta,
            "based_on": len(errores), "lesson": leccion}


@app.get("/api/lessons/custom")
def list_custom_lessons() -> list[dict]:
    return db.list_custom_lessons()


@app.get("/api/lessons/custom/{lid}")
def get_custom_lesson(lid: int) -> dict:
    row = db.get_custom_lesson(lid)
    if not row:
        raise HTTPException(404, "Esa lección no existe")
    return row


@app.post("/api/lessons/custom/{lid}/done")
def custom_lesson_done(lid: int, payload: dict = Body(default={})) -> dict:
    if not db.set_custom_lesson_done(lid, bool(payload.get("done", True))):
        raise HTTPException(404, "Esa lección no existe")
    return {"ok": True}


@app.delete("/api/lessons/custom/{lid}")
def delete_custom_lesson(lid: int) -> dict:
    if not db.delete_custom_lesson(lid):
        raise HTTPException(404, "Esa lección no existe")
    return {"deleted": lid}


@app.get("/api/lessons/{lesson_id}")
def lesson_detail(lesson_id: str) -> dict:
    ls = core.get_lesson(lesson_id)
    if not ls:
        raise HTTPException(404, "Lesson not found")
    out = dict(ls)
    out["done"] = lesson_id in set(db.lesson_done_ids())
    return out


@app.post("/api/lessons/{lesson_id}/done")
def lesson_done(lesson_id: str, payload: dict = Body(default={})) -> dict:
    if not core.get_lesson(lesson_id):
        raise HTTPException(404, "Lesson not found")
    done = bool(payload.get("done", True))
    db.set_lesson_done(lesson_id, done)
    return {"ok": True, "done": done}


# --------------------------------------------------------------------------- #
# Writing: extraer texto (incl. foto→OCR), corregir+explicar, upgrade
# --------------------------------------------------------------------------- #
@app.post("/api/writing/extract")
async def writing_extract(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    try:
        text = core.extract_text_from_upload(file.filename or "", data)
    except core.AIUnavailable as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:
        raise HTTPException(400, str(exc))
    return {"text": text}


@app.post("/api/writing/check")
def writing_check(payload: dict = Body(...)) -> dict:
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "Falta 'text'")
    try:
        result = core.writing_check(text)
    except core.AIUnavailable as exc:
        # 503: nada que guardar. Sin evaluación real no se inventa un nivel.
        raise HTTPException(503, str(exc))
    # guarda el escrito + los errores en el diario
    title = (payload.get("title") or text[:40]).strip()
    wid = db.save_writing(title, text, result.get("corrected"), result.get("level"),
                          result.get("assessment", ""))
    for e in result.get("errors", []):
        db.add_writing_error(wid, e.get("original", ""), e.get("correction", ""),
                             e.get("explanation", ""), e.get("category", "other"))
    result["writing_id"] = wid
    return result


@app.post("/api/writing/upgrade")
def writing_upgrade(payload: dict = Body(...)) -> dict:
    text = (payload.get("text") or "").strip()
    level = payload.get("level", "B2")
    if not text:
        raise HTTPException(400, "Falta 'text'")
    wid = payload.get("writing_id")
    # el upgrade parte del nivel evaluado: primero hay que saber en qué nivel escribes
    record = db.get_writing(int(wid)) if wid else None
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
    db.save_writing_upgrade(int(wid), upgraded, level)
    return {"upgraded": upgraded, "level": level, "from_level": from_level}


@app.get("/api/writings")
def list_writings() -> list[dict]:
    return db.list_writings()


@app.get("/api/writings/{wid}")
def get_writing(wid: int) -> dict:
    """Detalle completo: original, corrección, evaluación y upgrade (para comparar)."""
    record = db.get_writing(wid)
    if not record:
        raise HTTPException(404, "No existe ese escrito")
    return record


@app.delete("/api/writings/{wid}")
def delete_writing(wid: int) -> dict:
    if not db.delete_writing(wid):
        raise HTTPException(404, "No existe ese escrito")
    return {"deleted": wid}


@app.get("/api/writing/errors")
def writing_errors(category: str = "") -> list[dict]:
    return db.list_writing_errors(category=category)


@app.post("/api/writing/errors/{eid}/explain")
def explain_error(eid: int, force: bool = False) -> dict:
    """Mini-lección para UN error. Se cachea: la segunda vez no gasta IA."""
    err = db.get_writing_error(eid)
    if not err:
        raise HTTPException(404, "Ese error no existe")
    if err.get("lesson") and not force:
        return {"id": eid, "lesson": err["lesson"], "cached": True}
    nivel = (db.last_test() or {}).get("level") or "B1"
    try:
        leccion = core.explain_error(err.get("original", ""), err.get("correction", ""),
                                     err.get("explanation", ""), level=nivel)
    except core.AIUnavailable as exc:
        raise HTTPException(503, str(exc))
    db.set_error_lesson(eid, leccion)
    return {"id": eid, "lesson": leccion, "cached": False}


@app.post("/api/writing/errors/{eid}/reviewed")
def mark_error_reviewed(eid: int, payload: dict = Body(default={})) -> dict:
    if not db.set_error_reviewed(eid, bool(payload.get("reviewed", True))):
        raise HTTPException(404, "Ese error no existe")
    return {"ok": True, "reviewed": bool(payload.get("reviewed", True))}


@app.get("/api/writing/errors/summary")
def writing_error_summary() -> list[dict]:
    """Tus errores agrupados por tipo gramatical, del más repetido al menos."""
    return db.writing_error_summary()


@app.get("/api/writing/progress")
def writing_progress() -> dict:
    """Evolución de tu nivel CEFR escrito a lo largo del tiempo."""
    rows = [w for w in db.list_writings() if w.get("level")]
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
def deck_new(deck_id: int, limit: int = 10) -> list[dict]:
    """Siguientes tarjetas sin ver, ignorando el candado diario (a petición tuya)."""
    return _with_cloze(db.deck_new_cards(deck_id, limit=limit))


@app.get("/api/decks/{deck_id}/study")
def deck_study(deck_id: int) -> list[dict]:
    # todas las tarjetas, sin límite diario
    cards = db.deck_study_cards(deck_id)
    if not cards and not any(d["id"] == deck_id for d in db.list_decks()):
        raise HTTPException(404, "Ese mazo no existe")
    return _with_cloze(cards)


@app.get("/api/voices")
def voices(lang: str = "en") -> list[dict]:
    return core.list_voices(lang)


@app.get("/api/tts")
def tts(text: str, voice: str = "", rate: int = 0, lang: str = "en") -> FileResponse:
    """Genera (y cachea) audio para 'text' con la voz/velocidad pedidas. Sirve el .wav.
    Permite cambiar voz y ritmo de los decks dinámicamente sin re-sembrar."""
    text = (text or "").strip()
    if not text:
        raise HTTPException(400, "Falta 'text'")
    path = core.synthesize(text, lang, rate=rate or None, voice=voice or None)
    return FileResponse(path, media_type="audio/wav")


@app.post("/api/decks/cards/{card_id}/grade")
def grade_deck_card(card_id: int, payload: dict = Body(...)) -> dict:
    grade = payload.get("grade", "good")
    if grade not in ("again", "hard", "good", "easy"):
        raise HTTPException(400, "grade inválido")
    db.grade_deck_card(card_id, grade)
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Export a Anki (.apkg) — genera audio server-side y lo empaqueta
# --------------------------------------------------------------------------- #
@app.post("/api/export/anki")
def export_anki(payload: dict = Body(...)) -> FileResponse:
    items = payload.get("items") or []
    if not items:
        # sin items -> exporta TODO el vocabulario guardado
        items = [
            {"word": v["term"], "translation": v.get("translation") or "",
             "example": v.get("example") or "", "lang": v.get("lang") or "en"}
            for v in db.list_vocab()
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
    out_path = os.path.join(tempfile.gettempdir(), "vocabulario_appidiomas.apkg")
    core.AnkiExporter.export(enriched, deck_name, out_path)
    return FileResponse(
        out_path,
        media_type="application/octet-stream",
        filename="vocabulario_appidiomas.apkg",
    )


# audio pre-generado de los decks / TTS (para reproducir en el navegador)
os.makedirs(core.TTS_CACHE_DIR, exist_ok=True)
app.mount("/audio", StaticFiles(directory=core.TTS_CACHE_DIR), name="audio")

# static (por si luego servimos css/js como archivos)
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080)
