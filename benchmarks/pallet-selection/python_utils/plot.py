"""Plot task duration distributions from simulation result files.

This module provides functionality to visualize and compare task execution times
across different simulation runs and metrics (e.g., ID, DISTANCE, RANDOM).
"""

import argparse
import json
import os
import re
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

# Configure matplotlib style
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

# Constants
DEFAULT_METRICS = ["ID", "DISTANCE", "RANDOM"]
PLOT_COLORS = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3", "#937860"]
MAX_SUBPLOTS = 4
EXCLUDED_TASKS = {"WaitPalletAtSegment"}


def _load_task_durations(filepath: str) -> dict[str, list[int]]:
    """Load task durations from a result file.

    Args:
        filepath: Path to the result JSON file.

    Returns:
        Dictionary mapping task names to lists of durations.
    """
    with open(filepath) as f:
        data = json.load(f)

    task_durations = defaultdict(list)
    for tasks in data.get("mapping", {}).values():
        for entry in tasks:
            task_name = entry["task"]["name"]
            if task_name not in EXCLUDED_TASKS:
                duration = entry["end_time"] - entry["start_time"]
                task_durations[task_name].append(duration)

    return dict(task_durations)


def _extract_metric_name(filepath: str) -> str:
    """Extract the metric name from a filepath (e.g., '_DISTANCE_' -> 'DISTANCE')."""
    match = re.search(r"_([A-Z]+)_", filepath)
    return match.group(1) if match else Path(filepath).name


def _style_violin_plot(parts: dict, colors: list[str]) -> None:
    """Apply consistent styling to violin plot elements."""
    for i, body in enumerate(parts["bodies"]):
        body.set_facecolor(colors[i])
        body.set_edgecolor("white")
        body.set_alpha(0.85)
        body.set_linewidth(1.5)

    if "cmeans" in parts:
        parts["cmeans"].set_edgecolor("black")
        parts["cmeans"].set_linewidth(2)

    if "cquantiles" in parts:
        parts["cquantiles"].set_edgecolor("#333333")
        parts["cquantiles"].set_linewidth(1.2)
        parts["cquantiles"].set_linestyle("--")

    for partname in ("cbars", "cmins", "cmaxes"):
        if partname in parts:
            parts[partname].set_edgecolor("#555555")
            parts[partname].set_linewidth(1)


