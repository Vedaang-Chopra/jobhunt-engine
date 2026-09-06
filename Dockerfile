FROM python:3.9-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY ui ./ui
COPY setup ./setup
COPY scripts ./scripts
RUN pip install --no-cache-dir .

ENV JOBHUNT_HOME=/data \
    PYTHONUNBUFFERED=1

VOLUME /data
EXPOSE 8080

CMD ["python", "-m", "ui.app"]
