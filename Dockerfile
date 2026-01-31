# Backend API - FastAPI + MongoDB
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY backend_server.py .
COPY seed_admin.py .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["python", "backend_server.py"]
