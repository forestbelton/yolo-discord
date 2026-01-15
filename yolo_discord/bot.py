import discord
import re
from datetime import datetime, time
from discord.ext import commands, tasks
from logging import Logger, getLogger
from moneyed import Money
from tempfile import NamedTemporaryFile
from yolo_discord.chart import render_portfolio_balance_chart
from yolo_discord.db import DatabaseImpl
from yolo_discord.service.security import SecurityService, SecurityServiceImpl
from yolo_discord.service.yolo import (
    CreateOrderRequest,
    NotEnoughMoneyException,
    NotEnoughQuantityException,
    YoloService,
    YoloServiceImpl,
)
from yolo_discord.table import Table, format_tables
from yolo_discord.util import (
    format_return_rate,
    calculate_return_rate,
    sum_money,
)

USER_ID_RE = re.compile(r"^<@(\d+)>$")
MONEY_RE = re.compile(r"^\$(\d+)(\.\d{1,2})?$")


class CommandsCog(commands.Cog):
    bot: Bot

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.command()
    async def buy(self, ctx: commands.Context["Bot"]) -> None:
        self.log_command(ctx)
        args = ctx.message.content.split(" ")
        if len(args) != 3:
            await ctx.reply("Incorrect usage. Should be: !buy {security} {quantity}")
            return
        try:
            quantity = int(args[2])
        except:
            await ctx.reply("Incorrect usage. Should be: !buy {security} {quantity}")
            return
        try:
            order = await self.bot.yolo_service.buy(
                CreateOrderRequest(
                    user_id=str(ctx.author.id),
                    security_name=args[1],
                    quantity=quantity,
                )
            )
            await ctx.reply(
                f"You bought {order.quantity} shares of ${order.security_name} at {order.security_price} per share."
            )
        except NotEnoughMoneyException as exc:
            await ctx.reply(
                f"You need {exc.required_funds} to place this order, but you only have {exc.available_funds}."
            )
        except Exception as exc:
            self.bot.logger.error("Could not place order", exc_info=exc)
            await ctx.reply("The order could not be placed.")

    @commands.command()
    async def sell(self, ctx: commands.Context["Bot"]) -> None:
        self.log_command(ctx)
        args = ctx.message.content.split(" ")
        if len(args) != 3:
            await ctx.reply("Incorrect usage. Should be: !sell {security} {quantity}")
            return
        try:
            quantity = int(args[2])
        except:
            await ctx.reply("Incorrect usage. Should be: !sell {security} {quantity}")
            return
        try:
            order = await self.bot.yolo_service.sell(
                CreateOrderRequest(
                    user_id=str(ctx.author.id),
                    security_name=args[1],
                    quantity=quantity,
                )
            )
            await ctx.reply(
                f"You sold {order.quantity} shares of ${order.security_name} at {order.security_price} per share."
            )
        except NotEnoughQuantityException as exc:
            await ctx.reply(
                f"You need {quantity} shares of ${args[1]} to place this order, but you only have {exc.available_quantity}."
            )
        except Exception as exc:
            self.bot.logger.error("Could not place order", exc_info=exc)
            await ctx.reply("The order could not be placed.")

    @commands.command()
    async def price(self, ctx: commands.Context["Bot"]) -> None:
        self.log_command(ctx)
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
        self.log_command(ctx)
        await ctx.typing()
        try:
            portfolio = await self.bot.yolo_service.get_portfolio(str(ctx.author.id))
            cash = await self.bot.yolo_service.get_balance(str(ctx.author.id))
            total = sum_money(entry.balance for entry in portfolio)
            security_table = Table(
                column_headers=["Name", "Amount", "Balance", "Return"],
                formatters={
                    "Name": lambda entry: entry.security_name,
                    "Amount": lambda entry: str(entry.quantity),
                    "Balance": lambda entry: str(entry.balance),
                    "Return": lambda entry: format_return_rate(entry.return_rate),
                },
                data=portfolio,
            )
            width = security_table.width() - 7
            field_column = "Field".rjust(width // 2, " ")
            amount_column = "Amount".rjust(width - width // 2, " ")

            summary_table = Table(
                [field_column, amount_column],
                {
                    field_column: lambda entry: entry[0],
                    amount_column: lambda entry: str(entry[1]),
                },
                [
                    ("Available Funds", cash),
                    ("Total Assets", cash + total),
                    (
                        "Total Return",
                        format_return_rate(
                            calculate_return_rate(
                                sum_money(
                                    entry.total_price_paid for entry in portfolio
                                ),
                                total,
                            )
                        ),
                    ),
                ],
                include_header=False,
            )
            await ctx.reply(f"```{format_tables(security_table, summary_table)}```")
        except Exception as exc:
            self.bot.logger.error("Could not calculate portfolio", exc_info=exc)
            await ctx.reply("Could not calculate portfolio.")

    @commands.command()
    async def chart(self, ctx: commands.Context["Bot"]) -> None:
        self.log_command(ctx)
        try:
            await ctx.typing()
            snapshots = await self.bot.yolo_service.get_portfolio_snapshots(
                str(ctx.author.id)
            )
            with NamedTemporaryFile() as png_file:
                render_portfolio_balance_chart(png_file.file, snapshots)
                embed = discord.Embed()
                embed.set_image(url="attachment://chart.png")
                await ctx.reply(
                    embed=embed,
                    file=discord.File(png_file.name, filename="chart.png"),
                )
        except Exception as exc:
            self.bot.logger.error("Failed to generate chart", exc_info=exc)

    @commands.command()
    async def gift(self, ctx: commands.Context["Bot"]) -> None:
        self.log_command(ctx)
        args = ctx.message.content.split(" ")
        if len(args) != 3:
            await ctx.reply("Incorrect usage. Should be !gift {user} {amount}")
            return
        from_user_id = str(ctx.author.id)
        match = USER_ID_RE.match(args[1])
        if match is None:
            await ctx.reply("Incorrect usage. Should be !gift {user} {amount}")
            return
        to_user_id = match.group(1)
        match = MONEY_RE.match(args[2])
        if match is None:
            await ctx.reply("Incorrect usage. Should be !gift {user} {amount}")
            return
        amount = Money(match.group(0)[1:], "USD")
        try:
            await self.bot.yolo_service.send_gift(from_user_id, to_user_id, amount)
            await ctx.reply(f"You sent {amount} to <@{to_user_id}>. How nice of you!")
        except NotEnoughMoneyException as exc:
            await ctx.reply(
                f"You only have {exc.available_funds} of the required {exc.required_funds}."
            )

    def log_command(self, ctx: commands.Context["Bot"]) -> None:
        self.bot.logger.info(
            f"<@{ctx.author.id}> ({ctx.author.name}) used {ctx.message.content}"
        )


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

    @tasks.loop(time=time(hour=0, minute=0, tzinfo=datetime.now().astimezone().tzinfo))
    async def update_allowances(self) -> None:
        await self.yolo_service.update_allowances()

    @tasks.loop(time=time(hour=0, minute=0, tzinfo=datetime.now().astimezone().tzinfo))
    async def take_portfolio_snapshots(self) -> None:
        await self.yolo_service.take_portfolio_snapshots()

    async def on_ready(self) -> None:
        self.logger.info("Starting tasks")
        self.update_allowances.start()
        self.take_portfolio_snapshots.start()
