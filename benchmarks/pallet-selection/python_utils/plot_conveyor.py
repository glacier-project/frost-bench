"""Plot the conveyor graph defined in pallet_distance.py.

Usage:
    python python_utils/plot_conveyor.py
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx

sys.path.insert(0, str(Path(__file__).parent))
from pallet_distance import create_default_conveyor_graph

# ---------------------------------------------------------------------------
# Node categories and colours
# ---------------------------------------------------------------------------

MAIN_LOOP = ["A", "B", "C", "D", "M", "L", "I", "H", "40"]    # conveyor loop
BAY_RBTC   = ["25", "26", "27"]
BAY_QC     = ["34", "35", "36"]
BAY_MILL   = ["17", "18", "19"]
BAY_SPEA   = ["9"]

CATEGORY_COLOR = {
    "loop":  "#4C72B0",
    "rbtc":  "#55A868",
    "qc":    "#DD8452",
    "mill":  "#C44E52",
    "spea":  "#8172B3",
    "other": "#AAAAAA",
}

NODE_LABELS = {
    "A":  "A",  "B":  "B",  "C":  "C",  "D":  "D",
    "M":  "M",  "L":  "L",  "I":  "I",  "H":  "H",
    "40": "WH\n(40)",
    "25": "RBTC1\n(25)", "26": "RBTC2\n(26)", "27": "RBTC3\n(27)",
    "34": "QC1\n(34)",   "35": "QC2\n(35)",   "36": "QC3\n(36)",
    "17": "MILL1\n(17)", "18": "MILL2\n(18)", "19": "MILL3\n(19)",
    "9":  "SPEA\n(9)",
}

# Hand-tuned positions (x, y) — loop arranged clockwise, bays branching off
POS = {
    # main loop  (clockwise: A→B→C→D→M→L→I→H→40→A)
    "A":  (2, 0),
    "B":  (4, 0),
    "C":  (6, 0),
    "D":  (8, 0),
    "M":  (8, 2),
    "L":  (6, 2),
    "I":  (4, 2),
    "H":  (2, 2),
    "40": (0, 1),       # warehouse between H and A
    # RBTC bay (off B / L)
    "25": (4, 4),
    "26": (5, 5),
    "27": (6, 6),
    # QC bay (off A / I)
    "34": (2, 4),
    "35": (1, 5),
    "36": (0, 6),
    # MILL bay (off C / M)
    "17": (6, 4),
    "18": (7, 5),
    "19": (8, 6),
    # SPEA (off D)
    "9":  (10, 1),
}


def _node_color(node: str) -> str:
    if node in MAIN_LOOP:  return CATEGORY_COLOR["loop"]
    if node in BAY_RBTC:   return CATEGORY_COLOR["rbtc"]
    if node in BAY_QC:     return CATEGORY_COLOR["qc"]
    if node in BAY_MILL:   return CATEGORY_COLOR["mill"]
    if node in BAY_SPEA:   return CATEGORY_COLOR["spea"]
    return CATEGORY_COLOR["other"]


def _ms_label(ms: float) -> str:
    """Format edge weight: show in seconds, one decimal."""
    return f"{ms / 1000:.1f}s"


def plot_conveyor(show_weights: bool = True) -> None:
    G = create_default_conveyor_graph(pallets=None)

    # Keep only nodes we have positions for (drop UNDEFINED, pallet nodes, etc.)
    nodes_to_draw = [n for n in G.nodes if n in POS]
    subG = G.subgraph(nodes_to_draw)

    # Split edges into loop-internal and bay edges for styling
    loop_set = set(MAIN_LOOP)
    loop_edges = [(u, v) for u, v in subG.edges() if u in loop_set and v in loop_set]
    bay_edges  = [(u, v) for u, v in subG.edges() if (u, v) not in loop_edges]

    node_colors = [_node_color(n) for n in subG.nodes]
    node_sizes  = [900 if n in MAIN_LOOP else 700 for n in subG.nodes]

    fig, ax = plt.subplots(figsize=(15, 9))
    ax.set_facecolor("#F8F8F8")
    fig.patch.set_facecolor("white")

    # Draw edges
    nx.draw_networkx_edges(
        subG, POS, edgelist=loop_edges, ax=ax,
        edge_color="#4C72B0", width=2.2,
        arrows=True, arrowstyle="-|>", arrowsize=18,
        connectionstyle="arc3,rad=0.08",
    )
    nx.draw_networkx_edges(
        subG, POS, edgelist=bay_edges, ax=ax,
        edge_color="#888888", width=1.4,
        arrows=True, arrowstyle="-|>", arrowsize=14,
        connectionstyle="arc3,rad=0.08",
        style="dashed",
    )

    # Draw nodes
    nx.draw_networkx_nodes(
        subG, POS, ax=ax,
        node_color=node_colors, node_size=node_sizes,
        linewidths=1.5, edgecolors="white",
    )

    # Draw labels
    labels = {n: NODE_LABELS.get(n, n) for n in subG.nodes}
    nx.draw_networkx_labels(subG, POS, labels, ax=ax, font_size=7, font_color="white", font_weight="bold")

    # Edge weight labels
    if show_weights:
        edge_labels = {(u, v): _ms_label(d["weight"]) for u, v, d in subG.edges(data=True)}
        nx.draw_networkx_edge_labels(
            subG, POS, edge_labels=edge_labels, ax=ax,
            font_size=6.5, font_color="#333333",
            bbox=dict(boxstyle="round,pad=0.15", fc="white", alpha=0.7, ec="none"),
            label_pos=0.35,
        )

    # Legend
    legend_entries = [
        mpatches.Patch(color=CATEGORY_COLOR["loop"],  label="Main loop"),
        mpatches.Patch(color=CATEGORY_COLOR["rbtc"],  label="RBTC bay (25–27)"),
        mpatches.Patch(color=CATEGORY_COLOR["qc"],    label="QC bay (34–36)"),
        mpatches.Patch(color=CATEGORY_COLOR["mill"],  label="MILL bay (17–19)"),
        mpatches.Patch(color=CATEGORY_COLOR["spea"],  label="SPEA (9)"),
    ]
    ax.legend(handles=legend_entries, loc="lower right", frameon=True, fontsize=9)

    ax.set_title("Conveyor Graph — node labels show IDs, edge weights in seconds", pad=14,
                 fontsize=13, fontweight="bold")
    ax.axis("off")
    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Visualise the conveyor graph.")
    parser.add_argument("--no-weights", action="store_true", help="Hide edge weight labels.")
    args = parser.parse_args()
    plot_conveyor(show_weights=not args.no_weights)
