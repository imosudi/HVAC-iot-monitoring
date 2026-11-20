FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
COPY wheels/ /tmp/wheels/
RUN (pip install --no-cache-dir --no-index --find-links=/tmp/wheels -r requirements.txt \
    || pip install --no-cache-dir -r requirements.txt) \
    && rm -rf /tmp/wheels

COPY schemas/ /app/schemas/
COPY src/ /app/src/

ENTRYPOINT ["python3", "-m", "src.main"]
