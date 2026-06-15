"""Unified CLI for the benchmark_plotting package.

Subcommands:
    lego       Plot Lego recipe execution times.
    distance   Plot distance-recipe task durations.
    conveyor   Plot the conveyor graph topology.
"""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

from .conveyor import plot_conveyor
from .distance import (
    DEFAULT_METRICS,
    get_files_in_directory,
    group_distance_runs,
    plot_comparisons,
    plot_distributions,
)
from .lego import (
    DEFAULT_LEGO_METRICS,
    TOPIC_LABELS,
    Recipe,
    aggregate_by_topic_metric,
    load_recipes_by_metric,
    normalize_recipes,
    plot_compare_durations,
    plot_compare_durations_stacked,
    plot_compare_gaussians,
    plot_compare_tasks,
    plot_compare_waiting_times,
    plot_gaussian_distribution,
    plot_recipe_durations,
    plot_recipe_timeline,
    plot_speedup_comparison,
    plot_task_distributions,
    plot_waiting_times,
    print_recipe_stats,
)
from .outliers import DEFAULT_PERCENTILE_RANGE, filter_recipes_by_duration_percentile
from .style import PLOT_COLORS, maybe_show

LEGO_PLOT_TYPES = {"gaussian", "violin", "tasks", "waiting", "timeline"}


# ---------------------------------------------------------------------------
# Lego subcommand
# ---------------------------------------------------------------------------


def _selected_lego_plots(args: argparse.Namespace, parser: argparse.ArgumentParser) -> set[str]:
    selected: set[str] = set()
    for flag in ("gaussian", "violin", "tasks", "waiting", "timeline"):
        if getattr(args, flag):
            selected.add(flag)
    if args.compare_plots:
        selected.add("compare")
    if not selected & LEGO_PLOT_TYPES:
        parser.error(
            "Select at least one plot type with --gaussian, --violin, --tasks, --waiting, or --timeline."
        )
    return selected


def _plot_individual_lego(
    recipes: list[Recipe], label: str, color: str, selected_plots: set[str]
) -> None:
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


def _plot_lego_comparison(
    recipes_a: list[Recipe],
    recipes_b: list[Recipe],
    label_a: str,
    label_b: str,
    selected_plots: set[str],
    normalized: bool = False,
) -> None:
    if "gaussian" in selected_plots:
        plot_compare_gaussians(recipes_a, recipes_b, label_a, label_b, DEFAULT_PERCENTILE_RANGE)
    if "violin" in selected_plots:
        plot_compare_durations(recipes_a, recipes_b, label_a, label_b)
    if "tasks" in selected_plots:
        plot_compare_tasks(recipes_a, recipes_b, label_a, label_b, normalized=normalized)
    if "waiting" in selected_plots:
        plot_compare_waiting_times(recipes_a, recipes_b, label_a, label_b)


def _maybe_filter(recipes: list[Recipe], use_filter: bool) -> list[Recipe]:
    if not use_filter:
        return recipes
    return filter_recipes_by_duration_percentile(recipes)


