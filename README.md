# ⚡ EVRPTW Optimization Framework

> Adaptive Large Neighborhood Search (ALNS) for the Electric Vehicle Routing Problem with Time Windows (EVRPTW)

Python
Optimization
Metaheuristics
Status

---

# 🚗 Project Overview

This project tackles the Electric Vehicle Routing Problem with Time Windows (EVRPTW) using benchmark instances introduced by Schneider et al. (2014).

The objective is to determine feasible routes for electric vehicles while satisfying:

✅ Customer Time Windows  
✅ Vehicle Capacity Constraints  
✅ Battery Constraints  
✅ Charging Station Feasibility  

while minimizing:

🎯 Number of Vehicles Used  
🎯 Total Travel Distance

---

# 🧠 Solvers Included

## 1️⃣ Baseline Solver

A simple capacity-constrained Nearest Neighbor heuristic.

### Characteristics
- Fast execution
- Low computational cost
- Frequently infeasible under EV constraints
- Used as a reference benchmark

---

## 2️⃣ Enhanced ALNS Solver

The proposed optimization framework combines:

- Adaptive Large Neighborhood Search (ALNS)
- Variable Neighborhood Search (VNS)
- Simulated Annealing (SA)
- Adaptive Operator Selection
- Fleet-Aware Repair Heuristics
- Charging-Aware Optimization

This solver was developed iteratively through controlled benchmarking and profiling experiments.

---

# ⚙️ Optimization Architecture

## Destroy Operators

The ALNS layer dynamically selects among:

### 🎲 Random Destroy
Random customer removal.

### 🔥 Worst Destroy
Removes customers contributing the highest routing cost.

### 🧩 Shaw Destroy
Removes related customers based on similarity measures.

### 🔋 Charging-Aware Destroy
Targets customers near charging detours to improve route structure.

### 🚛 Smallest Route Destroy
Eliminates the smallest route and attempts route consolidation.

---

## Repair Operators

### 🟢 Greedy Repair
Inserts customers into the cheapest feasible positions.

### 🟣 Regret-2 Repair
Uses future insertion opportunities to guide customer placement.

---

## Adaptive Layer

### 🎯 Roulette Wheel Selection
Operators are selected according to adaptive probabilities.

### 📈 Dynamic Weight Updates
Successful operators receive higher future selection probabilities.

---

## Local Search Components

### 🔄 2-Opt
Route sequence improvement.

### 🔀 Relocate
Moves customers between routes.

### 🔁 Exchange
Swaps customers between routes.

### 🔗 Route Merge Optimization
Attempts route consolidation while preserving feasibility.

---

# 🔋 EVRPTW Constraints

The solver explicitly handles:

| Constraint | Supported |
|-----------|-----------|
| Vehicle Capacity | ✅ |
| Battery Capacity | ✅ |
| Charging Stations | ✅ |
| Time Windows | ✅ |
| Route Feasibility Validation | ✅ |
| Fleet Minimization | ✅ |

---

# 📊 Benchmark Results

Results after integrating ALNS and Fleet-Aware Repair Penalties:

| Instance | Vehicles | Distance |
|----------|----------|----------|
| C101_21 | 14 | 1285.80 |
| R101_21 | 24 | 1899.29 |
| RC101_21 | 21 | 2184.43 |

All reported solutions satisfy capacity, battery, charging, and time-window constraints.

---

# 🏆 Best Known Solution (BKS) Validation

The framework includes:

✅ BKS Database Support

✅ Vehicle Gap Analysis

✅ Distance Gap Analysis

✅ Automated Benchmark Comparison

This allows objective evaluation against literature results.

---

# 📁 Repository Structure

text evrptw-optimization/ │ ├── alns_operators.py        # ALNS destroy & repair operators ├── baseline.py             # Baseline heuristic ├── bks_database.py         # Best Known Solutions database ├── charging.py             # Charging station handling ├── distance.py             # Cached distance provider ├── evaluation.py           # Feasibility evaluation ├── experiment_runner.py    # Benchmark runner ├── local_search.py         # VNS operators ├── main.py                 # Entry point ├── models.py               # Core models ├── parser.py               # Schneider benchmark parser ├── proposed_method.py      # Enhanced ALNS solver ├── visualization.py        # Route visualization │ ├── data/                   # Benchmark instances ├── reports/                # Project reports ├── ui/                     # Streamlit dashboard │ └── requirements.txt 

---

# 🚀 Installation

bash pip install -r requirements.txt 

---

# ▶️ Run Single Instance

bash python3 main.py --instance C101_21 

---

# 📈 Run Complete Benchmark

bash python3 main.py --run-all 

---

# 🖥️ Interactive Dashboard

Launch the Streamlit dashboard:

bash streamlit run ui/app.py 

Features:

✅ Instance exploration

✅ Benchmark execution

✅ Route visualization

✅ Performance comparison

✅ Interactive charts

---

# 🛠️ Technologies Used

- Python
- Adaptive Large Neighborhood Search (ALNS)
- Variable Neighborhood Search (VNS)
- Simulated Annealing
- Streamlit
- Matplotlib
- Benchmark-Driven Optimization

---

# 🔬 Future Work

Potential improvements identified during profiling:

### ⚡ Partial Charging Policy
Reduce unnecessary charging delays.

### ⚡ Infeasible Search
Allow temporary constraint violations with adaptive penalties.

### ⚡ Charging Optimization
Accelerate charging insertion routines.

### ⚡ Route Elimination Neighborhoods
Further fleet-size reduction strategies.

### ⚡ Full Schneider Benchmark Campaign
Evaluation on all benchmark instances.

---

# 👨‍💻 Authors

Developed as part of an Optimization Project focused on advanced metaheuristics for electric vehicle routing problems.

---

⭐ If you find this project useful, consider starring the re