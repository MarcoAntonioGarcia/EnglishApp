# Flujo TTS + LLM asíncrono — Lectura asistida

Punto de **mayor riesgo técnico**: reproducir voz por oración, resaltar en sincronía,
traducir bajo demanda y avanzar solo, todo **sin congelar la UI**.

## Regla de oro

> El hilo de UI (PyQt) **nunca** hace `time.sleep`, ni espera a la red, ni bloquea.
> TTS (pyttsx3) y LLM (Gemini) corren en `QThread` workers y responden por **señales**.

---

## Dos motores distintos

| Motor | Qué produce | Dónde vive | Delay real |
|---|---|---|---|
| **TTS — pyttsx3** | Voz (`.wav`) | Local (voz del SO) | ~instantáneo |
| **LLM — Gemini** | Texto (traducción, gramática, ejemplos) | Nube (free tier) | ~0.5–2 s |

El delay del LLM se **esconde** con async + caché + prefetch → se siente fluido.

---

## Actores

- **AppWindow** — hilo principal. Dueña del resaltado y del índice de oración actual.
- **TTSWorker (QThread)** — llama a `synthesize()` (pyttsx3, hoy mock) → emite `ready(index, path)`.
- **LLMWorker (QThread)** — llama a `translate()` (Gemini, hoy mock) → emite `translated(text)`.
- **AudioPlayer** — `QMediaPlayer`; reproduce el `.wav` y emite `finished`.
- **DatabaseManager** — persiste `reading_state` y cachea traducciones (`translations`).

---

## Estado en memoria (en AppWindow)

```
current_chapter_index : int
current_sentence_index: int
sentences             : list[str]        # oraciones del capítulo actual
is_playing            : bool
prefetch_cache        : dict[int, str]   # index -> path de audio ya generado
```

---

## Ciclo principal (play → highlight → next)

```
[ Usuario pulsa PLAY ]
        │
        ▼
1. AppWindow.highlight(current_sentence_index)      # resalta la oración COMPLETA
        │
        ▼
2. ¿está en prefetch_cache?
        ├─ sí → usa el path cacheado
        └─ no → TTSWorker.request(index, texto)     # asíncrono, NO bloquea
                        │
                        ▼ (señal)
                 ready(index, path)
        │
        ▼
3. AudioPlayer.play(path)
        │
        │  (en paralelo) TTSWorker.request(index+1)  # PREFETCH del audio siguiente
        │
        ▼
4. AudioPlayer.finished  ──► AppWindow.advance()
        │
        ▼
5. advance():
        current_sentence_index += 1
        DatabaseManager.save_reading_state(...)      # AUTOGUARDADO
        ¿queda oración en el capítulo?
              ├─ sí → volver a paso 1
              └─ no → cargar siguiente capítulo (o detener si es el final)
```

---

## Traducción bajo demanda (LLM)

```
[ Usuario selecciona una palabra/oración y pide traducir ]
        │
        ▼
1. DatabaseManager.get_cached_translation(text)      # busca en caché
        ├─ hit  → mostrar al instante (0 delay, 0 tokens)
        └─ miss →
             LLMWorker.request(text)                 # asíncrono, NO bloquea
                   │  (la UI sigue usable mientras llega)
                   ▼ (señal, ~0.5–2 s)
             translated(text_result)
                   │
                   ▼
             mostrar en el panel de traducción
             DatabaseManager.cache_translation(...)  # guardar para la próxima
```

> La caché convierte el segundo (y siguiente) acceso al mismo texto en **instantáneo**.

---

## PAUSA

```
[ Usuario pulsa PAUSE ]
        │
        ▼
AudioPlayer.pause()
is_playing = False
DatabaseManager.save_reading_state(chapter, sentence)   # guarda índice actual
(el resaltado se mantiene en la oración actual)
```

Reanudar = `play()` desde `current_sentence_index` (sin regenerar si sigue en cache).

---

## SALTO (clic en otra oración)

```
[ Usuario hace clic en la oración N ]
        │
        ▼
AudioPlayer.stop()
current_sentence_index = N
AppWindow.highlight(N)
DatabaseManager.save_reading_state(chapter, N)          # guarda salto
descartar prefetch obsoleto
si is_playing → recalcular audio de N (TTSWorker.request(N)) y reproducir
```

---

## Mocks (por ahora)

```python
def synthesize(text: str) -> str:
    """Mock TTS: simula latencia y devuelve un .wav de prueba local.
    Real: pyttsx3.save_to_file(text, path) → engine.runAndWait()."""
    time.sleep(1)                 # SOLO dentro del TTSWorker (nunca en UI)
    return "assets/sample.wav"

def translate(text: str, target_lang="es") -> str:
    """Mock LLM: simula latencia de Gemini y devuelve texto falso.
    Real: cliente google-generativeai con prompt de traducción."""
    time.sleep(1)                 # SOLO dentro del LLMWorker (nunca en UI)
    return f"[traducción simulada de: {text}]"
```

> Contrato estable: al conectar lo real, solo cambian los cuerpos de `synthesize()` y
> `translate()`. Workers, señales, prefetch, caché y resaltado quedan intactos.

---

## Invariantes de seguridad de hilos

1. `synthesize()` y `translate()` (con sus `sleep`) viven **solo** dentro de sus workers.
2. La UI se actualiza **solo** desde slots conectados a señales (hilo principal).
3. Un único `AudioPlayer`; antes de un `play` nuevo siempre hay `stop`.
4. Cada transición de estado de lectura llama a `save_reading_state` → nunca se pierde la posición.
5. Toda traducción pasa antes por la caché → menos red, menos tokens, menos delay.
