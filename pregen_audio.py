#!/usr/bin/env python3
"""Pre-genera el audio de las tarjetas con la voz neural, para el servidor.

En el servidor no existe ninguna voz del sistema: ni el `say` de macOS, ni los
modelos de Piper (175 MB, fuera del repo). Sin esto, las tarjetas sonarían con
la voz del navegador, que es bastante peor.

Los ficheros se indexan SOLO por el texto -- no por voz ni velocidad, como la
caché normal -- para que cualquier petición los encuentre sea cual sea la voz
que pida el navegador.

Se guardan en AAC y no en WAV porque pesa el 17 %: los 1.376 clips bajan de
~68 MB a ~12 MB, que sí caben razonablemente en el repo y no hacen eterno cada
despliegue.

    python3 pregen_audio.py            # genera lo que falte
    python3 pregen_audio.py --rehacer  # vuelve a generarlo todo
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

import core

BITRATE = "48000"


def textos() -> list[str]:
    """El frente de cada tarjeta y la parte inglesa de su ejemplo, sin repetir."""
    db = core.DatabaseManager()
    fuera, vistos = [], set()
    for d in db.list_decks():
        for c in db.deck_study_cards(d["id"]):
            candidatos = [c["front"]]
            en = (c.get("note") or "").split("—")[0].strip()
            if en:
                candidatos.append(en)
            for t in candidatos:
                t = (t or "").strip()
                if t and t.lower() not in vistos:
                    vistos.add(t.lower())
                    fuera.append(t)
    return fuera


def a_aac(wav: str, destino: str) -> bool:
    """WAV -> AAC con afconvert, que viene con macOS. Devuelve si salió bien."""
    try:
        subprocess.run(
            ["afconvert", "-f", "m4af", "-d", "aac", "-b", BITRATE, wav, destino],
            check=True, timeout=60,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return os.path.exists(destino) and os.path.getsize(destino) > 0
    except Exception:
        return False


def main() -> int:
    if sys.platform != "darwin":
        print("Esto se ejecuta en el Mac, que es donde estan las voces buenas.",
              file=sys.stderr)
        return 1
    rehacer = "--rehacer" in sys.argv
    os.makedirs(core.PREGEN_DIR, exist_ok=True)

    lista = textos()
    print(f"{len(lista)} textos. Voz {core.VOZ_PREGEN}, ritmo {core.RITMO_PREGEN}.")
    hechos = saltados = fallos = 0
    t0 = time.time()
    for i, texto in enumerate(lista, 1):
        destino = os.path.join(core.PREGEN_DIR, core.clave_pregen(texto))
        if os.path.exists(destino) and os.path.getsize(destino) > 0 and not rehacer:
            saltados += 1
            continue
        wav = core.synthesize(texto, "en", rate=core.RITMO_PREGEN,
                              voice=core.VOZ_PREGEN)
        if os.path.realpath(wav) == os.path.realpath(core.SAMPLE_WAV):
            fallos += 1
            print(f"  FALLO al generar: {texto[:60]}", file=sys.stderr)
            continue
        if a_aac(wav, destino):
            hechos += 1
        else:
            fallos += 1
            print(f"  FALLO al convertir: {texto[:60]}", file=sys.stderr)
        if i % 100 == 0:
            print(f"  {i}/{len(lista)}  ({time.time()-t0:.0f}s)")

    peso = sum(os.path.getsize(os.path.join(core.PREGEN_DIR, n))
               for n in os.listdir(core.PREGEN_DIR)) / 1e6
    print(f"\nGenerados {hechos}, ya estaban {saltados}, fallos {fallos}.")
    print(f"Carpeta: {peso:.1f} MB en {len(os.listdir(core.PREGEN_DIR))} ficheros.")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
