FROM node:current-slim AS node

FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Node (current release) for solving YouTube JS challenges
COPY --from=node /usr/local/bin/node /usr/local/bin/node

WORKDIR /app

ENV DATA_DIR="/app/data"

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

CMD ["python", "main.py"]
