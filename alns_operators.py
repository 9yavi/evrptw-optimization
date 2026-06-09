import random
import math
import copy
from typing import List, Tuple, Set, Dict, Optional
from models import Node, Vehicle, Route, Solution
from distance import calculate_distance
from charging import insert_charging_stations
from local_search import try_optimize_sequence

class AdaptiveOperatorSelector:
    """
    Manages Roulette Wheel Selection and adaptive weight tuning for destroy
    and repair operators based on historical success score tracking.
    """
    def __init__(self, destroy_names: List[str] = None, repair_names: List[str] = None,
                 r: float = 0.1, P: int = 100,
                 sigma1: float = 33.0, sigma2: float = 20.0, sigma3: float = 13.0):
        self.destroy_names = destroy_names if destroy_names else ['random', 'worst', 'shaw', 'charging_aware', 'smallest_route']
        self.repair_names = repair_names if repair_names else ['greedy', 'regret2']
        self.r = r  # Reaction factor
        self.P = P  # Segment length
        self.sigma1 = sigma1  # New global best score
        self.sigma2 = sigma2  # Incumbent improvement score
        self.sigma3 = sigma3  # Accepted worse solution score
        
        # Initialize weights to 1.0
        self.destroy_weights = {name: 1.0 for name in self.destroy_names}
        self.repair_weights = {name: 1.0 for name in self.repair_names}
        
        # Initialize scores to 0.0
        self.destroy_scores = {name: 0.0 for name in self.destroy_names}
        self.repair_scores = {name: 0.0 for name in self.repair_names}
        
        # Initialize usage counts to 0
        self.destroy_usage = {name: 0 for name in self.destroy_names}
        self.repair_usage = {name: 0 for name in self.repair_names}
        
        # Initialize total usage counts (not reset at segment boundaries)
        self.total_destroy_usage = {name: 0 for name in self.destroy_names}
        self.total_repair_usage = {name: 0 for name in self.repair_names}
        
        self.iteration_count = 0

    def select_operators(self, r_seed: int = None) -> Tuple[str, str]:
        """Selects a destroy and repair operator using Roulette Wheel Selection."""
        if r_seed is not None:
            random.seed(r_seed)
            
        def roulette_select(weights: Dict[str, float]) -> str:
            total = sum(weights.values())
            pick = random.uniform(0, total)
            current = 0.0
            for name, w in weights.items():
                current += w
                if current >= pick:
                    return name
            return list(weights.keys())[0]
            
        d_op = roulette_select(self.destroy_weights)
        r_op = roulette_select(self.repair_weights)
        
        self.destroy_usage[d_op] += 1
        self.repair_usage[r_op] += 1
        self.total_destroy_usage[d_op] += 1
        self.total_repair_usage[r_op] += 1
        self.iteration_count += 1
        
        return d_op, r_op

    def register_score(self, d_op: str, r_op: str, status: int):
        """
        Registers success points for the chosen operators.
        status:
        - 1: New global best (sigma1)
        - 2: Incumbent improvement (sigma2)
        - 3: Accepted worse solution (sigma3)
        """
        points = 0.0
        if status == 1:
            points = self.sigma1
        elif status == 2:
            points = self.sigma2
        elif status == 3:
            points = self.sigma3
            
        if d_op in self.destroy_scores:
            self.destroy_scores[d_op] += points
        if r_op in self.repair_scores:
            self.repair_scores[r_op] += points
            
        # If segment boundary is reached, update operator weights
        if self.iteration_count >= self.P:
            self.update_weights()

    def update_weights(self):
        """Updates operator weights and resets segment metrics."""
        w_min = 0.05
        
        # Update destroy operator weights
        for name in self.destroy_names:
            u = self.destroy_usage[name]
            w = self.destroy_weights[name]
            if u > 0:
                average_score = self.destroy_scores[name] / u
                new_w = (1 - self.r) * w + self.r * average_score
                self.destroy_weights[name] = max(new_w, w_min)
            # Reset statistics for new segment
            self.destroy_scores[name] = 0.0
            self.destroy_usage[name] = 0
            
        # Update repair operator weights
        for name in self.repair_names:
            u = self.repair_usage[name]
            w = self.repair_weights[name]
            if u > 0:
                average_score = self.repair_scores[name] / u
                new_w = (1 - self.r) * w + self.r * average_score
                self.repair_weights[name] = max(new_w, w_min)
            # Reset statistics for new segment
            self.repair_scores[name] = 0.0
            self.repair_usage[name] = 0
            
        self.iteration_count = 0


