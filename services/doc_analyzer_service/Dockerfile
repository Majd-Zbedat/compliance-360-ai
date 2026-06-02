FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY services/doc_analyzer_service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY services/doc_analyzer_service /app/services/doc_analyzer_service

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8002/healthz')"

CMD ["python", "-m", "uvicorn", "services.doc_analyzer_service.app.main:app", "--host", "0.0.0.0", "--port", "8002"]
