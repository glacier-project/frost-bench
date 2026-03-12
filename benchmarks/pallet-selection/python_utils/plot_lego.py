"""Plot Lego recipe execution times from result JSON files.

This module reconstructs end-to-end Lego recipe durations and per-task timing
distributions from the output files produced by LegoScheduler.

Usage:
    python plot_lego.py --directory results/lego/lego-sim-20260311_103354
    python plot_lego.py --directory results/lego/   # aggregates all runs
    python plot_lego.py --directory results/lego/run1 --compare results/lego/run2
    python plot_lego.py --base-dir results/lego/    # topic-grouped view
    python plot_lego.py --base-dir results/lego/ --topic movements
"""

import argparse
import json
import re
import textwrap
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

# Reuse the same visual style as plot.py
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

# Ordered steps of the Lego recipe (used for sorting subplots)
# Full recipe: LD → RBTC → QC → DISASSEMBLE → RESERVE → PUT_BACK
# Movements recipe (no cells): RBTC → QC → DISASSEMBLE → PUT_BACK
# Functions filter by presence, so both variants are handled automatically.
LEGO_RECIPE_STEPS = ["LD", "RBTC", "QC", "DISASSEMBLE", "RESERVE", "PUT_BACK"]
LEGO_RECIPE_END = "PUT_BACK"
PLOT_COLORS = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3", "#937860"]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _load_json(filepath: str) -> dict:
    with open(filepath) as f:
        return json.load(f)


def _flatten_tasks(data: dict) -> dict[str, dict]:
    """Return a flat dict {task_id: entry} from a schedule JSON."""
    tasks: dict[str, dict] = {}
    for entries in data.get("mapping", {}).values():
        for entry in entries:
            tid = entry["task"]["id"]
            tasks[tid] = entry
    return tasks


def _reconstruct_recipes(tasks: dict[str, dict]) -> list[dict[str, dict]]:
    """Group tasks into complete Lego recipes by following the dependency chain.

    Each recipe is a dict {task_name: entry} for every step that belongs to
    the same chain starting with an LD task (no dependencies).

    Returns:
        List of recipes. Each recipe is a dict mapping task name → task entry.
    """
    # Index: dependency_id → list of tasks that require it
    dependents: dict[str, list[str]] = defaultdict(list)
    for tid, entry in tasks.items():
        for dep in entry["task"].get("dependencies", []):
            dependents[dep].append(tid)

    # Roots of recipes: tasks with no dependencies (first step = RBTC)
    roots = [
        tid
        for tid, entry in tasks.items()
        if not entry["task"].get("dependencies")
    ]

    recipes = []
    for root_id in roots:
        recipe: dict[str, dict] = {}
        stack = [root_id]
        while stack:
            tid = stack.pop()
            entry = tasks[tid]
            name = entry["task"]["name"]
            recipe[name] = entry
            stack.extend(dependents.get(tid, []))

        # Keep only recipes that have the last step with timing (at least one start step present)
        last = recipe.get(LEGO_RECIPE_END)
        first_time = next(
            (e["start_time"] for s in LEGO_RECIPE_STEPS
             if (e := recipe.get(s)) is not None and e.get("start_time") is not None),
            None,
        )
        if last is not None and last.get("end_time") is not None and first_time is not None:
            recipes.append(recipe)

    return recipes


def load_lego_results(filepath: str) -> list[dict[str, dict]]:
    """Load and reconstruct Lego recipes from a single result JSON file.

    Returns:
        List of recipe dicts ({task_name: entry}).
    """
    data = _load_json(filepath)
    tasks = _flatten_tasks(data)
    return _reconstruct_recipes(tasks)


def get_json_files(directory: str) -> list[str]:
    """Recursively find all JSON files in a directory."""
    return [str(p) for p in Path(directory).rglob("*.json")]


def _extract_metric(filepath: str) -> str | None:
    """Return the metric name embedded in a result filename, e.g. 'DISTANCE', 'ID', 'RANDOM'.

    Filename pattern: <type>_<instance>_<run_type>_<METRIC>_<uuid>.json
    """
    stem = Path(filepath).stem
    match = re.search(r"_(DISTANCE|RANDOM|ID)_", stem)
    return match.group(1) if match else None


def _load_recipes_by_metric(directory: str) -> dict[str, list[dict[str, dict]]]:
    """Load all JSON results under *directory* and group recipes by metric.

    Returns:
        {metric_name: [recipe, ...]}
    """
    by_metric: dict[str, list[dict[str, dict]]] = defaultdict(list)
    for filepath in get_json_files(directory):
        metric = _extract_metric(filepath)
        if metric is None:
            continue
        by_metric[metric].extend(load_lego_results(filepath))
    return dict(by_metric)


def _recipe_start_time(recipe: dict[str, dict]) -> float:
    """Return the start_time of the first present step in the recipe."""
    for step in LEGO_RECIPE_STEPS:
        entry = recipe.get(step)
        if entry is not None and entry.get("start_time") is not None:
            return entry["start_time"]
    raise ValueError(f"Recipe has no known step with a start_time: {list(recipe.keys())}")


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------


def recipe_duration(recipe: dict[str, dict]) -> float:
    """End-to-end duration: from first step start_time to PUT_BACK end_time (seconds)."""
    start = _recipe_start_time(recipe)
    end = recipe[LEGO_RECIPE_END]["end_time"]
    return end - start


