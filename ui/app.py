import os
import sys
import time
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

# Adjust sys.path to import modules from the parent directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from parser import parse_benchmark_file
from baseline import solve_baseline
from proposed_method import solve_proposed
from evaluation import evaluate_solution
from models import Solution, Route

# Page configuration
st.set_page_config(
    page_title="EVRPTW Optimization Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header { font-size: 2.4rem; font-weight: bold; color: #1E3A8A; margin-bottom: 0.5rem; }
    .sub-header { font-size: 1.2rem; color: #4B5563; margin-bottom: 1.5rem; }
    .card { background-color: #F3F4F6; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; border-left: 5px solid #3B82F6; }
</style>
""", unsafe_allow_html=True)

# Sidebar navigation
st.sidebar.title("⚡ EVRPTW Solver UI")
page = st.sidebar.radio(
    "Navigation Menu",
    [
        "Home Page",
        "Instance Viewer",
        "Optimization Center",
        "Route Visualizations",
        "Benchmark Comparison",
        "Export Center"
    ]
)

# Helper function to find instances
def get_instances():
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data"))
    if not os.path.exists(data_dir):
        return []
    return sorted([f[:-4] for f in os.listdir(data_dir) if f.endswith(".txt")])

instances = get_instances()

# --- HOME PAGE ---
if page == "Home Page":
    st.markdown('<div class="main-header">Electric Vehicle Routing Problem with Time Windows (EVRPTW)</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">An Advanced Academic Optimization & Metaheuristic Framework</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Project Overview")
        st.write("""
        This project presents a comparative optimization framework designed to solve the **Electric Vehicle Routing Problem with Time Windows (EVRPTW)**.
        EVRPTW extends the traditional vehicle routing problem (VRPTW) by factoring in:
        * **Limited Battery Capacity**: Vehicles consume energy based on distance traveled and must recharge when battery levels run low.
        * **Charging Stations**: Recharging stops can be inserted at dedicated charging locations with linear recharging rates.
        * **Tight Time Windows**: Customers must be served within their specific ready-time and due-date windows. Arrival before the ready time requires waiting.
        """)
        
        st.subheader("Dataset Overview")
        st.write("""
        We use the authoritative **Schneider et al. (2014)** EVRPTW benchmark collection. 
        The benchmark instances include:
        * **C (Clustered)**: Customers grouped in tight spatial clusters.
        * **R (Random)**: Customers randomly distributed across coordinates.
        * **RC (Random-Clustered)**: A hybrid layout combining clusters and random coordinates.
        """)

    with col2:
        st.subheader("Solver Pipeline")
        st.markdown("""
        <div class="card">
            <h4>1. Precomputations</h4>
            <p>A global <code>DistanceProvider</code> precomputes pairwise distance/time matrices and nearest-station caches for fast O(1) lookups.</p>
        </div>
        <div class="card">
            <h4>2. Proposed Initial Solver</h4>
            <p>Uses a sequential best-insertion construction heuristic prioritizing customer due dates and minimizing detour cost.</p>
        </div>
        <div class="card">
            <h4>3. VNS Local Search</h4>
            <p>Refines solutions using intra-route 2-Opt, inter-route Relocate, inter-route Exchange, and Route Merging.</p>
        </div>
        <div class="card">
            <h4>4. ILS Metaheuristic</h4>
            <p>Perturbs routing sequences and accepts moves based on a Simulated Annealing cooling schedule.</p>
        </div>
        """, unsafe_allow_html=True)

# --- INSTANCE VIEWER ---
elif page == "Instance Viewer":
    st.markdown('<div class="main-header">Benchmark Instance Viewer</div>', unsafe_allow_html=True)
    
    if not instances:
        st.error("No benchmark files found in `./data/`. Please verify the directory path.")
    else:
        selected_name = st.selectbox("Select Schneider Instance", instances)
        file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), f"../data/{selected_name}.txt"))
        
        nodes, vehicle = parse_benchmark_file(file_path)
        depot = next(n for n in nodes if n.is_depot())
        customers = [n for n in nodes if n.is_customer()]
        stations = [n for n in nodes if n.is_station()]
        
        # Save selected instance in session state
        st.session_state["selected_instance"] = selected_name
        st.session_state["nodes"] = nodes
        st.session_state["vehicle"] = vehicle

        st.subheader(f"Instance Properties: {selected_name}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Customers Count", len(customers))
        c2.metric("Charging Stations Count", len(stations))
        c3.metric("Vehicle Capacity (C)", vehicle.capacity)
        c4.metric("Battery Capacity (Q)", vehicle.battery_capacity)

        # Tabular View
        st.subheader("Nodes Metadata Table")
        nodes_data = []
        for n in nodes:
            nodes_data.append({
                "ID": n.id,
                "Type": "Depot" if n.is_depot() else ("Customer" if n.is_customer() else "Charging Station"),
                "X": n.x,
                "Y": n.y,
                "Demand": n.demand,
                "Ready Time": n.ready_time,
                "Due Time": n.due_time,
                "Service Time": n.service_time
            })
        st.dataframe(pd.DataFrame(nodes_data), use_container_width=True)

# --- OPTIMIZATION CENTER & RESULTS PAGE ---
elif page == "Optimization Center":
    st.markdown('<div class="main-header">Optimization Center</div>', unsafe_allow_html=True)
    
    # Check if instance is selected
    if "selected_instance" not in st.session_state:
        st.warning("Please go to the 'Instance Viewer' page and select an instance first.")
    else:
        selected_name = st.session_state["selected_instance"]
        nodes = st.session_state["nodes"]
        vehicle = st.session_state["vehicle"]
        
        st.subheader(f"Selected Instance: {selected_name}")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.write("Run optimization solvers on the current instance:")
            run_baseline = st.button("Run Baseline Solver")
            run_proposed = st.button("Run Proposed Solver")
            run_both = st.button("Compare Both Solvers")

        with col2:
            solvers_to_run = []
            if run_baseline:
                solvers_to_run = ["Baseline"]
            elif run_proposed:
                solvers_to_run = ["Proposed"]
            elif run_both:
                solvers_to_run = ["Baseline", "Proposed"]

            if solvers_to_run:
                for solver in solvers_to_run:
                    with st.spinner(f"Running {solver} Solver..."):
                        start_time = time.time()
                        if solver == "Baseline":
                            sol = solve_baseline(nodes, vehicle)
                        else:
                            sol = solve_proposed(nodes, vehicle, max_iter=20)
                        runtime = time.time() - start_time
                        eval_res = evaluate_solution(sol, runtime)
                        
                        # Store in session state for route plotting
                        st.session_state[f"sol_{solver}"] = sol
                        st.session_state[f"eval_{solver}"] = eval_res
                        
                    st.success(f"{solver} Solver finished in {runtime:.3f} seconds!")
                    
                    # Display metrics in cards
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Distance", f"{eval_res['total_distance']:.2f}")
                    m2.metric("Route Count", eval_res["num_routes"])
                    m3.metric("Feasibility", "Feasible" if eval_res["feasible"] else "Infeasible")
                    m4.metric("Runtime (s)", f"{eval_res['runtime']:.3f}")
                    
                    # Violations summary
                    if not eval_res["feasible"]:
                        st.error(f"Violations detected: Load={eval_res['capacity_violations']:.1f}, "
                                 f"Battery={eval_res['battery_violations']:.1f}, "
                                 f"Time Windows={eval_res['time_window_violations']:.1f}")
                    else:
                        st.info("Route satisfies all capacity, battery, and time-window constraints.")

# --- ROUTE VISUALIZATIONS ---
elif page == "Route Visualizations":
    st.markdown('<div class="main-header">Route Visualizations</div>', unsafe_allow_html=True)
    
    if "selected_instance" not in st.session_state:
        st.warning("Please go to the 'Instance Viewer' page and select an instance first.")
    else:
        selected_name = st.session_state["selected_instance"]
        nodes = st.session_state["nodes"]
        vehicle = st.session_state["vehicle"]
        
        # Check if solvers have been run
        has_baseline = f"sol_Baseline" in st.session_state
        has_proposed = f"sol_Proposed" in st.session_state
        
        if not has_baseline and not has_proposed:
            st.info("Please run a solver in the 'Optimization Center' to generate routes for visualization.")
        else:
            solver_choice = st.radio("Select Solver Route to Visualize", 
                                     [s for s in ["Baseline", "Proposed"] if f"sol_{s}" in st.session_state])
            
            sol = st.session_state[f"sol_{solver_choice}"]
            eval_res = st.session_state[f"eval_{solver_choice}"]
            
            st.subheader(f"{solver_choice} Routing Plan: {selected_name}")
            
            # Draw interactive zoomable Plotly map
            fig = go.Figure()
            
            # Map node groups
            depot = next(n for n in nodes if n.is_depot())
            customers = [n for n in nodes if n.is_customer()]
            stations = [n for n in nodes if n.is_station()]
            
            # Plot Depot
            fig.add_trace(go.Scatter(
                x=[depot.x], y=[depot.y],
                mode='markers',
                marker=dict(size=16, color='red', symbol='square'),
                name='Depot',
                hovertext=f"Depot: {depot.id}<br>Coords: ({depot.x}, {depot.y})",
                hoverinfo='text'
            ))
            
            # Plot Stations
            fig.add_trace(go.Scatter(
                x=[s.x for s in stations], y=[s.y for s in stations],
                mode='markers',
                marker=dict(size=12, color='green', symbol='triangle-up'),
                name='Charging Stations',
                hovertext=[f"Station: {s.id}<br>Coords: ({s.x}, {s.y})" for s in stations],
                hoverinfo='text'
            ))
            
            # Plot Customers
            fig.add_trace(go.Scatter(
                x=[c.x for c in customers], y=[c.y for c in customers],
                mode='markers',
                marker=dict(size=8, color='blue', symbol='circle'),
                name='Customers',
                hovertext=[f"Cust: {c.id}<br>Demand: {c.demand}<br>Time Window: [{c.ready_time}, {c.due_time}]" for c in customers],
                hoverinfo='text'
            ))
            
            # Draw routes
            colors = px.colors.qualitative.Dark24
            for r_idx, route in enumerate(sol.routes):
                rx = [n.x for n in route.nodes]
                ry = [n.y for n in route.nodes]
                color = colors[r_idx % len(colors)]
                
                # Plot line path
                fig.add_trace(go.Scatter(
                    x=rx, y=ry,
                    mode='lines+markers',
                    line=dict(color=color, width=2),
                    marker=dict(size=6, color=color),
                    name=f"Route {r_idx+1}",
                    hovertext=[f"Stop {idx}: {n.id}" for idx, n in enumerate(route.nodes)],
                    hoverinfo='text'
                ))
            
            fig.update_layout(
                title=f"Plotly Interactive Route Map ({solver_choice})",
                xaxis_title="X Coordinate",
                yaxis_title="Y Coordinate",
                width=900,
                height=700,
                legend_title="Legend"
            )
            
            st.plotly_chart(fig, use_container_width=True)

# --- BENCHMARK COMPARISON ---
elif page == "Benchmark Comparison":
    st.markdown('<div class="main-header">Benchmark Comparison Page</div>', unsafe_allow_html=True)
    
    comp_table_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../output/comparison_table.csv"))
    
    if not os.path.exists(comp_table_path):
        st.warning("No benchmark comparison file found at `./output/comparison_table.csv`. Please execute `python3 main.py --run-all` first.")
    else:
        df = pd.read_csv(comp_table_path)
        
        # Clean numeric columns for plotting
        df["Baseline_Distance"] = pd.to_numeric(df["Baseline_Distance"])
        df["Proposed_Distance"] = pd.to_numeric(df["Proposed_Distance"])
        df["Baseline_Runtime_Sec"] = pd.to_numeric(df["Baseline_Runtime_Sec"])
        df["Proposed_Runtime_Sec"] = pd.to_numeric(df["Proposed_Runtime_Sec"])
        
        st.subheader("Objective Comparison Table")
        st.dataframe(df, use_container_width=True)
        st.caption("Note: Distance comparison is not meaningful because the baseline violates battery and time-window constraints.")
        
        st.subheader("Distance Comparison")
        # Plot distance comparison
        fig_dist = go.Figure(data=[
            go.Bar(name='Baseline', x=df['Instance'], y=df['Baseline_Distance'], marker_color='rgb(107, 114, 128)'),
            go.Bar(name='Proposed', x=df['Instance'], y=df['Proposed_Distance'], marker_color='rgb(59, 130, 246)')
        ])
        fig_dist.update_layout(barmode='group', xaxis_title="Instance", yaxis_title="Total Distance")
        st.plotly_chart(fig_dist, use_container_width=True)
        
        # Plot route count comparison
        st.subheader("Route Count Comparison")
        fig_routes = go.Figure(data=[
            go.Bar(name='Baseline', x=df['Instance'], y=df['Baseline_Routes'], marker_color='rgb(107, 114, 128)'),
            go.Bar(name='Proposed', x=df['Instance'], y=df['Proposed_Routes'], marker_color='rgb(34, 197, 94)')
        ])
        fig_routes.update_layout(barmode='group', xaxis_title="Instance", yaxis_title="Number of Routes")
        st.plotly_chart(fig_routes, use_container_width=True)
        
        # Plot runtime comparison
        st.subheader("Runtime Comparison")
        fig_run = go.Figure(data=[
            go.Bar(name='Baseline', x=df['Instance'], y=df['Baseline_Runtime_Sec'], marker_color='rgb(107, 114, 128)'),
            go.Bar(name='Proposed', x=df['Instance'], y=df['Proposed_Runtime_Sec'], marker_color='rgb(239, 68, 68)')
        ])
        fig_run.update_layout(barmode='group', xaxis_title="Instance", yaxis_title="Runtime (Seconds)")
        st.plotly_chart(fig_run, use_container_width=True)

# --- EXPORT CENTER ---
elif page == "Export Center":
    st.markdown('<div class="main-header">Export Center</div>', unsafe_allow_html=True)
    st.write("Export and download generated tables, CSV results, and reports:")
    
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../output"))
    
    # Download results.csv
    res_path = os.path.join(out_dir, "results.csv")
    if os.path.exists(res_path):
        with open(res_path, "r") as f:
            st.download_button(
                label="Download results.csv",
                data=f.read(),
                file_name="results.csv",
                mime="text/csv"
            )
            
    # Download comparison_table.csv
    comp_path = os.path.join(out_dir, "comparison_table.csv")
    if os.path.exists(comp_path):
        with open(comp_path, "r") as f:
            st.download_button(
                label="Download comparison_table.csv",
                data=f.read(),
                file_name="comparison_table.csv",
                mime="text/csv"
            )
            
    # Download summary_report.md
    report_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../reports/summary_report.md"))
    if os.path.exists(report_path):
        with open(report_path, "r") as f:
            st.download_button(
                label="Download summary_report.md",
                data=f.read(),
                file_name="summary_report.md",
                mime="text/markdown"
            )
