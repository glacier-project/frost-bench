"""Plot Lego recipe execution times from result JSON files.

This module reconstructs end-to-end Lego recipe durations and per-task timing
distributions from the output files produced by LegoScheduler.

Usage:
    python plot_lego.py --directory lego/opcua-lego-20260309_084139
    python plot_lego.py --directory lego/            # aggregates all runs
    python plot_lego.py --directory lego/run1 --compare lego/run2
"""

import argparse
import json
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
# Matches gen_lego_job() in gen_instances.py: RBTC -> QC -> DISASSEMBLE -> PUT_BACK
LEGO_RECIPE_STEPS = ["RBTC", "QC", "DISASSEMBLE", "PUT_BACK"]
LEGO_RECIPE_START = "RBTC"
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

        # Keep only recipes that have at least the first and last step with timing
        first = recipe.get(LEGO_RECIPE_START)
        last = recipe.get(LEGO_RECIPE_END)
        if (
            first is not None and first.get("start_time") is not None
            and last is not None and last.get("end_time") is not None
        ):
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


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------


def recipe_duration(recipe: dict[str, dict]) -> float:
    """End-to-end duration: from RBTC.start_time to PUT_BACK.end_time (seconds)."""
    start = recipe[LEGO_RECIPE_START]["start_time"]
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

    # Sort by RBTC start time
    recipes_sorted = sorted(recipes, key=lambda r: r[LEGO_RECIPE_START]["start_time"])

    fig, ax = plt.subplots(figsize=(14, max(4, len(recipes_sorted) * 0.5 + 2)))
    _setup_axes(ax)

    colors = {name: PLOT_COLORS[i % len(PLOT_COLORS)] for i, name in enumerate(LEGO_RECIPE_STEPS)}
    yticks, ylabels = [], []

    for i, recipe in enumerate(recipes_sorted):
        ld_start = recipe[LEGO_RECIPE_START]["start_time"]
        y = i
        yticks.append(y)
        ylabels.append(f"Recipe {i + 1}")

        for step in LEGO_RECIPE_STEPS:
            entry = recipe.get(step)
            if entry is None:
                continue
            start = entry["start_time"] - ld_start
            dur = entry["end_time"] - entry["start_time"]
            ax.barh(y, dur, left=start, color=colors[step], edgecolor="white", linewidth=0.5, height=0.7)

    legend_handles = [Patch(facecolor=colors[s], label=s) for s in LEGO_RECIPE_STEPS if s in colors]
    ax.legend(handles=legend_handles, loc="lower right", frameon=True, fontsize=9)
    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels)
    ax.set_xlabel("Time from LD start (s)")
    ax.set_title(title or f"Lego Recipe Gantt — {len(recipes_sorted)} recipes")
    fig.patch.set_facecolor("white")
    plt.tight_layout()


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

    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 4 * nrows))
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
    fig.suptitle(
        f"Per-task duration distribution{recipe_label}  (n={len(recipes)} recipes)",
        y=1.01,
    )
    plt.tight_layout()


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

    fig, (ax_vio, ax_line) = plt.subplots(1, 2, figsize=(13, 5))
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
    recipes_sorted = sorted(recipes, key=lambda r: r[LEGO_RECIPE_START]["start_time"])
    sorted_durations = [recipe_duration(r) for r in recipes_sorted]
    ax_line.plot(range(1, len(sorted_durations) + 1), sorted_durations, marker="o", color=color, linewidth=1.5, alpha=0.8)
    ax_line.axhline(np.mean(sorted_durations), color="black", linestyle="--", linewidth=1, label=f"Mean={np.mean(sorted_durations):.1f}s")
    ax_line.set_xlabel("Recipe # (chronological order)")
    ax_line.set_ylabel("Duration (s)")
    ax_line.set_title("Recipe duration over time")
    ax_line.legend(frameon=True)

    title_label = f" — {label}" if label else ""
    fig.suptitle(f"Lego Recipe Durations{title_label}", y=1.01)
    plt.tight_layout()


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
    fig.suptitle(f"Waiting times between recipe steps{title_label}  (n={len(recipes)} recipes)", y=1.01)
    plt.tight_layout()


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
    dur_a = [recipe_duration(r) for r in sorted(recipes_a, key=lambda r: r[LEGO_RECIPE_START]["start_time"])]
    dur_b = [recipe_duration(r) for r in sorted(recipes_b, key=lambda r: r[LEGO_RECIPE_START]["start_time"])]

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

    fig.suptitle(f"Recipe Duration — {label_a} vs {label_b}", y=1.01)
    plt.tight_layout()


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
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 4 * nrows))
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

    fig.suptitle(
        f"Per-task duration — {label_a} vs {label_b}",
        y=1.01,
    )
    plt.tight_layout()


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

    fig.suptitle(
        f"Waiting times between steps — {label_a} vs {label_b}",
        y=1.01,
    )
    plt.tight_layout()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


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
        description="Plot Lego recipe execution times from result JSON files."
    )
    parser.add_argument(
        "--directory",
        "-d",
        required=True,
        type=str,
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
        "--no-timeline",
        action="store_true",
        help="Skip the Gantt timeline plots.",
    )
    args = parser.parse_args()

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