def task_duration(recipe: dict[str, dict], task_name: str) -> float | None:
    """Duration of a single task step within a recipe (seconds)."""
    entry = recipe.get(task_name)
    if entry is None:
        return None
    return entry["end_time"] - entry["start_time"]


def waiting_time(recipe: dict[str, dict], step_a: str, step_b: str) -> float | None:
    """Gap between the end of step_a and the start of step_b (seconds)."""
    a = recipe.get(step_a)
    b = recipe.get(step_b)
    if a is None or b is None:
        return None
    return b["start_time"] - a["end_time"]


# ---------------------------------------------------------------------------
# Shared plot helpers (same style as plot.py)
# ---------------------------------------------------------------------------


def _setup_axes(ax: plt.Axes) -> None:
    ax.set_facecolor("#FAFAFA")
    ax.grid(True, alpha=0.4, axis="y", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#CCCCCC")
    ax.spines["bottom"].set_color("#CCCCCC")


def _violin_or_bar(ax: plt.Axes, data: list[float], color: str, label: str, pos: int) -> None:
    """Draw a violin if enough data points, otherwise a bar."""
    if len(data) >= 3:
        parts = ax.violinplot(
            [data],
            positions=[pos],
            showmeans=True,
            showextrema=True,
            quantiles=[[0.25, 0.75]],
            widths=0.6,
        )
        for body in parts["bodies"]:
            body.set_facecolor(color)
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
        for key in ("cbars", "cmins", "cmaxes"):
            if key in parts:
                parts[key].set_edgecolor("#555555")
                parts[key].set_linewidth(1)
    else:
        ax.bar(pos, np.mean(data), color=color, alpha=0.8, width=0.5)

    tick = f"{label}\n(n={len(data)}, μ={np.mean(data):.1f}s)"
    return tick


# ---------------------------------------------------------------------------
# Plot 1 — End-to-end recipe duration timeline
# ---------------------------------------------------------------------------


def plot_recipe_timeline(recipes: list[dict[str, dict]], title: str = "") -> None:
    """Bar chart showing each recipe's start time and total duration."""
    if not recipes:
        print("No complete recipes to plot.")
        return

    # Sort by first step start time
    recipes_sorted = sorted(recipes, key=_recipe_start_time)

    fig, ax = plt.subplots(figsize=(14, max(4, len(recipes_sorted) * 0.5 + 2)))
    _setup_axes(ax)

    colors = {name: PLOT_COLORS[i % len(PLOT_COLORS)] for i, name in enumerate(LEGO_RECIPE_STEPS)}
    yticks, ylabels = [], []

    for i, recipe in enumerate(recipes_sorted):
        first_start = _recipe_start_time(recipe)
        y = i
        yticks.append(y)
        ylabels.append(f"Recipe {i + 1}")

        for step in LEGO_RECIPE_STEPS:
            entry = recipe.get(step)
            if entry is None:
                continue
            start = entry["start_time"] - first_start
            dur = entry["end_time"] - entry["start_time"]
            ax.barh(y, dur, left=start, color=colors[step], edgecolor="white", linewidth=0.5, height=0.7)

    legend_handles = [Patch(facecolor=colors[s], label=s) for s in LEGO_RECIPE_STEPS if s in colors]
    ax.legend(handles=legend_handles, loc="lower right", frameon=True, fontsize=9)
    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels)
    ax.set_xlabel("Time from first step (s)")
    ax.set_title(title or f"Lego Recipe Gantt — {len(recipes_sorted)} recipes")
    fig.patch.set_facecolor("white")
    fig.tight_layout(pad=1.2)


# ---------------------------------------------------------------------------
# Plot 2 — Per-task duration distributions
# ---------------------------------------------------------------------------


def plot_task_distributions(
    recipes: list[dict[str, dict]],
    label: str = "",
    color: str = PLOT_COLORS[0],
) -> None:
    """Violin plots for each Lego task step duration."""
    if not recipes:
        print("No recipes to plot.")
        return

    steps = [s for s in LEGO_RECIPE_STEPS if any(s in r for r in recipes)]
    ncols = 3
    nrows = (len(steps) + ncols - 1) // ncols

    fig, axes = plt.subplots(nrows, ncols, figsize=(14, max(5, 4.5 * nrows)))
    axes = np.array(axes).flatten()
    fig.patch.set_facecolor("white")

    for idx, step in enumerate(steps):
        ax = axes[idx]
        _setup_axes(ax)
        durations = [d for r in recipes if (d := task_duration(r, step)) is not None]
        if not durations:
            ax.set_visible(False)
            continue
        tick = _violin_or_bar(ax, durations, color, step, 1)
        ax.set_xticks([1])
        ax.set_xticklabels([tick])
        ax.set_ylabel("Duration (s)")
        ax.set_title(step, pad=10)
        ax.set_xlim(0.3, 1.7)

    for idx in range(len(steps), len(axes)):
        axes[idx].set_visible(False)

    recipe_label = f" — {label}" if label else ""
    fig.suptitle(f"Per-task duration distribution{recipe_label}  (n={len(recipes)} recipes)")
    fig.tight_layout(rect=[0, 0, 1, 0.94])


# ---------------------------------------------------------------------------
# Plot 3 — End-to-end recipe durations
# ---------------------------------------------------------------------------


