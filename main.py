import base64
import datetime
import hashlib
import os
import re
import sqlite3
import time
from typing import Any, Callable
from urllib.parse import urlparse

import requests
import telebot
import yt_dlp
from cryptography.fernet import Fernet
from telebot import types
from telebot.util import quick_markup
from yt_dlp.utils import DownloadCancelled, DownloadError, ExtractorError

import config

whitelist = getattr(config, "whitelist", None)
blacklist = getattr(config, "blacklist", None)
logs = getattr(config, "logs", None)
js_runtime = getattr(config, "js_runtime", None)
max_filesize = getattr(config, "max_filesize", 50000000)
allowed_domains = getattr(config, "allowed_domains", [])

os.makedirs(config.output_folder, exist_ok=True)

key = hashlib.sha256(config.secret_key.encode()).digest()
cipher = Fernet(base64.urlsafe_b64encode(key))

script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(script_dir, "db.db")
db_conn = sqlite3.connect(db_path, check_same_thread=False)
db_cursor = db_conn.cursor()
db_cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_cookies (
        user_id INTEGER PRIMARY KEY,
        cookie_data TEXT NOT NULL
    )
""")
db_conn.commit()

ses = requests.Session()
bot = telebot.TeleBot(config.token)
last_edited = {}


def encrypt_cookie(cookie_data: str) -> str:
    """Encrypt cookie data using the secret key."""
    return cipher.encrypt(cookie_data.encode()).decode()


def decrypt_cookie(encrypted_data: str) -> str:
    """Decrypt cookie data using the secret key."""
    return cipher.decrypt(encrypted_data.encode()).decode()


def youtube_url_validation(url):
    youtube_regex = (
        r"(https?://)?(www\.|m\.)?"
        r"(youtube|youtu|youtube-nocookie)\.(com|be)/"
        r"(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})"
    )

    youtube_regex_match = re.match(youtube_regex, url)
    if youtube_regex_match:
        return youtube_regex_match

    return youtube_regex_match


def is_allowed_domain(url):
    """
    Check if URL belongs to allowed domains: YouTube, TikTok, Instagram, Twitter/X, Bluesky
    """

    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()

        # Remove port if present
        if ":" in domain:
            domain = domain.split(":")[0]

        return domain in allowed_domains
    except (ValueError, AttributeError):
        return False


@bot.message_handler(commands=["start", "help"])
def test(message):
    bot.reply_to(
        message,
        "*Send me a video link* and I'll download it for you, works with *YouTube*, *TikTok*, *Instagram*, *Twitter* and *Bluesky*.\n\n_Powered by_ [yt-dlp](https://github.com/yt-dlp/yt-dlp/)",
        parse_mode="MARKDOWN",
        disable_web_page_preview=True,
    )


def _validate_url(message, url: str) -> bool:
    """Validate URL domain and YouTube-specific rules. Returns False and replies if invalid."""
    if not is_allowed_domain(url):
        bot.reply_to(
            message,
            "Invalid URL. Only YouTube, TikTok, Instagram, Twitter and Bluesky links are supported.",
        )
        return False

    if urlparse(url).netloc in {
        "www.youtube.com",
        "youtube.com",
        "youtu.be",
        "m.youtube.com",
        "youtube-nocookie.com",
    }:
        if not youtube_url_validation(url):
            bot.reply_to(message, "Invalid URL")
            return False

    return True


def _make_progress_hook(message, msg) -> Callable:
    """Return a yt-dlp progress hook that throttles Telegram edits to once per 5s."""

    def progress(d):
        if d["status"] != "downloading":
            return
        try:
            last = last_edited.get(f"{message.chat.id}-{msg.message_id}")
            if last and (datetime.datetime.now() - last).total_seconds() < 5:
                return

            downloaded_bytes = d.get("downloaded_bytes", 0)
            if downloaded_bytes > max_filesize:
                raise DownloadCancelled("File too large")

            perc = round(d["downloaded_bytes"] * 100 / d["total_bytes"])
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=msg.message_id,
                text=(
                    f"Downloading {d['info_dict']['title']}\n\n{perc}%\n\n"
                    f"<i>Want to stay updated? @SatoruStatus</i>"
                ),
                parse_mode="HTML",
            )
            last_edited[f"{message.chat.id}-{msg.message_id}"] = datetime.datetime.now()
        except DownloadCancelled:
            raise
        except Exception as e:
            print(e)

    return progress


class MissingInfoError(Exception):
    pass


def _send_media(message, info: Any, audio: bool) -> None:
    """Send the downloaded file back to the user via Telegram."""

    downloads = info.get("requested_downloads") or None

    if not downloads:
        if info.get("entries") is not None and len(info.get("entries")) > 0:
            downloads = info.get("entries")[0].get("requested_downloads") or None

    if not downloads or len(downloads) == 0:
        raise MissingInfoError("No requested downloads found")

    filepath = downloads[0]["filepath"]

    with open(filepath, "rb") as f:
        if audio:
            bot.send_audio(message.chat.id, f, reply_to_message_id=message.message_id)
        else:
            bot.send_video(
                message.chat.id,
                f,
                reply_to_message_id=message.message_id,
                width=downloads[0]["width"],
                height=downloads[0]["height"],
            )


def _cleanup(video_title: int) -> None:
    """Remove all files in the output folder that belong to this download."""
    for file in os.listdir(config.output_folder):
        if file.startswith(str(video_title)):
            os.remove(os.path.join(config.output_folder, file))


def check_url(content: str, message) -> dict:
    match = re.search(r"https?://\S+", content)
    url = match.group(0) if match else content

    if not urlparse(url).scheme:
        bot.reply_to(message, "Invalid URL")
        return {"success": False}

    if not _validate_url(message, url):
        return {"success": False}

    return {"success": True, "url": url}


def download_video(message, content, audio=False, format_id="mp4") -> None:

    forbidden = False
    if whitelist is not None and message.from_user.id not in whitelist:
        forbidden = True

    if blacklist is not None and message.from_user.id in blacklist:
        forbidden = True

    if forbidden:
        bot.reply_to(message, "You are not allowed to use this bot")
        return

    check = check_url(content, message)
    if not check["success"]:
        return

    url = check["url"]

    msg = bot.reply_to(
        message,
        "Downloading...\n\n<i>Want to stay updated? @SatoruStatus</i>",
        parse_mode="HTML",
    )
    video_title = round(time.time() * 1000)

    ydl_opts: yt_dlp._Params = {
        "format": format_id,
        "outtmpl": f"{config.output_folder}/{video_title}.%(ext)s",
        "progress_hooks": [_make_progress_hook(message, msg)],
        "max_filesize": max_filesize,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}]
        if audio
        else [],
    }

    if js_runtime is not None:
        ydl_opts["js_runtimes"] = js_runtime
        ydl_opts["remote_components"] = {"ejs:github"}

    cookie_file = None
    try:
        user_id = message.from_user.id
        db_cursor.execute(
            "SELECT cookie_data FROM user_cookies WHERE user_id = ?", (user_id,)
        )
        result = db_cursor.fetchone()

        if result:
            decrypted_data = decrypt_cookie(result[0])
            cookie_file = f"{config.output_folder}/cookies_{user_id}.txt"
            with open(cookie_file, "w") as f:
                f.write(decrypted_data)
            ydl_opts["cookiefile"] = cookie_file

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=msg.message_id,
                text="Sending file to Telegram...",
            )

            _send_media(message, info, audio)
            bot.delete_message(message.chat.id, msg.message_id)
    except MissingInfoError:
        bot.edit_message_text(
            "Couldn't find a way to download this video, you can report it here: @SatoruSupport",
            message.chat.id,
            msg.message_id,
        )
    except (DownloadError, ExtractorError) as e:
        err = str(e).lower()
        text: str

        if "[youtube]" in err and "sign in" in err:
            text = "We're sorry, YouTube is ratelimiting third party downloaders right now, try again later."
        elif "login required" in err or "rate-limit reached" in err:
            text = "Content not available (Rate limit or login required)."
        else:
            text = "There was an error downloading the video, please try again later."

        bot.edit_message_text(text, message.chat.id, msg.message_id)
    except Exception:
        bot.edit_message_text(
            f"Couldn't send file — make sure it doesn't exceed "
            f"*{round(max_filesize / 1_000_000)}MB* and is supported by Telegram.",
            message.chat.id,
            msg.message_id,
            parse_mode="MARKDOWN",
        )

    finally:
        if cookie_file and os.path.exists(cookie_file):
            os.remove(cookie_file)
        _cleanup(video_title)


def log(message, text: str, media: str):
    if logs:
        if message.chat.type == "private":
            chat_info = "Private chat"
        else:
            chat_info = f"Group: *{message.chat.title}* (`{message.chat.id}`)"

        bot.send_message(
            logs,
            f"Download request ({media}) from @{message.from_user.username} ({message.from_user.id})\n\n{chat_info}\n\n{text}",
        )


def get_text(message):
    if len(message.text.split(" ")) < 2:
        if message.reply_to_message and message.reply_to_message.text:
            return message.reply_to_message.text
        else:
            return None
    else:
        return message.text.split(" ")[1]


@bot.message_handler(commands=["download"])
def download_command(message):
    text = get_text(message)
    if not text:
        bot.reply_to(
            message, "Invalid usage, use `/download url`", parse_mode="MARKDOWN"
        )
        return

    log(message, text, "video")
    download_video(message, text)


@bot.message_handler(commands=["audio"])
def download_audio_command(message):
    text = get_text(message)
    if not text:
        bot.reply_to(message, "Invalid usage, use `/audio url`", parse_mode="MARKDOWN")
        return

    log(message, text, "audio")
    download_video(message, text, True)


@bot.message_handler(commands=["custom"])
def custom(message):
    text = message.text if message.text else message.caption

    check = check_url(text, message)
    if not check["success"]:
        return

    url = check["url"]

    msg = bot.reply_to(message, "Getting formats...")

    with yt_dlp.YoutubeDL() as ydl:
        info = ydl.extract_info(url, download=False)

    formats = info.get("formats") or []

    data = {
        f"{x['resolution']}.{x['ext']}": {"callback_data": f"{x['format_id']}"}
        for x in formats
        if x["video_ext"] != "none"
    }

    markup = quick_markup(data, row_width=2)

    bot.delete_message(msg.chat.id, msg.message_id)
    bot.reply_to(message, "Choose a format", reply_markup=markup)


def filter_cookies_by_domain(cookie_data: str) -> str:
    lines = cookie_data.split("\n")
    filtered_lines = []

    for line in lines:
        if line.startswith("#") or not line.strip():
            filtered_lines.append(line)
            continue

        parts = line.split("\t")
        if len(parts) < 7:
            continue

        domain = parts[0].lstrip(".")

        is_allowed = False
        for allowed_domain in allowed_domains:
            if domain == allowed_domain or domain.endswith("." + allowed_domain):
                is_allowed = True
                break

        if is_allowed:
            filtered_lines.append(line)

    return "\n".join(filtered_lines)


@bot.message_handler(commands=["id"])
def get_chat_id(message):
    bot.reply_to(message, message.chat.id)


def is_cookie_command(message):
    text = message.text or message.caption or ""
    return text.startswith("/cookie") or text.startswith("/cookies")


@bot.message_handler(func=is_cookie_command, content_types=["document", "text"])
def handle_cookie(message):
    user_id = message.from_user.id

    if not message.document:
        db_cursor.execute(
            "SELECT cookie_data FROM user_cookies WHERE user_id = ?", (user_id,)
        )
        result = db_cursor.fetchone()

        if result:
            cookie_file = f"{config.output_folder}/cookies_{user_id}_temp.txt"
            try:
                decrypted_data = decrypt_cookie(result[0])
                with open(cookie_file, "w") as f:
                    f.write(decrypted_data)

                markup = types.InlineKeyboardMarkup()
                delete_btn = types.InlineKeyboardButton(
                    "🗑 Delete", callback_data="delete_cookies"
                )
                markup.add(delete_btn)

                with open(cookie_file, "rb") as f:
                    bot.send_document(
                        message.chat.id,
                        f,
                        reply_to_message_id=message.message_id,
                        visible_file_name="cookies.txt",
                        reply_markup=markup,
                    )
            finally:
                if os.path.exists(cookie_file):
                    os.remove(cookie_file)
        else:
            bot.reply_to(
                message,
                "No cookies stored. Send a file with this command to store cookies.",
            )
        return

    file_info = bot.get_file(message.document.file_id)
    if not file_info.file_path:
        bot.reply_to(message, "Failed to get file information.")
        return

    downloaded_file = bot.download_file(file_info.file_path)
    cookie_data = downloaded_file.decode("utf-8")

    filtered_cookie_data = filter_cookies_by_domain(cookie_data)

    encrypted_data = encrypt_cookie(filtered_cookie_data)

    db_cursor.execute(
        "INSERT OR REPLACE INTO user_cookies (user_id, cookie_data) VALUES (?, ?)",
        (user_id, encrypted_data),
    )
    db_conn.commit()
    bot.reply_to(message, "Cookies saved successfully!")


@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data == "delete_cookies":
        user_id = call.from_user.id
        db_cursor.execute("DELETE FROM user_cookies WHERE user_id = ?", (user_id,))
        db_conn.commit()

        bot.edit_message_caption(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            caption="Cookies deleted successfully!",
            reply_markup=None,
        )
        bot.answer_callback_query(call.id, "Cookies deleted!")
    elif call.message.reply_to_message:
        if call.from_user.id == call.message.reply_to_message.from_user.id:
            url = get_text(call.message.reply_to_message)
            bot.delete_message(call.message.chat.id, call.message.message_id)
            download_video(
                call.message.reply_to_message, url, format_id=f"{call.data}+bestaudio"
            )
        else:
            bot.answer_callback_query(call.id, "You didn't send the request")


@bot.message_handler(
    func=lambda m: True,
    content_types=[
        "text",
        "photo",
        "audio",
        "video",
        "document",
    ],
)
def handle_private_messages(message: types.Message):
    text = (
        message.text if message.text else message.caption if message.caption else None
    )

    if message.chat.type == "private":
        log(message, text or "<no text>", "video")
        download_video(message, text)
        return


print(f"ready as @{bot.user.username}")
bot.infinity_polling()
