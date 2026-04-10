# EventForge

A modern event management platform built with Python 3.11+ and FastAPI.

## Features

- **Event Management** — Create, update, and manage events with full CRUD operations
- **User Authentication** — Secure JWT-based authentication with role-based access control
- **Async Architecture** — Built on async SQLAlchemy with aiosqlite for non-blocking I/O
- **RESTful API** — Clean, well-documented API endpoints with automatic OpenAPI/Swagger docs
- **Data Validation** — Pydantic v2 schemas for request/response validation
- **Background Tasks** — FastAPI BackgroundTasks for fire-and-forget operations
- **CORS Support** — Configurable cross-origin resource sharing

## Tech Stack

- **Runtime:** Python 3.11+
- **Framework:** FastAPI
- **ORM:** SQLAlchemy 2.0 (async)
- **Database:** SQLite (aiosqlite) / PostgreSQL (asyncpg)
- **Auth:** JWT via python-jose, password hashing via bcrypt
- **Validation:** Pydantic v2
- **Server:** Uvicorn (ASGI)
- **Testing:** pytest + pytest-asyncio + httpx

## Folder Structure

```
eventforge/
├── app/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py          # Pydantic Settings configuration
│   │   ├── database.py        # Async SQLAlchemy engine & session
│   │   └── security.py        # JWT token & password utilities
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py            # User model
│   │   └── event.py           # Event model
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py            # User request/response schemas
│   │   └── event.py           # Event request/response schemas
│   ├── services/
│   │   ├── __init__.py
│   │   ├── user.py            # User business logic
│   │   └── event.py           # Event business logic
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py            # Authentication routes
│   │   ├── users.py           # User management routes
│   │   └── events.py          # Event management routes
│   ├── dependencies/
│   │   ├── __init__.py
│   │   └── auth.py            # Auth dependency injection
│   ├── templates/             # Jinja2 templates (if applicable)
│   └── main.py                # FastAPI application entry point
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # Shared fixtures
│   ├── test_auth.py           # Auth endpoint tests
│   ├── test_users.py          # User endpoint tests
│   └── test_events.py         # Event endpoint tests
├── .env                       # Environment variables (not committed)
├── .env.example               # Example environment variables
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## Prerequisites

- Python 3.11 or higher
- pip (Python package manager)

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-url>
cd eventforge
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example environment file and update values:

```bash
cp .env.example .env
```

Edit `.env` with your configuration (see [Environment Variables](#environment-variables) below).

### 5. Run Database Migrations

The database tables are created automatically on application startup via the lifespan handler. No manual migration step is required for development.

For production, consider using Alembic:

```bash
pip install alembic
alembic init alembic
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

### 6. Run the Application

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.

### 7. Access API Documentation

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Environment Variables

| Variable | Description | Default | Required |
|---|---|---|---|
| `DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///./eventforge.db` | No |
| `SECRET_KEY` | JWT signing secret key | — | **Yes** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT token expiration in minutes | `30` | No |
| `ALGORITHM` | JWT signing algorithm | `HS256` | No |
| `CORS_ORIGINS` | Comma-separated allowed origins | `http://localhost:3000` | No |
| `DEBUG` | Enable debug mode | `false` | No |

Example `.env` file:

```env
DATABASE_URL=sqlite+aiosqlite:///./eventforge.db
SECRET_KEY=your-super-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30
ALGORITHM=HS256
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
DEBUG=true
```

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/register` | Register a new user |
| `POST` | `/api/auth/login` | Login and receive JWT token |
| `GET` | `/api/auth/me` | Get current authenticated user |

### Users

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/users` | List all users (admin) |
| `GET` | `/api/users/{id}` | Get user by ID |
| `PUT` | `/api/users/{id}` | Update user |
| `DELETE` | `/api/users/{id}` | Delete user (admin) |

### Events

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/events` | List all events (with filters) |
| `POST` | `/api/events` | Create a new event |
| `GET` | `/api/events/{id}` | Get event by ID |
| `PUT` | `/api/events/{id}` | Update an event |
| `DELETE` | `/api/events/{id}` | Delete an event |

### Health

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check endpoint |

## Testing

### Run All Tests

```bash
pytest
```

### Run Tests with Verbose Output

```bash
pytest -v
```

### Run Tests with Coverage

```bash
pip install pytest-cov
pytest --cov=app --cov-report=term-missing
```

### Run a Specific Test File

```bash
pytest tests/test_auth.py -v
```

### Run a Specific Test

```bash
pytest tests/test_auth.py::test_register_creates_new_user -v
```

## Deployment

### Vercel

1. Install the Vercel CLI:

```bash
npm install -g vercel
```

2. Create a `vercel.json` in the project root:

```json
{
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
  ]
}
```

3. Set environment variables in the Vercel dashboard.

4. Deploy:

```bash
vercel --prod
```

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:

```bash
docker build -t eventforge .
docker run -p 8000:8000 --env-file .env eventforge
```

## Development

### Code Style

This project follows PEP 8 conventions. Use a linter to maintain consistency:

```bash
pip install ruff
ruff check app/
ruff format app/
```

### Adding New Models

1. Create the model in `app/models/`
2. Create schemas in `app/schemas/`
3. Create service layer in `app/services/`
4. Create router in `app/routers/`
5. Register the router in `app/main.py`
6. Update `__init__.py` files to re-export new symbols
7. Write tests in `tests/`

## License

Private — All rights reserved.