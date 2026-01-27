import argparse
import csv
import numpy as np
import matplotlib.pyplot as plt
import networkx as nx

from dataclasses import dataclass
from pallet_distance import create_default_conveyor_graph, PalletPosition


@dataclass
class PalletEvent:
    timestamp: int
    pallet_id: int
    position: PalletPosition

@dataclass
class PalletTransition:
    from_position: str
    to_position: str
    mean_time: float
    std_dev: float

def _load_pallet_events(filepath: str) -> list[PalletEvent]:
    """Load pallet events from a CSV file into a list of PalletEvent objects.
    Args:
        filepath (str): Path to the CSV file.
    Returns:
        list: A list of PalletEvent objects.
    """
    events = []
    with open(filepath, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            events.append(PalletEvent(
                timestamp=int(row['timestamp']),
                pallet_id=int(row['pallet_id']),
                position=PalletPosition[row['pallet_position']]
            ))
    return events


def _compute_pallet_transitions(events: list[PalletEvent]) -> dict[tuple[str, str], list[tuple[PalletEvent, PalletEvent]]]:    
    """Compute pallet transitions from events.

    Args:
        events (list): List of PalletEvent objects sorted by timestamp.
    Returns:
        dict: A dictionary mapping (from_segment, to_segment) to list of (source_event, destination_event) tuples.
    """
    last_pallet_event: dict[int, PalletEvent] = {}
    transitions: dict[tuple[str, str], list[tuple[PalletEvent, PalletEvent]]] = {}

    # Checks that all the transitions are sorted by time
    sorted_events = sorted(events, key=lambda e: e.timestamp)
    assert events == sorted_events, "Events are not sorted by timestamp"
    
    for event in events:
        pallet_id = event.pallet_id

        if pallet_id == 0:
            continue  

        # Skip first event for each pallet
        if pallet_id not in last_pallet_event:
            last_pallet_event[pallet_id] = event
            continue
        
        src_event = last_pallet_event[pallet_id]
        dst_event = event
        key = (src_event.position.value.get_source_node(), dst_event.position.value.get_source_node())
            
        if key not in transitions:
            transitions[key] = []
        transitions[key].append((src_event, dst_event))

        # Update last event for this pallet
        last_pallet_event[pallet_id] = event
    
    return transitions

def _aggregate_transition_times(transitions: dict[tuple[str, str], list[tuple[PalletEvent, PalletEvent]]]) -> dict[tuple[str, str], PalletTransition]:
    """Aggregate transition times to compute mean and standard deviation for each segment.

    Args:
        transitions (dict): A dictionary mapping (from_segment, to_segment) to list of (source_event, destination_event) tuples.
    Returns:
        dict: A dictionary mapping (from_segment, to_segment) to PalletTransition objects with mean and std_dev.
    """

    pallet_transitions = {}
    for (from_seg, to_seg), event_pairs in transitions.items():
        timings = []
        for src, dst in event_pairs:
            src_timestamp = src.timestamp
            dst_timestamp = dst.timestamp
            assert src_timestamp <= dst_timestamp, "Source timestamp is after destination timestamp"
            timings.append(dst_timestamp - src_timestamp)

        mean_time = int(np.round(np.mean(timings)))
        assert isinstance(mean_time, int)
        std_dev = int(np.round(np.std(timings)))
        assert isinstance(std_dev, int)
        pallet_transitions[(from_seg, to_seg)] = PalletTransition(
            from_position=from_seg,
            to_position=to_seg,
            mean_time=mean_time,
            std_dev=std_dev
        )
    return pallet_transitions

def _create_conveyor_graph(transitions: dict[tuple[str, str], PalletTransition]) -> nx.DiGraph:
    """
    Create a conveyor graph with updated edge weights based on measured transition times.

    Args:
        transitions (dict): A dictionary mapping (from_segment, to_segment) to PalletTransition objects.
    Returns:
        nx.DiGraph: The updated conveyor graph with edge weights set to measured mean transition times
    """
    # Get default conveyor graph 
    conveyor_graph = create_default_conveyor_graph([])

    # Update edge weights with measured transition times
    for (from_seg, to_seg), transition in transitions.items():
        # assert conveyor_graph.has_edge(from_seg, to_seg), f"Edge {from_seg} -> {to_seg} not in conveyor graph"
        if not conveyor_graph.has_edge(from_seg, to_seg):
            print(f"Warning: Edge {from_seg} -> {to_seg} not in conveyor graph, skipping update.")
            continue
        
        conveyor_graph[from_seg][to_seg]['weight'] = transition.mean_time
        conveyor_graph[from_seg][to_seg]['std_dev'] = transition.std_dev

    return conveyor_graph

def render_graph_visual(graph: nx.DiGraph) -> None:
    """
    Render the conveyor graph visually following the layout from conveyor_readme.md:
    
       Z         P         O         N
       |         |         |         |
       |         |         |         |
       M ------- L ------- I ------- H ------- G--- F
       |         |         |         |              |
       |         |         |         |              |
       E ------- D ------- C ------- B ------------ A
    
    Bay positions (Z=SPEA, P=MILL, O=RBTC, N=QC/WH, G=entry)

    Args:
        graph (nx.DiGraph): The conveyor graph to render.
    """
    pos = {
        # Top row (main line)
        "M": (0, 1),
        "L": (2, 1),
        "I": (4, 1),
        "H": (6, 1),
        "40": (7, 1),  # Junction to warehouse/exit
        "F": (8, 1),
        
        # Bottom row (return line)
        "E": (0, 0),
        "D": (2, 0),
        "C": (4, 0),
        "B": (6, 0),
        "A": (8, 0),
        
        # Bay Z - SPEA (above M)
        "9": (0, 2),
        
        # Bay P - MILL (above L)
        "17": (2, 2),
        "18": (2, 2.5),
        "19": (2, 3),
        
        # Bay O - RBTC (above I)
        "25": (4, 2),
        "26": (4, 2.5),
        "27": (4, 3),
        
        # Bay N - QC (above H)
        "34": (6, 2),
        "35": (6, 2.5),
        "36": (6, 3),
    }
    
    # Filter to only nodes in the graph
    pos = {k: v for k, v in pos.items() if k in graph.nodes()}
    
    fig, ax = plt.subplots(1, 1, figsize=(14, 10))
    
    main_nodes = ["M", "L", "I", "H", "40", "F", "E", "D", "C", "B", "A"]
    bay_nodes = ["9", "17", "18", "19", "25", "26", "27", "34", "35", "36"]
    
    main_in_graph = [n for n in main_nodes if n in graph.nodes()]
    bay_in_graph = [n for n in bay_nodes if n in graph.nodes()]
    
    # Draw edges with weights
    edge_labels = {}
    edge_colors = []
    edge_widths = []
    
    for u, v, data in graph.edges(data=True):
        if u in pos and v in pos:
            weight = data.get('weight', 0)
            sample_count = data.get('sample_count', 0)
            edge_labels[(u, v)] = f"{weight}"
            
            # Color edges with measured data differently
            if sample_count > 0:
                edge_colors.append('darkgreen')
                edge_widths.append(2.0)
            else:
                edge_colors.append('gray')
                edge_widths.append(1.0)
    
    
    # Draw nodes
    nx.draw_networkx_nodes(
        graph, pos, ax=ax,
        nodelist=main_in_graph,
        node_color='lightblue',
        node_size=800,
        node_shape='s'
    )
    nx.draw_networkx_nodes(
        graph, pos, ax=ax,
        nodelist=bay_in_graph,
        node_color='lightyellow',
        node_size=600,
        node_shape='o'
    )
    # Draw labels
    nx.draw_networkx_labels(graph, pos, ax=ax, font_size=10, font_weight='bold')

    # Draw the edges
    nx.draw_networkx_edges(
        graph, pos, ax=ax,
        edge_color=edge_colors,
        width=edge_widths,
        alpha=0.7,
        arrows=True,
        arrowsize=15,
        connectionstyle="arc3,rad=0.1"
    )
    
    # Draw edge labels (weights)
    nx.draw_networkx_edge_labels(
        graph, pos, ax=ax,
        edge_labels=edge_labels,
        font_size=7,
        label_pos=0.3
    )
    
    # Add bay labels
    bay_labels = {
        (0, 2.5): "Bay Z\n(SPEA)",
        (2, 3.5): "Bay P\n(MILL)",
        (4, 3.5): "Bay O\n(RBTC)",
        (6, 3.5): "Bay N\n(QC)",
        (8, 0.5): "Bay G\n(Entry)",
    }
    for (x, y), label in bay_labels.items():
        ax.annotate(label, (x, y), fontsize=9, ha='center', color='darkblue', style='italic')
    
    # Add segment labels
    segment_labels = {
        (1, 1.15): "S1",
        (3, 1.15): "S2",
        (5, 1.15): "S3",
        (6.5, 1.15): "S4",
        (7, 0.15): "S5",
        (5, -0.15): "S6",
        (3, -0.15): "S7",
        (1, -0.15): "S8",
    }
    for (x, y), label in segment_labels.items():
        ax.annotate(label, (x, y), fontsize=8, ha='center', color='gray', alpha=0.8)
    
    # Legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color='darkgreen', linewidth=2, label='Measured timing'),
        Line2D([0], [0], color='gray', linewidth=1, label='Default timing'),
        Line2D([0], [0], marker='s', color='w', markerfacecolor='lightblue',
               markersize=12, label='Main conveyor'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='lightyellow',
               markersize=10, label='Bay position'),
    ]
    ax.legend(handles=legend_elements, loc='upper right')
    
    ax.set_title('Conveyor System Graph\n(Edge weights = transit time in ms)', fontsize=12)
    ax.axis('off')
    plt.tight_layout()
    plt.show()

