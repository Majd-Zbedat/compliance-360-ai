FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    RAG_SERVICE_URL=http://rag-service:8001

COPY services/langgraph_agent_service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY services/langgraph_agent_service /app/services/langgraph_agent_service

EXPOSE 8004

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8004/healthz')"

CMD ["python", "-m", "uvicorn", "services.langgraph_agent_service.app.main:app", "--host", "0.0.0.0", "--port", "8004"]
