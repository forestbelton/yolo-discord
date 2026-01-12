from dataclasses import dataclass
from os import getenv
from moneyed import Money
from typing import Optional
from yolo_discord.util import from_cents


@dataclass
class ApplicationConfiguration:
    starting_balance: Money
    weekly_allowance: Money


config: Optional[ApplicationConfiguration] = None


def get_config() -> ApplicationConfiguration:
    global config
    if config is None:
        config = ApplicationConfiguration(
            starting_balance=from_cents(int(getenv("STARTING_BALANCE_CENTS"))),  # type: ignore
            weekly_allowance=from_cents(int(getenv("WEEKLY_ALLOWANCE_CENTS"))),  # type: ignore
        )
    return config
