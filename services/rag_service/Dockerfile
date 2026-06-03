FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HF_HOME=/cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/cache/huggingface

COPY services/rag_service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir "torch==2.5.1" --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY services/rag_service /app/services/rag_service

RUN mkdir -p /app/data/chroma \
    && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); print('embedding model ok')"

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=15s --retries=8 --start-period=300s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/healthz')"

CMD ["python", "-m", "uvicorn", "services.rag_service.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
