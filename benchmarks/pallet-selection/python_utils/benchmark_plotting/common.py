from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

DEFAULT_METRICS = ["ID", "DISTANCE", "RANDOM"]
PLOT_COLORS = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3", "#937860"]
UTILS_DIR = Path(__file__).resolve().parent.parent


def configure_matplotlib() -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 11,
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.labelsize": 11,
            "xtick.labelsize": 9,
            "ytick.labelsize": 10,
            "figure.titlesize": 14,
            "figure.titleweight": "bold",
        }
    )


configure_matplotlib()


def resolve_input_path(path_str: str, anchor: Path = UTILS_DIR) -> Path:
    candidate = Path(path_str).expanduser()
    if candidate.is_absolute():
        return candidate

    cwd_path = candidate.resolve()
    if cwd_path.exists():
        return cwd_path

    anchor_path = (anchor / candidate).resolve()
    if anchor_path.exists():
        return anchor_path

    return cwd_path


def find_json_files(directory: str, anchor: Path = UTILS_DIR) -> list[str]:
    return [str(path) for path in resolve_input_path(directory, anchor).rglob("*.json")]


def extract_metric_name(filepath: str, metrics: list[str]) -> str | None:
    pattern = "|".join(re.escape(metric) for metric in metrics)
    match = re.search(rf"_({pattern})_", Path(filepath).stem)
    return match.group(1) if match else None


def setup_axes(ax: plt.Axes) -> None:
    ax.set_facecolor("#FAFAFA")
    ax.grid(True, alpha=0.4, axis="y", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#CCCCCC")
    ax.spines["bottom"].set_color("#CCCCCC")


def style_violin_parts(parts: dict, colors: list[str], alphas: list[float] | None = None) -> None:
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


def violin_or_bar(ax: plt.Axes, data: list[float], color: str, label: str, pos: int) -> str:
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
        ax.bar(pos, np.mean(data), color=color, alpha=0.8, width=0.5)

    return f"{label}\n(n={len(data)}, μ={np.mean(data):.1f}s)"


def maybe_show() -> None:
    if plt.get_backend().lower() != "agg":
        plt.show()
