"""Plotting utilities for the pallet-selection benchmarks.

Layout — one module per benchmark kind, plus shared helpers:
    lego        Lego recipe loading, statistics, and plots.
    distance    Distance recipe task-duration loading and plots.
    conveyor    Conveyor-graph visualisation.
    io          Shared filesystem helpers (path resolution, file discovery).
    outliers    Shared outlier-filter helpers.
    style       Shared matplotlib styling and plot primitives.
    cli         Unified command-line interface.

The package re-exports the most common symbols at the top level so notebooks
and scripts can do ``import benchmark_plotting as bp``.
"""

from __future__ import annotations

from .conveyor import plot_conveyor
from .distance import (
    DEFAULT_EXCLUDED_TASKS,
    DEFAULT_MAX_DURATION,
    DEFAULT_METRICS,
    aggregate_metric_durations,
    classify_distance_dir,
    get_files_in_directory,
    group_distance_runs,
    load_task_durations,
    plot_comparisons,
    plot_distributions,
)
from .io import (
    extract_metric_name,
    find_json_files,
    get_all_files,
    resolve_input_path,
)
from .lego import (
    DEFAULT_LEGO_METRICS,
    LEGO_RECIPE_END,
    LEGO_RECIPE_STEPS,
    TOPIC_LABELS,
    VARIANT_LABELS,
    Recipe,
    aggregate_by_topic_metric,
    classify_run_dir,
    load_all_recipes,
    load_lego_results,
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
    recipe_duration,
    recipe_start_time,
    task_duration,
    waiting_time,
)
from .outliers import (
    DEFAULT_PERCENTILE_RANGE,
    FilterEvaluation,
    FilterResult,
    evaluate_outlier_methods,
    filter_recipes_by_duration_percentile,
    mad_range,
    trim_percentile_range,
    tukey_fence_range,
)
from .style import (
    PLOT_COLORS,
    configure_matplotlib,
    maybe_show,
    setup_axes,
    style_violin_parts,
    violin_or_bar,
)

__all__ = [
    # io
    "extract_metric_name",
    "find_json_files",
    "get_all_files",
    "resolve_input_path",
    # lego — data
    "Recipe",
    "LEGO_RECIPE_STEPS",
    "LEGO_RECIPE_END",
    "TOPIC_LABELS",
    "VARIANT_LABELS",
    "DEFAULT_LEGO_METRICS",
    "load_lego_results",
    "load_recipes_by_metric",
    "load_all_recipes",
    "aggregate_by_topic_metric",
    "classify_run_dir",
    "recipe_duration",
    "recipe_start_time",
    "task_duration",
    "waiting_time",
    "print_recipe_stats",
    "normalize_recipes",
    # lego — plots
    "plot_compare_durations",
    "plot_compare_durations_stacked",
    "plot_compare_gaussians",
    "plot_compare_tasks",
    "plot_compare_waiting_times",
    "plot_gaussian_distribution",
    "plot_recipe_durations",
    "plot_recipe_timeline",
    "plot_speedup_comparison",
    "plot_task_distributions",
    "plot_waiting_times",
    # distance — data
    "DEFAULT_METRICS",
    "DEFAULT_EXCLUDED_TASKS",
    "DEFAULT_MAX_DURATION",
    "load_task_durations",
    "get_files_in_directory",
    "group_distance_runs",
    "classify_distance_dir",
    "aggregate_metric_durations",
    # distance — plots
    "plot_distributions",
    "plot_comparisons",
    # conveyor
    "plot_conveyor",
    # styling
    "PLOT_COLORS",
    "configure_matplotlib",
    "maybe_show",
    "setup_axes",
    "style_violin_parts",
    "violin_or_bar",
    # outliers
    "DEFAULT_PERCENTILE_RANGE",
    "FilterEvaluation",
    "FilterResult",
    "evaluate_outlier_methods",
    "filter_recipes_by_duration_percentile",
    "mad_range",
    "trim_percentile_range",
    "tukey_fence_range",
]
