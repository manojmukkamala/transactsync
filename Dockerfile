FROM python:3.12.9-slim

# Metadata for GitHub Container Registry (GHCR)
LABEL org.opencontainers.image.source="https://github.com/${GITHUB_REPOSITORY}"
LABEL org.opencontainers.image.description="AI-powered Python app to log financial transactions by parsing email alerts. Privacy-focused, supports multiple email folders, and database checkpointing."
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.title="transactsync"
LABEL org.opencontainers.image.authors="Manoj <your-email@example.com>"

# Install system dependencies and uv
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --upgrade pip && pip install uv

# Set working directory
WORKDIR /workspace

# Copy only dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Install Python dependencies
RUN uv pip install -r pyproject.toml --system

# Copy only necessary source and config files
COPY src/ ./src/

# Set entrypoint (use exec form for proper signal handling)
CMD ["uv", "run", "src/main.py"]