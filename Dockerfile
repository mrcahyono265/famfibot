FROM python:3.14-slim

WORKDIR /app

COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
