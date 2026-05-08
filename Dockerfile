FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libcairo2-dev \
    pkg-config \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY .env.example .env

# Create necessary directories
RUN mkdir -p image_cache logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV USE_PRO_SCRAPER=true

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from src.health_monitor import HealthMonitor; hm = HealthMonitor(); print('OK')" || exit 1

# Default command
CMD ["python", "src/automation.py"]
