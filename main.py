from urllib.parse import urlparse
import datetime
import telebot
import config
import yt_dlp
import re
import os
import requests
import urllib.parse

bot = telebot.TeleBot(config.token)
ses = requests.Session()
last_edited = {}


def youtube_url_validation(url):
    youtube_regex = (
        r'(https?://)?(www\.)?'
        '(youtube|youtu|youtube-nocookie)\.(com|be)/'
        '(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')

    youtube_regex_match = re.match(youtube_regex, url)
    if youtube_regex_match:
        return youtube_regex_match

    return youtube_regex_match


@bot.message_handler(commands=['start', 'help'])
def test(message):
    bot.reply_to(
        message, "*Send me a video link* and I'll download it for you, works with *YouTube*, *Twitter*, *TikTok*, *Reddit* and more.\n\n_Powered by_ [yt-dlp](https://github.com/yt-dlp/yt-dlp/)", parse_mode="MARKDOWN", disable_web_page_preview=True)


def download_video(message, url, audio=False):
    url_info = urlparse(url)
    if url_info.scheme:
        if url_info.netloc in ['www.youtube.com', 'youtu.be', 'youtube.com', 'youtu.be']:
            if not youtube_url_validation(url):
                bot.reply_to(message, 'Invalid URL')
                return

        def progress(d):

            if d['status'] == 'downloading':
                try:
                    update = False

                    if last_edited.get(f"{message.chat.id}-{msg.message_id}"):
                        if (datetime.datetime.now() - last_edited[f"{message.chat.id}-{msg.message_id}"]).total_seconds() >= 5:
                            update = True
                    else:
                        update = True

                    if update:
                        perc = round(d['downloaded_bytes'] *
                                     100 / d['total_bytes'])
                        bot.edit_message_text(
                            chat_id=message.chat.id, message_id=msg.message_id, text=f"Downloading {d['info_dict']['title']}\n\n{perc}%")
                        last_edited[f"{message.chat.id}-{msg.message_id}"] = datetime.datetime.now()
                except Exception as e:
                    print(e)

        msg = bot.reply_to(message, 'Downloading...')
        with yt_dlp.YoutubeDL({'format': 'mp4', 'outtmpl': 'outputs/%(title)s.%(ext)s', 'progress_hooks': [progress], 'postprocessors': [{  # Extract audio using ffmpeg
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        }] if audio else []}) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
                bot.edit_message_text(
                    chat_id=message.chat.id, message_id=msg.message_id, text='Sending file to Telegram...')
                try:
                    if audio:
                        bot.send_audio(message.chat.id, open(
                            info['requested_downloads'][0]['filepath'], 'rb'), reply_to_message_id=message.message_id)

                    else:
                        bot.send_video(message.chat.id, open(
                            info['requested_downloads'][0]['filepath'], 'rb'), reply_to_message_id=message.message_id)
                    bot.delete_message(message.chat.id, msg.message_id)
                except Exception as e:
                    print(e)
                    bot.edit_message_text(
                        chat_id=message.chat.id, message_id=msg.message_id, text="Couldn't send file")

                for file in info['requested_downloads']:
                    os.remove(file['filepath'])
            except Exception as e:
                if isinstance(e, yt_dlp.utils.DownloadError):
                    bot.edit_message_text(
                        'Invalid URL', message.chat.id, msg.message_id)
                else:
                    bot.edit_message_text(
                        'There was an error downloading your video', message.chat.id, msg.message_id)
    else:
        bot.reply_to(message, 'Invalid URL')


def log(message, text: str, media: str):
    if config.logs:
        if message.chat.type == 'private':
            chat_info = "Private chat"
        else:
            chat_info = f"Group: *{message.chat.title}* (`{message.chat.id}`)"

        bot.send_message(
            config.logs, f"Download request (`{media}`) from @{message.from_user.username} (`{message.from_user.id}`)\n\n{chat_info}\n\n{text}", parse_mode="MARKDOWN")


def get_text(message):
    if len(message.text.split(' ')) < 2:
        if message.reply_to_message and message.reply_to_message.text:
            return message.reply_to_message.text

        else:
            return None
    else:
        return message.text.split(' ')[1]


@bot.message_handler(commands=['download'])
def download_command(message):
    text = get_text(message)
    if not text:
        bot.reply_to(
            message, 'Invalid usage, use `/download url`', parse_mode="MARKDOWN")
        return

    log(message, text, 'video')
    download_video(message, text)


@bot.message_handler(commands=['audio'])
def download_audio_command(message):
    text = get_text(message)
    if not text:
        bot.reply_to(
            message, 'Invalid usage, use `/audio url`', parse_mode="MARKDOWN")
        return

    log(message, text, 'audio')
    download_video(message, text, True)


@bot.message_handler(commands=['define', 'urban', 'definisci', 'dictionary', 'dizionario'])
def define(message):
    text = get_text(message)
    if not text:
        bot.reply_to(
            message, 'Invalid usage, use `/define word`', parse_mode="MARKDOWN")
        return
    res = ses.get(
        "https://api.urbandictionary.com/v0/define?term=" + urllib.parse.quote(text))
    data = res.json()
    if len(data['list']) > 0:
        bot.reply_to(message, data['list'][0]['definition'])
    else:
        bot.reply_to(message, "No results found")


shortcuts = {
    "smh": "shake my head",
    "dw": "don't worry",
    "hf": "have fun",
    "brb": "be right back",
    "g2g": "got to go",
    "smth": "something",
    "ty": "thank you",
    "yw": "you're welcome",
    "jk": "just kidding",
    "wp": "well played",
    "gl": "good luck",
    "imo": "in my opinion",
    "ngl": "not gonna lie",
    "ong": "on god",
    "obv": "obviously",
    "idk": "I don't know",
    "til": "today I learned",
    "tih": "thanks I hate",
    "tbf": "to be fair",
    "rn": "right now",
    "fr": "for real",
    "tbh": "to be honest",
    "yw": "you're welcome",
    "wbu": "what about you",
    "hmu": "hit me up",
    "istg": "I swear to god",
}


@bot.message_handler(func=lambda m: True, content_types=["text", "pinned_message", "photo", "audio", "video", "location", "contact", "voice", "document"])
def handle_private_messages(message):
    text = message.text if message.text else message.caption if message.caption else None

    if message.chat.type == 'private':
        log(message, text, 'video')
        download_video(message, text)
        return

    found = []
    words = text.split(' ') if text else []
    words = [w.lower() for w in words]

    for shortcut in shortcuts:
        if shortcut.lower() in words:
            found.append(shortcuts[shortcut])

    if len(found) > 0:
        bot.reply_to(message, " ".join(found))

    if text and 'furry' in text.lower():
        bot.send_sticker(message.chat.id, config.sticker_id,
                         reply_to_message_id=message.message_id)
    if text and 'whatsapp' in text.lower():
        bot.send_video(message.chat.id, 'BAACAgQAAx0CW_bolQACd8ljEeYX0Ub3EQphxa2xmV6HUcDoOAACzA0AAnCIkFCE3KhF14BM7SkE',
                       reply_to_message_id=message.message_id)
    if message.chat.type == 'private':
        download_video(message, text)


bot.infinity_polling()