# ==========================================
# UTILITY AND HELPERS
# ==========================================

def find_depot(solution: Solution) -> Optional[Node]:
    """Helper to locate the depot node (Type 'd') in the current solution or provider."""
    for route in solution.routes:
        for node in route.nodes:
            if node.is_depot():
                return node
    import distance
    if distance._provider is not None:
        for node in distance._provider.nodes:
            if node.is_depot():
                return node
    return None


def rebuild_partial_solution(solution: Solution, removed_customers: Set[Node], stations: List[Node]) -> Solution:
    """
    Rebuilds a solution by removing a set of customers. Removes empty routes,
    re-runs charging station optimization for modified routes, and returns a new Solution.
    """
    new_routes = []
    vehicle = solution.routes[0].vehicle
    depot = find_depot(solution)
    if not depot:
        raise ValueError("Could not locate depot node.")
    
    for route in solution.routes:
        # Exclude depot and stations to get remaining customers
        route_custs = [n for n in route.nodes if n.is_customer() and n not in removed_customers]
        if not route_custs:
            continue # Discard empty route
        
        # Rebuild route customer sequence starting and ending with the depot
        seq = [depot] + route_custs + [depot]
        repaired_seq = insert_charging_stations(seq, vehicle, stations, prune_redundant=True)
        if repaired_seq:
            new_routes.append(Route(repaired_seq, vehicle))
        else:
            new_routes.append(Route(seq, vehicle))
            
    return Solution(new_routes)


# ==========================================
# DESTROY OPERATORS
# ==========================================

def destroy_random(solution: Solution, k: int, stations: List[Node], seed: int = None) -> Tuple[Solution, List[Node]]:
    """Removes k random customers from the solution."""
    if seed is not None:
        random.seed(seed)
        
    all_customers = []
    for route in solution.routes:
        all_customers.extend([n for n in route.nodes if n.is_customer()])
        
    k = min(k, len(all_customers))
    if k == 0:
        return copy.deepcopy(solution), []
        
    removed = random.sample(all_customers, k)
    partial_sol = rebuild_partial_solution(solution, set(removed), stations)
    return partial_sol, removed


def destroy_worst(solution: Solution, k: int, stations: List[Node], p: float = 6.0, seed: int = None) -> Tuple[Solution, List[Node]]:
    """
    Removes k customers contributing the most detour distance to their current routes.
    Stochastically selects nodes based on detour savings sorted list.
    """
    if seed is not None:
        random.seed(seed)
        
    depot = find_depot(solution)
    if not depot:
        raise ValueError("Could not locate depot node.")

    savings_list = []
    for route in solution.routes:
        route_custs = [n for n in route.nodes if n.is_customer()]
        for customer in route_custs:
            orig_dist = route.get_total_distance()
            remaining_custs = [n for n in route_custs if n != customer]
            seq = [depot] + remaining_custs + [depot]
            repaired_seq = insert_charging_stations(seq, route.vehicle, stations, prune_redundant=True)
            if repaired_seq:
                new_dist = Route(repaired_seq, route.vehicle).get_total_distance()
            else:
                new_dist = Route(seq, route.vehicle).get_total_distance()
            
            savings = orig_dist - new_dist
            savings_list.append((savings, customer))
            
    if not savings_list:
        return copy.deepcopy(solution), []
        
    k = min(k, len(savings_list))
    removed = []
    
    # Sort in descending order of distance savings
    savings_list.sort(key=lambda x: x[0], reverse=True)
    
    for _ in range(k):
        r_val = random.random()
        idx = int(math.floor((r_val ** p) * len(savings_list)))
        idx = min(idx, len(savings_list) - 1)
        
        val = savings_list.pop(idx)
        removed.append(val[1])
        
    partial_sol = rebuild_partial_solution(solution, set(removed), stations)
    return partial_sol, removed


