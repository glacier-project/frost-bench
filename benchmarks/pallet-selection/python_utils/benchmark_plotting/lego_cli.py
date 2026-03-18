from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

from .common import PLOT_COLORS, maybe_show
from .lego_data import (
    DEFAULT_LEGO_METRICS,
    TOPIC_LABELS,
    VARIANT_LABELS,
    aggregate_by_topic_metric,
    load_all_recipes,
    load_recipes_by_metric,
    print_recipe_stats,
    normalize_recipes,
)
from .lego_plots import (
    plot_compare_durations,
    plot_compare_gaussians,
    plot_compare_tasks,
    plot_compare_waiting_times,
    plot_gaussian_distribution,
    plot_recipe_durations,
    plot_recipe_timeline,
    plot_task_distributions,
    plot_waiting_times,
    plot_speedup_comparison,
)
from .outliers import DEFAULT_PERCENTILE_RANGE, filter_recipes_by_duration_percentile

PLOT_TYPES = {"gaussian", "violin", "tasks", "waiting", "timeline"}


def selected_plot_modes(args: argparse.Namespace, parser: argparse.ArgumentParser) -> set[str]:
    selected = set()
    if args.gaussian:
        selected.add("gaussian")
    if args.violin:
        selected.add("violin")
    if args.tasks:
        selected.add("tasks")
    if args.waiting:
        selected.add("waiting")
    if args.timeline:
        selected.add("timeline")
    if args.compare_plots:
        selected.add("compare")
    if not selected & PLOT_TYPES:
        parser.error("Select at least one plot type with --gaussian, --violin, --tasks, --waiting, or --timeline.")
    return selected


def plot_individual(recipes, label: str, color: str, selected_plots: set[str]) -> None:
    print(f"\n[{label}] Plotting selected charts…")
    if "gaussian" in selected_plots:
        plot_gaussian_distribution(recipes, label=label, color=color, percentile_range=DEFAULT_PERCENTILE_RANGE)
    if "violin" in selected_plots:
        plot_recipe_durations(recipes, label=label, color=color)
    if "tasks" in selected_plots:
        plot_task_distributions(recipes, label=label, color=color)
    if "waiting" in selected_plots:
        plot_waiting_times(recipes, label=label)
    if "timeline" in selected_plots:
        plot_recipe_timeline(recipes, title=f"Lego Recipe Gantt — {label}")


def plot_selected_comparisons(recipes_a, recipes_b, label_a: str, label_b: str, selected_plots: set[str], normalized: bool = False) -> None:
    if "gaussian" in selected_plots:
        plot_compare_gaussians(recipes_a, recipes_b, label_a, label_b, DEFAULT_PERCENTILE_RANGE)
    if "violin" in selected_plots:
        plot_compare_durations(recipes_a, recipes_b, label_a, label_b)
    if "tasks" in selected_plots:
        plot_compare_tasks(recipes_a, recipes_b, label_a, label_b)
    if "waiting" in selected_plots:
        plot_compare_waiting_times(recipes_a, recipes_b, label_a, label_b)


