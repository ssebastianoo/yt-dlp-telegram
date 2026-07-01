## Overview

A single-file Telegram bot (`main.py`) that uses yt-dlp to download media from YouTube, TikTok, Instagram, Twitter/X, and Bluesky. All application logic lives in one file around 590 lines.

## Key Commands

- **Run bot**: `python3 main.py`
- **Install deps**: `pip install -r requirements.txt`
- **Run with Docker**: `docker compose up -d --build`
- **View Docker logs**: `docker compose logs -f bot`
- **Config setup**: `cp example.config.py config.py` (edit `token` at minimum)

## Dependencies

- `yt-dlp` — video/audio downloading
- `pyTelegramBotAPI` — Telegram bot framework (polling-based, not webhook)
- `cryptography` — Fernet encryption for stored cookies
- `requests` — HTTP session
- System dependency: `ffmpeg` (for audio extraction)

## Architecture

### Single-file structure (`main.py`)

- **Config** — imported from `config.py` as a plain Python module with typed variables
- **Database** — SQLite3 at `db.db`, single table `user_cookies` for encrypted cookie storage per user
- **Command handlers** (pyTelegramBotAPI):
  - `/start`, `/help` — help text
  - `/download <url>` — download video
  - `/audio <url>` — download MP3 extract
  - `/custom <url>` — list available formats via inline keyboard
  - `/cookies` — upload/store/delete cookies.txt (encrypted via Fernet)
  - `/id` — return current chat ID
  - Direct URL in private chat — auto-download via catch-all handler
- **Download flow**: validate URL → check whitelist/blacklist → reply with progress message → yt-dlp download with progress hook → send media file to Telegram → cleanup temp files
- **Retry logic**: up to `max_retries` (default 3) on transient errors (rate limits, 5xx, timeouts, connection resets) with `retry_delay` seconds between attempts
- **Domain validation**: URL domain checked against `allowed_domains` list; YouTube URLs additionally validated with regex for video ID format
- **Logging**: optional Telegram chat/channel for download request logging

### File layout

- `main.py` — bot logic
- `config.py` — runtime configuration (gitignored)
- `example.config.py` — documented config template
- `db.db` — SQLite3 database (gitignored)
- `Dockerfile` — Python 3.11-slim + ffmpeg + bun
- `docker-compose.yml` — mounts `config.py` as read-only volume

### Bot framework details

Uses `telebot.TeleBot` with `bot.infinity_polling()` — not a webhook server. All message handlers are synchronous. The `infinity_polling()` call at the end of `main.py` blocks forever.

### Cookie system

- Users upload a Netscape-format `cookies.txt` via `/cookies`
- Cookies are filtered by allowed domains, then encrypted with Fernet (key derived from `secret_key` via SHA-256) and stored in SQLite
- On download, cookies are decrypted to a temp file and cleaned up in `finally`
- YouTube cookies require `js_runtime` config for JS challenge solving

### Error handling patterns

- `DownloadCancelled` raised inside progress hook when file exceeds `max_filesize` (mid-download check)
- `MissingInfoError` when yt-dlp returns no requested downloads
- Transient errors trigger retry; permanent errors show user-friendly messages
- Outer `finally` always cleans up cookie temp files and downloaded media
