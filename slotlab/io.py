"""Strict text input and portable exports."""

import csv
from dataclasses import asdict
from io import StringIO
import json

from .solver import Graph, Result


def parse_graph(text: str, density: float | None = None, seed: int = 42) -> Graph:
    lines = [line.split("#", 1)[0].strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        raise ValueError("Input is empty. Start with N M R, or N R for a random graph.")
    try:
        header = [int(x) for x in lines[0].split()]
    except ValueError as exc:
        raise ValueError("The first line must contain integers: N M R or N R.") from exc
    if len(header) == 2:
        if len(lines) != 1:
            raise ValueError("Random input accepts only N R. Use N M R for an edge list.")
        if density is None:
            raise ValueError("Specify an edge density for random graph input.")
        return Graph.random(header[0], header[1], density, seed)
    if len(header) != 3:
        raise ValueError("The first line must be N M R or N R.")
    n, m, capacity = header
    if m < 0 or len(lines) - 1 != m:
        raise ValueError(f"Expected exactly {m} conflict lines; found {len(lines) - 1}.")
    edges = []
    for index, line in enumerate(lines[1:], 2):
        try:
            pair = [int(x) for x in line.split()]
        except ValueError as exc:
            raise ValueError(f"Line {index}: course IDs must be integers.") from exc
        if len(pair) != 2:
            raise ValueError(f"Line {index}: expected exactly two course IDs.")
        edges.append((pair[0] - 1, pair[1] - 1))
    return Graph(n, capacity, tuple(edges))


def graph_text(graph: Graph) -> str:
    return f"{graph.n} {len(graph.edges)} {graph.capacity}\n" + "".join(f"{u + 1} {v + 1}\n" for u, v in graph.edges)


def timetable_csv(graph: Graph, result: Result) -> str:
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["Slot"] + [f"Hall {i + 1}" for i in range(graph.capacity)])
    for i, courses in enumerate(result.slots, 1):
        writer.writerow([f"Slot {i}"] + courses + [""] * (graph.capacity - len(courses)))
    return stream.getvalue()


def report_json(graph: Graph, results: list[Result]) -> str:
    reports = []
    for result in results:
        row = asdict(result)
        row["assignment"] = {str(i + 1): c + 1 for i, c in enumerate(result.assignment)}
        row["order"] = [v + 1 for v in result.order]
        row["slots"] = result.slots
        row["slots_used"] = result.slots_used
        reports.append(row)
    return json.dumps({"courses": graph.n, "capacity": graph.capacity,
                       "edges": [[u + 1, v + 1] for u, v in graph.edges],
                       "results": reports}, indent=2)
