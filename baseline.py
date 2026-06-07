import time
from typing import List
from models import Node, Vehicle, Route, Solution
from distance import calculate_distance

def solve_baseline(nodes: List[Node], vehicle: Vehicle) -> Solution:
    """
    Constructs a baseline routing solution using:
    - Nearest Neighbor heuristic
    - Vehicle payload capacity constraint (C)
    
    Ignores:
    - Battery range constraints
    - Charging stations
    - Customer time windows
    """
    start_time = time.time()
    
    # Identify depot and customers
    depot = next((n for n in nodes if n.is_depot()), None)
    if not depot:
        raise ValueError("No depot node found in the instance nodes list.")
    
    customers = [n for n in nodes if n.is_customer()]
    
    unvisited = set(customers)
    routes: List[Route] = []

    while unvisited:
        # Start a new route
        current_node = depot
        route_nodes = [depot]
        current_capacity = 0.0

        while True:
            # Find the nearest customer that fits in remaining capacity
            best_next = None
            min_dist = float('inf')

            for customer in unvisited:
                if current_capacity + customer.demand <= vehicle.capacity:
                    dist = calculate_distance(current_node, customer)
                    if dist < min_dist:
                        min_dist = dist
                        best_next = customer

            if best_next:
                # Visit customer
                route_nodes.append(best_next)
                unvisited.remove(best_next)
                current_capacity += best_next.demand
                current_node = best_next
            else:
                # No more customers can be visited on this route, return to depot
                route_nodes.append(depot)
                break

        routes.append(Route(route_nodes, vehicle))

    return Solution(routes)
