import datetime
import os
import re
import time
from typing import Any, Callable
from urllib.parse import urlparse

import requests
import telebot
import yt_dlp
from telebot import types
from telebot.util import quick_markup
from yt_dlp.utils import DownloadError, ExtractorError

import config

os.makedirs(config.output_folder, exist_ok=True)

ses = requests.Session()
bot = telebot.TeleBot(config.token)
last_edited = {}


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

        return domain in config.allowed_domains
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
        except Exception as e:
            print(e)

    return progress


def _send_media(message, info: Any, audio: bool) -> None:
    """Send the downloaded file back to the user via Telegram."""
    downloads = info.get("requested_downloads") or []
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


def download_video(message, content, audio=False, format_id="mp4") -> None:
    match = re.search(r"https?://\S+", content)
    url = match.group(0) if match else content

    if not urlparse(url).scheme:
        bot.reply_to(message, "Invalid URL")
        return

    if not _validate_url(message, url):
        return

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
        "max_filesize": config.max_filesize,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}]
        if audio
        else [],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=msg.message_id,
                text="Sending file to Telegram...",
            )

            _send_media(message, info, audio)
            bot.delete_message(message.chat.id, msg.message_id)

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
            f"*{round(config.max_filesize / 1_000_000)}MB* and is supported by Telegram.",
            message.chat.id,
            msg.message_id,
            parse_mode="MARKDOWN",
        )

    finally:
        _cleanup(video_title)


def log(message, text: str, media: str):
    if config.logs:
        if message.chat.type == "private":
            chat_info = "Private chat"
        else:
            chat_info = f"Group: *{message.chat.title}* (`{message.chat.id}`)"

        bot.send_message(
            config.logs,
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
    text = get_text(message)
    if not text:
        bot.reply_to(message, "Invalid usage, use `/custom url`", parse_mode="MARKDOWN")
        return

    msg = bot.reply_to(message, "Getting formats...")

    with yt_dlp.YoutubeDL() as ydl:
        info = ydl.extract_info(text, download=False)

    formats = info.get("formats") or []

    data = {
        f"{x['resolution']}.{x['ext']}": {"callback_data": f"{x['format_id']}"}
        for x in formats
        if x["video_ext"] != "none"
    }

    markup = quick_markup(data, row_width=2)

    bot.delete_message(msg.chat.id, msg.message_id)
    bot.reply_to(message, "Choose a format", reply_markup=markup)


@bot.message_handler(commands=["id"])
def get_chat_id(message):
    bot.reply_to(message, message.chat.id)


@bot.callback_query_handler(func=lambda call: True)
def callback(call):
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
