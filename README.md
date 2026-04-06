# YT-DLP Telegram Bot

A Telegram bot that downloads media on Telegram using [yt-dlp](https://github.com/yt-dlp/yt-dlp), with support for:

- YouTube
- TikTok
- Instagram
- Twitter / X
- Bluesky

> Public bot: [@SatoruBot](https://t.me/SatoruBot)

**Need more help?** Join the [support group](https://t.me/satorubotsupport) or the [status](https://t.me/satorustatus) channel

<a href="https://www.star-history.com/?repos=ssebastianoo%2Fyt-dlp-telegram&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=ssebastianoo/yt-dlp-telegram&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=ssebastianoo/yt-dlp-telegram&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=ssebastianoo/yt-dlp-telegram&type=date&legend=top-left" />
 </picture>
</a>

## Table of Contents

- [Features](#features)
- [Commands](#commands)
- [Requirements](#requirements)
  - [Local run](#local-run)
  - [Docker run](#docker-run)
- [Quick Start (Local)](#quick-start-local)
- [Configuration Reference](#configuration-reference)
- [Docker Tutorial](#docker-tutorial)
  - [1) Prepare config](#1-prepare-config)
  - [2) Build and start container](#2-build-and-start-container)
  - [3) Check logs](#3-check-logs)
  - [4) Stop / restart / update](#4-stop--restart--update)
  - [5) Troubleshooting Docker setup](#5-troubleshooting-docker-setup)
- [Usage Notes](#usage-notes)
- [Telegram File Size Limit](#telegram-file-size-limit)
- [Cookies Support](#cookies-support)
- [License](#license)

---

## Features

- Download video with `/download <url>`
- Download audio (MP3 extract) with `/audio <url>`
- Choose custom format with `/custom <url>`
- Cookie support for authentication
- Optional logging to a Telegram chat/channel
- Domain allowlist for safer URL handling
- Docker support with `docker-compose`

---

## Commands

- `/start` or `/help` - Show usage help
- `/download <url>` - Download video
- `/audio <url>` - Download and extract MP3
- `/custom <url>` - Show available formats and pick one
- `/cookies` - Attach a cookies txt file to be used when downloading videos
- `/id` - Return current chat ID (useful for `logs` config)

In private chat, you can also just send a URL directly.

---

## Requirements

### Local run

- Python 3.11+
- `ffmpeg` installed on your system
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

### Docker run

- Docker
- Docker Compose plugin (`docker compose`)

---

## Quick Start (Local)

1. Clone the repo:
   ```bash
   git clone https://github.com/ssebastianoo/yt-dlp-telegram
   cd yt-dlp-telegram
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create `config.py` from the example:
   ```bash
   cp example.config.py config.py
   ```

4. Edit `config.py` (at minimum set `token`).

5. Start the bot:
   ```bash
   python3 main.py
   ```

If everything is correct, you should see output similar to:
`ready as @your_bot_username`

---

## Configuration Reference

Create a `config.py` file in the project root. `config.py` example:
```python
# The telegram bot token
token: str = "123456789:ABcdefGhiJKlmnO"

# The logs channel id, if none set to None
logs: int | None = None

# The maximum file size in bytes
max_filesize: int = 50000000

# The output folder for downloaded files, it gets cleared after each download
output_folder: str = "/tmp/satoru"

# The allowed domains for downloading videos
allowed_domains: list[str] = [
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "m.youtube.com",
    "youtube-nocookie.com",
    "tiktok.com",
    "www.tiktok.com",
    "vm.tiktok.com",
    "vt.tiktok.com",
    "instagram.com",
    "www.instagram.com",
    "twitter.com",
    "www.twitter.com",
    "x.com",
    "www.x.com",
    "bsky.app",
    "www.bsky.app",
]

# secret key used to encrypt/decrypt stores cookies
secret_key: str = "your-secret-key"

# this is used to solve youtube challenges, you can set it to None if you don't
# need it or change the runtime like {"bun": {"path": "bun"}}
js_runtime: dict[str, dict[str, str] | None] | None = {"node": {"path": "node"}}
```

---

## Docker Tutorial

This project includes:

- `Dockerfile` (Python + ffmpeg + app)
- `docker-compose.yml` (single `bot` service)

### 1) Prepare config

From project root:

```bash
cp example.config.py config.py
```

Edit `config.py` and set at least:

- `token`
- optionally `logs`, `max_filesize`, etc.

---

### 2) Build and start container

```bash
docker compose up -d --build
```

This will:

- build the image
- mount your local `config.py` into container as read-only:
  - `./config.py:/app/config.py:ro`
- start bot with restart policy `unless-stopped`

---

### 3) Check logs

```bash
docker compose logs -f bot
```

Look for:
`ready as @your_bot_username`

---

### 4) Stop / restart / update

Stop:
```bash
docker compose down
```

Restart:
```bash
docker compose restart bot
```

Rebuild after code changes:
```bash
docker compose up -d --build
```

---

### 5) Troubleshooting Docker setup

- **Bot not starting**
  - Verify `config.py` exists in project root.
  - Verify `token` is valid.
  - Check logs: `docker compose logs -f bot`.

- **No logs sent to `logs` chat**
  - Ensure bot is in that chat/channel.
  - Ensure `logs` is correct numeric chat ID.
  - Ensure bot has permission to send messages.

- **Downloads fail due to size**
  - Reduce quality / choose smaller format via `/custom`.
  - Lower `max_filesize` to fail fast and avoid long downloads.
  - Telegram limits still apply.

---

## Usage Notes

- In private chats, paste a link directly.
- In groups, use commands like `/download <url>`.
- `/custom` can list many formats depending on source media.
- Audio mode uses FFmpeg post-processing to extract MP3.

---

## Telegram File Size Limit

Bots are limited by Telegram upload constraints.  
Reference: https://core.telegram.org/bots/faq#how-do-i-upload-a-large-file

Set `max_filesize` according to what you want the bot to attempt and what Telegram will accept in your use case.

---

## Cookies Support

Some websites may require authentication to download content, this can be set by passing a `cookies.txt` file to the `/cookie` command.
YouTube requires a js challenge to be solved to download videos using cookies, this needs `js_runtime` to be set in `config.py`, for example if you use **Node** you can set:
```py
js_runtime: dict[str, dict[str, str] | None] | None = {"node": {"path": "node"}}

# Or if you use Bun
js_runtime: dict[str, dict[str, str] | None] | None = {"bun": {"path": "bun"}}
```
Cookies are stored in `db.db` (using Sqlite3) and encrypted with a `secret_key` that can be set in the config file.

### Where can I find cookies.txt
You need to export it from your browser using an extension like [this one](https://github.com/kairi003/Get-cookies.txt-LOCALLY?tab=readme-ov-file#from-webstore)

---

## License

This project is licensed under the repository’s `LICENSE` file.
