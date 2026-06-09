from typing import List, Optional, Tuple
from models import Node, Vehicle, Route, Solution
from charging import insert_charging_stations

def try_optimize_sequence(customer_seq: List[Node], vehicle: Vehicle, stations: List[Node]) -> Optional[Route]:
    """
    Strips out any charging stations, re-inserts optimal charging stations,
    and returns a Route if the resulting sequence is fully feasible (no capacity,
    battery, or time-window violations). Otherwise returns None.
    """
    # Strip existing stations
    clean_seq = [n for n in customer_seq if not n.is_station()]
    
    # Check payload capacity before running expensive station insertion
    if sum(c.demand for c in clean_seq) > vehicle.capacity:
        return None
    
    # Try inserting stations without pruning first for speed
    seq_with_stations = insert_charging_stations(clean_seq, vehicle, stations, prune_redundant=False)
    if not seq_with_stations:
        return None

    route = Route(seq_with_stations, vehicle)
    details = route.get_route_details()
    violations = details["violations"]

    if violations["capacity"] < 1e-5 and violations["battery"] < 1e-5 and violations["time_window"] < 1e-5:
        # Feasible! Now run the redundancy pruning to clean up charging stations
        pruned_seq = insert_charging_stations(clean_seq, vehicle, stations, prune_redundant=True)
        if pruned_seq:
            return Route(pruned_seq, vehicle)
        return route
    return None

def run_2opt_intra(route: Route, stations: List[Node]) -> Route:
    """
    Tries all 2-Opt moves (reversing segments of customers) within the route.
    Returns the improved route, or the original if no improvements were found.
    """
    best_route = route
    best_dist = route.get_total_distance()
    vehicle = route.vehicle

    # Strip stations to identify customer positions
    customers_only = [n for n in route.nodes if not n.is_station()]
    n_customers = len(customers_only) - 2 # Exclude start and end depot

    if n_customers < 2:
        return route

    improved = True
    while improved:
        improved = False
        for i in range(1, n_customers):
            for j in range(i + 1, n_customers + 1):
                # Reverse customer segment from index i to j (inclusive)
                new_cust_seq = (
                    customers_only[:i] + 
                    list(reversed(customers_only[i:j+1])) + 
                    customers_only[j+1:]
                )

                # Try to build a feasible route
                new_route = try_optimize_sequence(new_cust_seq, vehicle, stations)
                if new_route:
                    new_dist = new_route.get_total_distance()
                    if new_dist < best_dist - 1e-2:
                        best_route = new_route
                        best_dist = new_dist
                        # Update customers_only to match the new route for subsequent iterations
                        customers_only = [n for n in new_route.nodes if not n.is_station()]
                        improved = True
                        break
            if improved:
                break

    return best_route

def run_relocate_inter(solution: Solution, stations: List[Node]) -> Solution:
    """
    Tries to move a customer from one route to another position in another route.
    Returns the improved Solution, or the original if no improvements were found.
    """
    improved = True
    routes = list(solution.routes)
    vehicle = routes[0].vehicle if routes else None
    if not vehicle:
        return solution

    while improved:
        improved = False
        for r1_idx in range(len(routes)):
            for r2_idx in range(len(routes)):
                if r1_idx == r2_idx:
                    continue

                r1 = routes[r1_idx]
                r2 = routes[r2_idx]

                r1_cust = [n for n in r1.nodes if not n.is_station()]
                r2_cust = [n for n in r2.nodes if not n.is_station()]

                # Exclude start/end depots
                for i in range(1, len(r1_cust) - 1):
                    customer = r1_cust[i]

                    # Check capacity feasibility on r2 before running insertion checks
                    r2_demand = sum(c.demand for c in r2_cust if c.is_customer())
                    if r2_demand + customer.demand > vehicle.capacity:
                        continue

                    for j in range(1, len(r2_cust)):
                        # Relocate customer from r1_cust[i] to r2_cust[j]
                        new_r1_cust = r1_cust[:i] + r1_cust[i+1:]
                        new_r2_cust = r2_cust[:j] + [customer] + r2_cust[j:]

                        # Try to optimize both routes
                        opt_r1 = try_optimize_sequence(new_r1_cust, vehicle, stations)
                        opt_r2 = try_optimize_sequence(new_r2_cust, vehicle, stations)

                        if opt_r1 and opt_r2:
                            old_dist = r1.get_total_distance() + r2.get_total_distance()
                            new_dist = opt_r1.get_total_distance() + opt_r2.get_total_distance()

                            if new_dist < old_dist - 1e-2:
                                routes[r1_idx] = opt_r1
                                routes[r2_idx] = opt_r2
                                improved = True
                                break
                    if improved:
                        break
                if improved:
                    break
            if improved:
                break

    # Clean up empty routes
    routes = [r for r in routes if len([n for n in r.nodes if n.is_customer()]) > 0]
    return Solution(routes)

