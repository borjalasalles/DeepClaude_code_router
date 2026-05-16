---
date: 2026-05-16
status: accepted
topic: Cierre de sesión — seguridad no bloqueante, `/model` aplazado-por-proceso, NER consciente del idioma
refs:
  - design.md
  - design.md §11
  - session-2026-05-16.md
  - session-2026-05-16-guardrail-middleware.md (superseded)
  - session-2026-05-16-ner-edgecases.md (superseded)
  - reference-deepagents-setup
  - Cap 3 p.144
  - Cap 10 p.451-455
---

# Cierre 2026-05-16 — seguridad no bloqueante; `/model` aplazado-por-proceso

Consolida y **supersede** los dos drafts del mismo día
(`session-2026-05-16-guardrail-middleware.md`,
`session-2026-05-16-ner-edgecases.md`). Aquellos eran propuestas; este es el
resultado real.

## Contexto

Testing post-M2.1 destapó dos hallazgos arquitectónicos. Esta sesión cierra
ambos con una postura coherente — "reforzar seguridad **no bloqueante**;
iterar wordlists/lógica desde fugas observadas reales, no especulativamente;
no sobre-complejizar la llamada a DeepSeek China hasta que Tier-2 (Nebius) y
Tier-3 (Anthropic) estén aprobados".

## Decisiones tomadas

1. **Hallazgo /model (puenteo del guardrail) — aplazado-por-proceso, NO técnicamente.**
   Consigna a devs: lanzar con `--model deep-devops:router` y **no usar `/model`**.
   El fix técnico (middleware del grafo, `wrap_model_call`) queda identificado
   y planificado, no descartado. `design.md §11` ("`RouterChatModel` … single
   entry point") queda anotado como **inválido frente a `/model`** (ver amendment
   en design.md). Riesgo residual aceptado conscientemente: si un dev usa
   `/model`, la fuga a China es silenciosa, irreversible, y nuestro propio
   código ni puede detectarla (no está en la ruta).