def destroy_shaw(solution: Solution, k: int, stations: List[Node], 
                 phi: Tuple[float, float, float] = (9.0, 3.0, 2.0), 
                 p: float = 6.0, seed: int = None) -> Tuple[Solution, List[Node]]:
    """
    Shaw removal: removes related customers according to distance, ready times, and demands.
    """
    if seed is not None:
        random.seed(seed)
        
    all_customers = []
    for route in solution.routes:
        all_customers.extend([n for n in route.nodes if n.is_customer()])
        
    k = min(k, len(all_customers))
    if k == 0:
        return copy.deepcopy(solution), []
        
    seed_cust = random.choice(all_customers)
    removed = [seed_cust]
    remaining = set(all_customers)
    remaining.remove(seed_cust)
    
    phi1, phi2, phi3 = phi
    
    while len(removed) < k:
        ref_cust = random.choice(removed)
        candidates = list(remaining)
        rel_list = []
        
        for cust in candidates:
            dist_val = calculate_distance(ref_cust, cust)
            time_diff = abs(ref_cust.ready_time - cust.ready_time)
            demand_diff = abs(ref_cust.demand - cust.demand)
            
            relatedness = phi1 * dist_val + phi2 * time_diff + phi3 * demand_diff
            rel_list.append((relatedness, cust))
            
        rel_list.sort(key=lambda x: x[0])
        
        r_val = random.random()
        idx = int(math.floor((r_val ** p) * len(rel_list)))
        idx = min(idx, len(rel_list) - 1)
        
        selected_cust = rel_list[idx][1]
        removed.append(selected_cust)
        remaining.remove(selected_cust)
        
    partial_sol = rebuild_partial_solution(solution, set(removed), stations)
    return partial_sol, removed


