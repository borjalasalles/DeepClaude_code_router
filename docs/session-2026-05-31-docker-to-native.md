---
date: 2026-05-31
status: accepted
topic: Docker descartado para el agente — setup.sh como distribución nativa
refs:
  - design.md §2
  - design.md §6.3
---

# Docker descartado para el agente CLI

## Decision

Docker no es viable como mecanismo de distribución del agente de código. `setup.sh` es el reemplazo. Docker queda reservado para Langfuse/Postgres (M3).

## Rationale

El agente necesita acceso directo al filesystem del desarrollador — edita ficheros del proyecto activo, que cambia cada sesión. Un contenedor sin mount del directorio actual no puede hacer eso; con mount, el contenedor es efímero y la ventaja de Docker desaparece.

`design.md §6.3` ya lo decía: *"The application process runs on the user's machine; the provider only handles model inference."* Claude Code funciona igual: binario nativo, `~/.claude/` para memoria, CWD como workspace.

## Outcome

- Rama `dev` anterior (Docker) eliminada y recreada desde `main`.
- Portado a `dev`: `setup.sh` (install nativo), `deepagents_config.example.toml` (template config), comandos actualizados en `CLAUDE.md`.
- `main` intacta.

## Follow-ups

- Validar `setup.sh` en máquina limpia antes de mergear `dev` → `main` (M5).
- Docker para Langfuse: `docker compose up` en M3, independiente del agente CLI.
