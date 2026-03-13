from __future__ import annotations

import argparse
import json
import textwrap
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from .common import DEFAULT_METRICS, PLOT_COLORS, extract_metric_name, find_json_files, maybe_show, resolve_input_path, setup_axes, style_violin_parts

MAX_SUBPLOTS = 4
EXCLUDED_TASKS = {"WaitPalletAtSegment"}


def load_task_durations(filepath: str) -> dict[str, list[int]]:
    with open(filepath) as handle:
        data = json.load(handle)

    task_durations = defaultdict(list)
    for tasks in data.get("mapping", {}).values():
        for entry in tasks:
            task_name = entry["task"]["name"]
            if task_name not in EXCLUDED_TASKS:
                task_durations[task_name].append(entry["end_time"] - entry["start_time"])
    return dict(task_durations)


def get_files_in_directory(directory: str, metrics: list[str]) -> list[str]:
    all_files = find_json_files(directory)
    return [filepath for filepath in all_files if extract_metric_name(filepath, metrics) in metrics]


def plot_violin(ax: plt.Axes, plot_data: list[tuple[list[int], str, str]], title: str) -> None:
    if not plot_data:
        ax.set_visible(False)
        return
    setup_axes(ax)
    durations_list = [durations for durations, _, _ in plot_data]
    colors = [color for _, _, color in plot_data]
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
    style_violin_parts(parts, colors)
    tick_labels = [f"{label}\n(n={len(durations)}, μ={sum(durations)/len(durations):.0f})" for durations, label, _ in plot_data]
    ax.set_xticks(positions)
    ax.set_xticklabels(tick_labels, fontweight="medium")
    ax.set_title(title, pad=12)
    ax.set_ylabel("Duration (in seconds)")
    ax.set_xlim(0.3, len(plot_data) + 0.7)


def plot_distributions(files: list[str]) -> None:
    metric_durations: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for filepath in files:
        metric = extract_metric_name(filepath)
        if metric is None:
            continue
        for task, durations in load_task_durations(filepath).items():
            metric_durations[metric][task].extend(durations)

    metrics = sorted(metric_durations.keys())
    colors = PLOT_COLORS[: len(metrics)]
    all_tasks = set().union(*[durations.keys() for durations in metric_durations.values()])
    task_names = sorted(all_tasks)

    fig, axes = plt.subplots(2, 2, figsize=(14, 11))
    axes = axes.flatten()
    fig.patch.set_facecolor("white")

    for index, task in enumerate(task_names[:MAX_SUBPLOTS]):
        plot_data = [
            (metric_durations[metric].get(task, []), metric, colors[i])
            for i, metric in enumerate(metrics)
            if metric_durations[metric].get(task)
        ]
        plot_violin(axes[index], plot_data, task)

    for index in range(len(task_names), MAX_SUBPLOTS):
        axes[index].set_visible(False)

    fig.suptitle(f"Task Duration Distributions — {' vs '.join(metrics)} (n={len(files)} runs)")
    plt.tight_layout(rect=[0, 0, 1, 0.95])


