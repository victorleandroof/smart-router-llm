FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.yaml .
COPY app/ ./app/

EXPOSE 4000

CMD ["litellm", "--config", "config.yaml", "--port", "4000", "--num_workers", "4"]