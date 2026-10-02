#!/usr/bin/env python3
"""Copia los datos de la base local (SQLite) a Postgres.

De una vez, para la mudanza a producción. No es idempotente a medias: vacía las
tablas de destino y las vuelve a llenar, para que no queden filas de una
ejecución anterior mezcladas con las nuevas.

    python3 pg_migrate.py --dry-run     # solo dice qué haría
    python3 pg_migrate.py               # lo hace
"""
from __future__ import annotations

import sqlite3
import sys

import core
import pg_schema

# El orden importa: una fila no puede apuntar con clave ajena a otra que
# todavía no existe. Postgres sí comprueba las claves ajenas, al contrario que
# SQLite cuando están desactivadas.
ORDEN = [
    "users",
    "books", "chapters", "sentences",
    "decks", "deck_cards",
    "translations",
    "vocabulary", "reading_state", "chapter_done", "card_progress",
    "writings", "writing_errors",
    "custom_lessons", "test_results", "lesson_done",
    "study_log", "activity_log", "session_log", "new_intro",
    "user_settings",
    # sessions NO se copia: son cookies de sesiones abiertas en local y no
    # tienen ningún sentido en producción. Que cada uno entre de nuevo.
]


def columnas(cx, tabla: str) -> list[str]:
    return [r[1] for r in cx.execute("PRAGMA table_info(%s)" % tabla)]


def main() -> int:
    seco = "--dry-run" in sys.argv
    url = core.url_del_fichero_env()
    if not url:
        print("No hay DATABASE_URL en .env", file=sys.stderr)
        return 1

    origen = sqlite3.connect(core.DB_PATH)
    origen.row_factory = sqlite3.Row

    import psycopg
    destino = psycopg.connect(url, connect_timeout=30)

    print("%-16s %8s %8s" % ("TABLA", "ORIGEN", "COPIADAS"))
    print("-" * 36)
    total = 0
    with destino:
        with destino.cursor() as cur:
            # se vacía todo de golpe: TRUNCATE con CASCADE respeta las claves
            if not seco:
                cur.execute("TRUNCATE %s CASCADE" % ", ".join(ORDEN + ["sessions"]))

            for tabla in ORDEN:
                cols = columnas(origen, tabla)
                filas = origen.execute(
                    "SELECT %s FROM %s" % (", ".join(cols), tabla)).fetchall()
                if seco:
                    print("%-16s %8d %8s" % (tabla, len(filas), "(seco)"))
                    total += len(filas)
                    continue
                if filas:
                    marcas = ", ".join(["%s"] * len(cols))
                    cur.executemany(
                        "INSERT INTO %s (%s) VALUES (%s)"
                        % (tabla, ", ".join(cols), marcas),
                        [tuple(f) for f in filas])
                # Las columnas id de Postgres son IDENTITY con su contador
                # aparte. Al insertar ids explícitos el contador NO avanza, así
                # que el siguiente INSERT reutilizaría un id existente y
                # fallaría. Hay que ponerlo al día a mano.
                if "id" in cols and filas:
                    cur.execute(
                        "SELECT setval(pg_get_serial_sequence(%s, 'id'), "
                        "(SELECT MAX(id) FROM %s))" % ("%s", tabla), (tabla,))
                cur.execute("SELECT COUNT(*) FROM %s" % tabla)
                n = cur.fetchone()[0]
                marca = "" if n == len(filas) else "  <<< DIFIERE"
                print("%-16s %8d %8d%s" % (tabla, len(filas), n, marca))
                total += n
    print("-" * 36)
    print("%-16s %8s %8d" % ("TOTAL", "", total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
