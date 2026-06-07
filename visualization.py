import math
import matplotlib.pyplot as plt
from typing import List
from models import Solution, Node

def plot_routes(solution: Solution, all_nodes: List[Node], title: str, save_path: str) -> None:
    """
    Generates a publication-quality route map using Matplotlib.
    - Depot: Red Square
    - Customers: Blue Circles
    - Charging Stations: Green Triangles
    - Routes: Colored paths with direction arrows
    """
    plt.figure(figsize=(10, 8), dpi=300)
    
    # Separate nodes by type for plotting
    depot = next((n for n in all_nodes if n.is_depot()), None)
    customers = [n for n in all_nodes if n.is_customer()]
    stations = [n for n in all_nodes if n.is_station()]

    # Plot customer nodes
    if customers:
        cx = [n.x for n in customers]
        cy = [n.y for n in customers]
        plt.scatter(cx, cy, color='#3498db', marker='o', s=60, edgecolors='black', 
                    linewidths=0.8, label='Customer', zorder=3)

    # Plot charging stations
    if stations:
        sx = [n.x for n in stations]
        sy = [n.y for n in stations]
        plt.scatter(sx, sy, color='#2ecc71', marker='^', s=100, edgecolors='black', 
                    linewidths=0.8, label='Charging Station', zorder=3)

    # Plot depot
    if depot:
        plt.scatter([depot.x], [depot.y], color='#e74c3c', marker='s', s=160, edgecolors='black', 
                    linewidths=1.0, label='Depot', zorder=4)

    # Colormap for routes
    cmap = plt.cm.get_cmap('tab20', len(solution.routes))
    
    for r_idx, route in enumerate(solution.routes):
        color = cmap(r_idx)
        
        # Plot route path
        rx = [node.x for node in route.nodes]
        ry = [node.y for node in route.nodes]
        
        # Draw the continuous route line
        plt.plot(rx, ry, color=color, linewidth=1.8, alpha=0.85, 
                 label=f"Route {r_idx+1}", zorder=2)
        
        # Draw directional arrows on each segment
        for k in range(len(route.nodes) - 1):
            n1 = route.nodes[k]
            n2 = route.nodes[k+1]
            dx = n2.x - n1.x
            dy = n2.y - n1.y
            
            # Position arrow at the mid-point of the segment
            mid_x = n1.x + dx * 0.5
            mid_y = n1.y + dy * 0.5
            
            # Normalize vector for constant arrow head size
            length = math.sqrt(dx**2 + dy**2)
            if length > 1e-3:
                arrow_dx = (dx / length) * 1.5
                arrow_dy = (dy / length) * 1.5
                plt.arrow(mid_x - arrow_dx * 0.5, mid_y - arrow_dy * 0.5, 
                          arrow_dx, arrow_dy, 
                          color=color, head_width=1.2, head_length=1.8, 
                          length_includes_head=True, zorder=2.5)

    plt.title(title, fontsize=14, fontweight='bold', pad=15)
    plt.xlabel("X Coordinate", fontsize=11, labelpad=8)
    plt.ylabel("Y Coordinate", fontsize=11, labelpad=8)
    plt.grid(True, linestyle='--', alpha=0.5, zorder=1)
    
    # Handle duplicate legends (keep only one marker type label)
    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    plt.legend(by_label.values(), by_label.keys(), loc='best', fontsize=9, frameon=True, shadow=False)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
