# Document Copilot Backend

## Setup

From `backend/`, install the locked dependencies and create `.env` from the example:

```powershell
uv sync
Copy-Item .env.example .env
```

Fill in every required value in `.env` before starting the app.

## Run

Start from the terminal:

```powershell
uv run uvicorn app.main:app --reload
```

Alternatively, run `app/main.py` using your IDE's Run button. The API is available at:

- Health check: <http://127.0.0.1:8000/health>
- API documentation: <http://127.0.0.1:8000/docs>

Stop the server with `Ctrl+C` or your IDE's Stop button.

## Maintain

```powershell
uv add <package>       # Add a dependency
uv run ruff check app # Lint the application
uv run pytest         # Run tests
```

Run backend commands from `backend/`. If another virtual environment is active, run `deactivate` first and let `uv` use `backend/.venv`.
