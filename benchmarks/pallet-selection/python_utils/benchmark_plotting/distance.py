"""Distance recipe benchmark: task-duration loading and plots.

Loads per-task durations straight from result JSON, groups runs by
``sim``/``opcua`` variant, and renders violin distributions plus
metric-aware comparison charts.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import TypeAlias

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

from .io import extract_metric_name, find_json_files, resolve_input_path
from .style import PLOT_COLORS, setup_axes, style_violin_parts

DEFAULT_METRICS: list[str] = ["ID", "DISTANCE", "RANDOM"]
DEFAULT_EXCLUDED_TASKS: frozenset[str] = frozenset({"WaitPalletAtSegment"})
DEFAULT_MAX_DURATION: int = 150

MAX_SUBPLOTS = 4

TASK_DISPLAY_NAMES: dict[str, str] = {
    "ToMillAndBack": "Milling Cell round trip",
    "ToQcAndBack": "Quality Cell round trip",
    "ToRbtcAndBack": "Robotic Cell round trip",
    "ToWarehouseAndBack": "Warehouse Cell round trip",
}

TaskDurations: TypeAlias = dict[str, list[int]]
MetricTaskDurations: TypeAlias = dict[str, TaskDurations]


# ---------------------------------------------------------------------------
# Loading + grouping
# ---------------------------------------------------------------------------


def load_task_durations(
    filepath: str,
    excluded_tasks: frozenset[str] | set[str] = DEFAULT_EXCLUDED_TASKS,
    max_duration: int | None = DEFAULT_MAX_DURATION,
) -> TaskDurations:
    """Load per-task durations from a result JSON, dropping outliers and excluded tasks."""
    with open(filepath) as handle:
        data = json.load(handle)

    durations: TaskDurations = defaultdict(list)
    for tasks in data.get("mapping", {}).values():
        for entry in tasks:
            task_name = entry["task"]["name"]
            if task_name in excluded_tasks:
                continue
            duration = entry["end_time"] - entry["start_time"]
            if max_duration is not None and duration >= max_duration:
                continue
            durations[task_name].append(duration)
    return dict(durations)


def get_files_in_directory(directory: str, metrics: list[str]) -> list[str]:
    all_files = find_json_files(directory)
    return [filepath for filepath in all_files if extract_metric_name(filepath, metrics) in metrics]


def classify_distance_dir(dirname: str) -> str | None:
    """Return ``sim``/``opcua`` for a distance-results directory name, else ``None``."""
    name = Path(dirname).name.lower()
    if name.startswith("sim"):
        return "sim"
    if name.startswith("opcua"):
        return "opcua"
    return None


def group_distance_runs(base_dir: str, metrics: list[str]) -> dict[str, list[str]]:
    """Walk ``base_dir`` and group result files by ``sim`` / ``opcua`` variant."""
    base = resolve_input_path(base_dir)
    grouped: dict[str, list[str]] = {"sim": [], "opcua": []}
    if not base.is_dir():
        return grouped
    for run_dir in sorted(base.iterdir()):
        if not run_dir.is_dir():
            continue
        variant = classify_distance_dir(run_dir.name)
        if variant is None:
            continue
        grouped[variant].extend(get_files_in_directory(str(run_dir), metrics))
    return grouped


def aggregate_metric_durations(
    files: list[str],
    metrics: list[str],
    excluded_tasks: frozenset[str] | set[str] = DEFAULT_EXCLUDED_TASKS,
    max_duration: int | None = DEFAULT_MAX_DURATION,
) -> MetricTaskDurations:
    """Aggregate task durations across many files, keyed by metric then task name."""
    aggregated: MetricTaskDurations = defaultdict(lambda: defaultdict(list))
    for filepath in files:
        metric = extract_metric_name(filepath, metrics)
        if metric is None:
            continue
        for task, durations in load_task_durations(filepath, excluded_tasks, max_duration).items():
            aggregated[metric][task].extend(durations)
    return {metric: dict(task_map) for metric, task_map in aggregated.items()}


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------


def _display_task_name(task: str) -> str:
    return TASK_DISPLAY_NAMES.get(task, task)


def _violin(
    ax: plt.Axes,
    plot_data: list[tuple[list[int], str, str]],
    title: str,
    alphas: list[float] | None = None,
    ylabel: str = "Duration (in seconds)",
    mean_format: str = ".0f",
) -> None:
    if not plot_data:
        ax.set_visible(False)
        return
    setup_axes(ax)
    durations_list = [durations for durations, _, _ in plot_data]
    colors = [color for _, _, color in plot_data]
    positions = list(range(1, len(plot_data) + 1))
    parts = ax.violinplot(
        durations_list,
        positions=positions,
        showmeans=True,
        showextrema=True,
        quantiles=[[0.25, 0.75]] * len(durations_list),
        widths=0.7,
    )
    style_violin_parts(parts, colors, alphas=alphas)
    tick_labels = [
        f"{label.split(chr(10))[0]}\n(n={len(durations)}, μ={sum(durations) / len(durations):{mean_format}})"
        for durations, label, _ in plot_data
    ]
    ax.set_xticks(positions)
    ax.set_xticklabels(tick_labels, fontweight="medium")
    ax.set_title(title, pad=12)
    ax.set_ylabel(ylabel)
    ax.set_xlim(0.3, len(plot_data) + 0.7)


def plot_distributions(
    files: list[str],
    metrics_to_extract: list[str] = DEFAULT_METRICS,
    excluded_tasks: frozenset[str] | set[str] = DEFAULT_EXCLUDED_TASKS,
    max_duration: int | None = DEFAULT_MAX_DURATION,
) -> None:
    metric_task = aggregate_metric_durations(files, metrics_to_extract, excluded_tasks, max_duration)
    metrics = sorted(metric_task.keys())
    colors = PLOT_COLORS[: len(metrics)]
    all_tasks = set().union(*(durations.keys() for durations in metric_task.values()))
    task_names = sorted(all_tasks)

    fig, axes = plt.subplots(2, 2, figsize=(14, 11))
    axes = axes.flatten()
    fig.patch.set_facecolor("white")

    for index, task in enumerate(task_names[:MAX_SUBPLOTS]):
        plot_data = [
            (metric_task[metric].get(task, []), metric, colors[i])
            for i, metric in enumerate(metrics)
            if metric_task[metric].get(task)
        ]
        _violin(axes[index], plot_data, _display_task_name(task))

    for index in range(len(task_names), MAX_SUBPLOTS):
        axes[index].set_visible(False)

    fig.suptitle(f"Task Duration Distributions — {' vs '.join(metrics)} (n={len(files)} runs)")
    plt.tight_layout(rect=[0, 0, 1, 0.95])


def _normalize_against_reference(
    dir1_metric_task: dict,
    dir2_metric_task: dict,
    common_metrics: list[str],
) -> tuple[dict, dict]:
    """Rescale per-(metric, task) durations of both sets by the mean of ``dir2``.

    The reference (``dir2``) becomes mean ≈ 1.0 per task; ``dir1`` is expressed as a
    ratio of that mean. Tasks with no reference samples are left unchanged.
    """
    norm_dir1: dict = {metric: {} for metric in common_metrics}
    norm_dir2: dict = {metric: {} for metric in common_metrics}
    for metric in common_metrics:
        tasks = set(dir1_metric_task[metric]) | set(dir2_metric_task[metric])
        for task in tasks:
            ref = dir2_metric_task[metric].get(task, [])
            d1 = dir1_metric_task[metric].get(task, [])
            d2 = dir2_metric_task[metric].get(task, [])
            mean_ref = float(np.mean(ref)) if ref else 0.0
            if mean_ref > 0:
                norm_dir1[metric][task] = [value / mean_ref for value in d1]
                norm_dir2[metric][task] = [value / mean_ref for value in d2]
            else:
                norm_dir1[metric][task] = list(d1)
                norm_dir2[metric][task] = list(d2)
    return norm_dir1, norm_dir2


def plot_comparisons(
    dir1_files: list[str],
    dir2_files: list[str],
    dir1_label: str,
    dir2_label: str,
    metrics_to_extract: list[str] = DEFAULT_METRICS,
    excluded_tasks: frozenset[str] | set[str] = DEFAULT_EXCLUDED_TASKS,
    max_duration: int | None = DEFAULT_MAX_DURATION,
    normalized: bool = False,
) -> None:
    dir1_metric_task = aggregate_metric_durations(dir1_files, metrics_to_extract, excluded_tasks, max_duration)
    dir2_metric_task = aggregate_metric_durations(dir2_files, metrics_to_extract, excluded_tasks, max_duration)
    common_metrics = sorted(set(dir1_metric_task) & set(dir2_metric_task))
    if not common_metrics:
        print("No common metrics found between directories.")
        return

    if normalized:
        dir1_metric_task, dir2_metric_task = _normalize_against_reference(
            dir1_metric_task, dir2_metric_task, common_metrics
        )

    all_tasks: set[str] = set()
    for metric in common_metrics:
        all_tasks.update(dir1_metric_task[metric].keys())
        all_tasks.update(dir2_metric_task[metric].keys())
    task_names = sorted(all_tasks)
    metric_colors = {metric: PLOT_COLORS[i % len(PLOT_COLORS)] for i, metric in enumerate(common_metrics)}

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    axes = axes.flatten()
    fig.patch.set_facecolor("white")

    ylabel = f"Duration / mean({dir2_label})" if normalized else "Duration (in seconds)"
    mean_format = ".2f" if normalized else ".0f"
    for index, task in enumerate(task_names[:MAX_SUBPLOTS]):
        plot_data: list[tuple[list[int], str, str]] = []
        for metric in common_metrics:
            color = metric_colors[metric]
            durations_1 = dir1_metric_task[metric].get(task, [])
            durations_2 = dir2_metric_task[metric].get(task, [])
            if durations_1:
                plot_data.append((durations_1, f"{metric}\n({dir1_label})", color))
            if durations_2:
                plot_data.append((durations_2, f"{metric}\n({dir2_label})", color))
        alphas = [0.9 if idx % 2 == 0 else 0.5 for idx in range(len(plot_data))]
        _violin(
            axes[index],
            plot_data,
            _display_task_name(task),
            alphas=alphas,
            ylabel=ylabel,
            mean_format=mean_format,
        )

    for index in range(len(task_names), MAX_SUBPLOTS):
        axes[index].set_visible(False)

    legend_elements = [
        Patch(facecolor=metric_colors[metric], edgecolor="white", alpha=0.9, label=metric)
        for metric in common_metrics
    ]
    legend_elements.extend(
        [
            Patch(facecolor="#2c3e50", edgecolor="#1a1a1a", alpha=0.9, label=f"{dir1_label} (solid)"),
            Patch(facecolor="#2c3e50", edgecolor="#1a1a1a", alpha=0.45, label=f"{dir2_label} (light)"),
        ]
    )
    legend = fig.legend(
        handles=legend_elements,
        loc="lower center",
        ncol=len(common_metrics) + 2,
        bbox_to_anchor=(0.5, 0.01),
        frameon=True,
        fontsize=11,
        handlelength=2.4,
        handleheight=1.4,
        borderpad=0.6,
    )
    legend.get_frame().set_edgecolor("#888888")
    legend.get_frame().set_linewidth(1.0)
    legend.get_frame().set_alpha(1.0)
    suptitle = f"Task Duration Comparison: {dir1_label} vs {dir2_label}"
    if normalized:
        suptitle += f"  (normalized to {dir2_label} mean)"
    fig.suptitle(suptitle)
    plt.tight_layout(rect=[0, 0.07, 1, 0.96])
