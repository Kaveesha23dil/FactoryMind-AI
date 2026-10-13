FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8080
ENV FACTORYMIND_DB_PATH=/tmp/factorymind/incidents.db FACTORYMIND_VISUAL_STORAGE_DIR=/tmp/factorymind/images
WORKDIR /app
COPY services/api/requirements*.txt /app/services/api/
RUN pip install --no-cache-dir -r services/api/requirements-cloud.txt \
    && useradd --uid 10001 --create-home factorymind
COPY services /app/services
COPY datasets/telemetry/ai4i2020.csv /app/datasets/telemetry/ai4i2020.csv
USER 10001
EXPOSE 8080
CMD ["sh", "-c", "exec python -m uvicorn services.api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
