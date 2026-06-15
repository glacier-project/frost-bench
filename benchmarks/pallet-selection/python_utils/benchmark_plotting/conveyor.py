"""Conveyor-graph visualisation.

Reads the topology from ``pallet_distance.create_default_conveyor_graph`` and
draws it with hand-tuned positions, colour-coded bays and edge weights.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import networkx as nx

# pallet_distance lives in python_utils, two levels up from this file.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pallet_distance import create_default_conveyor_graph  # noqa: E402

MAIN_LOOP: list[str] = ["A", "B", "C", "D", "M", "L", "I", "H", "40"]
BAY_RBTC: list[str] = ["25", "26", "27"]
BAY_QC: list[str] = ["34", "35", "36"]
BAY_MILL: list[str] = ["17", "18", "19"]
BAY_SPEA: list[str] = ["9"]

CATEGORY_COLOR: dict[str, str] = {
    "loop": "#4C72B0",
    "rbtc": "#55A868",
    "qc": "#DD8452",
    "mill": "#C44E52",
    "spea": "#8172B3",
    "other": "#AAAAAA",
}

NODE_LABELS: dict[str, str] = {
    "A": "A", "B": "B", "C": "C", "D": "D",
    "M": "M", "L": "L", "I": "I", "H": "H",
    "40": "WH\n(40)",
    "25": "RBTC1\n(25)", "26": "RBTC2\n(26)", "27": "RBTC3\n(27)",
    "34": "QC1\n(34)", "35": "QC2\n(35)", "36": "QC3\n(36)",
    "17": "MILL1\n(17)", "18": "MILL2\n(18)", "19": "MILL3\n(19)",
    "9": "SPEA\n(9)",
}

NODE_POSITIONS: dict[str, tuple[float, float]] = {
    # main loop  (clockwise: A→B→C→D→M→L→I→H→40→A)
    "A": (2, 0), "B": (4, 0), "C": (6, 0), "D": (8, 0),
    "M": (8, 2), "L": (6, 2), "I": (4, 2), "H": (2, 2),
    "40": (0, 1),       # warehouse between H and A
    # RBTC bay (off B / L)
    "25": (4, 4), "26": (5, 5), "27": (6, 6),
    # QC bay (off A / I)
    "34": (2, 4), "35": (1, 5), "36": (0, 6),
    # MILL bay (off C / M)
    "17": (6, 4), "18": (7, 5), "19": (8, 6),
    # SPEA (off D)
    "9": (10, 1),
}


def _node_color(node: str) -> str:
    if node in MAIN_LOOP:
        return CATEGORY_COLOR["loop"]
    if node in BAY_RBTC:
        return CATEGORY_COLOR["rbtc"]
    if node in BAY_QC:
        return CATEGORY_COLOR["qc"]
    if node in BAY_MILL:
        return CATEGORY_COLOR["mill"]
    if node in BAY_SPEA:
        return CATEGORY_COLOR["spea"]
    return CATEGORY_COLOR["other"]


def _ms_label(ms: float) -> str:
    return f"{ms / 1000:.1f}s"


def plot_conveyor(show_weights: bool = True) -> None:
    graph = create_default_conveyor_graph(pallets=None)
    nodes_to_draw = [node for node in graph.nodes if node in NODE_POSITIONS]
    sub_graph = graph.subgraph(nodes_to_draw)

    loop_set = set(MAIN_LOOP)
    loop_edges = [(u, v) for u, v in sub_graph.edges() if u in loop_set and v in loop_set]
    bay_edges = [(u, v) for u, v in sub_graph.edges() if (u, v) not in loop_edges]

    node_colors = [_node_color(node) for node in sub_graph.nodes]
    node_sizes = [900 if node in MAIN_LOOP else 700 for node in sub_graph.nodes]

    fig, ax = plt.subplots(figsize=(15, 9))
    ax.set_facecolor("#F8F8F8")
    fig.patch.set_facecolor("white")

    nx.draw_networkx_edges(
        sub_graph, NODE_POSITIONS, edgelist=loop_edges, ax=ax,
        edge_color="#4C72B0", width=2.2,
        arrows=True, arrowstyle="-|>", arrowsize=18,
        connectionstyle="arc3,rad=0.08",
    )
    nx.draw_networkx_edges(
        sub_graph, NODE_POSITIONS, edgelist=bay_edges, ax=ax,
        edge_color="#888888", width=1.4,
        arrows=True, arrowstyle="-|>", arrowsize=14,
        connectionstyle="arc3,rad=0.08",
        style="dashed",
    )

    nx.draw_networkx_nodes(
        sub_graph, NODE_POSITIONS, ax=ax,
        node_color=node_colors, node_size=node_sizes,
        linewidths=1.5, edgecolors="white",
    )
    labels = {node: NODE_LABELS.get(node, node) for node in sub_graph.nodes}
    nx.draw_networkx_labels(
        sub_graph, NODE_POSITIONS, labels, ax=ax,
        font_size=7, font_color="white", font_weight="bold",
    )

    if show_weights:
        edge_labels = {(u, v): _ms_label(d["weight"]) for u, v, d in sub_graph.edges(data=True)}
        nx.draw_networkx_edge_labels(
            sub_graph, NODE_POSITIONS, edge_labels=edge_labels, ax=ax,
            font_size=6.5, font_color="#333333",
            bbox={"boxstyle": "round,pad=0.15", "fc": "white", "alpha": 0.7, "ec": "none"},
            label_pos=0.35,
        )

    legend_entries = [
        mpatches.Patch(color=CATEGORY_COLOR["loop"], label="Main loop"),
        mpatches.Patch(color=CATEGORY_COLOR["rbtc"], label="RBTC bay (25–27)"),
        mpatches.Patch(color=CATEGORY_COLOR["qc"], label="QC bay (34–36)"),
        mpatches.Patch(color=CATEGORY_COLOR["mill"], label="MILL bay (17–19)"),
        mpatches.Patch(color=CATEGORY_COLOR["spea"], label="SPEA (9)"),
    ]
    ax.legend(handles=legend_entries, loc="lower right", frameon=True, fontsize=9)
    ax.set_title(
        "Conveyor Graph — node labels show IDs, edge weights in seconds",
        pad=14, fontsize=13, fontweight="bold",
    )
    ax.axis("off")
    fig.tight_layout()
