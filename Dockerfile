FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl unzip && \
    rm -rf /var/lib/apt/lists/*

# yt-dlp only supports bun up to 1.3.14 for solving YouTube JS challenges
RUN curl -fsSL https://bun.sh/install | bash -s "bun-v1.3.14"
ENV PATH="/root/.bun/bin:$PATH"

WORKDIR /app

ENV DATA_DIR="/app/data"

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

CMD ["python", "main.py"]