def plot_comparisons(dir1_files: list[str], dir2_files: list[str], dir1_label: str, dir2_label: str) -> None:
    dir1_by_metric = {extract_metric_name(filepath): filepath for filepath in dir1_files}
    dir2_by_metric = {extract_metric_name(filepath): filepath for filepath in dir2_files}
    common_metrics = sorted(set(dir1_by_metric.keys()) & set(dir2_by_metric.keys()))
    if not common_metrics:
        print("No common metrics found between directories.")
        return

    all_durations = {}
    all_tasks: set[str] = set()
    for metric in common_metrics:
        durations_1 = load_task_durations(dir1_by_metric[metric])
        durations_2 = load_task_durations(dir2_by_metric[metric])
        all_durations[metric] = (durations_1, durations_2)
        all_tasks.update(durations_1.keys(), durations_2.keys())

    task_names = sorted(all_tasks)
    metric_colors = {metric: PLOT_COLORS[i % len(PLOT_COLORS)] for i, metric in enumerate(common_metrics)}

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    axes = axes.flatten()
    fig.patch.set_facecolor("white")

    for index, task in enumerate(task_names[:MAX_SUBPLOTS]):
        setup_axes(axes[index])
        plot_data = []
        for metric in common_metrics:
            durations_1, durations_2 = all_durations[metric]
            color = metric_colors[metric]
            if task_dur_1 := durations_1.get(task, []):
                plot_data.append((task_dur_1, f"{metric}\n({dir1_label})", color))
            if task_dur_2 := durations_2.get(task, []):
                plot_data.append((task_dur_2, f"{metric}\n({dir2_label})", color))
        if not plot_data:
            axes[index].set_visible(False)
            continue

        durations_list = [durations for durations, _, _ in plot_data]
        colors = [color for _, _, color in plot_data]
        positions = list(range(1, len(plot_data) + 1))
        parts = axes[index].violinplot(
            durations_list,
            positions=positions,
            showmeans=True,
            showextrema=True,
            quantiles=[[0.25, 0.75]] * len(durations_list),
            widths=0.7,
        )
        style_violin_parts(parts, colors, alphas=[0.9 if idx % 2 == 0 else 0.5 for idx in range(len(colors))])
        tick_labels = [f"{label.split(chr(10))[0]}\n(n={len(durations)}, μ={sum(durations)/len(durations):.0f})" for durations, label, _ in plot_data]
        axes[index].set_xticks(positions)
        axes[index].set_xticklabels(tick_labels, fontweight="medium")
        axes[index].set_title(task, pad=12)
        axes[index].set_ylabel("Duration (time units)")
        axes[index].set_xlim(0.3, len(plot_data) + 0.7)

    for index in range(len(task_names), MAX_SUBPLOTS):
        axes[index].set_visible(False)

    legend_elements = [Patch(facecolor=metric_colors[metric], edgecolor="white", alpha=0.9, label=metric) for metric in common_metrics]
    legend_elements.extend([
        Patch(facecolor="gray", edgecolor="white", alpha=0.9, label=f"{dir1_label} (solid)"),
        Patch(facecolor="gray", edgecolor="white", alpha=0.5, label=f"{dir2_label} (light)"),
    ])
    fig.legend(handles=legend_elements, loc="upper center", ncol=len(common_metrics) + 2, bbox_to_anchor=(0.5, 0.02), frameon=True)
    fig.suptitle(f"Task Duration Comparison: {dir1_label} vs {dir2_label}")
    plt.tight_layout(rect=[0, 0.05, 1, 0.95])


def classify_distance_dir(dirname: str) -> str | None:
    name = dirname.lower()
    if name.startswith("sim"):
        return "sim"
    if name.startswith("opcua"):
        return "opcua"
    return None


def run_base_dir_mode(base_dir: str, metrics: list[str]) -> None:
    base = resolve_input_path(base_dir)
    grouped: dict[str, list[str]] = {"sim": [], "opcua": []}
    for run_dir in sorted(base.iterdir()):
        if not run_dir.is_dir():
            continue
        variant = classify_distance_dir(run_dir.name)
        if variant is None:
            continue
        grouped[variant].extend(get_files_in_directory(str(run_dir), metrics))

    if not any(grouped.values()):
        print(f"No result files found under '{base_dir}'.")
        return

    variant_labels = {"sim": "Simulation", "opcua": "OPC-UA"}
    for variant, files in grouped.items():
        if not files:
            continue
        print(f"\n[{variant_labels[variant]}] {len(files)} files found")
        plot_distributions(files)

    if grouped["sim"] and grouped["opcua"]:
        print("\nPlotting Simulation vs OPC-UA comparison…")
        plot_comparisons(grouped["sim"], grouped["opcua"], "Simulation", "OPC-UA")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare task durations between distance-recipe result files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            MODES
            -----
            Single directory — compare metrics within one run:
              python plot.py -d results/distance/opcua-20260311_103354

            Compare two directories:
              python plot.py -d results/distance/sim-20260311 -c results/distance/opcua-20260311

            Base-dir mode — auto-group all sim-* and opcua-* subfolders and compare:
              python plot.py -b results/distance/
            """
        ),
    )
    parser.add_argument("--directory", "-d", type=str, default="", help="Directory containing result files.")
    parser.add_argument("--compare", "-c", type=str, default="", help="Directory to compare against.")
    parser.add_argument("--base-dir", "-b", type=str, default="", help="Base directory that auto-groups sim-* and opcua-* subfolders.")
    parser.add_argument("--metrics", "-m", nargs="*", default=DEFAULT_METRICS, help="Metric names to include.")
    args = parser.parse_args()

    if args.base_dir:
        run_base_dir_mode(args.base_dir, args.metrics)
        maybe_show()
        return

    if not args.directory:
        parser.error("Either --directory or --base-dir is required.")

    files = get_files_in_directory(args.directory, args.metrics)
    if args.compare:
        compare_files = get_files_in_directory(args.compare, args.metrics)
        plot_comparisons(files, compare_files, Path(args.directory).name, Path(args.compare).name)
    else:
        plot_distributions(files)
    maybe_show()
