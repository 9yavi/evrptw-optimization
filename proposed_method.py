import time
import math
import random
import copy
from typing import List, Set, Optional, Tuple
from models import Node, Vehicle, Route, Solution
from distance import calculate_distance, init_distance_provider
from charging import get_best_station_between, insert_charging_stations
from local_search import local_search_optimize, try_optimize_sequence, merge_routes_optimization
from evaluation import evaluate_solution

def check_candidate_feasibility(route_nodes: List[Node], candidate: Node, 
                                vehicle: Vehicle, stations: List[Node], depot: Node) -> Optional[Route]:
    """
    Checks if adding candidate to the route_nodes sequence results in a feasible route
    (zero capacity, battery, and time-window violations).
    Returns the Route object if feasible, else None.
    """
    # Extract customers in the current route sequence (excluding depot at the end)
    clean_seq = [n for n in route_nodes if not n.is_station()] + [candidate, depot]
    
    # Try to insert charging stations
    repaired_seq = insert_charging_stations(clean_seq, vehicle, stations)
    if not repaired_seq:
        return None
        
    route = Route(repaired_seq, vehicle)
    details = route.get_route_details()
    violations = details["violations"]
    
    if violations["capacity"] < 1e-5 and violations["battery"] < 1e-5 and violations["time_window"] < 1e-5:
        return route
    return None

def solve_initial_proposed(nodes: List[Node], vehicle: Vehicle) -> Solution:
    """
    Constructs an initial solution using a sequential best-insertion construction heuristic.
    For the current route, we find the best customer and insertion position that maintains feasibility,
    minimizing (insertion_cost + 0.1 * due_time).
    If no unvisited customer can be feasibly inserted into the current route, we start a new route.
    """
    depot = next((n for n in nodes if n.is_depot()), None)
    if not depot:
        raise ValueError("No depot node found in the instance nodes list.")
    
    customers = [n for n in nodes if n.is_customer()]
    stations = [n for n in nodes if n.is_station()]
    
    unvisited = set(customers)
    routes: List[Route] = []

    while unvisited:
        # Start a new route
        current_route_custs: List[Node] = []
        current_route_dist = 0.0
        
        while True:
            best_customer = None
            best_pos = -1
            best_score = float('inf')
            best_repaired_route = None

            for customer in unvisited:
                # Check load capacity first to avoid running expensive charging insertion
                demand_sum = sum(c.demand for c in current_route_custs) + customer.demand
                if demand_sum > vehicle.capacity:
                    continue

                # Sort positions by distance detour
                positions_with_detour = []
                for pos in range(len(current_route_custs) + 1):
                    prev_node = depot if pos == 0 else current_route_custs[pos-1]
                    next_node = depot if pos == len(current_route_custs) else current_route_custs[pos]
                    detour = calculate_distance(prev_node, customer) + calculate_distance(customer, next_node) - calculate_distance(prev_node, next_node)
                    positions_with_detour.append((detour, pos))
                
                positions_with_detour.sort(key=lambda x: x[0])
                
                # Check top 3 positions for feasibility
                for detour, pos in positions_with_detour[:3]:
                    temp_custs = current_route_custs[:pos] + [customer] + current_route_custs[pos:]
                    seq = [depot] + temp_custs + [depot]
                    
                    # Try to insert charging stations and evaluate feasibility (skip pruning for speed)
                    repaired_seq = insert_charging_stations(seq, vehicle, stations, prune_redundant=False)
                    if repaired_seq:
                        route = Route(repaired_seq, vehicle)
                        details = route.get_route_details()
                        violations = details["violations"]
                        if violations["capacity"] < 1e-5 and violations["battery"] < 1e-5 and violations["time_window"] < 1e-5:
                            new_dist = route.get_total_distance()
                            insertion_cost = new_dist - current_route_dist
                            score = insertion_cost + 0.1 * customer.due_time
                            if score < best_score:
                                best_score = score
                                best_customer = customer
                                best_pos = pos
                                best_repaired_route = route
                            # Found a feasible position for this customer, no need to check other positions
                            break

            if best_customer is not None:
                # Insert customer at the best position
                current_route_custs.insert(best_pos, best_customer)
                current_route_dist = best_repaired_route.get_total_distance()
                unvisited.remove(best_customer)
            else:
                # No customer can be feasibly inserted into this route anymore
                if current_route_custs:
                    # Reconstruct the route with charging stations
                    seq = [depot] + current_route_custs + [depot]
                    repaired_seq = insert_charging_stations(seq, vehicle, stations)
                    routes.append(Route(repaired_seq, vehicle))
                else:
                    # In extreme cases where a single customer cannot be added to a new empty route,
                    # force a direct route to ensure progress.
                    c = min(unvisited, key=lambda cust: calculate_distance(depot, cust))
                    seq = [depot, c, depot]
                    repaired_seq = insert_charging_stations(seq, vehicle, stations)
                    if repaired_seq:
                        routes.append(Route(repaired_seq, vehicle))
                    else:
                        routes.append(Route(seq, vehicle))
                    unvisited.remove(c)
                break

    return Solution(routes)