def plot_recipe_durations(
    recipes: list[dict[str, dict]],
    label: str = "",
    color: str = PLOT_COLORS[0],
) -> None:
    """Violin + scatter of total (LD→PUT_BACK) recipe durations."""
    if not recipes:
        print("No recipes to plot.")
        return

    durations = [recipe_duration(r) for r in recipes]

    fig, (ax_vio, ax_line) = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor("white")

    # Left: violin / bar
    _setup_axes(ax_vio)
    _violin_or_bar(ax_vio, durations, color, label or "recipes", 1)
    ax_vio.set_xticks([1])
    ax_vio.set_xticklabels([f"{label or 'recipes'}\n(n={len(durations)}, μ={np.mean(durations):.1f}s)"])
    ax_vio.set_ylabel("Total duration (s)")
    ax_vio.set_title("End-to-end recipe duration")
    ax_vio.set_xlim(0.3, 1.7)

    # Right: sequential trend
    _setup_axes(ax_line)
    recipes_sorted = sorted(recipes, key=_recipe_start_time)
    sorted_durations = [recipe_duration(r) for r in recipes_sorted]
    ax_line.plot(range(1, len(sorted_durations) + 1), sorted_durations, marker="o", color=color, linewidth=1.5, alpha=0.8)
    ax_line.axhline(np.mean(sorted_durations), color="black", linestyle="--", linewidth=1, label=f"Mean={np.mean(sorted_durations):.1f}s")
    ax_line.set_xlabel("Recipe # (chronological order)")
    ax_line.set_ylabel("Duration (s)")
    ax_line.set_title("Recipe duration over time")
    ax_line.legend(frameon=True)

    title_label = f" — {label}" if label else ""
    fig.suptitle(f"Lego Recipe Durations{title_label}")
    fig.tight_layout(rect=[0, 0, 1, 0.94])


# ---------------------------------------------------------------------------
# Plot 4 — Waiting times between steps
# ---------------------------------------------------------------------------


def plot_waiting_times(recipes: list[dict[str, dict]], label: str = "") -> None:
    """Visualize idle/waiting time between consecutive recipe steps."""
    consecutive_steps = list(zip(LEGO_RECIPE_STEPS, LEGO_RECIPE_STEPS[1:]))

    fig, axes = plt.subplots(1, len(consecutive_steps), figsize=(14, 5), sharey=False)
    fig.patch.set_facecolor("white")

    for idx, (step_a, step_b) in enumerate(consecutive_steps):
        ax = axes[idx]
        _setup_axes(ax)
        waits = [
            w
            for r in recipes
            if (w := waiting_time(r, step_a, step_b)) is not None and w >= 0
        ]
        if not waits:
            ax.set_visible(False)
            continue
        color = PLOT_COLORS[idx % len(PLOT_COLORS)]
        _violin_or_bar(ax, waits, color, f"{step_a}→{step_b}", 1)
        ax.set_xticks([1])
        ax.set_xticklabels([f"{step_a}→{step_b}\n(n={len(waits)}, μ={np.mean(waits):.1f}s)"])
        ax.set_ylabel("Wait (s)")
        ax.set_xlim(0.3, 1.7)

    title_label = f" — {label}" if label else ""
    fig.suptitle(f"Waiting times between recipe steps{title_label}  (n={len(recipes)} recipes)")
    fig.tight_layout(rect=[0, 0, 1, 0.94])


# ---------------------------------------------------------------------------
# Compare two directories
# ---------------------------------------------------------------------------


def plot_compare_durations(
    recipes_a: list[dict[str, dict]],
    recipes_b: list[dict[str, dict]],
    label_a: str,
    label_b: str,
) -> None:
    """Side-by-side violin of total recipe duration + sequential trend for both runs."""
    dur_a = [recipe_duration(r) for r in sorted(recipes_a, key=_recipe_start_time)]
    dur_b = [recipe_duration(r) for r in sorted(recipes_b, key=_recipe_start_time)]

    fig, (ax_vio, ax_line) = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor("white")

    # --- Violin ---
    _setup_axes(ax_vio)
    for i, (durations, label, color) in enumerate(
        [(dur_a, label_a, PLOT_COLORS[0]), (dur_b, label_b, PLOT_COLORS[1])]
    ):
        if not durations:
            continue
        _violin_or_bar(ax_vio, durations, color, label, i + 1)

    ax_vio.set_xticks([1, 2])
    ax_vio.set_xticklabels(
        [
            f"{label_a}\n(n={len(dur_a)}, μ={np.mean(dur_a):.1f}s)" if dur_a else label_a,
            f"{label_b}\n(n={len(dur_b)}, μ={np.mean(dur_b):.1f}s)" if dur_b else label_b,
        ]
    )
    ax_vio.set_ylabel("Total recipe duration (s)")
    ax_vio.set_title("End-to-end duration comparison")
    ax_vio.set_xlim(0.3, 2.7)

    # --- Trend lines ---
    _setup_axes(ax_line)
    for durations, label, color in [
        (dur_a, label_a, PLOT_COLORS[0]),
        (dur_b, label_b, PLOT_COLORS[1]),
    ]:
        if not durations:
            continue
        xs = range(1, len(durations) + 1)
        ax_line.plot(xs, durations, marker="o", color=color, linewidth=1.5, alpha=0.8, label=label)
        ax_line.axhline(
            np.mean(durations), color=color, linestyle="--", linewidth=1,
            alpha=0.6, label=f"{label} mean={np.mean(durations):.1f}s"
        )
    ax_line.set_xlabel("Recipe # (chronological order)")
    ax_line.set_ylabel("Duration (s)")
    ax_line.set_title("Recipe duration over time")
    ax_line.legend(frameon=True, fontsize=9)

    fig.suptitle(f"Recipe Duration — {label_a} vs {label_b}")
    fig.tight_layout(rect=[0, 0, 1, 0.94])


