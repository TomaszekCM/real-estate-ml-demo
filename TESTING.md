# 🧪 Testing Guide

This document describes testing procedures for the Real Estate ML Demo application.

---

## 📋 Test Categories

- **Unit Tests** - Django TestCase for individual components
- **Integration Tests** - Full stack testing with PostgreSQL + Redis + Celery
- **ML Service Tests** - FastAPI microservice testing with pytest
- **Manual Tests** - Interactive browser/API testing scenarios

---

## 🤖 Automated Tests

### Running All Tests

```bash
cd backend
python manage.py test valuation
```

### Test Coverage

The automated test suite covers all critical components:

- **Infrastructure Tests** - Redis cache operations, PostgreSQL connectivity, integrated health checks
- **Celery Integration Tests** - Task registration, imports, and synchronous execution validation  
- **API Endpoint Tests** - HTTP endpoints for task submission with full execution verification
- **Async Behavior Tests** - Task timing, execution flow, and result validation

All tests include both **unit-level** verification (imports, configurations) and **integration-level** verification (actual task execution with result validation).

**Run `python manage.py test valuation --verbosity=2` to see detailed test descriptions.**

---

## 🤖 ML Service Tests

### Running ML Service Tests

The ML service has its own isolated test suite using pytest and FastAPI TestClient:

```bash
# Run tests in Docker container (recommended)
docker exec ml_service pytest test_main.py -v

# Run tests with coverage report
docker exec ml_service pytest test_main.py --cov=app --cov-report=term-missing

# Run specific test class
docker exec ml_service pytest test_main.py::TestPredictEndpoint -v
```

### ML Test Coverage

The ML service test suite covers:

- **Health Endpoint Tests** - Service status, model loading verification
- **Prediction Endpoint Tests** - Input validation, ML model predictions  
- **Error Handling Tests** - Invalid inputs, missing model scenarios
- **API Documentation Tests** - OpenAPI schema, authentication warnings

**Key Test Categories:**
- ✅ **Input Validation**: Negative area, zero rooms, missing fields, too many rooms
- ✅ **Model Integration**: Real predictions with different cities/districts
- ✅ **Error Scenarios**: Model not loaded (503), validation errors (422)
- ✅ **API Structure**: Correct response format, required fields

### ML Service Test Structure

```
ml-service/
├── app/main.py          # FastAPI application code
├── test_main.py         # Complete pytest test suite  
├── pyproject.toml       # Pytest configuration (modern Python standard)
└── requirements.txt     # Dependencies including pytest + httpx
```

**Configuration File (`pyproject.toml`):**
- Modern Python project configuration standard (PEP 518)
- Centralizes tool configurations (pytest, coverage, linting)
- Replaces older `pytest.ini` and `setup.cfg` files
- Defines test discovery patterns and execution options

### Test Isolation

ML Service tests are completely **isolated** from Django backend:
- **Separate dependencies**: Own `requirements.txt` with pytest/httpx
- **Separate execution**: `docker exec ml_service pytest` vs Django `python manage.py test`  
- **Independent container**: Uses FastAPI TestClient, no HTTP server required
- **Own configuration**: `pyproject.toml` for pytest settings

---

## 🔍 Manual Testing Scenarios

### Scenario 1: Async Task Execution

**Purpose:** Verify that Celery tasks execute asynchronously without blocking Django requests

**Prerequisites:**
- Docker services running: `docker-compose up -d`
- Django migrations applied: `python manage.py migrate`

**Steps:**

1. **Open Real-Time Logs**
   ```bash
   docker-compose logs -f --tail=15 celery_worker
   ```
   This allows live monitoring of Celery worker activity.

2. **Test Worker Blocking Behavior**
   - Open 2 browser tabs
   - Navigate both to: `http://localhost:8000/api/manual-sleep-task/`
   - **Expected Result:** First tab loads after 10 seconds, second tab after another 10 seconds
   - **This demonstrates:** Single worker processes tasks sequentially

