import re
import os
from typing import Tuple, List, Dict
from models import Node, Vehicle

def parse_slashed_value(line: str) -> float:
    match = re.search(r'/([^/]+)/', line)
    if match:
        return float(match.group(1).strip())
    raise ValueError(f"Could not parse slashed value in line: {line}")

def parse_benchmark_file(file_path: str) -> Tuple[List[Node], Vehicle]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Benchmark file not found at: {file_path}")

    nodes: List[Node] = []
    
    # Default parameters
    capacity = 200.0
    battery_capacity = 79.69
    consumption_rate = 1.0
    recharging_rate = 3.39
    velocity = 1.0

    with open(file_path, 'r') as f:
        lines = f.readlines()

    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue

        # Check for slashed parameter footer format
        # Example: Q Vehicle fuel tank capacity /79.69/
        if '/' in line_strip:
            try:
                val = parse_slashed_value(line_strip)
                if line_strip.startswith('Q') or 'fuel tank' in line_strip.lower() or 'battery' in line_strip.lower():
                    battery_capacity = val
                elif line_strip.startswith('C') or 'load capacity' in line_strip.lower():
                    capacity = val
                elif line_strip.startswith('r') or 'consumption rate' in line_strip.lower():
                    consumption_rate = val
                elif line_strip.startswith('g') or 'refueling rate' in line_strip.lower():
                    recharging_rate = val
                elif line_strip.startswith('v') or 'velocity' in line_strip.lower():
                    velocity = val
            except Exception as e:
                # Fallback or log if line contains slash but isn't a parameter
                pass
            continue

        # Check for colon parameter format
        # Example: CAPACITY : 200.0
        if ':' in line_strip and not line_strip.startswith('NODE_SECTION') and not line_strip.startswith('DISTANCETIME_SECTION'):
            parts = line_strip.split(':', 1)
            key = parts[0].strip().upper()
            val_str = parts[1].strip()
            # Check if it has a numeric value
            try:
                # Extract first float-like substring if it's not simple
                val_match = re.search(r'[-+]?\d*\.\d+|\d+', val_str)
                if val_match:
                    val = float(val_match.group())
                    if 'CAPACITY' in key:
                        capacity = val
                    elif 'ELECTRIC_POWER' in key or 'BATTERY_CAPACITY' in key:
                        battery_capacity = val
                    elif 'CONSUMPTION_RATE' in key:
                        consumption_rate = val
                    elif 'RECHARGING_RATE' in key:
                        recharging_rate = val
                    elif 'VELOCITY' in key:
                        velocity = val
            except ValueError:
                pass
            continue

        # Try to parse node lines
        # Normalize commas to spaces for unified splitting
        normalized_line = line_strip.replace(',', ' ')
        tokens = normalized_line.split()
        
        # We expect 8 or 9 tokens for a node line
        # StringID Type x y demand ReadyTime DueDate ServiceTime  (8 tokens)
        # ID type x y delivery pickup ready_time due_date service_time (9 tokens)
        if len(tokens) >= 8 and tokens[1] in ['d', 'c', 'f']:
            try:
                node_id = tokens[0]
                node_type = tokens[1]
                x = float(tokens[2])
                y = float(tokens[3])
                
                if len(tokens) == 9:
                    # Delivery is typically the demand in EVRPTW (token 4)
                    demand = float(tokens[4])
                    ready_time = float(tokens[6])
                    due_time = float(tokens[7])
                    service_time = float(tokens[8])
                else:
                    demand = float(tokens[4])
                    ready_time = float(tokens[5])
                    due_time = float(tokens[6])
                    service_time = float(tokens[7])
                
                node = Node(node_id, node_type, x, y, demand, ready_time, due_time, service_time)
                nodes.append(node)
            except ValueError:
                # Skip header lines that might have matching token lengths but aren't numbers
                pass

    # Build Vehicle object
    vehicle = Vehicle(
        capacity=capacity,
        battery_capacity=battery_capacity,
        consumption_rate=consumption_rate,
        recharging_rate=recharging_rate,
        velocity=velocity
    )

    return nodes, vehicle
