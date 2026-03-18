FROM python:3.11-slim

WORKDIR /app

# Minimal runtime settings for container logs and filesystem behavior.
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install Python dependencies first for better layer caching.
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy Sprint 1 service code.
COPY api ./api
COPY agents ./agents
COPY config ./config

EXPOSE 8000

# FastAPI app entrypoint.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