def run_exchange_inter(solution: Solution, stations: List[Node]) -> Solution:
    """
    Tries to swap two customers between two different routes.
    Returns the improved Solution, or the original if no improvements were found.
    """
    improved = True
    routes = list(solution.routes)
    vehicle = routes[0].vehicle if routes else None
    if not vehicle:
        return solution

    while improved:
        improved = False
        for r1_idx in range(len(routes)):
            for r2_idx in range(r1_idx + 1, len(routes)):
                r1 = routes[r1_idx]
                r2 = routes[r2_idx]

                r1_cust = [n for n in r1.nodes if not n.is_station()]
                r2_cust = [n for n in r2.nodes if not n.is_station()]

                for i in range(1, len(r1_cust) - 1):
                    for j in range(1, len(r2_cust) - 1):
                        c1 = r1_cust[i]
                        c2 = r2_cust[j]

                        # Check capacity feasibility for both routes before running insertion checks
                        r1_demand_after = sum(c.demand for c in r1_cust if c.is_customer()) - c1.demand + c2.demand
                        r2_demand_after = sum(c.demand for c in r2_cust if c.is_customer()) - c2.demand + c1.demand
                        if r1_demand_after > vehicle.capacity or r2_demand_after > vehicle.capacity:
                            continue

                        # Exchange c1 and c2
                        new_r1_cust = r1_cust[:i] + [c2] + r1_cust[i+1:]
                        new_r2_cust = r2_cust[:j] + [c1] + r2_cust[j+1:]

                        opt_r1 = try_optimize_sequence(new_r1_cust, vehicle, stations)
                        opt_r2 = try_optimize_sequence(new_r2_cust, vehicle, stations)

                        if opt_r1 and opt_r2:
                            old_dist = r1.get_total_distance() + r2.get_total_distance()
                            new_dist = opt_r1.get_total_distance() + opt_r2.get_total_distance()

                            if new_dist < old_dist - 1e-2:
                                routes[r1_idx] = opt_r1
                                routes[r2_idx] = opt_r2
                                improved = True
                                break
                    if improved:
                        break
                if improved:
                    break
            if improved:
                break

    return Solution(routes)

def merge_routes_optimization(solution: Solution, stations: List[Node]) -> Solution:
    """
    Attempts to merge pairs of routes in the solution to minimize the number of routes.
    For each pair of routes, tries to concatenate their customer sequences and re-optimizes
    charging station insertions. If feasible, updates the solution and continues.
    """
    routes = list(solution.routes)
    if not routes:
        return solution
    vehicle = routes[0].vehicle
    
    improved = True
    while improved:
        improved = False
        n = len(routes)
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                r1 = routes[i]
                r2 = routes[j]
                
                # Check vehicle payload capacity first to avoid running expensive station insertion calculations
                r1_cust = [node for node in r1.nodes if node.is_customer()]
                r2_cust = [node for node in r2.nodes if node.is_customer()]
                
                total_demand = sum(c.demand for c in r1_cust) + sum(c.demand for c in r2_cust)
                if total_demand > vehicle.capacity:
                    continue
                
                # Try to merge by sorting all customers chronologically by ready_time
                depot = r1.nodes[0]
                merged_custs = [depot] + sorted(r1_cust + r2_cust, key=lambda node: node.ready_time) + [depot]
                opt_route = try_optimize_sequence(merged_custs, vehicle, stations)
                
                if not opt_route:
                    # Fallback to direct end-to-end concatenation
                    merged_custs_direct = [depot] + r1_cust + r2_cust + [depot]
                    opt_route = try_optimize_sequence(merged_custs_direct, vehicle, stations)
                
                if opt_route:
                    # Merge successful! Remove routes i and j, add merged route
                    new_routes = [routes[k] for k in range(n) if k != i and k != j]
                    new_routes.append(opt_route)
                    routes = new_routes
                    improved = True
                    break
            if improved:
                break
                
    return Solution(routes)

def local_search_optimize(solution: Solution, stations: List[Node]) -> Solution:
    """
    Runs full local search optimization on the solution:
    - Route Merge Optimization
    - Intra-route 2-Opt
    - Inter-route Relocate
    - Inter-route Exchange
    - Route Merge Optimization (again, to catch new merging opportunities)
    """
    # 1. First merge routes if possible
    sol = merge_routes_optimization(solution, stations)
    
    # 2. Optimize intra-route for each route
    routes = []
    for route in sol.routes:
        routes.append(run_2opt_intra(route, stations))
    sol = Solution(routes)

    # 3. Optimize inter-route moves
    sol = run_relocate_inter(sol, stations)
    sol = run_exchange_inter(sol, stations)
    
    # 4. Final merge check
    sol = merge_routes_optimization(sol, stations)

    return sol
