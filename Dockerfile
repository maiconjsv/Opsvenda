FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY models ./models
COPY routes ./routes
COPY services ./services
COPY templates ./templates
COPY static ./static
COPY migrations ./migrations
COPY app.py .
COPY config.py .
COPY extensions.py .
COPY scoping.py .
COPY cli.py .
COPY VERSION .
COPY wsgi.py .
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

RUN useradd --create-home appuser
RUN mkdir -p instance && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD curl -f http://localhost:5000/health || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
