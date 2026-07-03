---
name: backend-startup
description: Setup y arranque del backend FastAPI con SQLite
---
1. Verificar que `backend/.env` existe con `SECRET_KEY`.
2. Activar venv: `source backend/venv/bin/activate` (o crear con `python3 -m venv backend/venv`).
3. Instalar deps: `pip install -r requirements.txt` (solo si cambió `requirements.txt`).
4. Arrancar: `uvicorn app.main:app --reload` desde `backend/`.