def _run_topic_mode(
    base_dir: str,
    filter_topic: str | None,
    metrics: list[str],
    selected_plots: set[str],
    args: argparse.Namespace,
) -> None:
    data = aggregate_by_topic_metric(base_dir, metrics)
    if not data:
        print(f"No classifiable run directories found in {base_dir}")
        return

    for topic in [topic for topic in data if not filter_topic or topic == filter_topic]:
        topic_label = TOPIC_LABELS.get(topic, topic)
        print(f"\n{'=' * 60}\nTopic: {topic_label}\n{'=' * 60}")
        topic_variants = data[topic]

        if args.speedup:
            plot_speedup_comparison(
                _maybe_filter(topic_variants.get("sim", {}).get("ID", []), args.use_filter),
                _maybe_filter(topic_variants.get("sim", {}).get("DISTANCE", []), args.use_filter),
                _maybe_filter(topic_variants.get("opcua", {}).get("ID", []), args.use_filter),
                _maybe_filter(topic_variants.get("opcua", {}).get("DISTANCE", []), args.use_filter),
                topic_label,
            )

        # 1) SIM vs OPC-UA per metric
        for metric in metrics:
            sim_recipes = _maybe_filter(topic_variants.get("sim", {}).get(metric, []), args.use_filter)
            opcua_recipes = _maybe_filter(topic_variants.get("opcua", {}).get(metric, []), args.use_filter)
            if not sim_recipes and not opcua_recipes:
                continue

            print(f"\nMetric: {metric}")
            if sim_recipes:
                sim_label = f"{topic_label} [{metric}] [Simulation]"
                print_recipe_stats(sim_recipes, sim_label, include_outlier_evaluation="gaussian" in selected_plots)
                _plot_individual_lego(sim_recipes, sim_label, PLOT_COLORS[0], selected_plots)
            if opcua_recipes:
                opcua_label = f"{topic_label} [{metric}] [Real]"
                print_recipe_stats(opcua_recipes, opcua_label, include_outlier_evaluation="gaussian" in selected_plots)
                _plot_individual_lego(opcua_recipes, opcua_label, PLOT_COLORS[1], selected_plots)

            if "compare" in selected_plots and sim_recipes and opcua_recipes:
                print(f"\nPlotting comparison: {topic_label} [{metric}] Simulation vs Real…")
                if args.normalized:
                    sim_recipes, opcua_recipes = normalize_recipes(sim_recipes, opcua_recipes)
                _plot_lego_comparison(
                    sim_recipes,
                    opcua_recipes,
                    f"{topic_label} [{metric}] [Simulation]",
                    f"{topic_label} [{metric}] [Real]",
                    selected_plots,
                    normalized=args.normalized,
                )

        # 2) ID vs DISTANCE per variant
        if "compare" in selected_plots and "ID" in metrics and "DISTANCE" in metrics:
            variant_rows: list[tuple[str, list[Recipe], list[Recipe]]] = []
            for variant, variant_name in [("sim", "Simulation"), ("opcua", "Real")]:
                id_recipes = _maybe_filter(topic_variants.get(variant, {}).get("ID", []), args.use_filter)
                dist_recipes = _maybe_filter(topic_variants.get(variant, {}).get("DISTANCE", []), args.use_filter)
                if not id_recipes or not dist_recipes:
                    continue
                print(f"\nPreparing metric comparison: {topic_label} [{variant_name}] ID vs DISTANCE…")
                if args.normalized:
                    id_recipes, dist_recipes = normalize_recipes(id_recipes, dist_recipes)
                variant_rows.append((variant_name, id_recipes, dist_recipes))

            if variant_rows and "violin" in selected_plots:
                plot_compare_durations_stacked(
                    variant_rows,
                    label_a=f"{topic_label} [ID]",
                    label_b=f"{topic_label} [DISTANCE]",
                    title=f"Recipe Duration — {topic_label}: ID vs DISTANCE",
                    normalized=args.normalized,
                )

            non_violin = selected_plots - {"violin"}
            if non_violin:
                for variant_name, id_recipes, dist_recipes in variant_rows:
                    _plot_lego_comparison(
                        id_recipes,
                        dist_recipes,
                        f"{topic_label} [{variant_name}] [ID]",
                        f"{topic_label} [{variant_name}] [DISTANCE]",
                        non_violin,
                        normalized=args.normalized,
                    )


