from dotenv import load_dotenv

load_dotenv()

import os
from yolo_discord.bot import Bot


def main():
    token = os.getenv("YOLO_BOT_TOKEN")
    alphavantage_api_key = os.getenv('ALPHAVANTAGE_API_KEY')
    if token is None:
        raise Exception("YOLO_BOT_TOKEN environment variable not set")
    bot = Bot(alphavantage_api_key)
    bot.run(token)


if __name__ == "__main__":
    main()
