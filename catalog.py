"""
catalog.py — Catálogo curado de lecturas GRATIS y legales, por nivel CEFR.

Todo es dominio público (Project Gutenberg), así que descargarlo y leerlo es
legal. Los IDs están verificados uno a uno contra la API de Gutendex.

Criterio de selección — importante: un clásico NO es fácil por ser viejo. El
inglés victoriano (Dickens, Austen) es C1 largo aunque la historia sea sencilla.
Aquí sólo entra lo que de verdad se lee al nivel que dice, y se avisa de las
trampas conocidas (dialecto fonético, vocabulario técnico, arcaísmos).

Tipos:
  relato   — piezas de 5-30 min, autocontenidas. Lo mejor para empezar: terminas
             algo de una sentada, que es lo que sostiene el hábito.
  historia — novela corta / lectura de pocos días.
  libro    — novela completa.
"""

# Copyright (C) 2026 Marco Antonio Garcia
#
# Este archivo es parte de este proyecto, software libre bajo la GNU Affero
# General Public License v3 o posterior. Se distribuye SIN NINGUNA GARANTÍA.
# Ver el archivo LICENSE para los términos completos.

from __future__ import annotations

GUTENBERG_EPUB = "https://www.gutenberg.org/ebooks/{gid}.epub.noimages"

# (clave, título, autor, nivel, tipo, gutenberg_id, por qué / aviso)
CATALOG = [
    # ---------------- A2 ----------------
    ("aesop", "Aesop's Fables", "Esopo", "A2", "relato", 11339,
     "Fábulas de 5 a 10 frases, cada una independiente. El punto de entrada más "
     "suave que existe: si una se te atraganta, pasas a la siguiente."),
    ("happy-prince", "The Happy Prince and Other Tales", "Oscar Wilde", "A2", "relato", 902,
     "Cinco cuentos breves con vocabulario sencillo y frases cortas. Wilde "
     "escribiendo para niños, sin la ironía densa de su obra adulta."),
    ("andersen", "Andersen's Fairy Tales", "H. C. Andersen", "A2", "relato", 1597,
     "Cuentos que ya conoces en español (el patito feo, la sirenita). Saber la "
     "historia de antemano te deja concentrarte sólo en el idioma."),
    ("grimm", "Grimms' Fairy Tales", "Hermanos Grimm", "A2", "relato", 2591,
     "Más de 60 cuentos muy cortos. Vocabulario repetitivo entre historias, que "
     "para aprender es una ventaja: repasas sin darte cuenta."),
    ("oz", "The Wonderful Wizard of Oz", "L. Frank Baum", "A2", "historia", 55,
     "Prosa genuinamente simple: Baum escribía para niños de 1900 y evitaba "
     "adrede el vocabulario rebuscado. Frases cortas de principio a fin."),
    ("goblin", "The Princess and the Goblin", "George MacDonald", "A2", "historia", 708,
     "Aventura clásica con lenguaje llano y capítulos breves."),

    # ---------------- B1 ----------------
    ("call-wild", "The Call of the Wild", "Jack London", "B1", "historia", 215,
     "El mejor primer libro en B1: London escribe con frases secas y directas, "
     "sin subordinadas largas. Sólo 12 capítulos."),
    ("sherlock", "The Adventures of Sherlock Holmes", "Arthur Conan Doyle", "B1", "relato", 1661,
     "Doce casos independientes de unas 20 páginas. Terminas uno por sesión y "
     "el diálogo es muy natural."),
    ("time-machine", "The Time Machine", "H. G. Wells", "B1", "historia", 35,
     "Ciencia ficción sin florituras. Wells explica las cosas con claridad casi "
     "periodística."),
    ("jungle-book", "The Jungle Book", "Rudyard Kipling", "B1", "relato", 236,
     "Relatos sueltos del mismo mundo. Aviso: los poemas entre capítulos son "
     "bastante más difíciles — sáltatelos sin culpa."),
    ("just-so", "Just So Stories", "Rudyard Kipling", "B1", "relato", 2781,
     "Cuentos cortos con un estilo muy rítmico, pensado para leerse en voz alta. "
     "Encaja bien con la lectura frase a frase."),
    ("secret-garden", "The Secret Garden", "F. H. Burnett", "B1", "libro", 17396,
     "Aviso: los personajes de Yorkshire hablan con acento escrito tal cual. "
     "La narración es B1 fácil; los diálogos de Dickon cuestan más."),
    ("christmas-carol", "A Christmas Carol", "Charles Dickens", "B1", "historia", 46,
     "La única excepción a mi regla de evitar a Dickens: es corto, lo conoces de "
     "memoria y eso compensa el vocabulario victoriano."),
    ("yellow-wallpaper", "The Yellow Wallpaper", "C. P. Gilman", "B1", "relato", 1952,
     "Un solo relato de 20 páginas escrito como un diario, en primera persona y "
     "con frases cortas. Se lee de una sentada."),

    # ---------------- B2 ----------------
    ("war-worlds", "The War of the Worlds", "H. G. Wells", "B2", "libro", 36,
     "Narrado como una crónica. Algo más de vocabulario técnico que "
     "«The Time Machine», pero misma claridad."),
    ("four-million", "The Four Million", "O. Henry", "B2", "relato", 2776,
     "Relatos cortísimos de Nueva York, con finales sorpresa. Incluye "
     "«The Gift of the Magi». Inglés americano coloquial de 1900."),
    ("baskervilles", "The Hound of the Baskervilles", "Arthur Conan Doyle", "B2", "libro", 2852,
     "El Holmes largo. Si los relatos te van bien, este es el paso natural."),
    ("dorian", "The Picture of Dorian Gray", "Oscar Wilde", "B2", "libro", 174,
     "Prosa elegante pero muy legible, con diálogo brillante. Buen salto hacia "
     "el inglés literario."),
    ("treasure", "Treasure Island", "R. L. Stevenson", "B2", "libro", 120,
     "Aviso: mucho vocabulario náutico y jerga pirata. La historia es sencilla, "
     "las palabras no."),
    ("dubliners", "Dubliners", "James Joyce", "B2", "relato", 2814,
     "Quince relatos de prosa limpia y precisa. No confundir con «Ulises»: esto "
     "se lee sin problema en B2."),
    ("gatsby", "The Great Gatsby", "F. Scott Fitzgerald", "B2", "libro", 64317,
     "En dominio público desde 2021. Literario y con metáforas densas: déjalo "
     "para cuando los demás B2 te resulten cómodos."),
]

# Clásicos que suelen recomendarse y que NO conviene atacar a este nivel.
NOT_RECOMMENDED = [
    ("Alice in Wonderland", "Todo el libro son juegos de palabras y sinsentidos "
                            "deliberados: es de los textos más difíciles que hay."),
    ("Huckleberry Finn", "Está escrito en dialecto fonético ('dat', 'gwyne'). "
                         "Se lee peor que el inglés normal, no mejor."),
    ("Moby Dick", "Capítulos enteros de terminología ballenera del siglo XIX."),
    ("Frankenstein", "Mucho más arcaico y retórico de lo que sugiere su fama."),
    ("Orgullo y prejuicio / Dickens en general", "Inglés victoriano con frases "
                                                 "larguísimas: C1 real."),
]


def as_dicts() -> list[dict]:
    return [
        {"key": k, "title": t, "author": a, "level": lv, "kind": kind,
         "gutenberg_id": gid, "note": note,
         "url": GUTENBERG_EPUB.format(gid=gid),
         "source": f"https://www.gutenberg.org/ebooks/{gid}"}
        for (k, t, a, lv, kind, gid, note) in CATALOG
    ]


def get(key: str) -> dict | None:
    return next((b for b in as_dicts() if b["key"] == key), None)
