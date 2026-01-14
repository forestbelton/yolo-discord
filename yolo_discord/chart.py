from datetime import datetime
from typing import IO

import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from yolo_discord.dto import PortfolioSnapshot
from yolo_discord.util import sum_money


def render_portfolio_balance_chart(
    file: IO[bytes],
    snapshots: list[PortfolioSnapshot],
    figsize: tuple[int, int] = (12, 6),
    dpi: int = 100,
) -> None:
    """
    Renders a time series chart of portfolio balance and saves it as a PNG.

    Portfolio balance is calculated as the sum of (balance - total_price_paid)
    for each entry in each snapshot.

    Args:
        snapshots: List of PortfolioSnapshot objects sorted by created_at in ascending order
        figsize: Figure size in inches (width, height)
        dpi: Dots per inch for the output image
    """
    if not snapshots:
        raise ValueError("snapshots list cannot be empty")

    # Extract timestamps and calculate portfolio balances
    timestamps: list[datetime] = []
    balances: list[float] = []

    for snapshot in snapshots:
        timestamps.append(snapshot.created_at)

        # Calculate portfolio balance: sum of (balance - total_price_paid) for each entry
        portfolio_balance = sum_money(
            (entry.balance - entry.total_price_paid) for entry in snapshot.entries
        )
        balances.append(float(portfolio_balance.amount))

    # Determine color based on final balance
    final_balance = balances[-1]
    line_color = "red" if final_balance < 0 else "green"

    # Create the plot
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    # Plot the time series
    ax.plot(  # type: ignore[misc]
        timestamps, balances, color=line_color, linewidth=2, marker="o", markersize=4
    )

    # Fill area under the curve
    ax.fill_between(timestamps, balances, alpha=0.3, color=line_color)  # type: ignore[misc]

    # Add a horizontal line at y=0 for reference
    ax.axhline(y=0, color="black", linestyle="--", linewidth=1, alpha=0.5)  # type: ignore[misc]

    # Format the x-axis to show dates nicely
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))  # type: ignore[misc]
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate()  # Rotate date labels for better readability

    # Set labels and title
    ax.set_xlabel("Date", fontsize=12, fontweight="bold")  # type: ignore[misc]
    ax.set_ylabel("Portfolio Balance", fontsize=12, fontweight="bold")  # type: ignore[misc]
    ax.set_title("Portfolio Balance Over Time", fontsize=14, fontweight="bold")  # type: ignore[misc]

    # Add grid for better readability
    ax.grid(True, alpha=0.3, linestyle="--")  # type: ignore[misc]

    # Format y-axis to show currency-style numbers
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x:,.2f}"))  # type: ignore[misc]

    # Ensure all values fit on the chart with some padding
    y_margin = (
        (max(balances) - min(balances)) * 0.1
        if len(balances) > 1
        else abs(balances[0]) * 0.1
    )
    ax.set_ylim(min(balances) - y_margin, max(balances) + y_margin)

    # Tight layout to prevent label cutoff
    plt.tight_layout()

    # Save the figure
    plt.savefig(file, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
