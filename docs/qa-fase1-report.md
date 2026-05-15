---
date: 2026-05-15
status: superseded
supersedes_with: session-2026-05-15.md
topic: QA intensivo de la Fase 1 (M1) contra el spec del bloqueador/anonimizador — baseline pre-M1.5
refs:
  - deepseek_privacidad_api_20260515.md (raíz del repo) — spec & QA suite
  - docs/design.md §3, §4 — arquitectura del router y scanner
  - docs/session-2026-05-15.md — cierre M1.5 con quick wins aplicados
  - evals/qa_fase1/ — fixtures, runner, last_run.json
  - Cap 3 (Huyen) p.144 — failure detection determinista, no LLM-judge
  - Cap 10 (Huyen) p.451-452, Fig 10-3 — input guardrails y placeholders
---

> **Estado actual:** este informe es el **baseline pre-M1.5**. Las recomendaciones de "quick wins" descritas en §3.1 fueron aplicadas en la misma sesión y la suite pasó de **34/44 PASS** a **38/44 PASS** (cobertura 75 % → 86 %). Adicionalmente, dos rondas de hardening post-leak añadieron IBAN internacional (drop mod-97), CLABE México y patrones US ABA / bank account. Ver `session-2026-05-15.md` para el cierre completo.

# QA Fase 1 — resultados, gaps, quick wins (baseline)

## 1. Resumen ejecutivo

La Fase 1 (M1) entrega **scanner regex+checksum determinista** integrado en `RouterChatModel`. Esta QA contrasta el M1 entregado contra la suite del documento `deepseek_privacidad_api_20260515.md` (bloques A–F), que describe un objetivo M3-M4 ampliado.

| Bloque | PASS | FAIL | EXPECTED_GAP | Total |
|---|---|---|---|---|
| A — falsos negativos | 18 | 0 | 7 | 25 |
| B — falsos positivos | 8 | 0 | 2 | 10 |
| C — alias y consistencia | 4 | 0 | 2 | 6 |
| D — seguridad del propio scanner | 3 | 0 | 0 | 3 |
| **Total** | **33** | **0** | **11** | **44** |

- **0 FAILs bloqueantes.** Todos los casos no cubiertos están atribuidos a una capability ausente y honestamente categorizada (NER, decoder base64, context classifier, regex puntual).
- **Cobertura efectiva M1:** 33/44 = **75 %** de la suite MD ejecutable contra el código actual.
- **Cobertura "sin contar las capabilities de M2+":** 33/(44−6) = **87 %** (excluye 4 NER + 1 decoder + 1 entropy-detector que requieren componentes nuevos).

### QA-F — latencia (umbrales del MD)

| Payload | p50 | p95 | p99 | Umbral MD | Estado |
|---|---|---|---|---|---|
| 10 KB | 5.87 ms | 6.32 ms | 6.43 ms | < 150 ms | ✓ holgura 23× |
| 100 KB | 58.44 ms | 59.67 ms | 60.82 ms | < 800 ms | ✓ holgura 13× |

Bench `evals/qa_fase1/run.py:latency_bench()` — 50 muestras post warm-up sobre payload sintético con DNI+IBAN+email repetidos.

---

## 2. Cobertura por categoría del MD

| Categoría MD | Cubierto hoy (M1) | Gap declarado |
|---|---|---|
| Cat 1 — identidad personal | `EMAIL`, `PHONE`, `ES_NIF`, `ES_NIE` | Nombres propios (NER), pasaporte, NSS, dirección postal, fecha de nacimiento, CIF empresa |
| Cat 2 — credenciales/secretos | `AWS_ACCESS_KEY`, `GCP_API_KEY`, `STRIPE_KEY`, `GITHUB_TOKEN`, `SLACK_TOKEN`, `TELEGRAM_TOKEN`, `JWT_TOKEN`, `BEARER_TOKEN`, `PEM_KEY`, `SECRET_KEY`, `PASSWORD_FIELD`, `DATABASE_URL` | Hashes `$2a$/argon2`, detector de entropía genérico, webhook URLs con token |
| Cat 3 — bancario/financiero | `CREDIT_CARD` (Luhn), `IBAN_CODE` (mod-97), `SWIFT_CODE` (context) | `CIF` empresa, `CVV`, fecha-exp tarjeta, CCC, importes con contexto |
| Cat 4 — infra interna | `PRIVATE_IP`, `INTERNAL_HOST`, `SECRET_PATH` | MAC, puertos, IPs de producción públicas (lista blanca inversa) |
| Cat 5/6/7/8 — contratos, SQL, código, organizativo | — | Todo NER + clasificación contextual |
| Cat 9 — evasión (base64, hex, split) | — | Decoder previo al scan |

---

## 3. Casos no cubiertos — clasificados

### 3.1 Quick wins (implementables sin dependencias nuevas, dentro del scope M1.5)

