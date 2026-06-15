# benchmark_plotting — ready-to-launch commands

All commands assume the working directory is `benchmarks/pallet-selection/`
and that `python_utils/` is reachable from there. Replace `python` with
`python3` or your venv binary as needed.

General form: `python python_utils/plot.py <lego|distance|conveyor> <flags>`

For headless runs (no display) prepend `MPLBACKEND=agg`.

---

## Lego recipes

### Single directory, individual plots

```bash
# End-to-end violin + chronological line
python python_utils/plot.py lego -d results/lego-3-recipes --violin

# Per-step duration violins
python python_utils/plot.py lego -d results/lego-3-recipes --tasks

# Gaussian fit (P15-P85 trim)
python python_utils/plot.py lego -d results/lego-3-recipes --gaussian

# Waiting times between consecutive steps
python python_utils/plot.py lego -d results/lego-3-recipes --waiting

# Gantt timeline of every recipe
python python_utils/plot.py lego -d results/lego-3-recipes --timeline

# All plot types at once
python python_utils/plot.py lego -d results/lego-3-recipes \
    --gaussian --violin --tasks --waiting --timeline
```

### Base-dir mode (auto-groups sim-* / opcua-* by topic)

```bash
# Per-variant duration violins
python python_utils/plot.py lego -b results/lego --violin

# Same plus sim-vs-opcua and ID-vs-DISTANCE comparisons
python python_utils/plot.py lego -b results/lego --violin --compare-plots

# Full report
python python_utils/plot.py lego -b results/lego \
    --gaussian --violin --tasks --waiting --timeline --compare-plots --speedup

# Comparison with task normalisation relative to OPC-UA
python python_utils/plot.py lego -b results/lego \
    --violin --compare-plots --normalized --speedup

# Restrict to a single topic
python python_utils/plot.py lego -b results/lego --topic full     --violin --compare-plots
python python_utils/plot.py lego -b results/lego --topic movements --violin --compare-plots
```

### Two directories side-by-side

```bash
python python_utils/plot.py lego \
    -d results/lego/lego-sim-20260318_084239 \
    -c results/lego/lego-opcua-20260317_112548 \
    --violin --tasks --compare-plots
```

### Metric selection

```bash
# Default is ID + DISTANCE; broaden or narrow:
python python_utils/plot.py lego -b results/lego --violin --compare-plots \
    --metric-compare ID DISTANCE

# Just one metric (no comparison plots)
python python_utils/plot.py lego -b results/lego --violin --metric-compare ID
```

### Outlier-filter toggle

```bash
# Filter is on by default (P15-P85 on total duration). Disable with:
python python_utils/plot.py lego -b results/lego --violin --no-filter
```

### 3-recipe benchmark

```bash
python python_utils/plot.py lego -b results/lego-3-recipes \
    --violin --tasks --compare-plots --speedup
```

---

## Distance recipe (task-level durations)

```bash
# Single directory — compare metrics inside one run
python python_utils/plot.py distance -d results/distance/opcua-20260227_171322

# Two directories side-by-side
python python_utils/plot.py distance \
    -d results/distance/opcua-20260227_171322 \
    -c results/distance/opcua-20260302_132012

# Base-dir mode — auto-group sim-* and opcua-* subfolders
python python_utils/plot.py distance -b results/distance/

# Custom metric set
python python_utils/plot.py distance -b results/distance/ --metrics ID DISTANCE RANDOM
```

---

## Conveyor graph

```bash
# Topology with edge weights (seconds)
python python_utils/plot.py conveyor

# Same, no weight labels
python python_utils/plot.py conveyor --no-weights
```

---

## Save figures instead of showing them

Matplotlib's `agg` backend disables `plt.show()`. Combine with the helper script
or call `plt.savefig` from a Python session. Quick shell pattern:

```bash
MPLBACKEND=agg python python_utils/plot.py lego -b results/lego --violin --compare-plots
# (figures stay in memory; for actual file output use the library API below)
```

---

## Library API (notebooks / scripts)

```python
import benchmark_plotting as bp
import matplotlib.pyplot as plt

# Load all recipes by metric from a single directory
by_metric = bp.load_recipes_by_metric("results/lego-3-recipes", ["ID", "DISTANCE"])

bp.print_recipe_stats(by_metric["ID"], "Real [ID]", include_outlier_evaluation=True)

bp.plot_recipe_durations(by_metric["ID"], label="Real [ID]", color=bp.PLOT_COLORS[0])
bp.plot_task_distributions(by_metric["ID"], label="Real [ID]")
bp.plot_compare_durations(by_metric["ID"], by_metric["DISTANCE"], "ID", "DISTANCE")
bp.plot_conveyor()

plt.show()  # or bp.maybe_show()
```

### Aggregating a tree of results

```python
data = bp.aggregate_by_topic_metric("results/lego", ["ID", "DISTANCE"])
# data["full"]["sim"]["ID"]     -> list[Recipe]
# data["full"]["opcua"]["ID"]   -> list[Recipe]

bp.plot_speedup_comparison(
    data["full"]["sim"]["ID"],
    data["full"]["sim"]["DISTANCE"],
    data["full"]["opcua"]["ID"],
    data["full"]["opcua"]["DISTANCE"],
    topic_label="Full Lego Recipe",
)
```

### Outlier filtering

```python
clean = bp.filter_recipes_by_duration_percentile(by_metric["ID"])           # default P15-P85
clean = bp.filter_recipes_by_duration_percentile(by_metric["ID"], (5.0, 95.0))
```
