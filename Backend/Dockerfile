# Shared Python image for both API and worker containers.
# Compose overrides the default API command to start Celery in the worker container.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NLTK_DATA=/usr/local/share/nltk_data

WORKDIR /app

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

RUN python -c "import nltk; nltk.download('punkt_tab', download_dir='/usr/local/share/nltk_data')" \
    && groupadd -g 1000 spc \
    && useradd -u 1000 -g 1000 -m -s /bin/sh spc \
    && mkdir -p /app/storage/notes/personal /app/storage/notes/groups /app/storage/evidence/reports \
    && chmod 750 /app/storage/notes /app/storage/notes/personal /app/storage/notes/groups \
    && chmod 700 /app/storage/evidence /app/storage/evidence/reports \
    && chown -R 1000:1000 /app/storage

COPY --chown=1000:1000 app ./app

USER 1000:1000