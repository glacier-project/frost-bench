import logging
from venv import logger
import matplotlib.pyplot as plt
import networkx as nx
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

SEGMENT_1_TT = 12700
SEGMENT_2_TT = 20200
SEGMENT_3_TT = 13250
SEGMENT_4_TT = 4800
SEGMENT_5_TT = 6900
SEGMENT_6_TT = 14500
SEGMENT_7_TT = 20200
SEGMENT_8_TT = 12700
# Are these correct?
INTERCHANGE_TT = 4800 
BAY_TRANSFER_TT = 2000
# H -> 40 2s?
# 40 -> F 2s?

class ConveyorPosition:
    def __init__(self, start_node: str, end_node: str | None = None, duration: int = 0):
        self.start_node = start_node
        self.end_node = end_node
        self.duration = duration

    def _get_target_node(self) -> str:
        if self.end_node is not None:
            return self.end_node
        return self.start_node
    
    def _get_target_remaining_time(self, timestamp: int, position_timestamp: int) -> int:
        elapsed_time = timestamp - position_timestamp
        remaining_time = max(0, self.duration - elapsed_time)
        return remaining_time

class PalletPosition(Enum):
    S1 = ConveyorPosition("M", "L", SEGMENT_1_TT)
    S2 = ConveyorPosition("L", "I", SEGMENT_2_TT)
    S3 = ConveyorPosition("I", "H", SEGMENT_3_TT)
    S4_1 = ConveyorPosition("H", "40", BAY_TRANSFER_TT)
    S4_2 = ConveyorPosition("40", "F", BAY_TRANSFER_TT)
    S5 = ConveyorPosition("A", "B", SEGMENT_5_TT)
    S6 = ConveyorPosition("B", "C", SEGMENT_6_TT)
    S7 = ConveyorPosition("C", "D", SEGMENT_7_TT)
    S8 = ConveyorPosition("D", "E", SEGMENT_8_TT)
    WH = ConveyorPosition("40")
    QC_1 = ConveyorPosition("34")
    QC_2 = ConveyorPosition("35")
    QC_3 = ConveyorPosition("36")
    RBTC_1 = ConveyorPosition("25")
    RBTC_2 = ConveyorPosition("26")
    RBTC_3 = ConveyorPosition("27")
    MILL_1 = ConveyorPosition("17")
    MILL_2 = ConveyorPosition("18")
    MILL_3 = ConveyorPosition("19")
    SPEA_1 = ConveyorPosition("9")
    UNDEFINED = ConveyorPosition("UNDEFINED", duration=int(1e9))

_position_map = {pos.name: pos for pos in PalletPosition}
_position_map["40"] = PalletPosition.WH
_position_map["34"] = PalletPosition.QC_1
_position_map["35"] = PalletPosition.QC_2
_position_map["36"] = PalletPosition.QC_3
_position_map["25"] = PalletPosition.RBTC_1
_position_map["26"] = PalletPosition.RBTC_2
_position_map["27"] = PalletPosition.RBTC_3
_position_map["17"] = PalletPosition.MILL_1
_position_map["18"] = PalletPosition.MILL_2
_position_map["19"] = PalletPosition.MILL_3
_position_map["9"] = PalletPosition.SPEA_1

def get_conveyor_position(position: str|int):
    if isinstance(position, int):
        position = str(position)
    return _position_map.get(position, PalletPosition.UNDEFINED)

@dataclass
class PalletStatus:
    id: int 
    pallet_position: PalletPosition
    position_timestamp: int

def _create_conveyor_graph(pallets: list[PalletStatus]) -> nx.DiGraph:
    adjacency_dict = {
        "A": {"B": {"weight": SEGMENT_5_TT}},
        "B": {"H": {"weight": INTERCHANGE_TT}, "C": {"weight": SEGMENT_6_TT}},
        "H": {"40": {"weight": BAY_TRANSFER_TT}, "34": {"weight": BAY_TRANSFER_TT}, "B": {"weight": INTERCHANGE_TT}},
        "40": {"F": {"weight": BAY_TRANSFER_TT}},
        "34": {"35": {"weight": BAY_TRANSFER_TT}, "H": {"weight": BAY_TRANSFER_TT}},
        "35": {"36": {"weight": BAY_TRANSFER_TT}, "34": {"weight": BAY_TRANSFER_TT}},
        "36": {"35": {"weight": BAY_TRANSFER_TT}},
        "F": {"A": {"weight": INTERCHANGE_TT}},
        "C": {"D": {"weight": SEGMENT_7_TT}, "I": {"weight": INTERCHANGE_TT}},
        "I": {"H": {"weight": SEGMENT_3_TT}, "25": {"weight": BAY_TRANSFER_TT}, "C": {"weight": INTERCHANGE_TT}},
        "25": {"26": {"weight": BAY_TRANSFER_TT}, "I": {"weight": BAY_TRANSFER_TT}},
        "26": {"27": {"weight": BAY_TRANSFER_TT}, "25": {"weight": BAY_TRANSFER_TT}},
        "27": {"26": {"weight": BAY_TRANSFER_TT}},
        "D": {"E": {"weight": SEGMENT_8_TT}, "L": {"weight": INTERCHANGE_TT}},
        "L": {"I": {"weight": SEGMENT_2_TT}, "17": {"weight": BAY_TRANSFER_TT}, "D": {"weight": INTERCHANGE_TT}},
        "17": {"18": {"weight": BAY_TRANSFER_TT}, "L": {"weight": BAY_TRANSFER_TT}},
        "18": {"19": {"weight": BAY_TRANSFER_TT}, "17": {"weight": BAY_TRANSFER_TT}},
        "19": {"18": {"weight": BAY_TRANSFER_TT}},
        "E": {"M": {"weight": INTERCHANGE_TT}},
        "M": {"L": {"weight": SEGMENT_1_TT}, "9": {"weight": BAY_TRANSFER_TT}},
        "9": {"M": {"weight": BAY_TRANSFER_TT}},
    }

    # Add pallet nodes
    for pallet in pallets:
        node_id = _get_pallet_node_id(pallet)
        adjacency_dict[node_id] = {}

    conveyor_graph = nx.DiGraph(adjacency_dict)
    return conveyor_graph