def destroy_charging_aware(solution: Solution, k: int, stations: List[Node], p: float = 6.0, seed: int = None) -> Tuple[Solution, List[Node]]:
    """
    Charging-Aware removal (Original Contribution):
    Identifies customer nodes adjacent to charging stations and targets them for removal
    to potentially bypass the charging detour.
    """
    if seed is not None:
        random.seed(seed)
        
    depot = find_depot(solution)
    if not depot:
        raise ValueError("Could not locate depot node.")

    charging_adjacent = set()
    for route in solution.routes:
        for i in range(1, len(route.nodes) - 1):
            curr_node = route.nodes[i]
            if curr_node.is_station():
                prev_node = route.nodes[i-1]
                if prev_node.is_customer():
                    charging_adjacent.add(prev_node)
                next_node = route.nodes[i+1]
                if next_node.is_customer():
                    charging_adjacent.add(next_node)
                    
    if not charging_adjacent:
        # Fall back to worst removal if no charging stations exist in routes
        return destroy_worst(solution, k, stations, p, seed)
        
    savings_list = []
    for route in solution.routes:
        route_custs = [n for n in route.nodes if n.is_customer()]
        for customer in route_custs:
            if customer in charging_adjacent:
                orig_dist = route.get_total_distance()
                remaining_custs = [n for n in route_custs if n != customer]
                seq = [depot] + remaining_custs + [depot]
                repaired_seq = insert_charging_stations(seq, route.vehicle, stations, prune_redundant=True)
                if repaired_seq:
                    new_dist = Route(repaired_seq, route.vehicle).get_total_distance()
                else:
                    new_dist = Route(seq, route.vehicle).get_total_distance()
                
                savings = orig_dist - new_dist
                savings_list.append((savings, customer))
                
    savings_list.sort(key=lambda x: x[0], reverse=True)
    
    k_target = min(k, len(savings_list))
    removed = []
    for _ in range(k_target):
        r_val = random.random()
        idx = int(math.floor((r_val ** p) * len(savings_list)))
        idx = min(idx, len(savings_list) - 1)
        val = savings_list.pop(idx)
        removed.append(val[1])
        
    # If the pool is not full, fill it stochastically using worst removal
    if len(removed) < k:
        all_customers = []
        for route in solution.routes:
            all_customers.extend([n for n in route.nodes if n.is_customer()])
        remaining_all = [c for c in all_customers if c not in removed]
        extra_needed = k - len(removed)
        extra_needed = min(extra_needed, len(remaining_all))
        
        extra_savings = []
        for route in solution.routes:
            route_custs = [n for n in route.nodes if n.is_customer()]
            for customer in route_custs:
                if customer in remaining_all:
                    orig_dist = route.get_total_distance()
                    remaining_custs = [n for n in route_custs if n != customer]
                    seq = [depot] + remaining_custs + [depot]
                    repaired_seq = insert_charging_stations(seq, route.vehicle, stations, prune_redundant=True)
                    if repaired_seq:
                        new_dist = Route(repaired_seq, route.vehicle).get_total_distance()
                    else:
                        new_dist = Route(seq, route.vehicle).get_total_distance()
                    
                    savings = orig_dist - new_dist
                    extra_savings.append((savings, customer))
                    
        extra_savings.sort(key=lambda x: x[0], reverse=True)
        for _ in range(extra_needed):
            if not extra_savings:
                break
            r_val = random.random()
            idx = int(math.floor((r_val ** p) * len(extra_savings)))
            idx = min(idx, len(extra_savings) - 1)
            val = extra_savings.pop(idx)
            removed.append(val[1])
            
    partial_sol = rebuild_partial_solution(solution, set(removed), stations)
    return partial_sol, removed


def destroy_smallest_route(solution: Solution, k: int, stations: List[Node], seed: int = None) -> Tuple[Solution, List[Node]]:
    """
    Identifies the route with the smallest positive number of customers,
    removes it entirely, and places its customers into the repair pool.
    """
    if seed is not None:
        random.seed(seed)
        
    routes_with_custs = [r for r in solution.routes if len([n for n in r.nodes if n.is_customer()]) > 0]
    if not routes_with_custs:
        return copy.deepcopy(solution), []
        
    smallest_route = min(routes_with_custs, key=lambda r: len([n for n in r.nodes if n.is_customer()]))
    removed = [n for n in smallest_route.nodes if n.is_customer()]
    
    new_routes = [r for r in solution.routes if r != smallest_route]
    partial_sol = Solution(new_routes)
    
    return partial_sol, removed


# ==========================================
# REPAIR HELPERS
# ==========================================

def evaluate_new_route(customer: Node, vehicle: Vehicle, depot: Node, stations: List[Node]) -> Tuple[float, Optional[Route]]:
    """Evaluates the feasibility and cost of opening a new route [depot -> customer -> depot]."""
    seq = [depot, customer, depot]
    new_route = try_optimize_sequence(seq, vehicle, stations)
    if new_route:
        return new_route.get_total_distance(), new_route
    return float('inf'), None


def find_best_insertion_in_single_route(customer: Node, route: Route, r_idx: int, stations: List[Node]) -> Tuple[float, Optional[Route], int]:
    """
    Evaluates all insertion slots in a single route. Enforces payload capacity filter first.
    Returns (best_detour, best_route_obj, best_pos)
    """
    vehicle = route.vehicle
    depot = route.nodes[0]
    
    # 1. Payload Capacity quick filter
    route_load = sum(n.demand for n in route.nodes if n.is_customer())
    if route_load + customer.demand > vehicle.capacity:
        return float('inf'), None, -1
        
    best_detour = float('inf')
    best_route_obj = None
    best_pos = -1
    
    cust_list = [n for n in route.nodes if n.is_customer()]
    
    for pos in range(len(cust_list) + 1):
        temp_seq = cust_list[:pos] + [customer] + cust_list[pos:]
        seq = [depot] + temp_seq + [depot]
        
        new_route = try_optimize_sequence(seq, vehicle, stations)
        if new_route:
            new_dist = new_route.get_total_distance()
            detour = new_dist - route.get_total_distance()
            if detour < best_detour:
                best_detour = detour
                best_route_obj = new_route
                best_pos = pos
                
    return best_detour, best_route_obj, best_pos


