import discord
from datetime import time
from discord.ext import commands, tasks
from logging import Logger, getLogger
from yolo_discord.db import DatabaseImpl
from yolo_discord.service.security import SecurityService, SecurityServiceImpl
from yolo_discord.service.yolo import YoloService, YoloServiceImpl
from yolo_discord.types import CreateOrderRequest, PortfolioEntry
from yolo_discord.util import format_table


class CommandsCog(commands.Cog):
    bot: Bot

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.command()
    async def balance(self, ctx: commands.Context["Bot"]) -> None:
        self.bot.logger.info(f"<@{ctx.author.id}> ({ctx.author.name}) used !balance")
        balance = await self.bot.yolo_service.get_balance(str(ctx.author.id))
        await ctx.reply(f"You have {balance} of available funds.")

    @commands.command()
    async def buy(self, ctx: commands.Context["Bot"]) -> None:
        self.bot.logger.info(f"<@{ctx.author.id}> ({ctx.author.name}) used !buy")
        args = ctx.message.content.split(" ")
        if len(args) != 3:
            await ctx.reply("Incorrect usage. Should be: !order {security} {quantity}")
            return
        try:
            quantity = int(args[2])
        except:
            await ctx.reply("Incorrect usage. Should be: !order {security} {quantity}")
            return
        try:
            order = await self.bot.yolo_service.buy(
                CreateOrderRequest(
                    user_id=str(ctx.author.id),
                    security_name=args[1],
                    quantity=quantity,
                )
            )
            await ctx.reply(f"{order}")
        except Exception as exc:
            print(f"could not place order: {exc}")
            await ctx.reply("The order could not be placed.")

    @commands.command()
    async def price(self, ctx: commands.Context["Bot"]) -> None:
        self.bot.logger.info(f"<@{ctx.author.id}> ({ctx.author.name}) used !price")
        args = ctx.message.content.split(" ")
        if len(args) != 2:
            await ctx.reply("Incorrect usage. Should be !price {security}")
            return
        security_price = await self.bot.security_service.get_security_price(args[1])
        if security_price is None:
            await ctx.reply(f"Could not fetch price of ${args[1]}.")
        else:
            await ctx.reply(f"The price of ${args[1]} is {security_price} per share.")

    @commands.command()
    async def portfolio(self, ctx: commands.Context["Bot"]) -> None:
        self.bot.logger.info(f"<@{ctx.author.id}> ({ctx.author.name}) used !portfolio")
        try:
            portfolio = await self.bot.yolo_service.get_portfolio(str(ctx.author.id))
            if len(portfolio) == 0:
                await ctx.reply("You have no securities in your portfolio.")
                return

            table = format_table(
                ["Name", "Amount", "Balance", "Return"],
                {
                    "Name": lambda entry: entry.security_name,
                    "Amount": lambda entry: str(entry.quantity),
                    "Balance": lambda entry: str(entry.balance),
                    "Return": format_return_rate,
                },
                portfolio,
            )

            await ctx.reply(
                f"""Your current portfolio:
```
{table}
```"""
            )

        except Exception as exc:
            self.bot.logger.error("Could not calculate portfolio", exc_info=exc)
            await ctx.reply("Could not calculate portfolio.")


def format_return_rate(entry: PortfolioEntry) -> str:
    return_rate = entry.return_rate
    if abs(return_rate - 0) < 0.001:
        return_rate = 0
    sign = ""
    if entry.return_rate >= 0:
        sign = "+"
    return f"{sign}{return_rate:.2f}%"


class Bot(commands.Bot):
    finnhub_api_key: str
    logger: Logger

    yolo_service: YoloService
    security_service: SecurityService

    def __init__(self, finnhub_api_key: str) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.finnhub_api_key = finnhub_api_key
        logger = getLogger("yolo-discord")
        logger.parent = getLogger("discord")
        self.logger = logger

    async def setup_hook(self) -> None:
        database = await DatabaseImpl.create("yolo.sqlite3")
        self.security_service = SecurityServiceImpl(self.finnhub_api_key)
        self.yolo_service = YoloServiceImpl(
            logger=self.logger,
            database=database,
            security_service=self.security_service,
        )
        await self.add_cog(CommandsCog(self))

    @tasks.loop(time=time(hour=0, minute=0))
    async def update_allowances(self) -> None:
        await self.yolo_service.update_allowances()

    @tasks.loop(time=time(hour=0, minute=0))
    async def take_portfolio_snapshots(self) -> None:
        print("Taking portfolio snapshots")

    async def on_ready(self) -> None:
        self.logger.info("Starting tasks")
        self.update_allowances.start()
        self.take_portfolio_snapshots.start()
