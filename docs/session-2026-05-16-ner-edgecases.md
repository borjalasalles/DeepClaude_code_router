---
date: 2026-05-16
status: superseded
superseded_by: session-2026-05-16-closeout.md
topic: NER edge-case testing — fail-open por spaCy ausente + bugs del suelo wordlist
refs:
  - design.md
  - design.md §4.2
  - chapters_notes.md
  - Cap 3 p.144
  - Cap 10 p.451-452
  - session-2026-05-16.md (M2.1)
  - project-ner-m2
---

# NER edge-cases — fail-open silencioso + suelo wordlist roto

## Context

Tras cerrar M2.1 (`session-2026-05-16.md`) se probó el scanner de nombres con 5
edge-cases internacionales (ES nombres-sustantivo, DE apellidos-oficio + `ß`/`ü`,
UK/US apellidos con guión + mal-casing, BR/CH partículas `de`/`da`, y un set de
falsos positivos: "Banco Santander", "Washington", "avenida San Juan", "el
Mercedes"). Los prompts se concatenaron y se enviaron como un único mensaje.
El LLM receptor reportó nombres reales aún visibles → indicio de fuga de PII.

## Findings (reproducido contra el código, no inferido)

**Causa dominante: spaCy NO está instalado en el venv.** `spacy` +
`es_core_news_sm` están declarados pero en el grupo opcional
`[dependency-groups].ner` de `pyproject.toml` (líneas 30-33); un `uv sync` plano
los omite. `ner_scanner._load_nlp()` captura el `ImportError` y devuelve `None`
en silencio → la capa NER contextual queda inactiva → la detección colapsa a
**wordlist-only**. La suite 220/220 corrió casi con seguridad así.

Esa degradación silenciosa es **en sí misma una violación de la Regla Dura #8**
(tier-1 leak target = 0): la capa de seguridad puede desaparecer sin señal.

Resultados reproducidos (blob concatenado, exactamente como lo ejecuta
`model.py:201` con `require_context=True`):

| Edge | Esperado | Real | Estado |
|---|---|---|---|
| 1 ES | enmascarar `Rosa de la Rosa`, `Santiago Blanco` | `Santiago Blanco` ✓; `Rosa`+`Rosa` como dos tokens, `de la` expuesto | parcial — estructura fuga |
| 2 DE | `Anke Koch`, `Jürgen Weiß` | solo `Koch` | **`Anke`, `Jürgen Weiß` fugan** |
| 3 UK/US | `Elizabeth Smith-Jones`, `mArIa pErEz` | ambos ✓ (mal-casing bien resuelto) | pass |
| 4 BR/CH | `Jean-Pierre de Watteville`, `Joao da Silva Santos` | `Jean-Pierre` solo; `Joao`/`Silva Santos` fragmentados | **`de Watteville` fuga; nombres fragmentados** |
| 5 FP | enmascarar **nada** | enmascaró `Juan` (de "avenida San Juan") y `Mercedes` (el coche) | **2 falsos positivos** |

Lo más grave: por-caso, en solitario, **E1, E3 y E4 detectan `detected=False`**.
El blob solo los pilló porque `_has_name_context` es **global**: un único
"jefe"/"cliente" en cualquier parte abre la puerta para todo el texto. Un prompt
E3 aislado → "Elizabeth Smith-Jones" fuga en completo silencio.

## Root causes (ordenadas por criticidad)

1. **Grupo `ner` no instalado → fail-open silencioso** (causa dominante; viola
   la Regla #8 por sí sola).
2. **Puerta de contexto global y todo-o-nada.** `_has_name_context` escanea el
   texto entero; sin keyword, *todos* los nombres reales se pierden sin señal.
   Es el peor modo de falso negativo.
3. **Normalización descarta caracteres no descomponibles.** Probado:
   `_norm("Weiß")→"wei"`, `"Łukasz"→"ukasz"`, `"Jørgen"→"jrgen"`. `ß ø æ ł đ`
   se borran, no se transliteran — los apellidos DE/Nórdicos/PL no matchean ni
   aunque se añadan al wordlist.
4. **Partículas no puenteadas.** `de / da / do / dos / del / de la / van / von /
   di` son tokens-palabra; `_merge_compound_names` (separador ≤3 chars) no los
   cruza: apellido desconocido tras partícula fuga (`de Watteville`), conocido
   se fragmenta (`Joao | da | Silva Santos`).
5. **Wordlist-only no distingue "San Juan" de persona ni "Mercedes" coche de
   persona** — intrínseco a correr sin NER; exactamente por esto el diseño
   manda NER (`design.md §4.2`).

Neto: el build a la vez **infra-enmascara PII real y sobre-enmascara palabras
de contexto** — el doble fallo que E1 y E5 estaban diseñados para exponer.

## Proposed plan (pendiente de decisión — ver Follow-ups)

- **P0 — Eliminar el fail-open.** (a) Mover `spacy`+`es_core_news_sm` a deps
  core (quick win, layer-agnóstico, seguro hacerlo ya). (b) `ner_scanner` debe
  distinguir "NER desactivada a propósito" de "NER ausente inesperadamente"; en
  el segundo caso la **enforcement** (no permitir tier-1 / forzar tier ≥ 2 +
  señal ruidosa) debe vivir en la capa que **siempre** está en la ruta — ver
  `session-2026-05-16-guardrail-middleware.md`. Implementar la enforcement en
  `RouterChatModel._route()` da falsa seguridad: no dispara si el usuario hace
  `/model`.
- **P1 — Suelo wordlist fiable (layer-agnóstico, código reutilizable):**
  transliterar `ß→ss, ø→o, ł→l, æ→ae, đ→d, þ→th, ð→d` antes del descarte ASCII;
  señal fuerte (nombre+apellido adyacentes / compuesto con guión) dispara sin
  exigir keyword, el contexto solo se exige para tokens sueltos ambiguos;
  bridging de partículas en `_merge_compound_names`.
- **P2 — FP Edge-5.** Trabajo intrínseco del modelo contextual; con la puerta
  de contexto arreglada varios FP caen solos. **No** blacklist de marcas (viola
  el espíritu whitelist del diseño, §3.5). FP residual se mide en eval set.
- **P3 — Regresión.** Estos 5 edge-cases en `evals/` con detecciones esperadas
  **y no-detecciones** (E5); re-ejecutar con `ner` instalado para línea base
  real. Pin de versión del modelo (Regla #7).

Ampliar el wordlist con "Jürgen/Anke/Weiß" es lo **menos** importante (tirita);
perseguir cobertura de listas es infinito — por eso el diseño manda NER.

## Rationale

- Cap 3 p.144: señales deterministas sin LLM-judge; `_norm`+wordlist y spaCy
  son O(n) sincrónicos — el suelo determinista debe ser correcto, no opcional.
- Cap 10 p.451-452: input guardrails antes de toda llamada al modelo; un
  guardrail que se degrada en silencio no es un guardrail.
- `design.md §4.2`: fail-closed. El estado actual es fail-**open** — contradice
  el diseño y la Regla Dura #8 (leak target = 0).
- `design.md §4.2` "NER gap (M2 candidate)": el plan ya preveía spaCy
  `es_core_news_sm`; el bug es que se dejó opcional y se degrada sin señal.

## Follow-ups

- [ ] **Decisión pendiente (P0b):** cuando la NER falte inesperadamente,
      ¿error duro al arrancar, o arranque permitido con tier-1 deshabilitado +
      warning ruidoso? La 2ª es más coherente con "la sesión nunca se bloquea"
      (§4.3); la 1ª es más estricta.
- [ ] **Secuenciación:** la *enforcement* de P0b debe implementarse en la capa
      que sobrevive a `/model` → depende de la decisión arquitectónica en
      `session-2026-05-16-guardrail-middleware.md`. P1 (calidad de scanner) es
      layer-agnóstico y puede avanzar en paralelo sin desperdicio.
- [ ] Quick win seguro ya: mover el grupo `ner` a deps core (P0a).
- [ ] Encaje en milestones: esto es **corrección de M2** (input guardrails);
      no abre M3. Es prioritario sobre el resto de M2 pendiente (entropía
      Shannon) — un scanner que se apaga solo invalida todo lo demás.

---

## Update 2026-05-16 — superseded (ver `session-2026-05-16-closeout.md`)

P0/P1 cerrados así:

- **P0a** ✓ `spacy` + `es_core_news_sm` + `en_core_web_sm` + `langdetect` a
  deps core. Grupo opcional `[dependency-groups].ner` eliminado.
- **P0b** ✓ en `RouterChatModel._route()` (NO en middleware, que queda
  aplazado): `ner_scanner.scan()` lanza `NerUnavailableError` ante ausencia
  total de la capa → camino existente `scan_error`. Es ausencia de capa, no
  bloqueo por-query.
- **Approach 2 (NER consciente del idioma)** ✓ doble pipeline ES+EN con
  `langdetect` determinista (`DetectorFactory.seed=0`). FP/DoS de inglés
  ("list") eliminado. `_PERSON_LABELS={PER,PERSON}` para no fugar nombres EN.
- **Bloqueo de turno por detección NER**: implementado y **revertido** en la
  misma sesión por decisión del usuario ("spaCy ayuda a securizar, no bloquea").
- **P1** (bridging de partículas, transliteración `ß/ø/ł`, FP residual,
  expansión wordlist): **diferido**, se itera desde fugas observadas reales.
- Hallazgos nuevos en testing TUI real: placeholder-as-filepath, nickname
  `micky` fugado, limitación estructural del modelo respondiendo "no PII".
  Documentados en el closeout y en el README.
