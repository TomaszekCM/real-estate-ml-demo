FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV DJANGO_SETTINGS_MODULE=valuation_api.settings

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        gcc \
        python3-dev \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend project  
COPY backend/ /app/

# Make entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# Create user to run Django (security best practice)
RUN groupadd -r django && useradd -r -g django django

# Change ownership of the app directory
RUN chown -R django:django /app

# Switch to non-root user
USER django

# Expose port
EXPOSE 8000

# Default Gunicorn configuration via environment variables
ENV GUNICORN_WORKERS=3
ENV GUNICORN_BIND=0.0.0.0:8000
ENV GUNICORN_MODULE=valuation_api.wsgi:application

# Use entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]