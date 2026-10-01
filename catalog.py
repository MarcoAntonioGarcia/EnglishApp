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

    # ------- No ficción: hábitos, foco y carácter -------
    # El género de la superación personal es MÁS VIEJO que el dominio público:
    # lo inventó Samuel Smiles en 1859, así que los clásicos del género son
    # libres. Los niveles de este bloque están MEDIDOS con el mismo analizador
    # que usa la app (core.readability), no estimados a ojo. Donde la fórmula
    # engaña, el aviso lo dice: mide sílabas y longitud de frase, no sabe nada
    # de vocabulario abstracto ni de inglés arcaico.
    ("24-hours", "How to Live on 24 Hours a Day", "Arnold Bennett", "B2", "ensayo", 2274,
     "Lo más parecido a «Deep Work» que existe libre, y es de 1908: cómo "
     "recuperar tu tiempo y tu atención del trabajo. Medido en 64.4 de Flesch, "
     "casi idéntico a «Atomic Habits» (65.0). Cincuenta páginas."),
    ("acres-diamonds", "Acres of Diamonds", "Russell H. Conwell", "B2", "ensayo", 368,
     "Una conferencia transcrita, así que suena a alguien hablando: ritmo "
     "natural y pocas palabras largas (7.3 %, menos que «The Time Machine»). "
     "La mejor puerta de entrada a la no ficción."),
    ("science-rich", "The Science of Getting Rich", "W. D. Wattles", "B2", "ensayo", 59844,
     "Prosa llana y deliberadamente repetitiva: vuelve sobre las mismas ideas "
     "con las mismas palabras, que para aprender es una ventaja. De 1910."),
    ("concentration", "The Power of Concentration", "W. W. Atkinson", "B2", "ensayo", 1570,
     "Entrenamiento de la atención en lecciones cortas e independientes. Las "
     "frases más cortas de todo este bloque: 14.4 palabras de media."),
    ("as-a-man-thinketh", "As a Man Thinketh", "James Allen", "C1", "ensayo", 4507,
     "El sustituto temático de «Atomic Habits»: cómo el pensamiento forma el "
     "carácter. Aviso: es el más CORTO (20 páginas) y también el más DIFÍCIL "
     "de aquí. 12.3 % de palabras largas, por encima incluso de «Deep Work». "
     "Corto no significa fácil."),
    ("self-help", "Self-Help", "Samuel Smiles", "B2", "ensayo", 935,
     "El libro que le dio nombre al género, en 1859. Son biografías breves de "
     "gente constante, así que puedes leer capítulos sueltos sin perder el hilo."),
    ("franklin", "The Autobiography of Benjamin Franklin", "Benjamin Franklin", "B2",
     "ensayo", 148,
     "Su tabla de 13 virtudes es, literalmente, un rastreador de hábitos de "
     "1791. Aviso: ortografía del XVIII y mayúsculas a media frase. El medidor "
     "dice B2, pero esa rareza cuesta más de lo que refleja el número."),
    ("emerson", "Essays (incluye «Self-Reliance»)", "R. W. Emerson", "B2", "ensayo", 16643,
     "Aviso: el medidor da B2 por lo cortas que son sus frases, pero Emerson "
     "escribe en aforismos abstractos. Entiendes cada palabra y aun así cuesta "
     "seguir el argumento. Mejor a párrafos sueltos que de corrido."),
    ("meditations", "Meditations", "Marco Aurelio", "C1", "ensayo", 2680,
     "Aviso importante: el medidor lo pone en B1 (71.7) porque tiene frases "
     "cortas y palabras llanas. La fórmula no ve el «thou/thee/hath» de la "
     "traducción de 1862 ni la densidad filosófica. En la práctica es C1."),
    ("walden", "Walden", "H. D. Thoreau", "C1", "ensayo", 205,
     "Mismo caso y más extremo: sale B1 medido (73.1, el «más fácil» de toda "
     "esta lista) y no lo es. Thoreau usa palabras corrientes para ideas "
     "abstractas y se va por las ramas durante páginas. La fórmula cuenta "
     "sílabas, no ideas."),
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
