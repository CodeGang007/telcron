# ADR-001 — React frontend, FastAPI backend

Date: 2026-11-15 · Status: accepted

The user chose React and FastAPI on 2026-11-15, replacing a TypeScript start. The backend is Python 3.13 with FastAPI, async SQLAlchemy and Alembic; the frontend is React with Vite and builds to static files. The sibling projects this repository borrows its working conventions from are TypeScript; only the conventions are borrowed, not the stack.
