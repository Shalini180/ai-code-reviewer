FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    gcc \
    g++ \
    make \
    curl \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Install Ruff (standalone binary)
RUN curl -LsSf https://astral.sh/ruff/install.sh | sh
ENV PATH="/root/.cargo/bin:${PATH}"

# Install Semgrep
RUN pip install --no-cache-dir semgrep

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p data/repos data/artifacts

# Set Python path
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Default command (overridden in docker-compose)
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]