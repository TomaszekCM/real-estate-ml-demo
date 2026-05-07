# Real Estate ML Demo

## Quick Start

```bash
docker compose up -d
```

Open in your browser: http://localhost:8000/api/valuation/

That's it. The entire stack (Django, FastAPI ML service, PostgreSQL, Redis, Celery) starts automatically.

---

A demo real estate valuation application built with:
- Django (web backend + API)
- Celery + Redis (async task processing)
- PostgreSQL (database)
- FastAPI (dedicated ML service)
- Docker Compose (local orchestration)

## Architecture

The application consists of two backend services:

1. **Django** — `backend/`
   - Valuation form and API endpoints
   - Data persistence in PostgreSQL
   - Dispatching async tasks via Celery
   - HTTP communication with the ML service

2. **FastAPI** — `ml-service/`
   - `/health` and `/predict` endpoints
   - Loads model from `ml-service/models/regression_model.joblib`
   - Served by Uvicorn

Supporting services:
- **Redis** — Celery message broker and result backend
- **PostgreSQL** — primary database

## Project Structure

```
Real-estate-ml-demo/
├── backend/
│   ├── valuation_api/        # Django project config + Celery setup
│   ├── valuation/            # Domain app (models, views, tasks, forms)
│   │   ├── templates/
│   │   ├── static/
│   │   └── tests/
│   └── manage.py
├── ml-service/
│   ├── app/main.py           # FastAPI application
│   ├── models/               # Trained ML model (.joblib)
│   └── training/train.py     # Model training script
├── docker-compose.yml        # Full stack orchestration
├── requirements.txt          # Python dependencies for local development
└── TESTING.md                # Test scenarios and instructions
```

## Running the Application

### Option A — recommended: everything in Docker Compose

The simplest and most reliable option.

1. Start all services from the project root:

   ```bash
   docker compose up -d --build
   ```

2. Check status:

   ```bash
   docker compose ps
   ```

3. Open:
   - Valuation form: http://localhost:8000/api/valuation/
   - Django admin: http://localhost:8000/admin/
   - FastAPI ML service docs: http://localhost:8001/docs
   - ML service health: http://localhost:8001/health

No need to run `manage.py runserver` or `uvicorn` locally.

### Option B: Django locally + infrastructure in Docker

Useful when you want to debug Django with live reload outside of a container.

1. Start infrastructure and the ML service:

   ```bash
   docker compose up -d database redis ml-service celery_worker
   ```

2. Activate the virtual environment and install dependencies:

   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Apply migrations:

   ```bash
   cd backend
   python manage.py migrate
   ```

4. Start Django:

   ```bash
   python manage.py runserver
   ```

In this mode the FastAPI ML service runs in Docker and is accessible at http://localhost:8001.

## Troubleshooting

### Django cannot reach the FastAPI ML service

- Verify the ML service is running: http://localhost:8001/health
- In local dev mode, `local_settings.py` must set `ML_SERVICE_URL = 'http://localhost:8001'`

### Celery not processing tasks

```bash
docker compose logs -f celery_worker
```

### Database connection error

```bash
docker compose ps
docker compose logs -f database
```

## Tests

See [TESTING.md](TESTING.md) for full test instructions and scenarios.
