import os
import argparse
from parser import parse_benchmark_file
from baseline import solve_baseline
from proposed_method import solve_proposed
from evaluation import evaluate_solution
from visualization import plot_routes
from experiment_runner import run_benchmarks, discover_local_instances

def print_metrics(eval_res: dict, solver_name: str):
    print(f"\n--- {solver_name} Solver Metrics ---")
    print(f"Feasible:             {eval_res['feasible']}")
    print(f"Total Distance:       {eval_res['total_distance']:.2f}")
    print(f"Number of Routes:     {eval_res['num_routes']}")
    print(f"Capacity Violations:  {eval_res['capacity_violations']:.2f}")
    print(f"Battery Violations:   {eval_res['battery_violations']:.2f}")
    print(f"Time-Window Violations:{eval_res['time_window_violations']:.2f}")
    print(f"Execution Runtime:    {eval_res['runtime']:.4f} seconds")

def main():
    parser = argparse.ArgumentParser(description="Electric Vehicle Routing Problem with Time Windows (EVRPTW) Optimizer")
    parser.add_argument("--instance", type=str, default=None,
                        help="Name of the benchmark instance to run (e.g. C101_21, R101_21, RC101_21)")
    parser.add_argument("--run-all", action="store_true",
                        help="Runs the full benchmarking suite across multiple instances")
    parser.add_argument("--data-dir", type=str, default="./data",
                        help="Directory to read/download benchmark files")
    parser.add_argument("--output-dir", type=str, default="./output",
                        help="Directory to save output files and plots")
    parser.add_argument("--method", type=str, default="alns", choices=["ils", "alns"],
                        help="Solver method (ils or alns, default is alns)")
    
    args = parser.parse_args()

    if args.run_all:
        all_raw = discover_local_instances(args.data_dir)
        # Filter for large instances (nodes = 100 customers + 21 stations) that end with _21
        instances = [name for name in all_raw if name.lower().endswith('_21')]
        
        print(f"Discovered {len(instances)} large-scale EVRPTW instances in '{args.data_dir}':")
        print(f"First 10: {instances[:10]}")
        print(f"Last 10:  {instances[-10:]}")
        print(f"Starting EVRPTW comparative benchmarking on all {len(instances)} instances...")
        
        # Verify count
        if len(instances) != 56:
            print(f"Warning: Expected exactly 56 instances, but found {len(instances)}.")
            
        run_benchmarks(instances, args.data_dir, args.output_dir, method=args.method)
        print(f"\nBenchmarking complete. All reports and visual plots are saved under: {args.output_dir}")
        return

    if args.instance:
        print(f"Running single instance optimization: {args.instance}")
        file_path = os.path.join(args.data_dir, f"{args.instance}.txt")
        if not os.path.exists(file_path):
            file_path = os.path.join(args.data_dir, args.instance)
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Instance file not found at {os.path.join(args.data_dir, args.instance + '.txt')}")
        
        # Load and parse data
        nodes, vehicle = parse_benchmark_file(file_path)
        
        # 1. Run Baseline
        import time
        start = time.time()
        baseline_sol = solve_baseline(nodes, vehicle)
        baseline_time = time.time() - start
        baseline_eval = evaluate_solution(baseline_sol, baseline_time)
        print_metrics(baseline_eval, "Baseline")
        
        os.makedirs(args.output_dir, exist_ok=True)
        baseline_plot_path = os.path.join(args.output_dir, f"{args.instance}_baseline.png")
        plot_routes(baseline_sol, nodes, f"Baseline Solver: {args.instance}", baseline_plot_path)
        print(f"Baseline route visualization saved to {baseline_plot_path}")

        # 2. Run Proposed Method
        start = time.time()
        proposed_sol = solve_proposed(nodes, vehicle, max_iter=20, method=args.method)
        proposed_time = time.time() - start
        proposed_eval = evaluate_solution(proposed_sol, proposed_time)
        print_metrics(proposed_eval, f"Proposed ({args.method.upper()})")
        
        proposed_plot_path = os.path.join(args.output_dir, f"{args.instance}_proposed.png")
        plot_routes(proposed_sol, nodes, f"Proposed Solver: {args.instance}", proposed_plot_path)
        print(f"Proposed route visualization saved to {proposed_plot_path}")
        return
        
    parser.print_help()

if __name__ == "__main__":
    main()
