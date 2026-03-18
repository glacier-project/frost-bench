from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from .common import extract_metric_name, find_json_files, resolve_input_path
from .outliers import evaluate_outlier_methods

LEGO_RECIPE_STEPS = ["LD", "RBTC", "QC", "DISASSEMBLE", "RESERVE", "PUT_BACK"]
LEGO_RECIPE_END = "PUT_BACK"
TOPIC_LABELS = {
    "full": "Full Lego Recipe",
    "movements": "Lego Conveyor Movements",
}
VARIANT_LABELS = {"sim": "Simulation", "opcua": "Real"}
DEFAULT_LEGO_METRICS = ["ID", "DISTANCE"]

Recipe = dict[str, dict]


def load_json(filepath: str) -> dict:
    with open(filepath) as handle:
        return json.load(handle)


def flatten_tasks(data: dict) -> dict[str, dict]:
    tasks: dict[str, dict] = {}
    for entries in data.get("mapping", {}).values():
        for entry in entries:
            tasks[entry["task"]["id"]] = entry
    return tasks


def reconstruct_recipes(tasks: dict[str, dict]) -> list[Recipe]:
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
    return reconstruct_recipes(flatten_tasks(load_json(filepath)))


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


def aggregate_by_topic_metric(base_dir: str, metrics: list[str]) -> dict[str, dict[str, dict[str, list[Recipe]]]]:
    result: dict[str, dict[str, dict[str, list[Recipe]]]] = {}
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


def print_recipe_stats(recipes: list[Recipe], label: str, include_outlier_evaluation: bool = False) -> None:
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
                f"(removed {evaluation.removed_count}) in [{evaluation.lower_bound:.1f}, {evaluation.upper_bound:.1f}]"
            )


def normalize_recipes(
    recipes_sim: list[Recipe], recipes_opcua: list[Recipe]
) -> tuple[list[Recipe], list[Recipe]]:
    """Normalizes task durations and total recipe time independently."""
    if not recipes_opcua:
        return recipes_sim, recipes_opcua

    mean_recipe_duration_opcua = np.mean([recipe_duration(r) for r in recipes_opcua])
    
    mean_task_durations_opcua = {}
    for step in LEGO_RECIPE_STEPS:
        durations = [
            task_duration(recipe, step)
            for recipe in recipes_opcua
            if task_duration(recipe, step) is not None
        ]
        if durations:
            mean_task_durations_opcua[step] = np.mean(durations)

    def normalize_single_recipe(recipe: Recipe) -> Recipe:
        new_recipe = {}
        
        real_total_dur = recipe_duration(recipe)
        norm_total_dur = real_total_dur / mean_recipe_duration_opcua if mean_recipe_duration_opcua > 0 else real_total_dur

        norm_task_durations = {}
        for task_name, entry in recipe.items():
            mean_duration = mean_task_durations_opcua.get(task_name)
            real_task_dur = entry["end_time"] - entry["start_time"]
            if mean_duration and mean_duration > 0:
                norm_task_durations[task_name] = real_task_dur / mean_duration
            else:
                norm_task_durations[task_name] = real_task_dur
                
        present_steps = [step for step in LEGO_RECIPE_STEPS if step in recipe]
        
        if len(present_steps) > 1 and LEGO_RECIPE_END in present_steps:
            sum_norm_tasks = sum(norm_task_durations[s] for s in present_steps)
            total_gap = norm_total_dur - sum_norm_tasks
            gap_per_step = total_gap / (len(present_steps) - 1)
        else:
            gap_per_step = 0
            
        current_time = 0.0
        for step in present_steps:
            dur = norm_task_durations[step]
            new_recipe[step] = {
                "start_time": current_time,
                "end_time": current_time + dur,
            }
            current_time += dur + gap_per_step
            
        for task_name, entry in recipe.items():
            if task_name not in new_recipe:
                dur = norm_task_durations[task_name]
                new_recipe[task_name] = {
                    "start_time": 0.0,
                    "end_time": dur,
                }
        
        return new_recipe

    return [normalize_single_recipe(r) for r in recipes_sim], [normalize_single_recipe(r) for r in recipes_opcua]
