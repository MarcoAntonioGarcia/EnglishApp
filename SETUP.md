# Instalación

App web **local**: corre en tu máquina y se abre en el navegador. Tus datos
(progreso, vocabulario, redacciones) se quedan en tu ordenador, en `database.db`.
Nada se sube a ningún sitio.

Requiere **Python 3.10+**.

## 1. Dependencias

```bash
pip install -r requirements.txt
```

## 2. Sembrar los mazos

Los mazos de estudio viven en el código, pero hay que volcarlos a tu base de
datos la primera vez:

```bash
python3 seed_decks.py
```

Crea 648 tarjetas en 6 mazos. Es seguro repetirlo: no duplica ni borra progreso.

## 3. Arrancar

```bash
python3 webapp.py
```

Abre **http://localhost:8080**.

Para dejarlo corriendo en segundo plano:

```bash
nohup python3 webapp.py > webapp.log 2>&1 &
# para pararlo:  kill $(lsof -ti:8080)
```

## 4. Tu clave de Gemini (opcional pero recomendable)

Sin clave, la app funciona para leer y repasar tarjetas, pero **no** hay
traducción al clicar palabras, evaluación de redacciones ni generación de
ejemplos.

Consigue una gratis en [Google AI Studio](https://aistudio.google.com/apikey)
y pégala en la app: **⚙ Ajustes → API key**. Se guarda en `config.local.json`,
que está en `.gitignore` y nunca se sube.

Cada uno usa su propia clave: las cuotas del free tier son por cuenta.

## 5. Libros

La app no trae libros. Dos formas de conseguirlos:

- **🔎 Find books by level** (barra lateral): 21 lecturas de dominio público
  clasificadas A2–B2, se descargan de Project Gutenberg con un clic. Gratis y
  legal.
- **＋ Add book**: sube tus propios `.epub` o `.pdf`.

## Notas

**Voces.** La lectura del libro usa la voz del navegador (Web Speech API). Las
tarjetas usan las voces del sistema. En macOS salen las de `say` (Samantha y
compañía). Hay soporte para voces neurales **Piper**, más humanas, pero sus
modelos ocupan ~175 MB y no van en el repo; sin ellos la app funciona igual con
las del sistema.

**Fuera de macOS** las voces del sistema pueden no estar disponibles; la lectura
del libro sigue funcionando porque la pone el navegador.

**Base de datos.** Se crea sola al arrancar. Si quieres empezar de cero, borra
`database.db` y vuelve a sembrar.
