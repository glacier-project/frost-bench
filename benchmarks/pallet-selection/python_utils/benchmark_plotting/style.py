"""Matplotlib styling and shared plot primitives."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

PLOT_COLORS: list[str] = [
    "#4C72B0",
    "#DD8452",
    "#55A868",
    "#C44E52",
    "#8172B3",
    "#937860",
]


def configure_matplotlib() -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 11,
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.labelsize": 11,
            "xtick.labelsize": 12,
            "ytick.labelsize": 10,
            "figure.titlesize": 14,
            "figure.titleweight": "bold",
        }
    )


configure_matplotlib()


def setup_axes(ax: plt.Axes) -> None:
    ax.set_facecolor("#FAFAFA")
    ax.grid(True, alpha=0.4, axis="y", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#CCCCCC")
    ax.spines["bottom"].set_color("#CCCCCC")


def style_violin_parts(
    parts: dict,
    colors: list[str],
    alphas: list[float] | None = None,
) -> None:
    for index, body in enumerate(parts["bodies"]):
        body.set_facecolor(colors[index])
        body.set_edgecolor("white")
        body.set_alpha(alphas[index] if alphas else 0.85)
        body.set_linewidth(1.5)

    if "cmeans" in parts:
        parts["cmeans"].set_edgecolor("black")
        parts["cmeans"].set_linewidth(2)
    if "cquantiles" in parts:
        parts["cquantiles"].set_edgecolor("#333333")
        parts["cquantiles"].set_linewidth(1.2)
        parts["cquantiles"].set_linestyle("--")
    for part_name in ("cbars", "cmins", "cmaxes"):
        if part_name in parts:
            parts[part_name].set_edgecolor("#555555")
            parts[part_name].set_linewidth(1)


def violin_or_bar(
    ax: plt.Axes,
    data: list[float],
    color: str,
    label: str,
    pos: int,
    unit: str = "s",
) -> str:
    if len(data) >= 3:
        parts = ax.violinplot(
            [data],
            positions=[pos],
            showmeans=True,
            showextrema=True,
            quantiles=[[0.25, 0.75]],
            widths=0.6,
        )
        style_violin_parts(parts, [color])
    else:
        ax.bar(pos, float(np.mean(data)), color=color, alpha=0.8, width=0.5)

    return f"{label}\n(n={len(data)}, μ={np.mean(data):.1f}{unit})"


def maybe_show() -> None:
    if plt.get_backend().lower() != "agg":
        plt.show()
