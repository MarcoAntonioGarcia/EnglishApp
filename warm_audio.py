"""
warm_audio.py — Pre-genera (cachea) el audio neural (Amy) de todas las tarjetas de
los decks, para que el primer repaso suene instantáneo. El audio es on-demand, así que
esto es solo para calentar la caché de la voz por defecto.
"""
# Copyright (C) 2026 Marco Antonio Garcia
#
# Este archivo es parte de este proyecto, software libre bajo la GNU Affero
# General Public License v3 o posterior. Se distribuye SIN NINGUNA GARANTÍA.
# Ver el archivo LICENSE para los términos completos.

import core

VOICE = "piper:en_US-amy-medium"
RATE = 145


def warm():
    db = core.DatabaseManager()
    n = 0
    for d in db.list_decks():
        for c in db.deck_study_cards(d["id"]):
            texts = [c["front"]]
            en = (c.get("note") or "").split("—")[0].strip()
            if en:
                texts.append(en)
            for t in texts:
                core.synthesize(t, "en", rate=RATE, voice=VOICE)
                n += 1
    print(f"Audio calentado: {n} clips (voz Amy, rate {RATE}).")


if __name__ == "__main__":
    warm()