def main():
    parser = argparse.ArgumentParser(
        description='Compute conveyor segment timings from pallet distance metric log files.'
    )
    parser.add_argument(
        'files',
        type=str,
        nargs='+',
        help='CSV file(s) containing pallet distance metric logs'
    )
    parser.add_argument(
        '--render-graph',
        action='store_true',
        help='Render the graph visually and show interactively (no file saved).'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Generate a networkx graph with updated edge weights and save to file (GML format)'
    )
    args = parser.parse_args()

    print(f"\n# Processing files: {args.files}")
    
    pallet_transitions: dict[tuple[str, str], list[tuple[PalletEvent, PalletEvent]]] = {}
    for filepath in args.files:
        events = _load_pallet_events(filepath)
        for key, event_pairs in _compute_pallet_transitions(events).items():
            if key not in pallet_transitions:
                pallet_transitions[key] = []
            pallet_transitions[key].extend(event_pairs) 

    # Aggregate transition times
    segment_timings = _aggregate_transition_times(pallet_transitions)
    for (from_seg, to_seg), transition in sorted(segment_timings.items()):
        print(f"{from_seg} -> {to_seg}: mean_time={transition.mean_time:.1f} ms, std_dev={transition.std_dev:.1f} ms")

    # Compute updated conveyor graph
    updated_graph = _create_conveyor_graph(segment_timings)
    if args.render_graph:
        render_graph_visual(updated_graph)

    if args.output:
        nx.write_gml(updated_graph, args.output)
        print(f"Graph saved to: {args.output}")

if __name__ == "__main__":
    main()