3. **Test Non-Blocking Django Responses**  
   - In browser, navigate multiple times to: `http://localhost:8000/api/manual-test-task/`
   - This triggers multiple 20-second async tasks
   - **Immediately** navigate to: `http://localhost:8000/api/health/`
   - **Expected Result:** Health endpoint responds instantly (not blocked by long-running tasks)
   - **In logs:** You should see Celery workers processing the long tasks in background

4. **Verify Async Execution**
   - Monitor the logs from step 1
   - **Expected Log Pattern:**
     ```
     Starting debug_sleep task [task-id] for 20 seconds
     Completed debug_sleep task [task-id] after 20.0 seconds  
     ```
   - **Timing:** Health endpoint responds in milliseconds while 20-second tasks run in background

**Success Criteria:**
- ✅ Django web requests are never blocked by long Celery tasks
- ✅ Multiple tasks can be queued and executed by available workers  
- ✅ Real-time logs show task start/completion with accurate timing
- ✅ Health check always responds immediately regardless of background load

---

### Scenario 2: API Task Execution

**Purpose:** Test programmatic task execution via REST API

**Steps:**

1. **Get Available Tasks**
   ```bash
   curl http://localhost:8000/api/test-task/
   ```

2. **Execute Simple Task**
   ```bash
   curl -X POST http://localhost:8000/api/test-task/ \
        -H "Content-Type: application/json" \
        -d '{"task": "hello_world"}'
   ```

3. **Execute Parameterized Task**  
   ```bash
   curl -X POST http://localhost:8000/api/test-task/ \
        -H "Content-Type: application/json" \
        -d '{"task": "add_numbers", "x": 15, "y": 25}'
   ```

4. **Execute Long-Running Task**
   ```bash
   curl -X POST http://localhost:8000/api/test-task/ \
        -H "Content-Type: application/json" \
        -d '{"task": "debug_sleep", "duration": 5}'
   ```

**Expected Response Format:**
```json
{
  "status": "task_started",
  "task_name": "debug_sleep", 
  "task_id": "abc123-def456-...",
  "params": {"duration": 5},
  "message": "Long-running task started (sleep 5s)",
  "note": "This task will not block other requests"
}
```

---

## 🐳 Docker Development Workflow

### Start Services
```bash
docker-compose up -d database redis celery_worker
```

### Monitor Services
```bash
# Real-time Celery logs
docker-compose logs -f celery_worker

# PostgreSQL connection
docker exec real_estate_db psql -U postgres -d real_estate_db -c "\dt"

# Redis connection  
docker exec real_estate_redis redis-cli ping
```

### Rebuild After Code Changes
```bash
# Celery worker auto-reloads via watchmedo
# No rebuild needed for task changes

# For Dockerfile changes:
docker-compose build celery_worker
docker-compose up -d celery_worker
```

---

## 🚨 Troubleshooting

### Common Issues

**Issue:** `relation "django_session" does not exist`  
**Solution:** Run migrations: `python manage.py migrate`

**Issue:** Celery tasks not found  
**Solution:** Check worker logs: `docker-compose logs celery_worker`

**Issue:** Redis connection refused  
**Solution:** Ensure Redis container is running: `docker-compose up -d redis`

**Issue:** PostgreSQL connection error  
**Solution:** Verify database container: `docker-compose up -d database`

### Debug Commands

```bash
# Check registered Celery tasks
docker exec real_estate_celery_worker celery -A valuation_api inspect registered

# Test task execution in container
docker exec real_estate_celery_worker python -c "
from valuation.tasks import hello_world
result = hello_world.delay()
print(f'Task ID: {result.id}')
"

# Verify Django settings  
python manage.py shell -c "from django.conf import settings; print(settings.DATABASES)"
```

---

## 📊 Performance Expectations

**Response Times:**
- Health endpoint: `< 50ms`  
- Task submission: `< 100ms`
- Simple tasks (hello_world): `~1s`
- Debug sleep tasks: `duration + ~10ms overhead`

**Concurrency:**
- Default Celery workers: `4 (concurrency=4)`
- Parallel task execution: ✅ Supported
- Non-blocking Django: ✅ Verified

---

*For questions about testing, check the logs first, then review this documentation.*