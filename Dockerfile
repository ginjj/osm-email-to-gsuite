# Dockerfile specifically for the Flask API service
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies and Poetry
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && ln -s /root/.local/bin/poetry /usr/local/bin/poetry

# Configure Poetry to not create virtual environments in container
ENV POETRY_VIRTUALENVS_CREATE=false

# Copy dependency files first for better caching
COPY pyproject.toml poetry.lock* ./

# Install Python dependencies (without dev dependencies and project package)
RUN poetry install --only main --no-root --no-interaction --no-ansi

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p output

# Expose Flask API port
EXPOSE 8080

# Set environment for cloud config
ENV USE_CLOUD_CONFIG=true

# Health check for API
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:8080/api/health || exit 1

# Run Flask API with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "300", "--access-logfile", "-", "--error-logfile", "-", "src.api:app"]
