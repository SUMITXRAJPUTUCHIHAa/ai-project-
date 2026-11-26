FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Cloud Run injects $PORT; Postgres via DATABASE_URL (SQLite fallback is ephemeral on Cloud Run)
CMD exec gunicorn --bind :$PORT --workers 2 --threads 4 --timeout 60 app:app