def plot_compare_tasks(
    recipes_a: list[dict[str, dict]],
    recipes_b: list[dict[str, dict]],
    label_a: str,
    label_b: str,
) -> None:
    """Side-by-side per-task duration comparison."""
    steps = [s for s in LEGO_RECIPE_STEPS if
             any(s in r for r in recipes_a) or any(s in r for r in recipes_b)]

    ncols = 3
    nrows = (len(steps) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, max(5, 4.5 * nrows)))
    axes = np.array(axes).flatten()
    fig.patch.set_facecolor("white")

    for idx, step in enumerate(steps):
        ax = axes[idx]
        _setup_axes(ax)
        dur_a = [d for r in recipes_a if (d := task_duration(r, step)) is not None]
        dur_b = [d for r in recipes_b if (d := task_duration(r, step)) is not None]

        tick_labels = []
        for pos, (durations, label, color) in enumerate(
            [(dur_a, label_a, PLOT_COLORS[0]), (dur_b, label_b, PLOT_COLORS[1])], start=1
        ):
            if not durations:
                tick_labels.append(label)
                continue
            tick = _violin_or_bar(ax, durations, color, label, pos)
            tick_labels.append(tick)

        ax.set_xticks([1, 2])
        ax.set_xticklabels(tick_labels)
        ax.set_ylabel("Duration (s)")
        ax.set_title(step, pad=10)
        ax.set_xlim(0.3, 2.7)

    for idx in range(len(steps), len(axes)):
        axes[idx].set_visible(False)

    fig.suptitle(f"Per-task duration — {label_a} vs {label_b}")
    fig.tight_layout(rect=[0, 0, 1, 0.94])


def plot_compare_waiting_times(
    recipes_a: list[dict[str, dict]],
    recipes_b: list[dict[str, dict]],
    label_a: str,
    label_b: str,
) -> None:
    """Side-by-side waiting time comparison between consecutive steps."""
    consecutive_steps = list(zip(LEGO_RECIPE_STEPS, LEGO_RECIPE_STEPS[1:]))

    fig, axes = plt.subplots(1, len(consecutive_steps), figsize=(14, 5))
    fig.patch.set_facecolor("white")

    for idx, (step_a, step_b) in enumerate(consecutive_steps):
        ax = axes[idx]
        _setup_axes(ax)
        waits_a = [w for r in recipes_a if (w := waiting_time(r, step_a, step_b)) is not None and w >= 0]
        waits_b = [w for r in recipes_b if (w := waiting_time(r, step_a, step_b)) is not None and w >= 0]

        color = PLOT_COLORS[idx % len(PLOT_COLORS)]
        tick_labels = []
        for pos, (waits, label, col) in enumerate(
            [(waits_a, label_a, PLOT_COLORS[0]), (waits_b, label_b, PLOT_COLORS[1])], start=1
        ):
            if not waits:
                tick_labels.append(label)
                continue
            tick = _violin_or_bar(ax, waits, col, label, pos)
            tick_labels.append(tick)

        ax.set_xticks([1, 2])
        ax.set_xticklabels(tick_labels)
        ax.set_ylabel("Wait (s)")
        ax.set_title(f"{step_a}→{step_b}", pad=10)
        ax.set_xlim(0.3, 2.7)

    fig.suptitle(f"Waiting times between steps — {label_a} vs {label_b}")
    fig.tight_layout(rect=[0, 0, 1, 0.94])


# ---------------------------------------------------------------------------
# Per-task 2×2 grid: sim/opcua × metric_a/metric_b
# ---------------------------------------------------------------------------


def plot_tasks_sim_opcua_by_metric(
    sim_by_metric: dict[str, list[dict[str, dict]]],
    opcua_by_metric: dict[str, list[dict[str, dict]]],
    metric_a: str,
    metric_b: str,
    topic_label: str = "",
) -> None:
    """One figure per task step, 2 rows × 2 columns.

    Row 0 — Simulation:  left = metric_a,  right = metric_b
    Row 1 — OPC-UA:      left = metric_a,  right = metric_b
    """
    buckets: dict[tuple[str, str], list[dict[str, dict]]] = {
        ("sim",   metric_a): sim_by_metric.get(metric_a, []),
        ("sim",   metric_b): sim_by_metric.get(metric_b, []),
        ("opcua", metric_a): opcua_by_metric.get(metric_a, []),
        ("opcua", metric_b): opcua_by_metric.get(metric_b, []),
    }
    all_recipes = [r for recs in buckets.values() for r in recs]
    steps = [s for s in LEGO_RECIPE_STEPS if any(s in r for r in all_recipes)]
    metric_colors = {metric_a: PLOT_COLORS[0], metric_b: PLOT_COLORS[1]}

    for step in steps:
        fig, axes = plt.subplots(2, 2, figsize=(10, 8), sharey=False)
        fig.patch.set_facecolor("white")

        for row, variant in enumerate(["sim", "opcua"]):
            variant_label = VARIANT_LABELS[variant]
            for col, metric in enumerate([metric_a, metric_b]):
                ax = axes[row][col]
                _setup_axes(ax)
                recipes = buckets[(variant, metric)]
                durations = [d for r in recipes if (d := task_duration(r, step)) is not None]
                if durations:
                    tick = _violin_or_bar(ax, durations, metric_colors[metric], metric, 1)
                    ax.set_xticks([1])
                    ax.set_xticklabels([tick])
                else:
                    ax.text(
                        0.5, 0.5, "No data",
                        ha="center", va="center",
                        transform=ax.transAxes, color="grey", fontsize=11,
                    )
                ax.set_ylabel("Duration (s)")
                ax.set_title(f"{variant_label} — {metric}", pad=8)
                ax.set_xlim(0.3, 1.7)

        suffix = f" [{topic_label}]" if topic_label else ""
        fig.suptitle(f"Task: {step}{suffix}  |  Sim (top) vs OPC-UA (bottom)")
        fig.tight_layout(rect=[0, 0, 1, 0.94])


