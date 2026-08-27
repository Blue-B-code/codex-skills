---
name: flownote
description: Projet FlowNote (Y-Note) : backend FastAPI async (uv/pytest/ruff/mypy, arq+RAG, Alembic doublé) + frontend-admin React/Vite (vitest/tsc/lint, i18n obligatoire). À utiliser pour tout travail sur /home/y-note/flownote : valider du code, appliquer les conventions (TDD, i18n), diagnostiquer la stack.
---

# FlowNote

## Repo / stack
- `/home/y-note/flownote` ; backend `backend/` (FastAPI async, SQLAlchemy, arq+Redis, Alembic, pgvector), frontend `frontend-admin/` (React/Vite/Mantine, vitest).
- Migrations Alembic **doublées** : `alembic.ini` (→ `flownote_dev`) et `alembic_rag.ini` (→ `rag_dev`).
- Blueprint de référence : `/home/y-note/YNote_AI_Factory/AI_Software_Factory_YNote.md`.

## Validation
- **Backend** (depuis `backend/`) : `uv run pytest -q`, `uv run ruff check .`, `uv run mypy src`. (`uv` absent de l'hôte → venv `uv` ou conteneur de dev `docker compose -f docker-compose.dev.yml`.)
- **Frontend** (depuis `frontend-admin/`) : `npx tsc --noEmit`, `npm run test`, `npm run lint -- --quiet`, `npm run check:jsx-collisions`.
- **TDD** : écrire le test, le voir échouer, puis implémenter.

## Conventions (source : `CLAUDE.md`)
- **i18n obligatoire** : aucun texte visible en dur dans le JSX ; passer par `useTranslation()`/`t()` et ajouter la clé dans `frontend-admin/public/locales/{fr,en}/translation.json`.
- **Fixtures** : `backend/tests/conftest.py` (`db_session`, `rag_db_session`, `client`, `admin_token`, `seeded_admin`).
- **Alembic** : au déploiement, appliquer **les deux** `alembic upgrade head` (`alembic.ini` + `alembic_rag.ini`), jamais seulement flownote_dev.
- **RAG** : `rag_client_documents` (pgvector 1536) ; ingestion HMAC `POST /api/v1/rag/ingest`, lecture JWT `POST /api/v1/rag/read`.
- Ne pas dupliquer de fonctions inline anonymes sur une même clé de prop (collision Istanbul/Vitest).

## Reporting
- Si issu d'un ticket Redmine → suivre le skill **ticket-driver** pour le reporting recette.
