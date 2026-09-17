# Shared Python image for both API and worker containers.
# Compose overrides the default API command to start Celery in the worker container.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK's sentence-tokenizer data at build time, so it's baked into
# the image -- without this, chunking fails at runtime with a LookupError
# for 'punkt_tab', since a fresh container has no NLTK data on disk.
RUN python -c "import nltk; nltk.download('punkt_tab')"

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
