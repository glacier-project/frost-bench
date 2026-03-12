"""Plot task duration distributions from simulation result files.

This module provides functionality to visualize and compare task execution times
across different simulation runs and metrics (e.g., ID, DISTANCE, RANDOM).
"""

import argparse
import json
import os
import re
import textwrap
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


# ---------------------------------------------------------------------------
# Base-dir mode — auto-group sim / opcua, compare
# ---------------------------------------------------------------------------


def _classify_distance_dir(dirname: str) -> str | None:
    """Return 'sim' or 'opcua' based on folder name, or None if unrecognised."""
    name = dirname.lower()
    if name.startswith("sim"):
        return "sim"
    if name.startswith("opcua"):
        return "opcua"
    return None


def _run_base_dir_mode(base_dir: str, metrics: list[str]) -> None:
    """Scan *base_dir*, group run folders by variant (sim/opcua), print stats,
    and produce:
      - one distribution plot per variant
      - a sim-vs-opcua comparison plot (if both are present)
    """
    base = Path(base_dir)
    grouped: dict[str, list[str]] = {"sim": [], "opcua": []}

    for run_dir in sorted(base.iterdir()):
        if not run_dir.is_dir():
            continue
        variant = _classify_distance_dir(run_dir.name)
        if variant is None:
            continue
        files = _get_files_in_directory(str(run_dir), metrics)
        grouped[variant].extend(files)

    if not any(grouped.values()):
        print(f"No result files found under '{base_dir}'.")
        return

    variant_labels = {"sim": "Simulation", "opcua": "OPC-UA"}

    for variant, files in grouped.items():
        if not files:
            continue
        label = variant_labels[variant]
        print(f"\n[{label}] {len(files)} files found")
        _plot_distributions(files)  # shows its own plt.show()

    sim_files = grouped["sim"]
    opcua_files = grouped["opcua"]
    if sim_files and opcua_files:
        print("\nPlotting Simulation vs OPC-UA comparison…")
        _plot_comparisons(sim_files, opcua_files, "Simulation", "OPC-UA")
    elif not sim_files:
        print("No simulation files found — skipping comparison.")
    else:
        print("No OPC-UA files found — skipping comparison.")


def main():
    """Main entry point for the plotting script."""
    parser = argparse.ArgumentParser(
        description="Compare task durations between distance-recipe result files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            MODES
            -----
            Single directory — compare metrics (ID / DISTANCE / RANDOM) within one run:
              python plot.py -d results/distance/opcua-20260311_103354
              python plot.py -d results/distance/sim-20260311_103354

            Compare two directories (e.g. sim vs opcua):
              python plot.py -d results/distance/sim-20260311 -c results/distance/opcua-20260311

            Base-dir mode — auto-group all sim-* and opcua-* subfolders and compare:
              python plot.py -b results/distance/

            OPTIONS
            -------
            --metrics   Restrict which metric names appear in filenames to include
                        (default: ID DISTANCE RANDOM)
        """),
    )
    parser.add_argument(
        "--directory",
        "-d",
        type=str,
        default="",
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
        "--base-dir",
        "-b",
        type=str,
        default="",
        help="Base directory: auto-groups sim-* and opcua-* subfolders and compares them.",
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

    # --- Base-dir mode ---
    if args.base_dir:
        _run_base_dir_mode(args.base_dir, args.metrics)
        return

    if not args.directory:
        parser.error("Either --directory or --base-dir is required.")

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
