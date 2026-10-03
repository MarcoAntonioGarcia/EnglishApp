#!/usr/bin/env bash
# Construcción para Render. Se ejecuta en cada despliegue.
set -euo pipefail

pip install -r requirements-web.txt

# --- Voz neural Piper -------------------------------------------------------
# El servidor es Linux y no tiene NINGUNA voz: ni el `say` de macOS, ni espeak.
# Sin esto, la app pediría audio al servidor, no podría generarlo y el navegador
# pondría su propia voz, que suena bastante peor.
#
# El modelo pesa 63 MB y NO va en el repo (está en .gitignore): se baja aquí, en
# cada construcción, desde el repositorio oficial de voces de Piper.
MODELO_DIR=assets/piper
MODELO=en_US-amy-medium
BASE=https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium

mkdir -p "$MODELO_DIR"
if [ ! -s "$MODELO_DIR/$MODELO.onnx" ]; then
  echo "Bajando la voz $MODELO (63 MB)..."
  curl -sfL --retry 3 -o "$MODELO_DIR/$MODELO.onnx"      "$BASE/$MODELO.onnx"
  curl -sfL --retry 3 -o "$MODELO_DIR/$MODELO.onnx.json" "$BASE/$MODELO.onnx.json"
fi

# Si la descarga falla, mejor enterarse AQUÍ que servir audio roto en producción.
test -s "$MODELO_DIR/$MODELO.onnx"
test -s "$MODELO_DIR/$MODELO.onnx.json"
echo "Voz lista: $(du -h "$MODELO_DIR/$MODELO.onnx" | cut -f1)"
