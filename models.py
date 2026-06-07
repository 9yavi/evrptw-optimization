import math
from typing import List, Dict, Any, Tuple

class Node:
    def __init__(self, node_id: str, node_type: str, x: float, y: float, 
                 demand: float, ready_time: float, due_time: float, service_time: float):
        self.id = node_id
        # 'd' = depot, 'c' = customer, 'f' = charging station
        self.type = node_type
        self.x = x
        self.y = y
        self.demand = demand
        self.ready_time = ready_time
        self.due_time = due_time
        self.service_time = service_time

    def is_depot(self) -> bool:
        return self.type.lower() == 'd'

    def is_customer(self) -> bool:
        return self.type.lower() == 'c'

    def is_station(self) -> bool:
        return self.type.lower() == 'f'

    def __repr__(self) -> str:
        return f"Node({self.id}, type={self.type}, x={self.x}, y={self.y}, demand={self.demand})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Node):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


class Vehicle:
    def __init__(self, capacity: float, battery_capacity: float, 
                 consumption_rate: float, recharging_rate: float, velocity: float):
        self.capacity = capacity              # Load capacity C
        self.battery_capacity = battery_capacity  # Battery capacity Q
        self.consumption_rate = consumption_rate  # Fuel consumption rate r
        self.recharging_rate = recharging_rate    # Inverse refueling rate g (time per unit charge)
        self.velocity = velocity              # Velocity v

    def __repr__(self) -> str:
        return (f"Vehicle(C={self.capacity}, Q={self.battery_capacity}, "
                f"r={self.consumption_rate}, g={self.recharging_rate}, v={self.velocity})")


class Route:
    def __init__(self, nodes: List[Node], vehicle: Vehicle):
        self.nodes = nodes  # Must start and end with the depot Node
        self.vehicle = vehicle

    def get_total_distance(self) -> float:
        from distance import calculate_distance
        distance = 0.0
        for i in range(len(self.nodes) - 1):
            n1 = self.nodes[i]
            n2 = self.nodes[i+1]
            distance += calculate_distance(n1, n2)
        return distance

    def get_total_demand(self) -> float:
        return sum(node.demand for node in self.nodes if node.is_customer())

    def get_route_details(self) -> Dict[str, Any]:
        """
        Calculates and returns arrival times, load levels, battery levels, 
        and violations along this route.
        """
        arrival_times = []
        battery_levels = []
        loads = []
        violations = {
            "capacity": 0.0,
            "battery": 0.0,
            "time_window": 0.0
        }

        if not self.nodes:
            return {
                "arrival_times": arrival_times,
                "battery_levels": battery_levels,
                "loads": loads,
                "violations": violations
            }

        # 1. Capacity evaluation
        total_demand = self.get_total_demand()
        if total_demand > self.vehicle.capacity:
            violations["capacity"] = total_demand - self.vehicle.capacity

        # Trace variables
        current_time = 0.0
        current_battery = self.vehicle.battery_capacity
        current_load = total_demand

        arrival_times.append(current_time)
        battery_levels.append(current_battery)
        loads.append(current_load)

        from distance import calculate_distance, calculate_travel_time

        for i in range(len(self.nodes) - 1):
            curr_node = self.nodes[i]
            next_node = self.nodes[i+1]

            # Calculate distance and travel metrics using provider functions
            dist = calculate_distance(curr_node, next_node)
            travel_time = calculate_travel_time(curr_node, next_node, self.vehicle)
            energy_consumed = dist * self.vehicle.consumption_rate

            # Update time and battery on arrival
            # Current node departure time: wait until ready_time if arriving early
            if i == 0:
                departure_time = max(arrival_times[0], curr_node.ready_time)
            else:
                if curr_node.is_station():
                    # Time spent charging: g * (Q - battery_on_arrival)
                    charge_needed = self.vehicle.battery_capacity - battery_levels[i]
                    charge_time = charge_needed * self.vehicle.recharging_rate
                    departure_time = max(arrival_times[i], curr_node.ready_time) + charge_time
                elif curr_node.is_customer():
                    departure_time = max(arrival_times[i], curr_node.ready_time) + curr_node.service_time
                else:
                    # Depot / unexpected
                    departure_time = max(arrival_times[i], curr_node.ready_time)

            arrival_time_next = departure_time + travel_time
            arrival_times.append(arrival_time_next)

            # Update battery level
            if i == 0:
                departure_battery = self.vehicle.battery_capacity
            else:
                departure_battery = self.vehicle.battery_capacity if curr_node.is_station() else battery_levels[i]

            battery_next = departure_battery - energy_consumed
            battery_levels.append(battery_next)

            # Update load
            current_load -= next_node.demand
            loads.append(current_load)

            # Checks violations at next_node
            # Time Window violation
            if arrival_time_next > next_node.due_time:
                violations["time_window"] += (arrival_time_next - next_node.due_time)

            # Battery violation
            if battery_next < -1e-6:
                violations["battery"] += abs(battery_next)

        return {
            "arrival_times": arrival_times,
            "battery_levels": battery_levels,
            "loads": loads,
            "violations": violations
        }

    def __repr__(self) -> str:
        route_str = " -> ".join(node.id for node in self.nodes)
        return f"Route(Dist={self.get_total_distance():.2f}, Nodes=[{route_str}])"


class Solution:
    def __init__(self, routes: List[Route]):
        self.routes = routes

    def get_total_distance(self) -> float:
        return sum(route.get_total_distance() for route in self.routes)

    def get_num_routes(self) -> int:
        return len(self.routes)

    def __repr__(self) -> str:
        return f"Solution(Routes={self.get_num_routes()}, TotalDist={self.get_total_distance():.2f})"