# ---------------------------------------------------------------------------
# Delta plots: OPC-UA minus Simulation
# ---------------------------------------------------------------------------


def plot_delta_sim_opcua(
    sim_by_metric: dict[str, list[dict[str, dict]]],
    opcua_by_metric: dict[str, list[dict[str, dict]]],
    metric_a: str,
    metric_b: str,
    topic_label: str = "",
) -> None:
    """Two complementary views of the difference OPC-UA − Simulation.

    Figure 1 — Grouped bar chart (one group per task step):
        Two bars per group: metric_a delta and metric_b delta.
        Error bars = std of individual recipe durations.
        Horizontal zero line. Positive = OPC-UA is slower.

    Figure 2 — Heatmap (task steps × metrics):
        Cell colour = delta mean (diverging palette, centred at 0).
        Cell text shows Δ mean ± std in seconds.
    """
    all_recipes = [r for m in (sim_by_metric, opcua_by_metric) for recs in m.values() for r in recs]
    steps = [s for s in LEGO_RECIPE_STEPS if any(s in r for r in all_recipes)]
    metrics = [metric_a, metric_b]
    metric_colors = {metric_a: PLOT_COLORS[0], metric_b: PLOT_COLORS[1]}

    # --- collect per-task, per-metric delta (mean and std) ---
    delta_mean: dict[str, dict[str, float]] = {m: {} for m in metrics}
    delta_std:  dict[str, dict[str, float]] = {m: {} for m in metrics}

    for metric in metrics:
        sim_recs   = sim_by_metric.get(metric, [])
        opcua_recs = opcua_by_metric.get(metric, [])
        for step in steps:
            sim_d   = [d for r in sim_recs   if (d := task_duration(r, step)) is not None]
            opcua_d = [d for r in opcua_recs if (d := task_duration(r, step)) is not None]
            if sim_d and opcua_d:
                delta_mean[metric][step] = np.mean(opcua_d) - np.mean(sim_d)
                # error bar = sqrt(var_sim/n_sim + var_opcua/n_opcua)
                delta_std[metric][step] = np.sqrt(
                    np.var(sim_d, ddof=1) / len(sim_d) + np.var(opcua_d, ddof=1) / len(opcua_d)
                )
            else:
                delta_mean[metric][step] = float("nan")
                delta_std[metric][step]  = float("nan")

    suffix = f" — {topic_label}" if topic_label else ""

    # ── Figure 1: grouped bar chart ──────────────────────────────────────────
    fig1, ax1 = plt.subplots(figsize=(max(8, len(steps) * 1.8), 6))
    fig1.patch.set_facecolor("white")
    _setup_axes(ax1)

    n_metrics = len(metrics)
    bar_width  = 0.35
    x = np.arange(len(steps))

    for i, metric in enumerate(metrics):
        offsets = x + (i - (n_metrics - 1) / 2) * bar_width
        means  = [delta_mean[metric].get(s, float("nan")) for s in steps]
        errors = [delta_std[metric].get(s, float("nan"))  for s in steps]
        bars = ax1.bar(
            offsets, means, bar_width,
            color=metric_colors[metric], alpha=0.85,
            label=metric,
            yerr=errors, capsize=4, error_kw={"elinewidth": 1.2, "alpha": 0.7},
        )
        # annotate value above / below each bar
        for bar, mean in zip(bars, means):
            if np.isnan(mean):
                continue
            va  = "bottom" if mean >= 0 else "top"
            pad = 0.05 if mean >= 0 else -0.05
            ax1.text(
                bar.get_x() + bar.get_width() / 2,
                mean + pad,
                f"{mean:+.1f}s",
                ha="center", va=va, fontsize=8, fontweight="bold",
                color=metric_colors[metric],
            )

    ax1.axhline(0, color="black", linewidth=1.2, linestyle="--", alpha=0.6)
    ax1.set_xticks(x)
    ax1.set_xticklabels(steps)
    ax1.set_ylabel("Δ duration  (OPC-UA − Sim)  [s]")
    ax1.set_title(f"Per-task duration difference  (OPC-UA − Simulation){suffix}")
    ax1.legend(frameon=True, fontsize=9)
    fig1.tight_layout(pad=1.4)

    # ── Figure 2: heatmap ────────────────────────────────────────────────────
    matrix = np.array([[delta_mean[m].get(s, float("nan")) for s in steps] for m in metrics])

    fig2, ax2 = plt.subplots(figsize=(max(7, len(steps) * 1.4), 3.5))
    fig2.patch.set_facecolor("white")

    vmax = np.nanmax(np.abs(matrix)) or 1.0
    im = ax2.imshow(matrix, cmap="RdBu_r", aspect="auto", vmin=-vmax, vmax=vmax)

    ax2.set_xticks(range(len(steps)))
    ax2.set_xticklabels(steps, fontsize=10)
    ax2.set_yticks(range(len(metrics)))
    ax2.set_yticklabels(metrics, fontsize=10)
    ax2.tick_params(left=False, bottom=False)

    for r, metric in enumerate(metrics):
        for c, step in enumerate(steps):
            val = delta_mean[metric].get(step, float("nan"))
            std = delta_std[metric].get(step, float("nan"))
            if np.isnan(val):
                txt = "n/a"
            else:
                txt = f"{val:+.1f}s\n±{std:.1f}s"
            ax2.text(
                c, r, txt,
                ha="center", va="center", fontsize=9, fontweight="bold",
                color="white" if abs(val) > vmax * 0.5 else "black",
            )

    cbar = fig2.colorbar(im, ax=ax2, orientation="vertical", fraction=0.04, pad=0.02)
    cbar.set_label("Δ [s]  (OPC-UA − Sim)", fontsize=9)
    ax2.set_title(f"Δ mean per task{suffix}  (red = OPC-UA slower, blue = OPC-UA faster)")
    fig2.tight_layout(pad=1.4)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _classify_run_dir(dirname: str) -> tuple[str, str] | None:
    """Classify a run directory name into (topic, variant).

    Topics:
        'full'      — complete lego recipe (LegoSim / LegoOpcua)
        'movements' — conveyor movements only (LegoMovementsSim / LegoMovementsOpcua)

    Variants: 'sim' or 'opcua'
    """
    name = Path(dirname).name.lower()
    # New naming: lego-sim-*, lego-opcua-*, movements-sim-*, movements-opcua-*
    if name.startswith("movements-sim") or name.startswith("sim-lego-movements"):
        return ("movements", "sim")
    if name.startswith("movements-opcua") or name.startswith("opcua-lego-movements"):
        return ("movements", "opcua")
    if name.startswith("lego-sim") or name.startswith("sim-lego"):
        return ("full", "sim")
    if name.startswith("lego-opcua") or name.startswith("opcua-lego"):
        return ("full", "opcua")
    return None


