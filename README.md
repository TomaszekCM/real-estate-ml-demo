# 🏠 Real Estate ML Demo

Demo backend application for real estate valuation using Django and Machine Learning.

The goal of this project is to demonstrate:

- Clean backend architecture
- REST API design
- Basic ML-based property valuation
- Containerization (Docker)
- Orchestration (Kubernetes)
- Async processing (Celery + Redis)
- Scalability & resilience concepts

This is a technical showcase project.

---

## 🚀 Project Vision

The application allows a user to:

- Submit property details (location, size, rooms, etc.)
- Receive an estimated property valuation
- (Future) Train/update valuation model
- (Future) Run async predictions via Celery
- (Future) Demonstrate Kubernetes auto-scaling & self-healing

---

## 🧠 Machine Learning Approach

The valuation model will be based on:

- Supervised learning (regression)
- Synthetic or sample dataset (initially)
- Feature-based prediction (e.g. area, rooms, city, etc.)

The ML model is initially embedded inside the Django app.
In later stages it may be separated into a dedicated service.

---

## 🏗 Architecture (Target)

Planned architecture:

- Django (API layer)
- PostgreSQL (database)
- Redis (cache / broker)
- Celery (async tasks)
- Docker (containerization)
- Kubernetes (orchestration & scaling)

Initial phase focuses on application logic.
Infrastructure will be added incrementally.

---

## 📂 Project Structure

Real-estate-ml-demo/
│
├── backend/
│ ├── valuation_api/ # Django project
│ ├── valuation/ # Core domain app
│ └── manage.py
│
└── README.md


---

## ⚙️ Local Development Setup

### 1️⃣ Create virtual environment

```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows


