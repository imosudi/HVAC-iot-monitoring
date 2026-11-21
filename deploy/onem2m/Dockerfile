FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python -m pip install --no-cache-dir --disable-pip-version-check "acmecse>=2025.0"

WORKDIR /data
EXPOSE 8080

CMD ["acmecse", "-dir", "/data", "--headless"]

