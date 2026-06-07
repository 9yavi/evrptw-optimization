from typing import Dict, Any, List
from models import Solution, Route

def evaluate_solution(solution: Solution, runtime: float = 0.0) -> Dict[str, Any]:
    """
    Evaluates the solution feasibility and calculates total metrics.
    Checks:
    - Load capacity constraints
    - Battery range constraints
    - Customer time window deadlines
    - Route structure correctness (must start and end at the depot)
    """
    total_distance = 0.0
    num_routes = len(solution.routes)
    
    total_capacity_violation = 0.0
    total_battery_violation = 0.0
    total_time_window_violation = 0.0

    violations_by_route = []

    for idx, route in enumerate(solution.routes):
        details = route.get_route_details()
        violations = details["violations"]

        route_dist = route.get_total_distance()
        total_distance += route_dist

        # Check route structure
        structure_correct = True
        if not route.nodes:
            structure_correct = False
        else:
            if not route.nodes[0].is_depot() or not route.nodes[-1].is_depot():
                structure_correct = False

        route_metrics = {
            "route_index": idx,
            "distance": route_dist,
            "capacity_violation": violations["capacity"],
            "battery_violation": violations["battery"],
            "time_window_violation": violations["time_window"],
            "structure_correct": structure_correct
        }
        violations_by_route.append(route_metrics)

        total_capacity_violation += violations["capacity"]
        total_battery_violation += violations["battery"]
        total_time_window_violation += violations["time_window"]

        if not structure_correct:
            # Structurally incorrect routes are considered feasibility failures
            total_capacity_violation += 99999.0

    # A solution is feasible if there are no violations and all routes are structurally correct
    is_feasible = (
        total_capacity_violation < 1e-5 and 
        total_battery_violation < 1e-5 and 
        total_time_window_violation < 1e-5 and
        all(r["structure_correct"] for r in violations_by_route)
    )

    return {
        "feasible": is_feasible,
        "total_distance": total_distance,
        "num_routes": num_routes,
        "capacity_violations": total_capacity_violation,
        "battery_violations": total_battery_violation,
        "time_window_violations": total_time_window_violation,
        "runtime": runtime,
        "violations_by_route": violations_by_route
    }