def find_best_insertion_for_customer(customer: Node, solution: Solution, stations: List[Node], max_routes_to_check: int = 3) -> Tuple[float, Optional[Route], int, int]:
    """
    Finds the best insertion slot for a customer across the top 3 closest candidate routes.
    Returns (best_detour, best_route_obj, route_idx, position)
    """
    vehicle = solution.routes[0].vehicle if solution.routes else None
    depot = find_depot(solution)
    if not vehicle or not depot:
        return float('inf'), None, -1, -1

    candidate_routes_info = []
    
    # Prune search space: capacity check and spatial sorting
    for r_idx, route in enumerate(solution.routes):
        route_load = sum(n.demand for n in route.nodes if n.is_customer())
        if route_load + customer.demand > vehicle.capacity:
            continue
            
        route_custs = [n for n in route.nodes if n.is_customer()]
        if not route_custs:
            d = calculate_distance(customer, depot)
        else:
            d = min(calculate_distance(customer, rc) for rc in route_custs)
            
        candidate_routes_info.append((d, r_idx))
        
    # Sort candidate routes by distance and inspect top N closest
    candidate_routes_info.sort(key=lambda x: x[0])
    selected_indices = [r_idx for _, r_idx in candidate_routes_info[:max_routes_to_check]]
    
    best_detour = float('inf')
    best_route_obj = None
    best_r_idx = -1
    best_pos = -1
    
    for r_idx in selected_indices:
        route = solution.routes[r_idx]
        detour, route_obj, pos = find_best_insertion_in_single_route(customer, route, r_idx, stations)
        if detour < best_detour:
            best_detour = detour
            best_route_obj = route_obj
            best_r_idx = r_idx
            best_pos = pos
            
    return best_detour, best_route_obj, best_r_idx, best_pos


# ==========================================
# REPAIR OPERATORS
# ==========================================

def repair_greedy(partial_solution: Solution, pool: List[Node], vehicle: Vehicle, stations: List[Node], stats: dict = None) -> Solution:
    """Inserts pool customers back into routes greedily based on cheapest detour."""
    current_sol = copy.deepcopy(partial_solution)
    
    depot = find_depot(current_sol)
    if not depot:
        raise ValueError("Could not locate depot node.")
            
    pool_customers = list(pool)
    
    while pool_customers:
        best_cost = float('inf')
        best_customer = None
        best_route_obj = None
        best_r_idx = -1
        
        for customer in pool_customers:
            # Evaluate insertion in existing routes
            detour, route_obj, r_idx, _ = find_best_insertion_for_customer(customer, current_sol, stations)
            if detour < best_cost:
                best_cost = detour
                best_customer = customer
                best_route_obj = route_obj
                best_r_idx = r_idx
                
            # Evaluate opening a new route
            new_r_cost, new_r_obj = evaluate_new_route(customer, vehicle, depot, stations)
            # Apply fleet penalty to discourage opening new routes unless necessary
            fleet_aware_new_route_cost = new_r_cost + 10000.0
            if fleet_aware_new_route_cost < best_cost:
                best_cost = fleet_aware_new_route_cost
                best_customer = customer
                best_route_obj = new_r_obj
                best_r_idx = -2  # New route indicator
                
        if best_customer is None:
            # Fallback: force open a direct route to prevent deadlock if constraints are extremely tight
            c = pool_customers[0]
            new_route = Route([depot, c, depot], vehicle)
            current_sol.routes.append(new_route)
            pool_customers.remove(c)
            if stats is not None:
                stats['fallback_count'] = stats.get('fallback_count', 0) + 1
            continue
            
        if best_r_idx == -2:
            current_sol.routes.append(best_route_obj)
        else:
            current_sol.routes[best_r_idx] = best_route_obj
            
        pool_customers.remove(best_customer)
        
    return current_sol


