from urllib.parse import urlparse
import datetime
import telebot
import config
import yt_dlp
import re
import os

bot = telebot.TeleBot(config.token)

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


def download_video(message, url):
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
        with yt_dlp.YoutubeDL({'format': 'mp4', 'outtmpl': 'outputs/%(title)s.%(ext)s', 'progress_hooks': [progress], }) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
                bot.edit_message_text(
                    chat_id=message.chat.id, message_id=msg.message_id, text='Sending file to Telegram...')
                try:
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

@bot.message_handler(commands=['download'])
def download_command(message):
    text = ''
    if len(message.text.split(' ')) < 2:
        if message.reply_to_message and message.reply_to_message.text:
            text = message.reply_to_message.text

        else:
            bot.reply_to(message, 'Invalid usage, use `/download url`', parse_mode="MARKDOWN")
            return
    else:
        text = message.text.split(' ')[1]
    download_video(message, text)

@bot.message_handler(func=lambda m: True, content_types=["text", "pinned_message", "photo", "audio", "video", "location", "contact", "voice", "document"])
def handle_private_messages(message):
    text = message.text if message.text else message.caption if message.caption else None

    if text and ('furry' in text.lower()):
        bot.send_sticker(message.chat.id, config.sticker_id, reply_to_message_id=message.message_id)

    if message.chat.type == 'private':
        download_video(message, text)

bot.infinity_polling()
