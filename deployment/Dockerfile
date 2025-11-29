# Use Python 3.13 slim image
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

# Copy and make startup script executable
COPY deployment/start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Create necessary directories
RUN mkdir -p output

# Expose ports: 8080 for Streamlit (main), 8081 for Flask API
EXPOSE 8080 8081


# Set environment variables for Streamlit (Cloud Run + Firebase Hosting proxy compatible)
ENV STREAMLIT_SERVER_PORT=8080
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_SERVER_ENABLECORS=false
ENV STREAMLIT_SERVER_ENABLEXSRFPROTECTION=false
ENV STREAMLIT_SERVER_ENABLE_WEBSOCKET_COMPRESSION=false

# Health check for Streamlit (main service)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:8080/_stcore/health || exit 1

# Run both Streamlit and Flask via startup script
CMD ["/app/start.sh"]
