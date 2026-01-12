import discord
from discord.ext import commands
from yolo_discord.db import DatabaseImpl
from yolo_discord.service.security import SecurityService, SecurityServiceImpl
from yolo_discord.service.yolo import YoloService, YoloServiceImpl
from yolo_discord.types import CreateOrderRequest


class CommandsCog(commands.Cog):
    bot: Bot

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.command()
    async def balance(self, ctx: commands.Context["Bot"]) -> None:
        balance = await self.bot.yolo_service.get_balance(str(ctx.author.id))
        await ctx.reply(f"You have a balance of {balance}")

    @commands.command()
    async def buy(self, ctx: commands.Context["Bot"]) -> None:
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
        args = ctx.message.content.split(" ")
        if len(args) != 2:
            await ctx.reply("Incorrect usage. Should be !price {security}")
            return
        security_price = await self.bot.security_service.get_security_price(args[1])
        if security_price is None:
            await ctx.reply(f"Could not fetch price of ${args[1]}.")
        else:
            await ctx.reply(f"The price of ${args[1]} is {security_price}.")


class Bot(commands.Bot):
    finnhub_api_key: str

    yolo_service: YoloService
    security_service: SecurityService

    def __init__(self, finnhub_api_key: str) -> None:
        self.finnhub_api_key = finnhub_api_key

        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        database = await DatabaseImpl.create("yolo.sqlite3")
        self.security_service = SecurityServiceImpl(self.finnhub_api_key)
        self.yolo_service = YoloServiceImpl(
            database=database,
            security_service=self.security_service,
        )
        await self.add_cog(CommandsCog(self))
