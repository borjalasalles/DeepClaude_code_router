---
date: 2026-05-16
status: superseded
superseded_by: session-2026-05-16-closeout.md
topic: La seguridad debe sobrevivir a /model — migrar de class_path a AgentMiddleware
refs:
  - design.md
  - design.md §11
  - design.md §2
  - design.md §4.1
  - design.md §8
  - chapters_notes.md
  - Cap 10 p.451-455
  - reference-deepagents-setup
---

# La seguridad debe sobrevivir a `/model` — guardrail como middleware

## Context

deepagents expone `/model` (y `--model`): el usuario puede cambiar en caliente
a `anthropic:…`, `openai:…`, `azure_openai:…`, `gemini:…` o `deep-devops:router`.
Pregunta: ¿pueden aplicarse SIEMPRE nuestras medidas de seguridad aunque el
usuario cambie de LLM? Investigado contra deepagents 0.6.1 / deepagents-cli
0.0.59 instalados.

## Findings (verificado en el código de deepagents)

**El layer actual es el equivocado y `design.md §11` es ahora falso.** La
seguridad vive dentro de `RouterChatModel` (provider `class_path`). Solo se
ejecuta si el modelo seleccionado *es* `deep-devops:router`. Un
`/model openai:gpt-5.4` instancia otro objeto modelo → el wrapper nunca está en
la ruta → **scan/redact/routing totalmente puenteados, sin aviso**. `design.md
§11` afirma "`RouterChatModel` … is the single entry point": esa premisa es
demostrablemente falsa en cuanto el usuario usa `/model`.

**El mecanismo correcto existe y es de primera clase:**

- deepagents construye el agente como grafo LangGraph con una pila de
  **middleware**: `create_deep_agent(..., middleware: Sequence[AgentMiddleware]
  = ())` (`graph.py:216-221`; el middleware de usuario se inserta a mitad de
  pila, `graph.py:307-324`). Hook relevante: `wrap_model_call` /
  `awrap_model_call` — envuelve **cada** invocación de modelo y puede
  reescribir mensajes o cortocircuitar (devolver respuesta sin llamar al
  proveedor).
- El propio `/model` del CLI **es** un middleware: `ConfigurableModelMiddleware.
  wrap_model_call` (`deepagents_cli/configurable_model.py`) cambia el modelo
  *por-petición* leyendo `runtime.context`. **El grafo se construye una sola
  vez**; `/model` NO reconstruye el agente ni salta el middleware.
- Conclusión: un `SecurityGuardrailMiddleware` con `wrap_model_call` corre en
  **todos** los turnos, sea cual sea el proveedor elegido. Ve los mensajes
  finales y el modelo destino resuelto, redacta/aliasa `HumanMessage`, aplica
  política de tier y puede **rechazar** antes de que salga un solo byte.

**Única fricción real:** el CLI upstream no expone hook público para inyectar
middleware. `create_cli_agent()` no tiene parámetro `middleware=`; el CLI arma
su lista y llama `create_deep_agent(..., middleware=agent_middleware)`
internamente (`deepagents_cli/agent.py:1276`; añade `ConfigurableModelMiddleware`
en `:1101`). No hay entry-point/plugin ni sección en `config.toml`.

## Decision / Outcome (propuesta — pendiente de confirmar)

Migrar la seguridad de wrapper-de-modelo (`RouterChatModel`) a un
**`SecurityGuardrailMiddleware(AgentMiddleware)`** (`wrap_model_call` +
`awrap_model_call`) que: escanea/aliasa/redacta `HumanMessage`, lee el
proveedor destino resuelto, aplica la política de tier y cortocircuita cuando
corresponde. La lógica de scan/redact/alias **no se reescribe — se mueve**.

Inyección (orden de preferencia):
- **(A) Shim de arranque sin fork (recomendado ya):** entrypoint propio que
  monkeypatchea `create_deep_agent` para añadir siempre nuestro middleware,
  luego delega en el `main()` del CLI. ~30 líneas. Sobrevive a `/model`.
