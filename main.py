import os
from yolo_discord.bot import Bot


def main():
    token = os.getenv("YOLO_BOT_TOKEN")
    if token is None:
        raise Exception("YOLO_BOT_TOKEN environment variable not set")
    bot = Bot()
    bot.run(token)


if __name__ == "__main__":
    main()
