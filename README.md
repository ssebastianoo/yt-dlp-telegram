# YT-DLP Telegram Bot
Telegram bot that allows you to download videos from YouTube, Twitter, Reddit and many other socials using [yt-dlp](https://github.com/yt-dlp/yt-dlp) 

[Use the Bot](https://t.me/SatoruBot)

## Usage
In the bot private chat just send the video url, otherwise use `/download <url>`

## Self hosting
```bash
git clone https://github.com/ssebastianoo/yt-dlp-telegram
cd yt-dlp-telegram
pip install -r requirements.txt
```
create a `config.py` file and set the `token` variable to your bot token (check `example.config.py`)
```py
python3 main.py
```

**The Telegram API limits files sent by bots to 50mb**

**https://core.telegram.org/bots/faq#how-do-i-upload-a-large-file**
