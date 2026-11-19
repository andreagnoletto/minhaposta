FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Os estáticos entram na imagem com nome versionado. A chave abaixo só vale
# para este comando; a de produção vem do ambiente, em tempo de execução.
RUN DJANGO_DEBUG=False DJANGO_SECRET_KEY=so-para-o-collectstatic \
    python manage.py collectstatic --noinput

# O banco SQLite fica em /data, que deve ser um volume persistente.
RUN useradd --uid 10001 --no-create-home app \
    && mkdir /data \
    && chown app:app /data
USER app

# A imagem é feita para rodar atrás de um proxy que termina o TLS.
ENV DJANGO_DEBUG=False \
    DJANGO_DB_PATH=/data/db.sqlite3 \
    DJANGO_TRUST_PROXY_HEADERS=True \
    WEB_CONCURRENCY=3

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"]

# gunicorn lê o número de workers de WEB_CONCURRENCY.
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --access-logfile -"]
