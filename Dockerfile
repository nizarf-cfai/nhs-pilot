FROM python:3.11-slim

WORKDIR /app

# Install dependencies (only essentials, no chromium/selenium)
RUN apt-get update && apt-get install -y \
    wget curl unzip gnupg ca-certificates \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# Start FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
