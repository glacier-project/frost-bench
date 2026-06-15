"""Lego recipe benchmark: data loading, statistics, and plots.

Data side reconstructs recipes from result JSON; the plot side renders
end-to-end duration violins, per-task distributions, Gaussian fits, waiting
times, Gantt timelines, and sim-vs-real comparisons.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import TypeAlias

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

from .io import extract_metric_name, find_json_files, resolve_input_path
from .outliers import (
    DEFAULT_PERCENTILE_RANGE,
    evaluate_outlier_methods,
    trim_percentile_range,
)
from .style import PLOT_COLORS, setup_axes, violin_or_bar

# ---------------------------------------------------------------------------
# Model + constants
# ---------------------------------------------------------------------------

LEGO_RECIPE_STEPS: list[str] = ["LD", "RBTC", "QC", "DISASSEMBLE", "RESERVE", "PUT_BACK"]
LEGO_RECIPE_END: str = "PUT_BACK"

TOPIC_LABELS: dict[str, str] = {
    "full": "Full Lego Recipe",
    "movements": "Lego Conveyor Movements",
}
VARIANT_LABELS: dict[str, str] = {"sim": "Simulation", "opcua": "Real"}

DEFAULT_LEGO_METRICS: list[str] = ["ID", "DISTANCE"]

Recipe: TypeAlias = dict[str, dict]
TopicMetricGrouping: TypeAlias = dict[str, dict[str, dict[str, list[Recipe]]]]


# ---------------------------------------------------------------------------
# Loading + reconstruction
# ---------------------------------------------------------------------------


def _load_json(filepath: str) -> dict:
    with open(filepath) as handle:
        return json.load(handle)


def _flatten_tasks(data: dict) -> dict[str, dict]:
    tasks: dict[str, dict] = {}
    for entries in data.get("mapping", {}).values():
        for entry in entries:
            tasks[entry["task"]["id"]] = entry
    return tasks


def _reconstruct_recipes(tasks: dict[str, dict]) -> list[Recipe]:
    dependents: dict[str, list[str]] = defaultdict(list)
    for task_id, entry in tasks.items():
        for dependency in entry["task"].get("dependencies", []):
            dependents[dependency].append(task_id)

    roots = [task_id for task_id, entry in tasks.items() if not entry["task"].get("dependencies")]

    recipes: list[Recipe] = []
    for root_id in roots:
        recipe: Recipe = {}
        stack = [root_id]
        while stack:
            task_id = stack.pop()
            entry = tasks[task_id]
            recipe[entry["task"]["name"]] = entry
            stack.extend(dependents.get(task_id, []))

        last = recipe.get(LEGO_RECIPE_END)
        first_time = next(
            (
                entry["start_time"]
                for step in LEGO_RECIPE_STEPS
                if (entry := recipe.get(step)) is not None and entry.get("start_time") is not None
            ),
            None,
        )
        if last is not None and last.get("end_time") is not None and first_time is not None:
            recipes.append(recipe)
    return recipes


def load_lego_results(filepath: str) -> list[Recipe]:
    """Load and reconstruct all complete recipes from a single result JSON."""
    return _reconstruct_recipes(_flatten_tasks(_load_json(filepath)))


def recipe_start_time(recipe: Recipe) -> float:
    for step in LEGO_RECIPE_STEPS:
        entry = recipe.get(step)
        if entry is not None and entry.get("start_time") is not None:
            return entry["start_time"]
    raise ValueError(f"Recipe has no known start step: {list(recipe.keys())}")


def recipe_duration(recipe: Recipe) -> float:
    return recipe[LEGO_RECIPE_END]["end_time"] - recipe_start_time(recipe)


def task_duration(recipe: Recipe, task_name: str) -> float | None:
    entry = recipe.get(task_name)
    if entry is None:
        return None
    return entry["end_time"] - entry["start_time"]


def waiting_time(recipe: Recipe, step_a: str, step_b: str) -> float | None:
    first = recipe.get(step_a)
    second = recipe.get(step_b)
    if first is None or second is None:
        return None
    return second["start_time"] - first["end_time"]


def classify_run_dir(dirname: str) -> tuple[str, str] | None:
    """Return ``(topic, variant)`` for a results-run directory name, or ``None``."""
    name = Path(dirname).name.lower()
    if name.startswith("movements-sim") or name.startswith("sim-lego-movements"):
        return ("movements", "sim")
    if name.startswith("movements-opcua") or name.startswith("opcua-lego-movements"):
        return ("movements", "opcua")
    if name.startswith("lego-sim") or name.startswith("sim-lego"):
        return ("full", "sim")
    if name.startswith("lego-opcua") or name.startswith("opcua-lego"):
        return ("full", "opcua")
    return None


def aggregate_by_topic_metric(base_dir: str, metrics: list[str]) -> TopicMetricGrouping:
    """Walk ``base_dir`` once and group recipes as ``topic → variant → metric → [recipes]``."""
    result: TopicMetricGrouping = {}
    base = resolve_input_path(base_dir)
    if not base.is_dir():
        print(f"Base directory not found: {base_dir}")
        return result

    for run_dir in sorted(base.iterdir()):
        if not run_dir.is_dir():
            continue
        classification = classify_run_dir(run_dir.name)
        if classification is None:
            continue
        topic, variant = classification
        for filepath in run_dir.rglob("*.json"):
            metric = extract_metric_name(str(filepath), metrics)
            if metric is None:
                continue
            recipes = load_lego_results(str(filepath))
            if recipes:
                result.setdefault(topic, {}).setdefault(variant, {}).setdefault(metric, []).extend(recipes)
    return result


def load_recipes_by_metric(directory: str, metrics: list[str]) -> dict[str, list[Recipe]]:
    grouped: dict[str, list[Recipe]] = defaultdict(list)
    for filepath in find_json_files(directory):
        metric = extract_metric_name(filepath, metrics)
        if metric is None:
            continue
        grouped[metric].extend(load_lego_results(filepath))
    return dict(grouped)


def load_all_recipes(directory: str) -> list[Recipe]:
    recipes: list[Recipe] = []
    for filepath in find_json_files(directory):
        recipes.extend(load_lego_results(filepath))
    return recipes


def print_recipe_stats(
    recipes: list[Recipe],
    label: str,
    include_outlier_evaluation: bool = False,
) -> None:
    if not recipes:
        return
    durations = [recipe_duration(recipe) for recipe in recipes]
    print(f"\n── {label} ──")
    print(f"  Recipes : {len(recipes)}")
    print(
        f"  Duration — mean: {np.mean(durations):.1f}s  "
        f"std: {np.std(durations):.1f}s  "
        f"min: {np.min(durations):.1f}s  "
        f"max: {np.max(durations):.1f}s"
    )
    for step in LEGO_RECIPE_STEPS:
        values = [value for recipe in recipes if (value := task_duration(recipe, step)) is not None]
        if values:
            print(f"  {step:12s} — mean: {np.mean(values):.1f}s  std: {np.std(values):.1f}s")
    if include_outlier_evaluation:
        print("  Outlier evaluation on total duration:")
        for evaluation in evaluate_outlier_methods(durations):
            print(
                f"    {evaluation.method:12s} keeps {evaluation.kept_count}/{len(durations)} "
                f"(removed {evaluation.removed_count}) in "
                f"[{evaluation.lower_bound:.1f}, {evaluation.upper_bound:.1f}]"
            )


def normalize_recipes(
    recipes_sim: list[Recipe],
    recipes_reference: list[Recipe],
) -> tuple[list[Recipe], list[Recipe]]:
    """Rescale task and total durations of both recipe sets to the mean of ``recipes_reference``."""
    if not recipes_reference:
        return recipes_sim, recipes_reference

    mean_recipe_duration_ref = float(
        np.mean([recipe_duration(recipe) for recipe in recipes_reference])
    )

    mean_task_durations_ref: dict[str, float] = {}
    for step in LEGO_RECIPE_STEPS:
        durations = [
            value for recipe in recipes_reference
            if (value := task_duration(recipe, step)) is not None
        ]
        if durations:
            mean_task_durations_ref[step] = float(np.mean(durations))

    def normalize_single(recipe: Recipe) -> Recipe:
        new_recipe: Recipe = {}
        norm_total_dur = (
            recipe_duration(recipe) / mean_recipe_duration_ref
            if mean_recipe_duration_ref > 0
            else recipe_duration(recipe)
        )

        norm_task_durations: dict[str, float] = {}
        for task_name, entry in recipe.items():
            real_task_dur = entry["end_time"] - entry["start_time"]
            ref_mean = mean_task_durations_ref.get(task_name)
            norm_task_durations[task_name] = (
                real_task_dur / ref_mean if ref_mean and ref_mean > 0 else real_task_dur
            )

        present_steps = [step for step in LEGO_RECIPE_STEPS if step in recipe]
        if len(present_steps) > 1 and LEGO_RECIPE_END in present_steps:
            sum_norm_tasks = sum(norm_task_durations[step] for step in present_steps)
            gap_per_step = (norm_total_dur - sum_norm_tasks) / (len(present_steps) - 1)
        else:
            gap_per_step = 0.0

        current_time = 0.0
        for step in present_steps:
            duration = norm_task_durations[step]
            new_recipe[step] = {"start_time": current_time, "end_time": current_time + duration}
            current_time += duration + gap_per_step

        for task_name, _ in recipe.items():
            if task_name not in new_recipe:
                duration = norm_task_durations[task_name]
                new_recipe[task_name] = {"start_time": 0.0, "end_time": duration}

        return new_recipe

    return (
        [normalize_single(recipe) for recipe in recipes_sim],
        [normalize_single(recipe) for recipe in recipes_reference],
    )


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------


def _gaussian_pdf(xs: np.ndarray, mean: float, std: float) -> np.ndarray:
    if std <= 0:
        return np.zeros_like(xs)
    coeff = 1.0 / (std * math.sqrt(2.0 * math.pi))
    return coeff * np.exp(-0.5 * ((xs - mean) / std) ** 2)


def _draw_gaussian(
    ax: plt.Axes,
    values: list[float],
    label: str,
    color: str,
    percentile_range: tuple[float, float] = DEFAULT_PERCENTILE_RANGE,
) -> None:
    setup_axes(ax)
    if not values:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes, color="grey")
        ax.set_title(label)
        return

    lower_pct, upper_pct = percentile_range
    filtered = trim_percentile_range(values, lower_pct, upper_pct)
    bins = min(16, max(5, int(np.sqrt(len(filtered.kept_values))) + 1))

    ax.hist(
        filtered.kept_values,
        bins=bins,
        density=True,
        color=color,
        alpha=0.35,
        edgecolor="white",
        linewidth=1,
    )

    mean = float(np.mean(filtered.kept_values))
    std = float(np.std(filtered.kept_values, ddof=1)) if len(filtered.kept_values) > 1 else 0.0
    if len(filtered.kept_values) > 1 and std > 0:
        xs = np.linspace(min(filtered.kept_values), max(filtered.kept_values), 400)
        ax.plot(xs, _gaussian_pdf(xs, mean, std), color=color, linewidth=2.2, label="Gaussian fit")
    else:
        ax.axvline(mean, color=color, linewidth=2.2, label="Mean")

    ax.axvline(filtered.lower_bound, color="#555555", linestyle="--", linewidth=1, label=f"P{lower_pct:.0f}")
    ax.axvline(filtered.upper_bound, color="#555555", linestyle="--", linewidth=1, label=f"P{upper_pct:.0f}")
    ax.set_title(label)
    ax.set_xlabel("Recipe duration (s)")
    ax.set_ylabel("Density")
    ax.legend(frameon=True, fontsize=9)
    ax.text(
        0.98,
        0.97,
        f"raw n={len(values)}\nkept n={len(filtered.kept_values)}\nμ={mean:.1f}s\nσ={std:.1f}s",
        ha="right",
        va="top",
        transform=ax.transAxes,
        fontsize=9,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "alpha": 0.9, "edgecolor": "#DDDDDD"},
    )


def plot_recipe_timeline(recipes: list[Recipe], title: str = "") -> None:
    if not recipes:
        print("No complete recipes to plot.")
        return
    recipes_sorted = sorted(recipes, key=recipe_start_time)
    fig, ax = plt.subplots(figsize=(14, max(4, len(recipes_sorted) * 0.5 + 2)))
    setup_axes(ax)

    step_colors = {name: PLOT_COLORS[i % len(PLOT_COLORS)] for i, name in enumerate(LEGO_RECIPE_STEPS)}
    yticks, ylabels = [], []
    for index, recipe in enumerate(recipes_sorted):
        first_start = recipe_start_time(recipe)
        yticks.append(index)
        ylabels.append(f"Recipe {index + 1}")
        for step in LEGO_RECIPE_STEPS:
            entry = recipe.get(step)
            if entry is None:
                continue
            start = entry["start_time"] - first_start
            duration = entry["end_time"] - entry["start_time"]
            ax.barh(index, duration, left=start, color=step_colors[step], edgecolor="white", linewidth=0.5, height=0.7)

    legend_handles = [Patch(facecolor=step_colors[step], label=step) for step in LEGO_RECIPE_STEPS]
    ax.legend(handles=legend_handles, loc="lower right", frameon=True, fontsize=9)
    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels)
    ax.set_xlabel("Time from first step (s)")
    ax.set_title(title or f"Lego Recipe Gantt — {len(recipes_sorted)} recipes")
    fig.patch.set_facecolor("white")
    fig.tight_layout(pad=1.2)


def plot_task_distributions(recipes: list[Recipe], label: str = "", color: str = PLOT_COLORS[0]) -> None:
    if not recipes:
        print("No recipes to plot.")
        return
    steps = [step for step in LEGO_RECIPE_STEPS if any(step in recipe for recipe in recipes)]
    ncols = 3
    nrows = (len(steps) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, max(5, 4.5 * nrows)))
    axes = np.array(axes).flatten()
    fig.patch.set_facecolor("white")

    for index, step in enumerate(steps):
        ax = axes[index]
        setup_axes(ax)
        durations = [value for recipe in recipes if (value := task_duration(recipe, step)) is not None]
        if not durations:
            ax.set_visible(False)
            continue
        tick = violin_or_bar(ax, durations, color, step, 1)
        ax.set_xticks([1])
        ax.set_xticklabels([tick])
        ax.set_ylabel("Duration (s)")
        ax.set_title(step, pad=10)
        ax.set_xlim(0.3, 1.7)

    for index in range(len(steps), len(axes)):
        axes[index].set_visible(False)

    recipe_label = f" — {label}" if label else ""
    fig.suptitle(f"Per-task duration distribution{recipe_label}  (n={len(recipes)} recipes)")
    fig.tight_layout(rect=[0, 0, 1, 0.94])


def plot_recipe_durations(recipes: list[Recipe], label: str = "", color: str = PLOT_COLORS[0]) -> None:
    if not recipes:
        print("No recipes to plot.")
        return
    durations = [recipe_duration(recipe) for recipe in recipes]
    fig, (ax_vio, ax_line) = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor("white")

    setup_axes(ax_vio)
    violin_or_bar(ax_vio, durations, color, label or "recipes", 1)
    ax_vio.set_xticks([1])
    ax_vio.set_xticklabels([f"{label or 'recipes'}\n(n={len(durations)}, μ={np.mean(durations):.1f}s)"])
    ax_vio.set_ylabel("Total duration (s)")
    ax_vio.set_title("End-to-end recipe duration")
    ax_vio.set_xlim(0.3, 1.7)

    setup_axes(ax_line)
    sorted_durations = [recipe_duration(recipe) for recipe in sorted(recipes, key=recipe_start_time)]
    ax_line.plot(range(1, len(sorted_durations) + 1), sorted_durations, marker="o", color=color, linewidth=1.5, alpha=0.8)
    ax_line.axhline(np.mean(sorted_durations), color="black", linestyle="--", linewidth=1, label=f"Mean={np.mean(sorted_durations):.1f}s")
    ax_line.set_xlabel("Recipe # (chronological order)")
    ax_line.set_ylabel("Duration (s)")
    ax_line.set_title("Recipe duration over time")
    ax_line.legend(frameon=True)

    title_label = f" — {label}" if label else ""
    fig.suptitle(f"Lego Recipe Durations{title_label}")
    fig.tight_layout(rect=[0, 0, 1, 0.94])


def plot_gaussian_distribution(
    recipes: list[Recipe],
    label: str = "",
    color: str = PLOT_COLORS[0],
    percentile_range: tuple[float, float] = DEFAULT_PERCENTILE_RANGE,
) -> None:
    if not recipes:
        print("No recipes to plot.")
        return
    fig, ax = plt.subplots(figsize=(9, 5.5))
    fig.patch.set_facecolor("white")
    _draw_gaussian(ax, [recipe_duration(recipe) for recipe in recipes], label or "recipes", color, percentile_range)
    lower_pct, upper_pct = percentile_range
    title_label = f" — {label}" if label else ""
    ax.set_title(f"Gaussian distribution of recipe durations{title_label}\ntrimmed to P{lower_pct:.0f}-P{upper_pct:.0f}")
    fig.tight_layout(pad=1.2)


def plot_compare_gaussians(
    recipes_a: list[Recipe],
    recipes_b: list[Recipe],
    label_a: str,
    label_b: str,
    percentile_range: tuple[float, float] = DEFAULT_PERCENTILE_RANGE,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), sharey=True)
    fig.patch.set_facecolor("white")
    _draw_gaussian(axes[0], [recipe_duration(recipe) for recipe in recipes_a], label_a, PLOT_COLORS[0], percentile_range)
    _draw_gaussian(axes[1], [recipe_duration(recipe) for recipe in recipes_b], label_b, PLOT_COLORS[1], percentile_range)
    lower_pct, upper_pct = percentile_range
    fig.suptitle(f"Gaussian duration comparison trimmed to P{lower_pct:.0f}-P{upper_pct:.0f}")
    fig.tight_layout(rect=[0, 0, 1, 0.94])


def plot_waiting_times(recipes: list[Recipe], label: str = "") -> None:
    consecutive_steps = list(zip(LEGO_RECIPE_STEPS, LEGO_RECIPE_STEPS[1:]))
    fig, axes = plt.subplots(1, len(consecutive_steps), figsize=(14, 5), sharey=False)
    fig.patch.set_facecolor("white")

    for index, (step_a, step_b) in enumerate(consecutive_steps):
        ax = axes[index]
        setup_axes(ax)
        waits = [
            value for recipe in recipes
            if (value := waiting_time(recipe, step_a, step_b)) is not None and value >= 0
        ]
        if not waits:
            ax.set_visible(False)
            continue
        violin_or_bar(ax, waits, PLOT_COLORS[index % len(PLOT_COLORS)], f"{step_a}→{step_b}", 1)
        ax.set_xticks([1])
        ax.set_xticklabels([f"{step_a}→{step_b}\n(n={len(waits)}, μ={np.mean(waits):.1f}s)"])
        ax.set_ylabel("Wait (s)")
        ax.set_xlim(0.3, 1.7)

    title_label = f" — {label}" if label else ""
    fig.suptitle(f"Waiting times between recipe steps{title_label}  (n={len(recipes)} recipes)")
    fig.tight_layout(rect=[0, 0, 1, 0.94])


def plot_compare_durations(
    recipes_a: list[Recipe], recipes_b: list[Recipe], label_a: str, label_b: str
) -> None:
    dur_a = [recipe_duration(recipe) for recipe in sorted(recipes_a, key=recipe_start_time)]
    dur_b = [recipe_duration(recipe) for recipe in sorted(recipes_b, key=recipe_start_time)]

    fig, ax_vio = plt.subplots(1, 1, figsize=(8, 6))
    fig.patch.set_facecolor("white")

    setup_axes(ax_vio)
    for pos, (durations, label, color) in enumerate(
        [(dur_a, label_a, PLOT_COLORS[0]), (dur_b, label_b, PLOT_COLORS[1])], start=1
    ):
        if durations:
            violin_or_bar(ax_vio, durations, color, label, pos)
    ax_vio.set_xticks([1, 2])
    ax_vio.set_xticklabels([
        f"{label_a}\n(n={len(dur_a)}, μ={np.mean(dur_a):.1f}s)" if dur_a else label_a,
        f"{label_b}\n(n={len(dur_b)}, μ={np.mean(dur_b):.1f}s)" if dur_b else label_b,
    ])
    ax_vio.set_ylabel("Total recipe duration (s)")
    ax_vio.set_title("End-to-end duration comparison")
    ax_vio.set_xlim(0.3, 2.7)

    fig.suptitle(f"Recipe Duration — {label_a} vs {label_b}")
    fig.tight_layout(rect=[0, 0, 1, 0.94])


def plot_compare_durations_stacked(
    variant_rows: list[tuple[str, list[Recipe], list[Recipe]]],
    label_a: str,
    label_b: str,
    title: str = "",
    normalized: bool = False,
) -> None:
    """Stack per-variant ID-vs-DISTANCE violins in a single figure.

    Each entry in ``variant_rows`` is ``(variant_name, recipes_a, recipes_b)`` and
    produces one row with an end-to-end duration violin.
    """
    rows = [(name, a, b) for (name, a, b) in variant_rows if a or b]
    if not rows:
        return

    unit = "" if normalized else "s"
    value_label = "Duration / mean(reference)" if normalized else "Duration (s)"
    mean_format = ".2f" if normalized else ".1f"

    nrows = len(rows)
    fig, axes = plt.subplots(nrows, 1, figsize=(8, 5 * nrows), squeeze=False)
    fig.patch.set_facecolor("white")

    row_axes: list = []
    for row_index, (variant_name, recipes_a, recipes_b) in enumerate(rows):
        ax_vio = axes[row_index][0]
        dur_a = [recipe_duration(recipe) for recipe in sorted(recipes_a, key=recipe_start_time)]
        dur_b = [recipe_duration(recipe) for recipe in sorted(recipes_b, key=recipe_start_time)]

        setup_axes(ax_vio)
        for pos, (durations, color) in enumerate(
            [(dur_a, PLOT_COLORS[0]), (dur_b, PLOT_COLORS[1])], start=1
        ):
            if durations:
                violin_or_bar(ax_vio, durations, color, variant_name, pos)
        ax_vio.set_xticks([1, 2])
        ax_vio.set_xticklabels(
            [
                f"{label_a}\n(n={len(dur_a)}, μ={np.mean(dur_a):{mean_format}}{unit})"
                if dur_a
                else label_a,
                f"{label_b}\n(n={len(dur_b)}, μ={np.mean(dur_b):{mean_format}}{unit})"
                if dur_b
                else label_b,
            ]
        )
        ax_vio.set_ylabel(value_label)
        ax_vio.set_title(f"{variant_name} — End-to-end duration")
        ax_vio.set_xlim(0.3, 2.7)
        row_axes.append(ax_vio)

    if row_axes:
        y_min = min(ax.get_ylim()[0] for ax in row_axes)
        y_max = max(ax.get_ylim()[1] for ax in row_axes)
        for ax in row_axes:
            ax.set_ylim(y_min, y_max)

    suptitle = title or f"Recipe Duration — {label_a} vs {label_b}"
    if normalized:
        suptitle += "  (normalized)"
    fig.suptitle(suptitle, fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])


def plot_compare_tasks(
    recipes_a: list[Recipe],
    recipes_b: list[Recipe],
    label_a: str,
    label_b: str,
    normalized: bool = False,
) -> None:
    steps = [
        step for step in LEGO_RECIPE_STEPS
        if any(step in recipe for recipe in recipes_a) or any(step in recipe for recipe in recipes_b)
    ]
    ncols = 3
    nrows = (len(steps) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, max(5, 4.5 * nrows)))
    axes = np.array(axes).flatten()
    fig.patch.set_facecolor("white")

    for index, step in enumerate(steps):
        ax = axes[index]
        setup_axes(ax)
        dur_a = [value for recipe in recipes_a if (value := task_duration(recipe, step)) is not None]
        dur_b = [value for recipe in recipes_b if (value := task_duration(recipe, step)) is not None]
        tick_labels: list[str] = []
        for pos, (durations, label, color) in enumerate(
            [(dur_a, label_a, PLOT_COLORS[0]), (dur_b, label_b, PLOT_COLORS[1])], start=1
        ):
            if not durations:
                tick_labels.append(label)
                continue
            tick_labels.append(violin_or_bar(ax, durations, color, label, pos))
        ax.set_xticks([1, 2])
        ax.set_xticklabels(tick_labels)
        ax.set_ylabel("Duration (s)")
        ax.set_title(step, pad=10)
        ax.set_xlim(0.3, 2.7)
        if normalized:
            all_values = dur_a + dur_b
            max_value = max(all_values) if all_values else 1
            ax.set_ylim(0, max_value * 1.15)

    for index in range(len(steps), len(axes)):
        axes[index].set_visible(False)

    fig.suptitle(f"Per-task duration — {label_a} vs {label_b}")
    fig.tight_layout(rect=[0, 0, 1, 0.94])


def plot_compare_waiting_times(
    recipes_a: list[Recipe], recipes_b: list[Recipe], label_a: str, label_b: str
) -> None:
    consecutive_steps = list(zip(LEGO_RECIPE_STEPS, LEGO_RECIPE_STEPS[1:]))
    fig, axes = plt.subplots(1, len(consecutive_steps), figsize=(14, 5))
    fig.patch.set_facecolor("white")

    for index, (step_a, step_b) in enumerate(consecutive_steps):
        ax = axes[index]
        setup_axes(ax)
        waits_a = [
            value for recipe in recipes_a
            if (value := waiting_time(recipe, step_a, step_b)) is not None and value >= 0
        ]
        waits_b = [
            value for recipe in recipes_b
            if (value := waiting_time(recipe, step_a, step_b)) is not None and value >= 0
        ]
        tick_labels: list[str] = []
        for pos, (waits, label, color) in enumerate(
            [(waits_a, label_a, PLOT_COLORS[0]), (waits_b, label_b, PLOT_COLORS[1])], start=1
        ):
            if not waits:
                tick_labels.append(label)
                continue
            tick_labels.append(violin_or_bar(ax, waits, color, label, pos))
        ax.set_xticks([1, 2])
        ax.set_xticklabels(tick_labels)
        ax.set_ylabel("Wait (s)")
        ax.set_title(f"{step_a}→{step_b}", pad=10)
        ax.set_xlim(0.3, 2.7)

    fig.suptitle(f"Waiting times between steps — {label_a} vs {label_b}")
    fig.tight_layout(rect=[0, 0, 1, 0.94])


def plot_speedup_comparison(
    id_recipes_sim: list[Recipe],
    dist_recipes_sim: list[Recipe],
    id_recipes_opcua: list[Recipe],
    dist_recipes_opcua: list[Recipe],
    topic_label: str,
) -> None:
    """Bar chart comparing the ID→DISTANCE speedup for sim vs. OPC-UA runs."""

    def speedup(id_recipes: list[Recipe], dist_recipes: list[Recipe]) -> float:
        if not id_recipes or not dist_recipes:
            return 0.0
        mean_id = float(np.mean([recipe_duration(r) for r in id_recipes]))
        mean_dist = float(np.mean([recipe_duration(r) for r in dist_recipes]))
        return mean_id / mean_dist if mean_dist > 0 else 0.0

    speedup_sim = speedup(id_recipes_sim, dist_recipes_sim)
    speedup_opcua = speedup(id_recipes_opcua, dist_recipes_opcua)

    if not speedup_sim and not speedup_opcua:
        print("Not enough data to plot speedup comparison.")
        return

    fig, ax = plt.subplots(figsize=(8, 6))
    setup_axes(ax)
    variants = ["Simulation", "Real"]
    speedups = [speedup_sim, speedup_opcua]
    colors = [PLOT_COLORS[0], PLOT_COLORS[1]]

    bars = ax.bar(variants, speedups, color=colors, width=0.5)
    ax.set_ylabel("Speedup (ID duration / DISTANCE duration)")
    ax.set_title(f"Speedup from ID to DISTANCE Metric for {topic_label}")
    ax.axhline(1, color="grey", linestyle="--", linewidth=1)
    ax.set_ylim(bottom=0, top=max(speedups) * 1.15 if speedups else 1.2)

    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{height:.2f}x",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
        )

    fig.tight_layout()
