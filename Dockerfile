FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    DB_PATH=/var/lib/contextpath/popups.db

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

COPY src ./src

RUN useradd --system --uid 10001 --no-create-home app \
    && mkdir -p /var/lib/contextpath \
    && chown app /var/lib/contextpath
USER app
