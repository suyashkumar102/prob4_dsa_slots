"""Plotly views. Colours stay consistent across graph, replay, and timetable."""

import colorsys
from math import ceil, sqrt
import networkx as nx
import plotly.graph_objects as go

from .solver import Graph, Result

PALETTE = ["#8061E8", "#28B49C", "#ECAF51", "#6099E8", "#E77D99", "#A0B866",
           "#B381CD", "#E79564", "#4BB6C8", "#AA8A70", "#6876BE", "#BCB454"]
ALGORITHM_COLORS = {"DSatur": "#8061E8", "Welsh–Powell": "#28B49C", "Exact B&B": "#ECAF51"}


def slot_color(index):
    if index < len(PALETTE):
        return PALETTE[index]
    rgb = colorsys.hsv_to_rgb((index * 0.61803398875) % 1, 0.48, 0.76)
    return "#" + "".join(f"{round(c * 255):02x}" for c in rgb)


def base_layout(fig, height=380):
    fig.update_layout(height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Inter, Segoe UI, sans-serif", color="#72778C", size=12),
                      margin=dict(l=15, r=15, t=20, b=15), hoverlabel=dict(bgcolor="#25253C", font_color="white"))
    return fig


def positions(graph: Graph, layout="Organic"):
    network = nx.Graph()
    network.add_nodes_from(range(graph.n))
    network.add_edges_from(graph.edges)
    if layout == "Circular":
        return nx.circular_layout(network)
    components = sorted(nx.connected_components(network), key=lambda nodes: (-len(nodes), min(nodes)))
    if len(components) > 1:
        # A single force layout compresses small disconnected components until
        # their nodes overlap. Give each component its own equally spaced cell.
        columns = ceil(sqrt(len(components)))
        rows = ceil(len(components) / columns)
        packed = {}
        for index, component in enumerate(components):
            local = nx.spring_layout(network.subgraph(sorted(component)), seed=19, iterations=80)
            cx = (index % columns - (columns - 1) / 2) * 2.5
            cy = ((rows - 1) / 2 - index // columns) * 2.5
            for v, point in local.items():
                packed[v] = (float(point[0]) * .8 + cx, float(point[1]) * .8 + cy)
        extent = max(max(abs(x), abs(y)) for x, y in packed.values()) or 1
        return {v: (x / extent, y / extent) for v, (x, y) in packed.items()}
    return nx.spring_layout(network, seed=19, k=1.9 / max(graph.n, 1) ** 0.5, iterations=100)


def conflict_figure(graph, result, pos, step=None, focus=None, height=410):
    shown = set(result.order[:step]) if step is not None else set(range(graph.n))
    adj = graph.adjacency
    edge_x, edge_y, highlight_x, highlight_y = [], [], [], []
    for u, v in graph.edges:
        xs, ys = (highlight_x, highlight_y) if focus is not None and focus in (u, v) else (edge_x, edge_y)
        xs.extend([float(pos[u][0]), float(pos[v][0]), None])
        ys.extend([float(pos[u][1]), float(pos[v][1]), None])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines", line=dict(color="#E0E2EC", width=1.3), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=highlight_x, y=highlight_y, mode="lines", line=dict(color="#8071B4", width=2), hoverinfo="skip"))
    colors = [slot_color(result.assignment[v]) if v in shown else "#E9EAF1" for v in range(graph.n)]
    latest = result.order[step - 1] if step and step <= graph.n else None
    fig.add_trace(go.Scatter(x=[float(pos[v][0]) for v in range(graph.n)],
                            y=[float(pos[v][1]) for v in range(graph.n)], mode="markers+text",
                            marker=dict(size=32 if graph.n <= 40 else 23, color=colors,
                                        line=dict(color=["#242436" if v == latest or v == focus else "#FFFFFF" for v in range(graph.n)],
                                                  width=[3 if v == latest or v == focus else 2 for v in range(graph.n)])),
                            text=[str(v + 1) for v in range(graph.n)], textfont=dict(color="#FFFFFF", size=12),
                            customdata=[[f"Course {v + 1:02d}", f"Slot {result.assignment[v] + 1}" if v in shown else "Unassigned",
                                         len(adj[v])] for v in range(graph.n)],
                            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>%{customdata[2]} conflicts<extra></extra>"))
    base_layout(fig, height)
    fig.update_layout(showlegend=False, dragmode="pan", uirevision="graph",
                      xaxis=dict(visible=False, range=[-1.25, 1.25]),
                      yaxis=dict(visible=False, scaleanchor="x", scaleratio=1, range=[-1.2, 1.2]))
    return fig


def comparison_figure(results):
    fig = go.Figure(go.Bar(x=[r.slots_used for r in results], y=[r.algorithm for r in results], orientation="h",
                           marker_color=[ALGORITHM_COLORS[r.algorithm] for r in results],
                           text=[f"{r.slots_used} slots" for r in results], textposition="outside",
                           width=0.42, cliponaxis=False,
                           hovertemplate="%{y}: %{x} slots<extra></extra>"))
    base_layout(fig, 205)
    fig.update_layout(margin=dict(l=0, r=55, t=0, b=0),
                      xaxis=dict(visible=False, range=[0, max((r.slots_used for r in results), default=1) * 1.3]),
                      yaxis=dict(autorange="reversed", ticksuffix="   ", showgrid=False))
    return fig


def benchmark_figure(frame, metric, title):
    fig = go.Figure()
    for algorithm, color in ALGORITHM_COLORS.items():
        rows = frame[frame.algorithm == algorithm]
        summary = rows.groupby("courses")[metric].agg(["mean", "min", "max"]).reset_index()
        fig.add_trace(go.Scatter(x=summary.courses, y=summary["mean"], name=algorithm,
                                mode="lines+markers", line=dict(color=color, width=3),
                                marker=dict(size=8), error_y=dict(type="data", symmetric=False,
                                array=summary["max"] - summary["mean"], arrayminus=summary["mean"] - summary["min"], thickness=1),
                                hovertemplate=algorithm + "<br>N=%{x}<br>Mean: %{y:.3f}<extra></extra>"))
    base_layout(fig, 355)
    fig.update_layout(title=dict(text=title, font=dict(size=17, color="#25253C")),
                      margin=dict(l=20, r=20, t=60, b=10), legend=dict(orientation="h", y=-0.2),
                      xaxis=dict(title="Number of courses", showgrid=False, dtick=10),
                      yaxis=dict(title="Milliseconds · log scale" if metric == "runtime_ms" else "Slots used",
                                 type="log" if metric == "runtime_ms" else "linear", gridcolor="#EDEEF4"))
    return fig