def perturb_solution(solution: Solution, stations: List[Node], k: int = 3) -> Solution:
    """
    Shakes (perturbs) the solution by removing k random customers and
    inserting them at random feasible spots in other routes.
    """
    vehicle = solution.routes[0].vehicle
    depot = solution.routes[0].nodes[0]
    
    # Extract all customers currently in the solution
    all_customers = []
    routes_customers = []
    
    for r in solution.routes:
        custs = [n for n in r.nodes if n.is_customer()]
        routes_customers.append(custs)
        all_customers.extend(custs)

    if len(all_customers) < k:
        return copy.deepcopy(solution)

    # Pick k customers to remove
    to_remove = random.sample(all_customers, k)
    
    # Rebuild routes with removed customers
    new_routes_cust = []
    for rc in routes_customers:
        new_rc = [c for c in rc if c not in to_remove]
        new_routes_cust.append(new_rc)

    # Insert removed customers back randomly
    for customer in to_remove:
        inserted = False
        route_indices = list(range(len(new_routes_cust)))
        random.shuffle(route_indices)
        
        for idx in route_indices:
            r_cust = new_routes_cust[idx]
            positions = list(range(len(r_cust) + 1))
            random.shuffle(positions)
            
            for pos in positions:
                temp_r_cust = r_cust[:pos] + [customer] + r_cust[pos:]
                
                # Check if it satisfies capacity and can be repaired
                demand_sum = sum(c.demand for c in temp_r_cust)
                if demand_sum <= vehicle.capacity:
                    # Construct full sequence including depot
                    seq = [depot] + temp_r_cust + [depot]
                    # Try to insert charging stations and evaluate feasibility (skip pruning for speed)
                    repaired = insert_charging_stations(seq, vehicle, stations, prune_redundant=False)
                    if repaired:
                        # Verify full time-window and battery feasibility
                        route = Route(repaired, vehicle)
                        details = route.get_route_details()
                        violations = details["violations"]
                        if violations["capacity"] < 1e-5 and violations["battery"] < 1e-5 and violations["time_window"] < 1e-5:
                            new_routes_cust[idx] = temp_r_cust
                            inserted = True
                            break
            if inserted:
                break
        
        if not inserted:
            # If no route could accommodate the customer feasibly, open a new route
            new_routes_cust.append([customer])

    # Convert customer sequences back to Route objects with charging stations
    final_routes = []
    for rc in new_routes_cust:
        if rc:
            seq = [depot] + rc + [depot]
            repaired_seq = insert_charging_stations(seq, vehicle, stations)
            if repaired_seq:
                final_routes.append(Route(repaired_seq, vehicle))
            else:
                final_routes.append(Route(seq, vehicle))

    return Solution(final_routes)

def solve_proposed(nodes: List[Node], vehicle: Vehicle, max_iter: int = 50, 
                   initial_temp: float = 100.0, cooling_rate: float = 0.92) -> Solution:
    """
    Proposed optimization method:
    - DistanceProvider initialization
    - Sequential Best-Insertion construction
    - Post-construction Route Merge Optimization
    - Local Search improvement (2-Opt, relocate, exchange, merge, station pruning)
    - Iterated Local Search (ILS) loop with Simulated Annealing
    """
    # Initialize global DistanceProvider for fast lookup in distance-related queries
    init_distance_provider(nodes, vehicle)
    
    stations = [n for n in nodes if n.is_station()]
    
    # 1. Construction Phase
    current_sol = solve_initial_proposed(nodes, vehicle)
    
    # Pack routes immediately after construction
    current_sol = merge_routes_optimization(current_sol, stations)
    
    # 2. Local Search Improvement
    current_sol = local_search_optimize(current_sol, stations)
    
    best_sol = current_sol
    best_eval = evaluate_solution(best_sol)
    
    temp = initial_temp

    for iteration in range(max_iter):
        # 3. Perturbation (Shaking)
        k_perturbed = min(len(nodes) // 10, random.randint(2, 4))
        perturbed_sol = perturb_solution(current_sol, stations, k=k_perturbed)
        
        # 4. Local Search
        perturbed_sol = local_search_optimize(perturbed_sol, stations)
        
        # Evaluate new solution
        new_eval = evaluate_solution(perturbed_sol)
        curr_eval = evaluate_solution(current_sol)

        new_dist = new_eval["total_distance"]
        curr_dist = curr_eval["total_distance"]
        
        # Feasibility check
        if new_eval["feasible"]:
            if not best_eval["feasible"]:
                best_sol = perturbed_sol
                best_eval = new_eval
                current_sol = perturbed_sol
                continue

            delta = new_dist - curr_dist
            if delta < 0:
                current_sol = perturbed_sol
                if new_dist < best_eval["total_distance"]:
                    best_sol = perturbed_sol
                    best_eval = new_eval
            else:
                prob = math.exp(-delta / temp)
                if random.random() < prob:
                    current_sol = perturbed_sol
        else:
            if not curr_eval["feasible"]:
                new_violations = new_eval["capacity_violations"] + new_eval["battery_violations"] + new_eval["time_window_violations"]
                curr_violations = curr_eval["capacity_violations"] + curr_eval["battery_violations"] + curr_eval["time_window_violations"]
                if new_violations < curr_violations:
                    current_sol = perturbed_sol

        temp *= cooling_rate

    return best_sol