def _aggregate_by_topic(
    base_dir: str,
) -> dict[str, dict[str, list[dict[str, dict]]]]:
    """Scan base_dir and group all runs by topic and variant.

    Returns:
        {topic: {variant: [recipes]}}
        e.g. {'full': {'sim': [...], 'opcua': [...]}, 'movements': {...}}
    """
    result: dict[str, dict[str, list]] = {}
    base = Path(base_dir)
    if not base.is_dir():
        print(f"Base directory not found: {base_dir}")
        return result

    for run_dir in sorted(base.iterdir()):
        if not run_dir.is_dir():
            continue
        classification = _classify_run_dir(run_dir.name)
        if classification is None:
            continue
        topic, variant = classification
        files = [str(p) for p in run_dir.rglob("*.json")]
        if not files:
            continue
        recipes: list[dict[str, dict]] = []
        for f in files:
            recipes.extend(load_lego_results(f))
        if recipes:
            result.setdefault(topic, {}).setdefault(variant, []).extend(recipes)

    return result


def _aggregate_by_topic_metric(
    base_dir: str,
) -> dict[str, dict[str, dict[str, list[dict[str, dict]]]]]:
    """Like _aggregate_by_topic but also splits by metric.

    Returns:
        {topic: {variant: {metric: [recipes]}}}
    """
    result: dict[str, dict[str, dict[str, list]]] = {}
    base = Path(base_dir)
    if not base.is_dir():
        print(f"Base directory not found: {base_dir}")
        return result

    for run_dir in sorted(base.iterdir()):
        if not run_dir.is_dir():
            continue
        classification = _classify_run_dir(run_dir.name)
        if classification is None:
            continue
        topic, variant = classification
        for filepath in run_dir.rglob("*.json"):
            metric = _extract_metric(str(filepath))
            if metric is None:
                continue
            recipes = load_lego_results(str(filepath))
            if recipes:
                (
                    result
                    .setdefault(topic, {})
                    .setdefault(variant, {})
                    .setdefault(metric, [])
                    .extend(recipes)
                )

    return result


TOPIC_LABELS = {
    "full": "Full Lego Recipe",
    "movements": "Lego Conveyor Movements",
}
VARIANT_LABELS = {"sim": "Simulation", "opcua": "OPC-UA"}


