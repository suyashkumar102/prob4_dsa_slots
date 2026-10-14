"""Reproducible benchmarks: the same instance is passed to all algorithms."""

from collections.abc import Callable

from .solver import Graph, solve_all


def benchmark(sizes=(10, 20, 30, 40, 50), capacity=5, density=0.3,
              seed=42, repeats=3, time_limit=0.5, progress: Callable | None = None):
    if repeats < 1:
        raise ValueError("Benchmark repeats must be at least 1.")
    rows = []
    total = len(sizes) * repeats
    done = 0
    for n in sizes:
        for trial in range(repeats):
            graph_seed = seed + 1009 * n + trial
            graph = Graph.random(n, capacity, density, graph_seed)
            for result in solve_all(graph, time_limit):
                rows.append({"courses": n, "trial": trial + 1, "seed": graph_seed,
                             "algorithm": result.algorithm, "slots": result.slots_used,
                             "runtime_ms": result.seconds * 1000, "optimal": result.optimal,
                             "lower_bound": result.lower_bound, "status": result.status,
                             "search_nodes": result.search_nodes, "capacity": capacity,
                             "density": density, "exact_budget_s": time_limit})
            done += 1
            if progress:
                progress(done / total)
    return rows
