from __future__ import annotations

import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

from .common import PLOT_COLORS, setup_axes, violin_or_bar
from .lego_data import LEGO_RECIPE_END, LEGO_RECIPE_STEPS, Recipe, recipe_duration, recipe_start_time, task_duration, waiting_time
from .outliers import DEFAULT_PERCENTILE_RANGE, trim_percentile_range


def gaussian_pdf(xs: np.ndarray, mean: float, std: float) -> np.ndarray:
    if std <= 0:
        return np.zeros_like(xs)
    coeff = 1.0 / (std * math.sqrt(2.0 * math.pi))
    return coeff * np.exp(-0.5 * ((xs - mean) / std) ** 2)


def plot_gaussian_axis(
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
        ax.plot(xs, gaussian_pdf(xs, mean, std), color=color, linewidth=2.2, label="Gaussian fit")
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

    colors = {name: PLOT_COLORS[i % len(PLOT_COLORS)] for i, name in enumerate(LEGO_RECIPE_STEPS)}
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
            ax.barh(index, duration, left=start, color=colors[step], edgecolor="white", linewidth=0.5, height=0.7)

    legend_handles = [Patch(facecolor=colors[step], label=step) for step in LEGO_RECIPE_STEPS if step in colors]
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
    plot_gaussian_axis(ax, [recipe_duration(recipe) for recipe in recipes], label or "recipes", color, percentile_range)
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
    plot_gaussian_axis(axes[0], [recipe_duration(recipe) for recipe in recipes_a], label_a, PLOT_COLORS[0], percentile_range)
    plot_gaussian_axis(axes[1], [recipe_duration(recipe) for recipe in recipes_b], label_b, PLOT_COLORS[1], percentile_range)
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
            value
            for recipe in recipes
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


def plot_compare_durations(recipes_a: list[Recipe], recipes_b: list[Recipe], label_a: str, label_b: str) -> None:
    dur_a = [recipe_duration(recipe) for recipe in sorted(recipes_a, key=recipe_start_time)]
    dur_b = [recipe_duration(recipe) for recipe in sorted(recipes_b, key=recipe_start_time)]

    fig, (ax_vio, ax_line) = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor("white")

    setup_axes(ax_vio)
    for pos, (durations, label, color) in enumerate([(dur_a, label_a, PLOT_COLORS[0]), (dur_b, label_b, PLOT_COLORS[1])], start=1):
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

    setup_axes(ax_line)
    for durations, label, color in [(dur_a, label_a, PLOT_COLORS[0]), (dur_b, label_b, PLOT_COLORS[1])]:
        if not durations:
            continue
        xs = range(1, len(durations) + 1)
        ax_line.plot(xs, durations, marker="o", color=color, linewidth=1.5, alpha=0.8, label=label)
        ax_line.axhline(np.mean(durations), color=color, linestyle="--", linewidth=1, alpha=0.6, label=f"{label} mean={np.mean(durations):.1f}s")
    ax_line.set_xlabel("Recipe # (chronological order)")
    ax_line.set_ylabel("Duration (s)")
    ax_line.set_title("Recipe duration over time")
    ax_line.legend(frameon=True, fontsize=9)

    fig.suptitle(f"Recipe Duration — {label_a} vs {label_b}")
    fig.tight_layout(rect=[0, 0, 1, 0.94])


def plot_compare_tasks(
    recipes_a: list[Recipe], recipes_b: list[Recipe], label_a: str, label_b: str, normalized: bool = False
) -> None:
    steps = [
        step
        for step in LEGO_RECIPE_STEPS
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
        tick_labels = []
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


def plot_compare_waiting_times(recipes_a: list[Recipe], recipes_b: list[Recipe], label_a: str, label_b: str) -> None:
    consecutive_steps = list(zip(LEGO_RECIPE_STEPS, LEGO_RECIPE_STEPS[1:]))
    fig, axes = plt.subplots(1, len(consecutive_steps), figsize=(14, 5))
    fig.patch.set_facecolor("white")

    for index, (step_a, step_b) in enumerate(consecutive_steps):
        ax = axes[index]
        setup_axes(ax)
        waits_a = [value for recipe in recipes_a if (value := waiting_time(recipe, step_a, step_b)) is not None and value >= 0]
        waits_b = [value for recipe in recipes_b if (value := waiting_time(recipe, step_a, step_b)) is not None and value >= 0]
        tick_labels = []
        for pos, (waits, label, color) in enumerate([(waits_a, label_a, PLOT_COLORS[0]), (waits_b, label_b, PLOT_COLORS[1])], start=1):
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
    """Plots a bar chart comparing the speedup from ID to DISTANCE metric for sim and opcua."""
    mean_duration_id_sim = np.mean([recipe_duration(r) for r in id_recipes_sim]) if id_recipes_sim else 0
    mean_duration_dist_sim = np.mean([recipe_duration(r) for r in dist_recipes_sim]) if dist_recipes_sim else 0
    speedup_sim = (
        mean_duration_id_sim / mean_duration_dist_sim if mean_duration_dist_sim > 0 else 0
    )

    mean_duration_id_opcua = np.mean([recipe_duration(r) for r in id_recipes_opcua]) if id_recipes_opcua else 0
    mean_duration_dist_opcua = (
        np.mean([recipe_duration(r) for r in dist_recipes_opcua]) if dist_recipes_opcua else 0
    )
    speedup_opcua = (
        mean_duration_id_opcua / mean_duration_dist_opcua if mean_duration_dist_opcua > 0 else 0
    )

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
