from __future__ import annotations

from dataclasses import dataclass

import numpy as np

DEFAULT_PERCENTILE_RANGE = (1.0, 99.0)


@dataclass(frozen=True)
class FilterResult:
    kept_values: list[float]
    lower_bound: float
    upper_bound: float
    removed_count: int


@dataclass(frozen=True)
class FilterEvaluation:
    method: str
    kept_count: int
    removed_count: int
    lower_bound: float
    upper_bound: float


def trim_percentile_range(
    values: list[float],
    lower_percentile: float = DEFAULT_PERCENTILE_RANGE[0],
    upper_percentile: float = DEFAULT_PERCENTILE_RANGE[1],
) -> FilterResult:
    if not values:
        return FilterResult([], float("nan"), float("nan"), 0)

    if len(values) < 3:
        return FilterResult(list(values), min(values), max(values), 0)

    lower_bound = float(np.percentile(values, lower_percentile))
    upper_bound = float(np.percentile(values, upper_percentile))
    kept_values = [value for value in values if lower_bound <= value <= upper_bound]
    if not kept_values:
        kept_values = list(values)
    return FilterResult(kept_values, lower_bound, upper_bound, len(values) - len(kept_values))


def tukey_fence_range(values: list[float], whisker_width: float = 1.5) -> FilterResult:
    if not values:
        return FilterResult([], float("nan"), float("nan"), 0)
    if len(values) < 4:
        return FilterResult(list(values), min(values), max(values), 0)

    q1 = float(np.percentile(values, 25))
    q3 = float(np.percentile(values, 75))
    iqr = q3 - q1
    lower_bound = q1 - whisker_width * iqr
    upper_bound = q3 + whisker_width * iqr
    kept_values = [value for value in values if lower_bound <= value <= upper_bound]
    return FilterResult(kept_values or list(values), lower_bound, upper_bound, len(values) - len(kept_values))


def mad_range(values: list[float], z_threshold: float = 3.5) -> FilterResult:
    if not values:
        return FilterResult([], float("nan"), float("nan"), 0)
    if len(values) < 4:
        return FilterResult(list(values), min(values), max(values), 0)

    median = float(np.median(values))
    deviations = np.abs(np.array(values) - median)
    mad = float(np.median(deviations))
    if mad == 0:
        return FilterResult(list(values), min(values), max(values), 0)

    scaled = 0.6745 * deviations / mad
    kept_values = [value for value, score in zip(values, scaled) if score <= z_threshold]
    lower_bound = median - (z_threshold * mad / 0.6745)
    upper_bound = median + (z_threshold * mad / 0.6745)
    return FilterResult(kept_values or list(values), lower_bound, upper_bound, len(values) - len(kept_values))


def evaluate_outlier_methods(values: list[float]) -> list[FilterEvaluation]:
    results = [
        ("P1-P99", trim_percentile_range(values, 1.0, 99.0)),
        ("P2.5-P97.5", trim_percentile_range(values, 2.5, 97.5)),
        ("Tukey 1.5×IQR", tukey_fence_range(values)),
        ("MAD z<=3.5", mad_range(values)),
    ]
    return [
        FilterEvaluation(
            method=name,
            kept_count=len(result.kept_values),
            removed_count=result.removed_count,
            lower_bound=result.lower_bound,
            upper_bound=result.upper_bound,
        )
        for name, result in results
    ]
