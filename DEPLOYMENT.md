# Deployment Guide — EventForge

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Environment Variables](#environment-variables)
4. [Vercel Configuration](#vercel-configuration)
5. [Build & Start Commands](#build--start-commands)
6. [Database Considerations for Serverless](#database-considerations-for-serverless)
7. [Seed Data](#seed-data)
8. [CI/CD Notes](#cicd-notes)
9. [Troubleshooting](#troubleshooting)

---

## Overview

EventForge is a Python 3.11+ FastAPI application. This guide covers deploying to **Vercel** as the primary target, with notes for other platforms (Docker, Railway, Render).

---

## Prerequisites

- Python 3.11 or higher
- A Vercel account with the Vercel CLI installed (`npm i -g vercel`)
- Git repository connected to Vercel
- (Optional) A managed PostgreSQL database (Vercel Postgres, Supabase, Neon, or Railway)

---

## Environment Variables

Set the following environment variables in your Vercel project dashboard under **Settings → Environment Variables**:

| Variable | Required | Description | Example |
|---|---|---|---|
| `SECRET_KEY` | ✅ | Secret key for JWT signing and session security. Use a long random string. | `openssl rand -hex 32` |
| `DATABASE_URL` | ✅ | Database connection string. See [Database Considerations](#database-considerations-for-serverless). | `postgresql+asyncpg://user:pass@host:5432/eventforge` |
| `ENVIRONMENT` | ❌ | Deployment environment identifier. | `production` |
| `DEBUG` | ❌ | Enable debug mode. **Must be `false` in production.** | `false` |
| `ALLOWED_ORIGINS` | ❌ | Comma-separated list of allowed CORS origins. | `https://eventforge.vercel.app` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ❌ | JWT access token lifetime in minutes. Default: `30`. | `60` |
| `LOG_LEVEL` | ❌ | Python logging level. | `INFO` |

### Generating a Secret Key

```bash
# Option 1: OpenSSL
openssl rand -hex 32

# Option 2: Python
python -c "import secrets; print(secrets.token_hex(32))"
```

> **Security Note:** Never commit secrets to version control. Always use environment variables or a secrets manager.

---

## Vercel Configuration

Create a `vercel.json` file in the project root:

```json
{
  "version": 2,
  "builds": [
    {
      "src": "app/main.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "app/main.py"
    }
  ],
  "env": {
    "ENVIRONMENT": "production",
    "DEBUG": "false"
  }
}
```

### Key Points

- **`@vercel/python`** runtime handles the FastAPI ASGI application.
- All routes are forwarded to `app/main.py`, which exposes the FastAPI `app` instance.
- Vercel expects the ASGI app object to be named `app` in the entry-point module.
- Static files and templates are bundled automatically as long as they are within the project directory.

### Vercel Project Settings

In the Vercel dashboard:

- **Framework Preset:** Other
- **Build Command:** `pip install -r requirements.txt`
- **Output Directory:** (leave empty)
- **Install Command:** `pip install -r requirements.txt`

---

## Build & Start Commands

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production (non-Vercel)

```bash
# Install production dependencies
pip install -r requirements.txt

# Run with uvicorn (production settings)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --log-level info
```

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

```bash
docker build -t eventforge .
docker run -p 8000:8000 --env-file .env eventforge
```

---

## Database Considerations for Serverless

### SQLite Limitations on Vercel

**SQLite is NOT recommended for Vercel deployments.** Vercel serverless functions run in ephemeral, read-only file systems. This means:

- **No persistent writes:** Any data written to SQLite is lost when the function instance is recycled (typically within seconds to minutes).
- **No shared state:** Each function invocation may run on a different instance, so concurrent requests cannot share an SQLite database file.
- **Read-only filesystem:** Vercel's `/var/task` directory is read-only. SQLite requires write access for WAL mode, journal files, and the database itself.

### Recommended: Managed PostgreSQL

For production deployments on Vercel, use a managed PostgreSQL database:

| Provider | Connection String Format | Notes |
|---|---|---|
| **Vercel Postgres** | `postgresql+asyncpg://...` | Native integration, auto-configured env vars |
| **Neon** | `postgresql+asyncpg://user:pass@ep-xxx.us-east-2.aws.neon.tech/dbname?sslmode=require` | Serverless-friendly, scales to zero |
| **Supabase** | `postgresql+asyncpg://postgres:pass@db.xxx.supabase.co:5432/postgres` | Generous free tier |
| **Railway** | `postgresql+asyncpg://postgres:pass@xxx.railway.app:5432/railway` | Simple setup |

### Switching from SQLite to PostgreSQL

1. Update `DATABASE_URL` in your environment variables:
   ```
   DATABASE_URL=postgresql+asyncpg://user:password@host:5432/eventforge
   ```

2. Ensure `asyncpg` is in `requirements.txt`:
   ```
   asyncpg>=0.29.0
   ```

3. Run database migrations or create tables on first startup (the app's lifespan handler creates tables automatically via `Base.metadata.create_all`).

### SQLite for Local Development Only

SQLite is acceptable for local development and testing:

```
DATABASE_URL=sqlite+aiosqlite:///./eventforge.db
```

Ensure `aiosqlite` is in `requirements.txt` for async SQLite support.

---

## Seed Data

### Running the Seed Script

If a seed script is provided:

```bash
# Set environment variables
export DATABASE_URL="sqlite+aiosqlite:///./eventforge.db"
export SECRET_KEY="dev-secret-key"

# Run the seed script
python -m app.seed
```

### Manual Seeding via API

After deployment, you can seed initial data through the API:

1. **Create an admin user** via the registration endpoint (if available) or directly in the database.
2. **Create initial resources** (events, categories, etc.) via authenticated API calls.

### Database Table Creation

Tables are created automatically on application startup via the lifespan handler. No manual migration step is required for initial deployment. For subsequent schema changes in production, consider using Alembic:

```bash
# Initialize Alembic (one-time)
alembic init alembic

# Generate a migration
alembic revision --autogenerate -m "description of change"

# Apply migrations
alembic upgrade head
```

---

## CI/CD Notes

### Vercel Auto-Deployments

When your Git repository is connected to Vercel:

- **Production deploys** trigger on pushes to the `main` branch.
- **Preview deploys** trigger on pull requests to `main`.
- Each preview deploy gets a unique URL for testing.

### GitHub Actions (Optional)

Add a `.github/workflows/ci.yml` for running tests before deployment:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run tests
        env:
          SECRET_KEY: "test-secret-key-for-ci"
          DATABASE_URL: "sqlite+aiosqlite:///./test.db"
          ENVIRONMENT: "testing"
        run: pytest tests/ -v --tb=short

      - name: Run linting
        run: |
          pip install ruff
          ruff check app/
```

### Pre-Deployment Checklist

- [ ] All tests pass locally (`pytest tests/ -v`)
- [ ] `SECRET_KEY` is set to a unique, random value in production
- [ ] `DEBUG` is set to `false` in production
- [ ] `DATABASE_URL` points to a managed PostgreSQL instance (not SQLite)
- [ ] `ALLOWED_ORIGINS` is configured with your actual domain(s)
- [ ] No secrets are committed to the repository
- [ ] `requirements.txt` is up to date (`pip freeze > requirements.txt` or manually maintained)

---

## Troubleshooting

### Common Issues

#### 1. `ModuleNotFoundError: No module named 'app'`

**Cause:** The Python path is not configured correctly for the Vercel runtime.

**Fix:** Ensure `vercel.json` points to `app/main.py` and that the `app` directory contains an `__init__.py` file.

#### 2. `sqlalchemy.exc.OperationalError: unable to open database file`

**Cause:** SQLite cannot write to the read-only Vercel filesystem.

**Fix:** Switch to a managed PostgreSQL database. See [Database Considerations](#database-considerations-for-serverless).

#### 3. `422 Unprocessable Entity` on all POST requests

**Cause:** Missing `python-multipart` dependency (required for `Form()` data parsing in FastAPI).

**Fix:** Ensure `python-multipart` is in `requirements.txt`:
```
python-multipart>=0.0.6
```

#### 4. `ImportError: email-validator is not installed`

**Cause:** A Pydantic schema uses `EmailStr` but `email-validator` is not installed.

**Fix:** Add to `requirements.txt`:
```
email-validator>=2.1.0
```

#### 5. `MissingGreenlet: greenlet_spawn has not been called`

**Cause:** SQLAlchemy lazy loading triggered outside an async context (common in Jinja2 templates accessing relationships).

**Fix:** Use `selectinload()` in all queries that fetch objects whose relationships are accessed in templates or serialization:
```python
from sqlalchemy.orm import selectinload

result = await db.execute(
    select(Event).options(selectinload(Event.attendees))
)
```

#### 6. `RuntimeError: no running event loop` or ASGI errors on Vercel

**Cause:** Vercel's Python runtime expects a specific ASGI app export.

**Fix:** Ensure `app/main.py` exports the FastAPI instance as `app`:
```python
app = FastAPI(...)
```

#### 7. CORS errors in the browser

**Cause:** `ALLOWED_ORIGINS` is not configured or does not include the frontend domain.

**Fix:** Set the `ALLOWED_ORIGINS` environment variable to include your Vercel deployment URL:
```
ALLOWED_ORIGINS=https://your-app.vercel.app,https://your-custom-domain.com
```

#### 8. Cold start timeouts

**Cause:** Vercel serverless functions have a default timeout of 10 seconds (Hobby) or 60 seconds (Pro).

**Fix:**
- Minimize startup imports and initialization logic.
- Use connection pooling for database connections.
- Consider upgrading to Vercel Pro for longer timeouts.
- Pre-warm the function with a health check endpoint (`GET /health`).

#### 9. `pydantic_core._pydantic_core.ValidationError: extra fields not permitted`

**Cause:** Vercel injects extra environment variables that Pydantic `BaseSettings` rejects.

**Fix:** Ensure your settings class includes `extra="ignore"`:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

#### 10. Static files / templates not found

**Cause:** Relative paths break when the working directory differs from the project root (common on Vercel).

**Fix:** Always use absolute paths resolved from `__file__`:
```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
```

---

## Support

For issues specific to:
- **FastAPI:** [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)
- **Vercel Python Runtime:** [https://vercel.com/docs/functions/runtimes/python](https://vercel.com/docs/functions/runtimes/python)
- **SQLAlchemy Async:** [https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)