def _shortest_path_length(graph: nx.DiGraph, source: str, target: str) -> float:
    if source == target:
        return 0.0

    try:
        return nx.shortest_path_length(graph, source=source, target=target, weight='weight')
    except nx.NetworkXNoPath:
        return float('inf')

def _get_pallet_node_id(pallet: PalletStatus) -> str:
    return f"Pallet_{pallet.id}"

def _update_pallet_edges(graph: nx.DiGraph, pallet: PalletStatus, timestamp: int) -> None:
        if pallet.pallet_position == PalletPosition.UNDEFINED:
            return

        # Remove existing edges from pallet node and add new edge to current position
        node_id = _get_pallet_node_id(pallet)
        current_edges = list(graph.edges(node_id))
        if current_edges:
            graph.remove_edges_from(current_edges)

        # Add edge from the pallet node to its current position in the conveyor graph
        pallet_target_node = pallet.pallet_position.value._get_target_node()
        weight = pallet.pallet_position.value._get_target_remaining_time(timestamp, pallet.position_timestamp)
        graph.add_edge(node_id, pallet_target_node, weight=weight)


class PalletDistanceMetric:
    
    def __init__(self):
        self._pallets = [
            PalletStatus(id=i, pallet_position=PalletPosition.UNDEFINED, position_timestamp=0)
            for i in range(1, 11)
        ]
        self._conveyor_graph = _create_conveyor_graph(self._pallets)

    def set_pallet_position(self, pallet_id: int, position: PalletPosition, timestamp: int) -> None:
        pallet = self._pallets[pallet_id - 1]

        if pallet.pallet_position == position:
            return

        # Update pallet position and timestamp
        pallet.pallet_position = position
        pallet.position_timestamp = timestamp

    def get_pallets_sorted_by_distance_to(self, destination: PalletPosition, timestamp: int) -> list[int]:
        pallet_distances: list[tuple[PalletStatus, float]] = []

        for pallet in self._pallets:
            _update_pallet_edges(self._conveyor_graph, pallet, timestamp)
            distance = _shortest_path_length(self._conveyor_graph, _get_pallet_node_id(pallet), destination.value.start_node)

            pallet_distances.append((pallet, distance))
        
        # Sort by distance, then by pallet ID
        # print("Pallet distances:", [(p.id, dist) for p, dist in pallet_distances])
        pallet_distances.sort(key=lambda x: (x[1], x[0].id))
        ret = [pallet.id for pallet, _ in pallet_distances]
        logger.debug(f"Pallets sorted by distance to {destination.name} at time {timestamp}: {[pallet for pallet, _ in pallet_distances]}")
        return ret


if __name__ == "__main__":
    metric = PalletDistanceMetric()
    conveyor_graph = metric._conveyor_graph
    
    metric.set_pallet_position(1, PalletPosition.S1, timestamp=10)
    metric.set_pallet_position(2, PalletPosition.S3, timestamp=20)
    metric.set_pallet_position(3, PalletPosition.QC_1, timestamp=15)

    print("Pallets for MILL_1:", metric.get_pallets_sorted_by_distance_to(PalletPosition.MILL_1, timestamp=30))

    # print(f"Distance from A to B: {_shortest_path_length(conveyor_graph, 'A', 'B')} s")
    # print(f"Distance from M to F: {_shortest_path_length(conveyor_graph, 'M', 'F')} s")
    # print(f"Distance from QC_1 to MILL_1: {_shortest_path_length(conveyor_graph, '34', '17')} s")
    # print(f"Distance from UNDEFINED to SPEA_1: {_shortest_path_length(conveyor_graph, 'UNDEFINED', '9')} s")

    # plt.figure(figsize=(12, 8))
    # # pos = nx.spring_layout(conveyor_graph)
    # nx.draw(conveyor_graph, with_labels=True, node_size=1000, node_color="lightblue", font_size=10, font_weight="bold", arrowsize=20)
    # plt.title("Conveyor System Graph")
    # plt.show()

    # print()