def _run_topic_mode(
    base_dir: str,
    filter_topic: str | None,
    no_timeline: bool,
    metrics: tuple[str, str] | None = None,
) -> None:
    """Aggregate all runs by topic and plot.

    If *metrics* is given (e.g. ('DISTANCE', 'ID')), also split by metric and
    produce 4-way comparisons:
      - sim[metric_a]   vs sim[metric_b]
      - opcua[metric_a] vs opcua[metric_b]
      - sim[metric_a]   vs opcua[metric_a]
      - sim[metric_b]   vs opcua[metric_b]
    """
    if metrics:
        data_m = _aggregate_by_topic_metric(base_dir)
        if not data_m:
            print(f"No classifiable run directories found in {base_dir}")
            return
        metric_a, metric_b = (m.upper() for m in metrics)

        for topic, variants in data_m.items():
            if filter_topic and topic != filter_topic:
                continue
            topic_label = TOPIC_LABELS.get(topic, topic)
            print(f"\n{'='*60}")
            print(f"Topic: {topic_label}  |  metrics: {metric_a} vs {metric_b}")
            print(f"{'='*60}")

            for variant, by_metric in variants.items():
                vl = VARIANT_LABELS[variant]
                ra = by_metric.get(metric_a, [])
                rb = by_metric.get(metric_b, [])
                if ra:
                    _print_stats(ra, f"{topic_label} [{vl}] [{metric_a}]")
                if rb:
                    _print_stats(rb, f"{topic_label} [{vl}] [{metric_b}]")
                # metric_a vs metric_b within same variant
                if ra and rb:
                    la = f"{vl} [{metric_a}]"
                    lb = f"{vl} [{metric_b}]"
                    print(f"\n  {la} vs {lb}")
                    plot_compare_durations(ra, rb, la, lb)
                    plot_compare_tasks(ra, rb, la, lb)
                    plot_compare_waiting_times(ra, rb, la, lb)

            # sim vs opcua for each metric
            for metric in (metric_a, metric_b):
                rs = variants.get("sim", {}).get(metric, [])
                ro = variants.get("opcua", {}).get(metric, [])
                if rs and ro:
                    ls = f"Simulation [{metric}]"
                    lo = f"OPC-UA [{metric}]"
                    print(f"\n  {ls} vs {lo}")
                    plot_compare_durations(rs, ro, ls, lo)
                    plot_compare_tasks(rs, ro, ls, lo)
                    plot_compare_waiting_times(rs, ro, ls, lo)

            # Per-task 2×2 grid: one figure per step, sim on top, opcua on bottom
            sim_bm = variants.get("sim", {})
            opcua_bm = variants.get("opcua", {})
            if sim_bm or opcua_bm:
                plot_tasks_sim_opcua_by_metric(
                    sim_bm, opcua_bm, metric_a, metric_b, topic_label
                )
            # Delta plots: OPC-UA − Simulation
            if sim_bm and opcua_bm:
                plot_delta_sim_opcua(
                    sim_bm, opcua_bm, metric_a, metric_b, topic_label
                )
        return

    # ---- original metric-agnostic path ----
    data = _aggregate_by_topic(base_dir)
    if not data:
        print(f"No classifiable run directories found in {base_dir}")
        return

    for topic, variants in data.items():
        if filter_topic and topic != filter_topic:
            continue
        topic_label = TOPIC_LABELS.get(topic, topic)
        print(f"\n{'='*60}")
        print(f"Topic: {topic_label}")
        print(f"{'='*60}")

        # Print stats for each variant
        for variant, recipes in variants.items():
            _print_stats(recipes, f"{topic_label} [{VARIANT_LABELS[variant]}]")

        # Individual plots per variant
        for i, (variant, recipes) in enumerate(variants.items()):
            label = f"{topic_label} [{VARIANT_LABELS[variant]}]"
            _plot_individual(recipes, label, PLOT_COLORS[i], no_timeline)

        # Comparison plot if both sim and opcua exist
        if "sim" in variants and "opcua" in variants:
            label_sim = f"{topic_label} [Simulation]"
            label_opcua = f"{topic_label} [OPC-UA]"
            print(f"\nPlotting comparison: Simulation vs OPC-UA for {topic_label}…")
            plot_compare_durations(variants["sim"], variants["opcua"], label_sim, label_opcua)
            plot_compare_tasks(variants["sim"], variants["opcua"], label_sim, label_opcua)
            plot_compare_waiting_times(variants["sim"], variants["opcua"], label_sim, label_opcua)


def _load_all_recipes(directory: str) -> list[dict[str, dict]]:
    files = get_json_files(directory)
    if not files:
        print(f"No JSON files found in {directory}")
        return []
    all_recipes = []
    for f in files:
        all_recipes.extend(load_lego_results(f))
    return all_recipes


def _print_stats(recipes: list[dict[str, dict]], label: str) -> None:
    durations = [recipe_duration(r) for r in recipes]
    print(f"\n── {label} ──")
    print(f"  Recipes : {len(recipes)}")
    print(
        f"  Duration — mean: {np.mean(durations):.1f}s  "
        f"std: {np.std(durations):.1f}s  "
        f"min: {np.min(durations):.1f}s  "
        f"max: {np.max(durations):.1f}s"
    )
    for step in LEGO_RECIPE_STEPS:
        durs = [d for r in recipes if (d := task_duration(r, step)) is not None]
        if durs:
            print(f"  {step:12s} — mean: {np.mean(durs):.1f}s  std: {np.std(durs):.1f}s")