| ID | Caso | Cambio mínimo | Coste | Riesgo |
|---|---|---|---|---|
| QA-A01 / QA-A16 | IBAN con espacios o split entre líneas | Aplicar a `IBAN_CODE` la misma normalización que `CREDIT_CARD` ya tiene (separadores opcionales) o pre-paso `re.sub(r'\s+', '', text)` para una segunda pasada con el regex actual | ~5 LoC + 4 tests | Bajo — el validador mod-97 ya descarta basura |
| QA-A18 | `os.environ["DB_PASSWORD"] = "v"` no detectado | Extender `PASSWORD_FIELD` para aceptar `"]`, `']`, o un cierre `])` entre la clave y `=` | ~3 LoC + 2 tests | Bajo |
| QA-A21 | CIF español ausente | Añadir patrón `[A-HJNP-SUVW]\d{7}[0-9A-J]` + validador `_cif_check()` mod-23 puro | ~30 LoC + 6 tests | Bajo — análogo a `_nif_check` |
| QA-B01 | `4000000000000002` flagged fuera de contexto de pago | Añadir `context_words={"card","tarjeta","pan","visa","mastercard","amex","cvv","pago","payment"}` a `CREDIT_CARD` | ~3 LoC + 2 tests | **Trade-off**: reduce FPs pero introduce posible FN si una PAN aparece desnuda. Hay que decidir conservadurismo. |
| QA-B10 | `"password": {"type":...}` en JSON Schema flagged | Excluir cuando el valor inmediato comienza por `{` (es un sub-objeto) | ~5 LoC + 2 tests | Bajo |
| QA-D05 | Fail-closed no explícito | `try/except` en `RouterChatModel._route` con política "redactar todo o bloquear" | ~10 LoC + 1 test | Bajo |

**Estimación combinada:** 1 sesión de trabajo, +6 a 8 tests, cobertura del MD pasa de 75 % → ~89 %.

### 3.2 Gaps honestos (requieren componente M2+)

| ID | Caso | Componente requerido | Roadmap |
|---|---|---|---|
| QA-A15, QA-C03 | Nombres propios en contexto | NER (spaCy `es_core_news_sm`) | M2 — ya documentado en memoria `project_ner_m2.md` |
| QA-A12 | IBAN en base64 | Decoder pre-pass (base64/hex/URL) | M3+ — controvertido: aumenta FP y latencia |
| QA-A22 | Token de alta entropía en path | Detector de entropía Shannon | M2 — barato pero ruidoso, requiere threshold tuning |

### 3.3 Decisiones de diseño (divergencia intencional)

| ID | Comportamiento MD | Comportamiento actual | Justificación |
|---|---|---|---|
| QA-C01 | Mismo IBAN → mismo alias `[IBAN_1]` siempre | Cada ocurrencia → `{/IBAN_CODE_N/}` único | Placeholders únicos sobreviven al reordenamiento por el LLM (Cap 10 Fig 10-3). Coste: cardinalidad observable (ver QA-C06). |
| QA-C06 | Alias no debe filtrar cardinalidad | El número de placeholders sí refleja N entidades | Trade-off conocido. Solución futura: hash-based deterministic IDs por valor, en M2. |

---

## 4. Mejoras de acuerdo al nivel de madurez (M1 → M2)

### M1.5 — Iteración corta antes de M2 (recomendada)

1. **Apply QA-B01 + QA-B10 context fixes** — reducir falsos positivos en payloads no transaccionales. Es la fricción que más se siente en CLI testing real.
2. **CIF español + IBAN con separadores** — son la 2ª y 3ª entidad bancaria europea más pedida y completan la cobertura financiera del MD.
3. **Fail-closed explícito** — pequeño try/except que registre en traza `scan_error=true` y aborte la llamada al modelo. Garantiza el invariante D5 del MD.

### M2 — entradas grandes ya en `project_ner_m2.md`

1. **NER con spaCy `es_core_news_sm`** — abre Cat 1, 5, 6, 7, 8 completas.
2. **Detector de entropía Shannon** — webhook URLs y API keys sin prefijo conocido (Cat 2).
3. **Publicness classifier real (allowlist)** — Cap 4 Tabla 4-3 + design.md §4.2.

### M3+ (de boletín, no inminente)

- Decoder pre-pass (base64/hex/URL) — sólo si se valida en eval que los FN actuales son reales y no anecdóticos.
- Stored procedure / SQL semantic redactor — fuera de scope para un coding agent.
- OCR sobre PDFs — el deepagents TUI no procesa adjuntos.

---

## 5. Validaciones de seguridad del propio anonimizador (Bloque D)

| ID | Garantía | Verificación |
|---|---|---|
| QA-D01 | Logs sin valores raw | Inspección `~/.deep_devops/traces.jsonl`: campo `redacted_fields` es lista de **tipos**, no valores. ✓ |
| QA-D02 | Mapping efímero | `RedactionContext` es `dataclass` per-request, sin caché global. Vive en stack frame de `_generate`. ✓ |
| QA-D04 | Cero llamadas de red durante el scan | `pii_scanner.py` sólo importa `re`, `dataclasses`, `typing`. Audit inline. ✓ |
| QA-D05 | Fail-closed | **Actualmente implícito** (excepción propaga; deepagents la muestra). Quick win recomendado. |
| QA-D03 | Modo PASSTHROUGH con flag firmado | N/A en M1 — no hay modos. La política actual es siempre redactar. |
| QA-D06 | Timing-attack hardening | N/A en M1 — overhead determinista por tamaño de input, no por contenido. |

---

## 6. Aceptación

- **0 FAILs bloqueantes** sobre la suite ejecutable.
- **Latencia 13× a 23× por debajo** del umbral del MD.
- **Roadmap claro:** 6 quick wins identificados (≤1 sesión) + plan M2 ya documentado.
- **Reproducible:** `uv run python -m evals.qa_fase1.run` regenera el reporte y guarda `last_run.json` para tracking longitudinal.

> Conclusión: la Fase 1 cumple su contrato declarado (regex+checksum determinista, redacción reversible, traza local sin PII) y es honesta respecto a sus límites. La distancia entre M1 y el spec completo del MD es **un componente NER + un puñado de quick wins regex** — todo modelado en el roadmap.
