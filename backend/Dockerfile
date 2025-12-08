FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=backend.app \
    FLASK_RUN_HOST=0.0.0.0 \
    FLASK_RUN_PORT=5000

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend /app/backend

EXPOSE 5000
CMD ["flask", "run"]