def _setup_axes(ax: plt.Axes) -> None:
    """Apply common axes styling."""
    ax.set_facecolor("#FAFAFA")
    ax.grid(True, alpha=0.4, axis="y", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#CCCCCC")
    ax.spines["bottom"].set_color("#CCCCCC")


def _plot_violin(
    ax: plt.Axes,
    plot_data: list[tuple[list[int], str, str]],
    title: str,
) -> None:
    """Plot a violin comparison on the given axes.

    Args:
        ax: Matplotlib axes to plot on.
        plot_data: List of tuples (durations, label, color).
        title: Title for the subplot.
    """
    if not plot_data:
        ax.set_visible(False)
        return

    _setup_axes(ax)

    durations_list = [d[0] for d in plot_data]
    colors = [d[2] for d in plot_data]
    # labels = [d[1] for d in plot_data]
    positions = list(range(1, len(plot_data) + 1))
    quantiles = [[0.25, 0.75]] * len(durations_list)

    parts = ax.violinplot(
        durations_list,
        positions=positions,
        showmeans=True,
        showextrema=True,
        quantiles=quantiles,
        widths=0.7,
    )
    _style_violin_plot(parts, colors)

    # Create tick labels with statistics
    tick_labels = [f"{lbl}\n(n={len(d)}, μ={np.mean(d):.0f})" for d, lbl, _ in plot_data]
    ax.set_xticks(positions)
    ax.set_xticklabels(tick_labels, fontweight="medium")
    ax.set_title(title, pad=12)
    ax.set_ylabel("Duration (in seconds)")
    ax.set_xlim(0.3, len(plot_data) + 0.7)


def _get_files_in_directory(directory: str, metrics: list[str]) -> list[str]:
    """Find result files in a directory (recursively) matching the specified metrics."""
    all_files = [str(p) for p in Path(directory).rglob("*.json")]
    return [f for metric in metrics for f in all_files if f"_{metric}_" in f]


def _plot_distributions(files: list[str]) -> None:
    """Plot duration distributions for each task comparing multiple metrics."""
    # Aggregate durations across all files of the same metric
    metric_durations: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for f in files:
        metric = _extract_metric_name(f)
        for task, durations in _load_task_durations(f).items():
            metric_durations[metric][task].extend(durations)

    metrics = sorted(metric_durations.keys())
    labels = metrics
    colors = PLOT_COLORS[: len(metrics)]

    all_tasks = set().union(*[d.keys() for d in metric_durations.values()])
    task_names = sorted(all_tasks)

    fig, axes = plt.subplots(2, 2, figsize=(14, 11))
    axes = axes.flatten()
    fig.patch.set_facecolor("white")

    for idx, task in enumerate(task_names[:MAX_SUBPLOTS]):
        plot_data = [
            (metric_durations[m].get(task, []), m, colors[i])
            for i, m in enumerate(metrics)
            if metric_durations[m].get(task)
        ]
        _plot_violin(axes[idx], plot_data, task)

    for idx in range(len(task_names), MAX_SUBPLOTS):
        axes[idx].set_visible(False)

    fig.suptitle(
        f'Task Duration Distributions — {" vs ".join(labels)} (n={len(files)} runs)',
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.show()


def _plot_comparisons(
    dir1_files: list[str],
    dir2_files: list[str],
    dir1_label: str,
    dir2_label: str,
) -> None:
    """Plot side-by-side comparisons of all metrics from two directories.

    Creates a 2x2 grid (one subplot per task), where each subplot shows all metrics
    side by side with a common legend.
    """
    dir1_by_metric = {_extract_metric_name(f): f for f in dir1_files}
    dir2_by_metric = {_extract_metric_name(f): f for f in dir2_files}
    common_metrics = sorted(set(dir1_by_metric.keys()) & set(dir2_by_metric.keys()))

    if not common_metrics:
        print("No common metrics found between directories.")
        return

    # Load all durations
    all_durations = {}
    all_tasks: set[str] = set()
    for metric in common_metrics:
        dur1 = _load_task_durations(dir1_by_metric[metric])
        dur2 = _load_task_durations(dir2_by_metric[metric])
        all_durations[metric] = (dur1, dur2)
        all_tasks.update(dur1.keys(), dur2.keys())

    task_names = sorted(all_tasks)

    # Assign colors to each metric
    metric_colors = {m: PLOT_COLORS[i % len(PLOT_COLORS)] for i, m in enumerate(common_metrics)}

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    axes = axes.flatten()
    fig.patch.set_facecolor("white")

    for idx, task in enumerate(task_names[:MAX_SUBPLOTS]):
        _setup_axes(axes[idx])

        # Build data: group by metric, dir1 then dir2
        plot_data = []
        for metric in common_metrics:
            dur1, dur2 = all_durations[metric]
            color = metric_colors[metric]

            if task_dur1 := dur1.get(task, []):
                plot_data.append((task_dur1, f"{metric}\n({dir1_label})", color))
            if task_dur2 := dur2.get(task, []):
                # Use lighter shade for dir2
                plot_data.append((task_dur2, f"{metric}\n({dir2_label})", color))

        if not plot_data:
            axes[idx].set_visible(False)
            continue

        durations_list = [d[0] for d in plot_data]
        colors = [d[2] for d in plot_data]
        positions = list(range(1, len(plot_data) + 1))
        quantiles = [[0.25, 0.75]] * len(durations_list)

        parts = axes[idx].violinplot(
            durations_list,
            positions=positions,
            showmeans=True,
            showextrema=True,
            quantiles=quantiles,
            widths=0.7,
        )

        # Alternate alpha for dir1 (solid) vs dir2 (lighter)
        for i, body in enumerate(parts["bodies"]):
            body.set_facecolor(colors[i])
            body.set_edgecolor("white")
            body.set_alpha(0.9 if i % 2 == 0 else 0.5)
            body.set_linewidth(1.5)

        if "cmeans" in parts:
            parts["cmeans"].set_edgecolor("black")
            parts["cmeans"].set_linewidth(2)
        if "cquantiles" in parts:
            parts["cquantiles"].set_edgecolor("#333333")
            parts["cquantiles"].set_linewidth(1.2)
            parts["cquantiles"].set_linestyle("--")
        for partname in ("cbars", "cmins", "cmaxes"):
            if partname in parts:
                parts[partname].set_edgecolor("#555555")
                parts[partname].set_linewidth(1)

        tick_labels = [
            f"{lbl.split(chr(10))[0]}\n(n={len(d)}, μ={np.mean(d):.0f})" for d, lbl, _ in plot_data
        ]
        axes[idx].set_xticks(positions)
        axes[idx].set_xticklabels(tick_labels, fontweight="medium")
        axes[idx].set_title(task, pad=12)
        axes[idx].set_ylabel("Duration (time units)")
        axes[idx].set_xlim(0.3, len(plot_data) + 0.7)

    for idx in range(len(task_names), MAX_SUBPLOTS):
        axes[idx].set_visible(False)

    # Create common legend
    legend_elements = [
        Patch(facecolor=metric_colors[m], edgecolor="white", alpha=0.9, label=m)
        for m in common_metrics
    ]
    legend_elements.extend(
        [
            Patch(facecolor="gray", edgecolor="white", alpha=0.9, label=f"{dir1_label} (solid)"),
            Patch(facecolor="gray", edgecolor="white", alpha=0.5, label=f"{dir2_label} (light)"),
        ]
    )

    fig.legend(
        handles=legend_elements,
        loc="upper center",
        ncol=len(common_metrics) + 2,
        bbox_to_anchor=(0.5, 0.02),
        frameon=True,
        fancybox=True,
        shadow=False,
    )

    fig.suptitle(
        f"Task Duration Comparison: {dir1_label} vs {dir2_label}",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )
    plt.tight_layout(rect=[0, 0.05, 1, 0.95])
    plt.show()


def main() -> None:
    """Main entry point for the plotting script."""
    parser = argparse.ArgumentParser(
        description="Compare task durations between simulation result files."
    )
    parser.add_argument(
        "--directory",
        "-d",
        required=True,
        type=str,
        help="Directory containing result files.",
    )
    parser.add_argument(
        "--compare",
        "-c",
        type=str,
        default="",
        help="Directory containing result files to compare against.",
    )
    parser.add_argument(
        "--metrics",
        "-m",
        type=str,
        nargs="*",
        default=DEFAULT_METRICS,
        help="Metric names to look for in filenames (e.g., ID DISTANCE RANDOM)",
    )
    args = parser.parse_args()

    dir_files = _get_files_in_directory(args.directory, args.metrics)

    if args.compare:
        compare_files = _get_files_in_directory(args.compare, args.metrics)
        dir1_label = Path(args.directory).name
        dir2_label = Path(args.compare).name
        _plot_comparisons(dir_files, compare_files, dir1_label, dir2_label)
    else:
        _plot_distributions(dir_files)


if __name__ == "__main__":
    main()
