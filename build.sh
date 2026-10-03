#!/usr/bin/env bash
# Construcción para Render. Se ejecuta en cada despliegue.
set -euo pipefail

pip install -r requirements-web.txt

# NO se baja la voz neural de Piper, aunque funcione: medido en Render, generar
# una frase tarda 24,6 s frente a 1,8 s en un portatil. La CPU del plan gratuito
# es ~14 veces mas lenta y esperar eso para oir una palabra no sirve de nada.
# El audio lo pone el navegador (TTS_SERVIDOR=0 en render.yaml), que en iPhone y
# en Mac usa las voces de Apple: las mismas de siempre y al instante.
#
# Si algun dia se paga un plan con mas CPU, basta con quitar TTS_SERVIDOR=0 y
# volver a bajar el modelo aqui.
echo "Construccion lista (sin voz en el servidor: la pone el navegador)."