2. **NER P0a — spaCy obligatoria a deps core.**
   `spacy>=3.7`, `es_core_news_sm`, `en_core_web_sm`, `langdetect` salen del
   grupo opcional `[dependency-groups].ner` (eliminado) y pasan a
   `dependencies`. Un `uv sync` plano ya no degrada en silencio a wordlist-only
   (violación silenciosa de Regla Dura #8 — cerrada).

3. **NER P0b — fail-closed solo ante ausencia de capa.**
   `ner_scanner.scan()` lanza `NerUnavailableError` si los modelos spaCy no
   cargan en absoluto. El camino existente `scan_error` en `model.py` lo
   absorbe (turno abortado, sin upstream). Es **ausencia de capa**, NO bloqueo
   por-query. Vive en `RouterChatModel._route()` — coherente con la postura
   "deferred-by-process" (el `--model deep-devops:router` SÍ está en la ruta).

4. **Política de bloqueo de turno por detección NER — probada y revertida.**
   Implementada (`Tier1BlockedError`, `_blocked_meta`, route `tier1_blocked`)
   y eliminada en la misma sesión por decisión del usuario: "spaCy debe ayudar
   a securizar, no ser bloqueante". Razón concreta: `es_core_news_sm` sobre
   texto inglés etiquetaba palabras comunes (`list` en "how do I sort a
   list?") como PER → con bloqueo, preguntas de código benignas quedaban
   denegadas. Sin código muerto: revertido completo. Vuelta al comportamiento
   pre-sesión: detección NER → `_merge_scan_results` → redacta y sigue.

5. **Approach 2 — NER consciente del idioma.**
   `ner_scanner` carga dos pipelines (`es_core_news_sm` + `en_core_web_sm`).
   `_detect_lang()` usa `langdetect` con `DetectorFactory.seed=0` (determinista,
   Cap 3 §señales deterministas; <12 chars o duda → `es` conservador).
   `_PERSON_LABELS = {"PER", "PERSON"}` para no fugar nombres EN (en_core_web_sm
   emite `PERSON`, no `PER`). FP/DoS de inglés eliminado. Como efecto colateral
   positivo: el modelo EN ahora caza "John Smith"/"Elizabeth Smith-Jones" que
   el modelo ES se perdía → **mejora neta de seguridad**.

6. **Compound-name labeling consistente.**
   En `_spacy_scan`, un span PER multi-token (≥2 tokens, p.ej. "Miguel Angel",
   "John Smith") se etiqueta `NOMBRE_COMPUESTO`. Antes solo el merge de wordlist
   emitía `NOMBRE_COMPUESTO`, dejando inconsistente el caso detectado por spaCy.
   Redacción idéntica; solo la etiqueta refleja la estructura. Test
   `test_miguel_angel_compound` pasa.

## Hallazgos observados en testing TUI real (post-implementación)

Probado en `deepagents --model deep-devops:router` end-to-end. Tres patrones
de fallo **observados** (no especulativos) — insumo válido para iterar:

- **Placeholder-as-filepath.** Frente a `{/NOMBRE_COMPUESTO_1/}` en el input
  redactado, el modelo (DeepSeek) lo trata como ruta y llama
  `read_file(NOMBRE_COMPUESTO_1)`. No es fuga (placeholder sin PII, fichero no
  existe) — pero:
  - Defecto UX/robustez en cada nombre redactado.
  - Vector latente: el modelo **especulando** sobre placeholders es el camino
    por el que podría intentar reconstruir el original. Y los args de
    tool-call / lecturas de fichero **hoy no se escanean** (solo `HumanMessage`).
  - Mitigaciones baratas (no bloqueantes, encajan en la directriz):
    system-prompt hardening vía `AGENTS.md`, y/o cambio de delimitador a forma
    no-path-like (p.ej. `⟦NOMBRE_COMPUESTO_1⟧`). Decisión post-testing.

- **Nickname `micky` fugado en claro.** No está en `DIMINUTIVOS`; spaCy no lo
  etiqueta. Brecha de wordlist conocida — el diseño manda NER precisamente
  porque las listas son infinitas (`design.md §4.2`).

- **Honestidad del modelo hacia el usuario — limitación estructural.**
  Ante "¿te he pasado PII?", el modelo responde "no" basándose en lo que ve
  (placeholders). El usuario sí pasó PII; el scanner la cazó *antes* de que
  el modelo la viera. El modelo es ciego por diseño → no puede responder con
  verdad. Esto **no se arregla en el código**; se documenta en README.

## Alcance reconocido (lo que NO está en scope)

En el blob adversarial, el modelo cita explícitamente *Madrid, Berlín,
Londres, Zúrich, São Paulo, Washington, Banco Santander, registros médicos
VIP, RRHH*. Esos tokens **viajaron en claro a tier-1/China**. El scanner
cubre PER (personas), instrumentos financieros, credenciales/secretos y
markers de red. **Ubicaciones, contexto organizativo y cliente bancario están
fuera de scope por diseño** (no son PII en sentido estricto; serían "contexto
sensible de negocio"). Decisión consciente alineada con la directriz: no
sobre-complejizar la llamada a DeepSeek China hasta que Tier-2/3 estén
cableados. Cuando los tiers EU/Anthropic estén operativos, el problema cambia
de forma — confidencial irá ahí, no a tier-1.

## Gotcha operativo

`deep_devops` está **editable-installed** en el venv aislado de
`deepagents-cli` (`__editable__.deep_devops-0.0.1.pth`). Un `uv pip install
-e` resuelve dependencias al instalar; si cambian las deps core (p.ej. añadir
spaCy/langdetect/modelos NER), hay que **re-ejecutarlo en ese venv** o
deepagents importa `deep_devops` pero no sus deps nuevas → `NerUnavailableError`
fail-closed en el primer mensaje. Confirmado y arreglado en esta sesión.
`uv sync` arregla el venv del *proyecto*, no el de deepagents-cli — son
entornos distintos. Documentado en `reference-deepagents-setup`.

## Estrategia explícita (durante Tier-1-only)

- No sobre-complejizar la llamada a DeepSeek China.
- Concentrar la inversión en **seguridad NO bloqueante** (redacta y continúa).
- Iterar wordlists/lógica NER **desde fugas observadas reales**, no especulativamente.
- El fix técnico de `/model` (middleware) sigue identificado y planificado.

Reflejado en `Documents/pptx/Deep-DevOps Strategy.pptx` (slides AS-IS + TO-BE
de seguridad añadidas esta sesión).

## Métricas finales

- Tests: **220/220** ✓
- `uv sync` plano: `spacy 3.8.14`, `es_core_news_sm`, `en_core_web_sm`,
  `langdetect` ya entran.
- Runtime deepagents-cli: NER carga, scan funciona end-to-end (`hola → []`;
  `Miguel Angel → NOMBRE_COMPUESTO`; `how do I sort a list? → []`).

## Cambios en código (resumen)

- `pyproject.toml`: deps core ampliadas; grupo `ner` eliminado.
- `deep_devops/router/ner_scanner.py`: `NerUnavailableError`, doble pipeline
  ES+EN, `_detect_lang` (langdetect determinista), `_PERSON_LABELS`, relabel
  compound (≥2 tokens) en `_spacy_scan`.
- `deep_devops/router/model.py`: sin cambios funcionales netos sobre M2.1.
  Revertidos los del intento de bloqueo (sin código muerto); docstring del
  módulo actualizado al modelo "spaCy AIDS redaction — never blocks the turn".

## Pendiente (futuras sesiones)

- **System-prompt hardening** contra speculation sobre placeholders. Subir
  prioridad: observado en TUI real, no teórico.
- **Cambio de delimitador** del placeholder a forma no-path-like — decisión
  post-testing.
- Cuando Tier-2 (Nebius) se cablee: retomar el fix técnico del bypass
  `/model` (middleware `wrap_model_call`) — enmienda `design.md §11/§2/§4.1/§8`.
- **Escaneo de `ToolMessage`** / lecturas de fichero (Fase 2 ya anotada).
- Expansión de wordlist / bridging de partículas (`Rosa de la Rosa`,
  `de Watteville`) — solo cuando aparezcan fugas observadas concretas.
