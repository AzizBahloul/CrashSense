# Dockerfile for CrashSense
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy application files
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
COPY kb/ ./kb/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create directory for configuration
RUN mkdir -p /root/.crashsense

# Expose ports for metrics and webhooks
EXPOSE 8000 9094

# Default command (can be overridden in deployment)
CMD ["python", "-m", "crashsense.cli", "k8s", "monitor", "--auto-heal"]
