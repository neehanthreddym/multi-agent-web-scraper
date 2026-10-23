FROM docker.io/library/python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
# This image is for local development, including user-run tests.
RUN python -m pip install --no-cache-dir -r requirements-dev.txt
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
COPY tests ./tests

USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
