# The telegram bot token
token: str = "123456789:ABcdefGhiJKlmnO"

# A list of user ids that are allowed to use the bot, if None everyone is allowed
whitelist: list[int] | None = None  # Example: [123456789, 987654321]

# A list of user ids that are not allowed to use the bot, if None everyone is allowed
blacklist: list[int] | None = None

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
# need it or change the runtime like {"node": {"path": "node"}}
js_runtime: dict[str, dict[str, str] | None] | None = {"bun": {"path": "bun"}}

# auto forward videos to this channel id when using the /forward command
forward_to: int | None = None
