import math
from typing import List, Optional
from models import Node, Vehicle, Route
from distance import calculate_distance, calculate_travel_time

def get_best_station_between(n1: Node, n2: Node, current_battery: float, current_time: float,
                              vehicle: Vehicle, stations: List[Node], depot: Node) -> Optional[Node]:
    """
    Finds the best charging station to insert between n1 and n2.
    The station must be:
    - Reachable from n1: current_battery - dist(n1, s) * r >= 0
    - Able to reach n2 after charging: Q - dist(s, n2) * r >= 0
    - Time-window feasible at n2: arrival at n2 <= n2.due_time, accounting for waiting and charging times.
    - Safe: From n2, we must be able to escape to depot or another station.
    - Minimizes detour distance: dist(n1, s) + dist(s, n2)
    """
    import distance
    
    best_station = None
    min_detour = float('inf')

    # Retrieve precomputed sorted stations if provider is initialized
    cand_stations = stations
    if distance._provider is not None:
        cand_stations = distance._provider.sorted_stations.get(n1.id, stations)[:5]

    for s in cand_stations:
        dist_1 = calculate_distance(n1, s)
        dist_2 = calculate_distance(s, n2)
        
        # Skip if station is at the same location as n1 or n2 (redundant)
        if dist_1 < 1e-3 or dist_2 < 1e-3:
            continue
            
        energy_to_station = dist_1 * vehicle.consumption_rate
        energy_to_next = dist_2 * vehicle.consumption_rate
        
        # 1. Battery feasibility check
        if current_battery < energy_to_station or vehicle.battery_capacity < energy_to_next:
            continue
            
        # 2. Time-window feasibility check at n2
        arr_s = current_time + calculate_travel_time(n1, s, vehicle)
        # Charging wait and process
        charge_needed = vehicle.battery_capacity - (current_battery - energy_to_station)
        charge_time = charge_needed * vehicle.recharging_rate
        dep_s = max(arr_s, s.ready_time) + charge_time
        
        arr_next = dep_s + calculate_travel_time(s, n2, vehicle)
        if arr_next > n2.due_time:
            continue
            
        # 3. Escape feasibility check from n2 (future reachability)
        rem_battery = vehicle.battery_capacity - energy_to_next
        dist_to_depot = calculate_distance(n2, depot)
        energy_to_depot = dist_to_depot * vehicle.consumption_rate
        
        # Optimize escape check using closest station from DistanceProvider
        import distance
        closest_s = None
        if distance._provider is not None:
            sorted_st = distance._provider.sorted_stations.get(n2.id)
            if sorted_st:
                closest_s = sorted_st[0]
                
        if closest_s is not None:
            dist_to_s = calculate_distance(n2, closest_s)
            can_escape = (rem_battery >= energy_to_depot) or (rem_battery >= dist_to_s * vehicle.consumption_rate)
        else:
            can_escape = (rem_battery >= energy_to_depot) or any(
                (rem_battery >= calculate_distance(n2, st) * vehicle.consumption_rate) 
                for st in stations if calculate_distance(n2, st) > 1e-3
            )
        
        if can_escape:
            detour = dist_1 + dist_2
            if detour < min_detour:
                min_detour = detour
                best_station = s

    return best_station

def insert_charging_stations(node_sequence: List[Node], vehicle: Vehicle, stations: List[Node], prune_redundant: bool = True) -> Optional[List[Node]]:
    """
    Takes a sequence of nodes (starting and ending with the depot) and 
    inserts charging stations where necessary.
    Includes:
    - Feasibility lookahead (escape checks)
    - Correct wait time propagation
    - Station redundancy elimination (optional for speed)
    """
    if len(node_sequence) < 2:
        return node_sequence

    # Remove any existing charging stations first to re-optimize from scratch
    customer_sequence = [n for n in node_sequence if not n.is_station()]
    depot = customer_sequence[-1]
    
    new_sequence = [customer_sequence[0]] # Start with depot
    current_battery = vehicle.battery_capacity
    current_time = max(0.0, customer_sequence[0].ready_time)

    for i in range(len(customer_sequence) - 1):
        curr_node = new_sequence[-1]  # May be a station we just inserted
        next_node = customer_sequence[i+1]

        dist = calculate_distance(curr_node, next_node)
        energy_needed = dist * vehicle.consumption_rate

        # Determine departure time of curr_node (including wait time & service time)
        if i == 0:
            departure_time = max(0.0, curr_node.ready_time)
        else:
            if curr_node.is_station():
                # Recomputed when inserted, but double check
                charge_needed = vehicle.battery_capacity - current_battery
                charge_time = charge_needed * vehicle.recharging_rate
                departure_time = max(current_time, curr_node.ready_time) + charge_time
            else:
                departure_time = max(current_time, curr_node.ready_time) + curr_node.service_time

        arrival_next = departure_time + calculate_travel_time(curr_node, next_node, vehicle)

        if current_battery >= energy_needed and arrival_next <= next_node.due_time:
            # Check if we can escape from next_node
            remaining = current_battery - energy_needed
            dist_to_depot = calculate_distance(next_node, depot)
            energy_to_depot = dist_to_depot * vehicle.consumption_rate
            
            # Optimize escape check using closest station from DistanceProvider
            import distance
            closest_s = None
            if distance._provider is not None:
                sorted_st = distance._provider.sorted_stations.get(next_node.id)
                if sorted_st:
                    closest_s = sorted_st[0]
                    
            if closest_s is not None:
                dist_to_s = calculate_distance(next_node, closest_s)
                can_escape = (remaining >= energy_to_depot) or (remaining >= dist_to_s * vehicle.consumption_rate)
            else:
                can_escape = (remaining >= energy_to_depot) or any(
                    (remaining >= calculate_distance(next_node, s) * vehicle.consumption_rate) 
                    for s in stations if calculate_distance(next_node, s) > 1e-3
                )

            if can_escape:
                # Direct travel is feasible and safe
                new_sequence.append(next_node)
                current_battery = remaining
                current_time = arrival_next
                continue

        # We must insert a station
        station = get_best_station_between(curr_node, next_node, current_battery, departure_time, vehicle, stations, depot)
        if not station:
            return None
        
        # Insert station
        new_sequence.append(station)
        
        # Travel to station
        arr_s = departure_time + calculate_travel_time(curr_node, station, vehicle)
        bat_at_s = current_battery - (calculate_distance(curr_node, station) * vehicle.consumption_rate)
        charge_needed = vehicle.battery_capacity - bat_at_s
        charge_time = charge_needed * vehicle.recharging_rate
        departure_s = max(arr_s, station.ready_time) + charge_time
        
        # Travel from station to next_node
        arr_next = departure_s + calculate_travel_time(station, next_node, vehicle)
        new_sequence.append(next_node)
        
        current_battery = vehicle.battery_capacity - (calculate_distance(station, next_node) * vehicle.consumption_rate)
        current_time = arr_next

    # 4. Redundancy Elimination Phase
    # Iteratively attempt to remove each inserted station and verify if the route remains feasible
    if prune_redundant:
        pruned = True
        while pruned:
            pruned = False
            for k in range(len(new_sequence)):
                if new_sequence[k].is_station():
                    test_seq = new_sequence[:k] + new_sequence[k+1:]
                    # Verify feasibility of test_seq
                    test_route = Route(test_seq, vehicle)
                    details = test_route.get_route_details()
                    violations = details["violations"]
                    if violations["capacity"] < 1e-5 and violations["battery"] < 1e-5 and violations["time_window"] < 1e-5:
                        new_sequence = test_seq
                        pruned = True
                        break

    return new_sequence