def repair_regret2(partial_solution: Solution, pool: List[Node], vehicle: Vehicle, stations: List[Node], stats: dict = None) -> Solution:
    """
    Inserts pool customers back based on Regret-2 lookahead heuristic.
    Prioritizes insertion of customers with the largest regret cost (difference
    between best and second-best insertion options across different routes).
    """
    current_sol = copy.deepcopy(partial_solution)
    
    depot = find_depot(current_sol)
    if not depot:
        raise ValueError("Could not locate depot node.")
            
    pool_customers = list(pool)
    
    while pool_customers:
        best_regret = -1.0
        best_customer = None
        best_insertion_option = None  # Tuple: (cost, r_idx, route_obj, position)
        
        for customer in pool_customers:
            options = []
            
            # Spatial Proximity: filter candidate routes
            candidate_routes = []
            for idx, route in enumerate(current_sol.routes):
                route_load = sum(n.demand for n in route.nodes if n.is_customer())
                if route_load + customer.demand > vehicle.capacity:
                    continue
                route_custs = [n for n in route.nodes if n.is_customer()]
                if not route_custs:
                    d = calculate_distance(customer, depot)
                else:
                    d = min(calculate_distance(customer, rc) for rc in route_custs)
                candidate_routes.append((d, idx))
                
            candidate_routes.sort(key=lambda x: x[0])
            selected_indices = [idx for _, idx in candidate_routes[:3]]
            
            for r_idx in selected_indices:
                route = current_sol.routes[r_idx]
                detour, route_obj, position = find_best_insertion_in_single_route(customer, route, r_idx, stations)
                if detour < float('inf'):
                    options.append((detour, r_idx, route_obj, position))
                    
            # Evaluate new route option
            new_r_cost, new_r_obj = evaluate_new_route(customer, vehicle, depot, stations)
            if new_r_cost < float('inf'):
                # Apply fleet penalty to discourage opening new routes unless necessary
                options.append((new_r_cost + 10000.0, -2, new_r_obj, 0))
                
            options.sort(key=lambda x: x[0])
            
            if not options:
                regret = -1.0
                best_opt = None
            elif len(options) == 1:
                c_1 = options[0][0]
                best_r_idx = options[0][1]
                if best_r_idx == -2:
                    regret = 0.0
                else:
                    c_2 = 100000.0  # Large default penalty cost for second choice
                    regret = c_2 - c_1
                best_opt = options[0]
            else:
                c_1 = options[0][0]
                best_r_idx = options[0][1]
                if best_r_idx == -2:
                    regret = 0.0
                else:
                    c_2 = 100000.0
                    # Find cheapest option in a different route
                    for opt in options[1:]:
                        if opt[1] != best_r_idx:
                            c_2 = opt[0]
                            break
                    regret = c_2 - c_1
                best_opt = options[0]
                
            if regret > best_regret and best_opt is not None:
                best_regret = regret
                best_customer = customer
                best_insertion_option = best_opt
                
        if best_customer is None:
            # Fallback: force direct route
            c = pool_customers[0]
            new_route = Route([depot, c, depot], vehicle)
            current_sol.routes.append(new_route)
            pool_customers.remove(c)
            if stats is not None:
                stats['fallback_count'] = stats.get('fallback_count', 0) + 1
            continue
            
        cost, r_idx, route_obj, pos = best_insertion_option
        if r_idx == -2:
            current_sol.routes.append(route_obj)
        else:
            current_sol.routes[r_idx] = route_obj
            
        pool_customers.remove(best_customer)
        
    return current_sol