def _plot_individual(recipes: list[dict[str, dict]], label: str, color: str, no_timeline: bool) -> None:
    """Plot all individual charts for one run."""
    print(f"\n[{label}] Plotting individual charts…")
    plot_recipe_durations(recipes, label=label, color=color)
    plot_task_distributions(recipes, label=label, color=color)
    plot_waiting_times(recipes, label=label)
    if not no_timeline:
        plot_recipe_timeline(recipes, title=f"Lego Recipe Gantt — {label}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot Lego recipe execution times from result JSON files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            MODES
            -----
            Single directory (one run or a folder of aggregated runs):
              python plot_lego.py -d results/lego/lego-sim-20260311_103354
              python plot_lego.py -d results/lego/

            Compare two runs side-by-side (e.g. sim vs opcua):
              python plot_lego.py -d results/lego/lego-sim-20260311 -c results/lego/lego-opcua-20260311

            Compare two metrics within a directory (e.g. DISTANCE vs ID):
              python plot_lego.py -d results/lego/ -M DISTANCE ID
              python plot_lego.py -d results/lego/movements-sim-20260311 -M DISTANCE ID

            Topic mode — auto-group all runs under a base dir by recipe×variant:
              python plot_lego.py -b results/lego/
              python plot_lego.py -b results/lego/ --topic full
              python plot_lego.py -b results/lego/ --topic movements

            Topic mode with metric comparison (-b + -M):
              python plot_lego.py -b results/lego/ -M DISTANCE ID
              python plot_lego.py -b results/lego/ --topic movements -M DISTANCE ID

              Produces the following figures per topic:
                1. Per-variant violin: Sim[MA] vs Sim[MB], OPC-UA[MA] vs OPC-UA[MB]
                2. Per-metric violin:  Sim[MA] vs OPC-UA[MA], Sim[MB] vs OPC-UA[MB]
                3. Per-task 2×2 grid: one figure per step — Sim on top, OPC-UA on bottom,
                   left column = MA, right column = MB
                4. Delta bar chart:   Δ(OPC-UA − Sim) per task, bars grouped by metric
                5. Delta heatmap:     task steps × metrics, diverging colour (red = OPC-UA
                   slower, blue = OPC-UA faster), cell text = Δmean ± std

            OPTIONS
            -------
            --no-timeline   Skip Gantt bar-chart (speeds up rendering for large datasets).
            --topic         Restrict -b mode to 'full' (LegoSim/LegoOpcua) or
                            'movements' (LegoMovementsSim/LegoMovementsOpcua).

            OUTPUT
            ------
            JSON files are expected to live inside OUTPUT_DIR subfolders as written
            by LegoScheduler / Scheduler (e.g. results/lego/lego-sim-20260311/).
            The filename pattern is:  <type>_<instance>_<RUN_TYPE>_<METRIC>_<uuid>.json
        """),
    )
    parser.add_argument(
        "--directory",
        "-d",
        type=str,
        default="",
        help="Directory containing result JSON files (searched recursively).",
    )
    parser.add_argument(
        "--compare",
        "-c",
        type=str,
        default="",
        help="Second directory to compare against (also shown individually).",
    )
    parser.add_argument(
        "--base-dir",
        "-b",
        type=str,
        default="",
        help="Base results/lego/ directory: auto-groups all runs by topic and plots aggregated.",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default="",
        choices=["full", "movements"],
        help="Filter --base-dir mode to a single topic ('full' or 'movements').",
    )
    parser.add_argument(
        "--metric-compare",
        "-M",
        type=str,
        nargs=2,
        metavar=("METRIC_A", "METRIC_B"),
        help="Compare two metrics from --directory, e.g. -M DISTANCE ID",
    )
    parser.add_argument(
        "--no-timeline",
        action="store_true",
        help="Skip the Gantt timeline plots.",
    )
    args = parser.parse_args()

    # --- Topic mode ---
    if args.base_dir:
        _run_topic_mode(
            args.base_dir,
            args.topic or None,
            args.no_timeline,
            metrics=tuple(args.metric_compare) if args.metric_compare else None,
        )
        plt.show()
        return

    if not args.directory:
        parser.error("Either --directory or --base-dir is required.")

    # --- Metric comparison mode ---
    if args.metric_compare:
        metric_a, metric_b = (m.upper() for m in args.metric_compare)
        by_metric = _load_recipes_by_metric(args.directory)
        recipes_a = by_metric.get(metric_a, [])
        recipes_b = by_metric.get(metric_b, [])
        if not recipes_a:
            parser.error(f"No recipes found for metric '{metric_a}' in {args.directory}")
        if not recipes_b:
            parser.error(f"No recipes found for metric '{metric_b}' in {args.directory}")
        _print_stats(recipes_a, metric_a)
        _print_stats(recipes_b, metric_b)
        plot_compare_durations(recipes_a, recipes_b, metric_a, metric_b)
        plot_compare_tasks(recipes_a, recipes_b, metric_a, metric_b)
        plot_compare_waiting_times(recipes_a, recipes_b, metric_a, metric_b)
        if not args.no_timeline:
            label_a = Path(args.directory).name
            plot_recipe_timeline(recipes_a, title=f"Gantt — {label_a} [{metric_a}]")
            plot_recipe_timeline(recipes_b, title=f"Gantt — {label_a} [{metric_b}]")
        plt.show()
        return

    # --- Load ---
    recipes_a = _load_all_recipes(args.directory)
    if not recipes_a:
        return
    label_a = Path(args.directory).name
    _print_stats(recipes_a, label_a)

    recipes_b: list[dict[str, dict]] = []
    label_b = ""
    if args.compare:
        recipes_b = _load_all_recipes(args.compare)
        label_b = Path(args.compare).name
        if recipes_b:
            _print_stats(recipes_b, label_b)

    # --- Individual plots ---
    _plot_individual(recipes_a, label_a, PLOT_COLORS[0], args.no_timeline)
    if recipes_b:
        _plot_individual(recipes_b, label_b, PLOT_COLORS[1], args.no_timeline)

    # --- Comparison plots ---
    if recipes_b:
        print(f"\nPlotting comparison: {label_a} vs {label_b}…")
        plot_compare_durations(recipes_a, recipes_b, label_a, label_b)
        plot_compare_tasks(recipes_a, recipes_b, label_a, label_b)
        plot_compare_waiting_times(recipes_a, recipes_b, label_a, label_b)

    plt.show()


if __name__ == "__main__":
    main()
