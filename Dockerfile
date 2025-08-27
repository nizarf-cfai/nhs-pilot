FROM python:3.11-slim

WORKDIR /app

# Install only essentials (no heavy GUI libs needed for FastAPI)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    wget curl unzip gnupg ca-certificates \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# Expose port 8080 for Cloud Run
EXPOSE 8080

# Start FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
