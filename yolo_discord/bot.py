import discord
from discord.ext import commands
from yolo_discord.db import DatabaseImpl
from yolo_discord.service.security import SecurityServiceImpl
from yolo_discord.service.yolo import YoloService, YoloServiceImpl
from yolo_discord.types import CreateOrderRequest


class CommandsCog(commands.Cog):
    bot: Bot

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.command()
    async def balance(self, ctx: commands.Context["Bot"]) -> None:
        balance = await self.bot.service.get_balance(str(ctx.author.id))
        await ctx.reply(f"You have a balance of {balance}")

    @commands.command()
    async def order(self, ctx: commands.Context["Bot"]) -> None:
        args = ctx.message.content.split(" ")
        if len(args) != 3:
            await ctx.reply("Incorrect usage. Should be: !order {security} {quantity}")
            return
        try:
            quantity = int(args[2])
        except:
            await ctx.reply("Incorrect usage. Should be: !order {security} {quantity}")
            return
        order = await self.bot.service.create_order(
            CreateOrderRequest(
                user_id=str(ctx.author.id),
                security_name=args[1],
                quantity=quantity,
            )
        )
        await ctx.reply(f"{order}")


class Bot(commands.Bot):
    service: YoloService

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        database = await DatabaseImpl.create("yolo.sqlite3")
        security_service = SecurityServiceImpl()
        self.service = YoloServiceImpl(
            database=database,
            security_service=security_service,
        )
        await self.add_cog(CommandsCog(self))
