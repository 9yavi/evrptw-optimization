import math
from typing import List, Dict
from models import Node, Vehicle

_provider = None

class DistanceProvider:
    def __init__(self, nodes: List[Node], vehicle: Vehicle):
        self.nodes = nodes
        self.vehicle = vehicle
        self.node_map = {node.id: idx for idx, node in enumerate(nodes)}
        n = len(nodes)
        
        # Precompute distance and travel time matrices
        self.distances = [[0.0] * n for _ in range(n)]
        self.travel_times = [[0.0] * n for _ in range(n)]
        
        for i in range(n):
            for j in range(n):
                d = math.sqrt((nodes[i].x - nodes[j].x)**2 + (nodes[i].y - nodes[j].y)**2)
                self.distances[i][j] = d
                self.travel_times[i][j] = d / vehicle.velocity
        
        # Precompute sorted stations for each node (station reachability)
        self.sorted_stations: Dict[str, List[Node]] = {}
        stations = [node for node in nodes if node.is_station()]
        
        for node in nodes:
            # Sort stations by distance from the current node
            self.sorted_stations[node.id] = sorted(stations, key=lambda s: self.get_distance(node, s))

    def get_distance(self, n1: Node, n2: Node) -> float:
        i = self.node_map.get(n1.id)
        j = self.node_map.get(n2.id)
        if i is not None and j is not None:
            return self.distances[i][j]
        # Fallback to Euclidean if nodes are not in the parsed list (e.g. temporary/copied nodes)
        return math.sqrt((n1.x - n2.x)**2 + (n1.y - n2.y)**2)

    def get_travel_time(self, n1: Node, n2: Node) -> float:
        i = self.node_map.get(n1.id)
        j = self.node_map.get(n2.id)
        if i is not None and j is not None:
            return self.travel_times[i][j]
        return math.sqrt((n1.x - n2.x)**2 + (n1.y - n2.y)**2) / self.vehicle.velocity

def init_distance_provider(nodes: List[Node], vehicle: Vehicle) -> None:
    """Initializes the global distance provider."""
    global _provider
    _provider = DistanceProvider(nodes, vehicle)

def calculate_distance(n1: Node, n2: Node) -> float:
    """Calculates the distance between two nodes (using cached matrix if available)."""
    if _provider is not None:
        return _provider.get_distance(n1, n2)
    return math.sqrt((n1.x - n2.x)**2 + (n1.y - n2.y)**2)

def calculate_travel_time(n1: Node, n2: Node, vehicle: Vehicle) -> float:
    """Calculates the travel time between two nodes (using cached matrix if available)."""
    if _provider is not None:
        return _provider.get_travel_time(n1, n2)
    return math.sqrt((n1.x - n2.x)**2 + (n1.y - n2.y)**2) / vehicle.velocity
