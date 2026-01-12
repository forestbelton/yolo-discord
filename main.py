from dotenv import load_dotenv

load_dotenv()

import os
from yolo_discord.bot import Bot


def main():
    token = os.getenv("YOLO_BOT_TOKEN")
    if token is None:
        raise Exception("YOLO_BOT_TOKEN environment variable not set")
    finnhub_api_key = os.getenv('FINNHUB_API_KEY')
    if finnhub_api_key is None:
        raise Exception("FINNHUB_API_KEY environment variable not set")
    bot = Bot(finnhub_api_key)
    bot.run(token)


if __name__ == "__main__":
    main()
