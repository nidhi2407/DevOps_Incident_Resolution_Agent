FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set HuggingFace cache directory inside /app so downloaded models are saved in the image
ENV HF_HOME=/app/.cache/huggingface

# Copy project files
COPY . .

# Run runbook embedding to seed ChromaDB during container build
RUN python ingestion/embed_runbooks.py

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