def _run_lego(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    selected = _selected_lego_plots(args, parser)
    metrics = [metric.upper() for metric in args.metric_compare]

    if args.base_dir:
        _run_topic_mode(args.base_dir, args.topic or None, metrics, selected, args)
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
        print_recipe_stats(recipes, label, include_outlier_evaluation="gaussian" in selected)
        _plot_individual_lego(recipes, label, PLOT_COLORS[index % len(PLOT_COLORS)], selected)

    if args.compare:
        compare_by_metric = load_recipes_by_metric(args.compare, metrics)
        for metric in metrics:
            recipes_a = by_metric.get(metric, [])
            recipes_b = compare_by_metric.get(metric, [])
            if not recipes_a or not recipes_b or "compare" not in selected:
                continue
            _plot_lego_comparison(
                recipes_a,
                recipes_b,
                f"{Path(args.directory).name} [{metric}]",
                f"{Path(args.compare).name} [{metric}]",
                selected,
            )

    maybe_show()


# ---------------------------------------------------------------------------
# Distance subcommand
# ---------------------------------------------------------------------------


def _run_distance(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.base_dir:
        grouped = group_distance_runs(args.base_dir, args.metrics)
        if not any(grouped.values()):
            print(f"No result files found under '{args.base_dir}'.")
            return
        for variant, files in grouped.items():
            if not files:
                continue
            label = {"sim": "Simulation", "opcua": "OPC-UA"}[variant]
            print(f"\n[{label}] {len(files)} files found")
            plot_distributions(files, args.metrics)
        if grouped["sim"] and grouped["opcua"]:
            print("\nPlotting Simulation vs OPC-UA comparison…")
            plot_comparisons(
                grouped["sim"],
                grouped["opcua"],
                "Simulation",
                "OPC-UA",
                args.metrics,
                normalized=args.normalized,
            )
        maybe_show()
        return

    if not args.directory:
        parser.error("Either --directory or --base-dir is required.")

    files = get_files_in_directory(args.directory, args.metrics)
    if args.compare:
        compare_files = get_files_in_directory(args.compare, args.metrics)
        plot_comparisons(
            files,
            compare_files,
            Path(args.directory).name,
            Path(args.compare).name,
            args.metrics,
            normalized=args.normalized,
        )
    else:
        plot_distributions(files, args.metrics)
    maybe_show()


# ---------------------------------------------------------------------------
# Argparse setup
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchmark-plot",
        description="Plot benchmark results for the pallet-selection experiments.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- lego ---
    lego_parser = subparsers.add_parser(
        "lego",
        help="Plot Lego recipe execution times.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    lego_parser.add_argument("--directory", "-d", type=str, default="", help="Directory with result JSON files.")
    lego_parser.add_argument("--compare", "-c", type=str, default="", help="Second directory to compare against.")
    lego_parser.add_argument("--base-dir", "-b", type=str, default="", help="Base results/lego directory grouped by topic/variant.")
    lego_parser.add_argument("--topic", type=str, default="", choices=["full", "movements"], help="Restrict --base-dir mode to a single topic.")
    lego_parser.add_argument("--metric-compare", "-M", nargs="*", default=DEFAULT_LEGO_METRICS, help="Metrics to include. Default: ID DISTANCE")
    lego_parser.add_argument("--gaussian", action="store_true", help="Plot Gaussian-like duration distributions.")
    lego_parser.add_argument("--violin", action="store_true", help="Plot end-to-end duration violins.")
    lego_parser.add_argument("--tasks", action="store_true", help="Plot per-task duration distributions.")
    lego_parser.add_argument("--waiting", action="store_true", help="Plot waiting times between recipe steps.")
    lego_parser.add_argument("--timeline", action="store_true", help="Plot Gantt-style recipe timelines.")
    lego_parser.add_argument("--compare-plots", action="store_true", help="Add sim-vs-opcua or dir-vs-dir comparison charts.")
    lego_parser.add_argument("--speedup", action="store_true", help="Show speedup comparison.")
    lego_parser.add_argument("--use-filter", action="store_true", default=True, help="Use percentile filter.")
    lego_parser.add_argument("--no-filter", action="store_false", dest="use_filter", help="Disable percentile filter.")
    lego_parser.add_argument("--normalized", action="store_true", help="Normalize tasks relative to opcua.")
    lego_parser.set_defaults(func=_run_lego)

    # --- distance ---
    distance_parser = subparsers.add_parser(
        "distance",
        help="Plot distance-recipe task durations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            MODES
            -----
            Single directory — compare metrics within one run:
              benchmark-plot distance -d results/distance/opcua-20260311_103354

            Compare two directories:
              benchmark-plot distance -d results/distance/sim-... -c results/distance/opcua-...

            Base-dir mode — auto-group sim-* and opcua-* subfolders:
              benchmark-plot distance -b results/distance/
            """
        ),
    )
    distance_parser.add_argument("--directory", "-d", type=str, default="", help="Directory with result files.")
    distance_parser.add_argument("--compare", "-c", type=str, default="", help="Directory to compare against.")
    distance_parser.add_argument("--base-dir", "-b", type=str, default="", help="Base directory grouping sim-* and opcua-* subfolders.")
    distance_parser.add_argument("--metrics", "-m", nargs="*", default=DEFAULT_METRICS, help="Metric names to include.")
    distance_parser.add_argument(
        "--normalized",
        action="store_true",
        help="Normalize comparison durations against the reference (second / OPC-UA) directory.",
    )
    distance_parser.set_defaults(func=_run_distance)

    # --- conveyor ---
    conveyor_parser = subparsers.add_parser(
        "conveyor", help="Plot the conveyor graph topology."
    )
    conveyor_parser.add_argument("--no-weights", action="store_true", help="Hide edge weight labels.")
    conveyor_parser.set_defaults(
        func=lambda args, parser: (plot_conveyor(show_weights=not args.no_weights), maybe_show())
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    args.func(args, parser)


if __name__ == "__main__":
    main()