def run_topic_mode(base_dir: str, filter_topic: str | None, metrics: list[str], selected_plots: set[str], args: argparse.Namespace) -> None:
    data = aggregate_by_topic_metric(base_dir, metrics)
    if not data:
        print(f"No classifiable run directories found in {base_dir}")
        return

    for topic in [topic for topic in data if not filter_topic or topic == filter_topic]:
        topic_label = TOPIC_LABELS.get(topic, topic)
        print(f"\n{'=' * 60}")
        print(f"Topic: {topic_label}")
        print(f"{'=' * 60}")
        topic_variants = data[topic]

        if args.speedup:
            id_recipes_sim = topic_variants.get("sim", {}).get("ID", [])
            dist_recipes_sim = topic_variants.get("sim", {}).get("DISTANCE", [])
            id_recipes_opcua = topic_variants.get("opcua", {}).get("ID", [])
            dist_recipes_opcua = topic_variants.get("opcua", {}).get("DISTANCE", [])

            if args.use_filter:
                id_recipes_sim = filter_recipes_by_duration_percentile(id_recipes_sim)
                dist_recipes_sim = filter_recipes_by_duration_percentile(dist_recipes_sim)
                id_recipes_opcua = filter_recipes_by_duration_percentile(id_recipes_opcua)
                dist_recipes_opcua = filter_recipes_by_duration_percentile(dist_recipes_opcua)

            plot_speedup_comparison(
                id_recipes_sim, dist_recipes_sim, id_recipes_opcua, dist_recipes_opcua, topic_label
            )

        # 1) Compare SIM vs OPC-UA for each metric (the original behaviour that the user wants to KEEP)
        for metric in metrics:
            sim_recipes = topic_variants.get("sim", {}).get(metric, [])
            opcua_recipes = topic_variants.get("opcua", {}).get(metric, [])

            if args.use_filter:
                sim_recipes = filter_recipes_by_duration_percentile(sim_recipes)
                opcua_recipes = filter_recipes_by_duration_percentile(opcua_recipes)

            if not sim_recipes and not opcua_recipes:
                continue

            print(f"\nMetric: {metric}")
            if sim_recipes:
                sim_label = f"{topic_label} [{metric}] [Simulation]"
                print_recipe_stats(sim_recipes, sim_label, include_outlier_evaluation="gaussian" in selected_plots)
                plot_individual(sim_recipes, sim_label, PLOT_COLORS[0], selected_plots)
            if opcua_recipes:
                opcua_label = f"{topic_label} [{metric}] [Real]"
                print_recipe_stats(opcua_recipes, opcua_label, include_outlier_evaluation="gaussian" in selected_plots)
                plot_individual(opcua_recipes, opcua_label, PLOT_COLORS[1], selected_plots)

            if "compare" in selected_plots and sim_recipes and opcua_recipes:
                print(f"\nPlotting comparison: {topic_label} [{metric}] Simulation vs Real…")

                if args.normalized:
                    sim_recipes, opcua_recipes = normalize_recipes(sim_recipes, opcua_recipes)

                plot_selected_comparisons(
                    sim_recipes,
                    opcua_recipes,
                    f"{topic_label} [{metric}] [Simulation]",
                    f"{topic_label} [{metric}] [Real]",
                    selected_plots,
                    normalized=args.normalized,
                )
                
        # 2) Additional comparison: compare metrics (ID vs DISTANCE) for the same context (SIM or Real)
        if "compare" in selected_plots and "ID" in metrics and "DISTANCE" in metrics:
            for variant, variant_name in [("sim", "Simulation"), ("opcua", "Real")]:
                id_recipes = topic_variants.get(variant, {}).get("ID", [])
                dist_recipes = topic_variants.get(variant, {}).get("DISTANCE", [])

                if args.use_filter:
                    id_recipes = filter_recipes_by_duration_percentile(id_recipes)
                    dist_recipes = filter_recipes_by_duration_percentile(dist_recipes)

                if id_recipes and dist_recipes:
                    print(f"\nPlotting metric comparison: {topic_label} [{variant_name}] ID vs DISTANCE…")

                    if args.normalized:
                        id_recipes, dist_recipes = normalize_recipes(id_recipes, dist_recipes)

                    plot_selected_comparisons(
                        id_recipes,
                        dist_recipes,
                        f"{topic_label} [{variant_name}] [ID]",
                        f"{topic_label} [{variant_name}] [DISTANCE]",
                        selected_plots,
                        normalized=args.normalized,
                    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot Lego recipe execution times from result JSON files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--directory", "-d", type=str, default="", help="Directory containing result JSON files.")
    parser.add_argument("--compare", "-c", type=str, default="", help="Second directory to compare against.")
    parser.add_argument("--base-dir", "-b", type=str, default="", help="Base results/lego directory grouped by topic/variant.")
    parser.add_argument("--topic", type=str, default="", choices=["full", "movements"], help="Restrict --base-dir mode to a single topic.")
    parser.add_argument("--metric-compare", "-M", nargs="*", default=DEFAULT_LEGO_METRICS, help="Metrics to include in comparisons. Default: ID DISTANCE")
    parser.add_argument("--gaussian", action="store_true", help="Plot Gaussian-like duration distributions with corner cases trimmed.")
    parser.add_argument("--violin", "--violing", dest="violin", action="store_true", help="Plot end-to-end duration violins.")
    parser.add_argument("--tasks", action="store_true", help="Plot per-task duration distributions.")
    parser.add_argument("--waiting", action="store_true", help="Plot waiting times between recipe steps.")
    parser.add_argument("--timeline", action="store_true", help="Plot Gantt-style recipe timelines.")
    parser.add_argument("--compare-plots", action="store_true", help="Also plot sim-vs-opcua or dir-vs-dir comparisons for the selected plot types.")
    parser.add_argument("--speedup", action="store_true", help="Show speedup comparison.")
    parser.add_argument("--use-filter", action="store_true", default=True, help="Use percentiles filter.")
    parser.add_argument("--no-filter", action="store_false", dest="use_filter", help="Disable percentiles filter.")
    parser.add_argument("--normalized", action="store_true", help="Normalize tasks relative to opcua.")
    
    args = parser.parse_args()

    selected_plots = selected_plot_modes(args, parser)
    metrics = [metric.upper() for metric in args.metric_compare]

    if args.base_dir:
        run_topic_mode(args.base_dir, args.topic or None, metrics, selected_plots, args)
        maybe_show()
        return

    if not args.directory:
        parser.error("Either --directory or --base-dir is required.")

    by_metric = load_recipes_by_metric(args.directory, metrics)
    if not by_metric:
        parser.error(f"No recipes found in {args.directory} for metrics: {', '.join(metrics)}")

    for index, metric in enumerate(metrics):
        recipes = by_metric.get(metric, [])
        if not recipes:
            continue
        label = f"{Path(args.directory).name} [{metric}]"
        print_recipe_stats(recipes, label, include_outlier_evaluation="gaussian" in selected_plots)
        plot_individual(recipes, label, PLOT_COLORS[index % len(PLOT_COLORS)], selected_plots)

    if args.compare:
        compare_by_metric = load_recipes_by_metric(args.compare, metrics)
        for metric in metrics:
            recipes_a = by_metric.get(metric, [])
            recipes_b = compare_by_metric.get(metric, [])
            if not recipes_a or not recipes_b or "compare" not in selected_plots:
                continue
            plot_selected_comparisons(
                recipes_a,
                recipes_b,
                f"{Path(args.directory).name} [{metric}]",
                f"{Path(args.compare).name} [{metric}]",
                selected_plots,
            )

    maybe_show()

if __name__ == "__main__":
    main()