- **(B) Upstream un hook de plugin** (PR a deepagents-cli). Lo más limpio a
  largo plazo; no controlamos el merge → enviar (A) ahora, perseguir (B) luego.
- **(C) Mantener `RouterChatModel` además**, como defensa en profundidad para
  la ruta `deep-devops:router` — nunca como única capa.

Esto **enmienda `design.md §11`** (class_path deja de ser el único entry point;
pasa a ser defensa-en-profundidad), y afecta `§2` (diagrama: el Router pasa a
ser middleware del grafo, no un modelo), `§4.1` (la regla dura hard-attribute
se enforcer­a a nivel de grafo, válido para cualquier proveedor) y `§8`
(la máquina de estados de routing corre dentro del guardrail).

## Rationale

- Cap 10 p.451-455 "Step 2. Put in Guardrails": los guardrails de entrada/salida
  son una capa de la arquitectura del sistema, **no** una propiedad del modelo.
  Atarlos al objeto modelo es precisamente el anti-patrón que este hallazgo
  expone.
- `design.md §4.1`: "Internal and confidential data never leave the EU" se
  define como input guardrail. Si el guardrail solo existe para un proveedor,
  la regla no se cumple para los demás → el middleware la hace universal.
- Regla Dura #1/#8 + `design.md §1`: el único fallo que importa es fuga de datos
  internos a un proveedor no-EU. `/model openai:` es exactamente esa puerta
  abierta hoy.
- Consecuencia de política: OpenAI/Azure(US)/Gemini **no están en el modelo de
  3 tiers**. Para confidencial el guardrail debe **rechazar** ante proveedor
  fuera de whitelist (coherente con la semántica whitelist de §3.5), no
  "redactar y enviar".

## Follow-ups

- [ ] **Decisión pendiente:** ante proveedor fuera de la whitelist de tiers,
      ¿rechazar confidencial (recomendado) o redactar-y-permitir?
- [ ] **Decisión pendiente:** inyección vía (A) shim o (B) PR upstream.
- [ ] Tras decidir: enmendar `design.md §11/§2/§4.1/§8` y actualizar
      `reference-deepagents-setup` (el lanzamiento dejaría de ser solo
      `--model deep-devops:router`).
- [ ] La *enforcement* fail-closed de la NER (`session-2026-05-16-ner-edgecases.md`
      P0b) debe aterrizar aquí, no en `RouterChatModel`.
- [ ] Encaje en milestones: esto es **fundacional, transversal a M2** — define
      *dónde* corren todos los input guardrails de M2. No es un milestone nuevo;
      es un pre-requisito de que M2 signifique algo.

---

## Update 2026-05-16 — superseded (ver `session-2026-05-16-closeout.md`)

Este doc era una **propuesta**. El resultado divergió:

- La migración a middleware queda **aplazada, no descartada**. Se mantiene
  identificada y planificada para cuando Tier-2 (Nebius) esté cableado.
- La mitigación **hoy es por proceso**, no técnica: consigna a devs =
  lanzar con `--model deep-devops:router` y **no usar `/model`**.
- Riesgo residual aceptado conscientemente y reflejado en el `README.md`
  con sección dedicada y transparente.
- `design.md §11` queda anotado como **inválido frente a `/model`** (ver
  amendment).

Decisiones #2/#3 de este doc (políticas frente a proveedor fuera de
whitelist y NER ausente) se concretaron así en el closeout:

- **NER ausente** → fail-closed en `RouterChatModel._route()` (no middleware)
  vía `NerUnavailableError` → camino `scan_error` existente.
- **Proveedor fuera de whitelist** → ya no aplica como decisión separada
  mientras `/model` quede prohibido por consigna; cuando llegue el middleware,
  se decidirá ahí.
