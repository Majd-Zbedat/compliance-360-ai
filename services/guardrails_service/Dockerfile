FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY services/guardrails_service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY services/guardrails_service /app/services/guardrails_service

EXPOSE 8003

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8003/healthz')"

CMD ["python", "-m", "uvicorn", "services.guardrails_service.app.main:app", "--host", "0.0.0.0", "--port", "8003"]
