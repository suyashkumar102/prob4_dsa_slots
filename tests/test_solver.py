"""Compare exact search to a deliberately independent partition enumeration."""

import itertools
import math
import random

import pytest

from slotlab.solver import Graph, clique_witness, dsatur, exact, solve_all, validate, welsh_powell


def brute_minimum(graph):
    """Enumerate set partitions in course-ID order, not DSatur order."""
    edges = set(graph.edges)
    groups = []
    best = graph.n

    def visit(v):
        nonlocal best
        if v == graph.n:
            best = min(best, len(groups))
            return
        if len(groups) >= best:
            return
        for group in groups:
            if len(group) < graph.capacity and all((u, v) not in edges for u in group):
                group.append(v)
                visit(v + 1)
                group.pop()
        groups.append([v])
        visit(v + 1)
        groups.pop()

    visit(0)
    return best


def test_all_graphs_through_four_vertices():
    for n in range(5):
        candidates = list(itertools.combinations(range(n), 2))
        for mask in range(1 << len(candidates)):
            edges = tuple(edge for i, edge in enumerate(candidates) if mask & (1 << i))
            for capacity in range(1, max(n, 1) + 1):
                graph = Graph(n, capacity, edges)
                expected = brute_minimum(graph)
                for result in solve_all(graph, 1):
                    validate(graph, result.assignment)
                    assert sorted(result.order) == list(range(n))
                    assert result.lower_bound <= expected <= result.slots_used
                    if result.optimal:
                        assert result.slots_used == expected
                result = exact(graph, 1)
                assert result.optimal
                assert result.slots_used == expected


@pytest.mark.parametrize("seed", range(60))
def test_random_small_against_independent_oracle(seed):
    rng = random.Random(seed)
    graph = Graph.random(rng.randint(5, 9), rng.randint(2, 5), rng.random(), seed)
    result = exact(graph, 2)
    assert result.optimal
    assert result.slots_used == brute_minimum(graph)
    validate(graph, result.assignment)
    witness = clique_witness(graph)
    assert all(tuple(sorted(pair)) in graph.edges for pair in itertools.combinations(witness, 2))


def test_greedy_trap_requires_capacity_aware_backtracking():
    graph = Graph(8, 4, ((0, 6), (1, 7), (2, 3), (2, 4), (5, 6)))
    assert dsatur(graph).slots_used == 3
    assert welsh_powell(graph).slots_used == 3
    result = exact(graph)
    assert result.slots_used == 2
    assert result.optimal and result.status == "search_proof"


def test_odd_cycle_proof_and_zero_budget_timeout():
    graph = Graph(5, 3, ((0, 1), (1, 2), (2, 3), (3, 4), (0, 4)))
    limited = exact(graph, 0)
    assert not limited.optimal
    assert limited.status == "timeout"
    assert limited.lower_bound == 2
    validate(graph, limited.assignment)
    completed = exact(graph, 2)
    assert completed.optimal and completed.lower_bound == 3
    assert completed.search_nodes > 0


def test_empty_edgeless_complete_and_capacity_one():
    for graph in [Graph(0, 3, ()), Graph(13, 4, ()), Graph(7, 100, tuple(itertools.combinations(range(7), 2))), Graph.random(12, 1, .2)]:
        result = exact(graph)
        assert result.optimal
        validate(graph, result.assignment)
    assert exact(Graph(13, 4, ())).slots_used == math.ceil(13 / 4)


def test_determinism():
    a = Graph.random(30, 4, .35, 42)
    b = Graph.random(30, 4, .35, 42)
    assert a == b
    assert dsatur(a).assignment == dsatur(b).assignment
    assert welsh_powell(a).order == welsh_powell(b).order


def test_size_limit_is_not_a_proof():
    graph = Graph(251, 251, tuple((i, (i + 1) % 251) for i in range(251)))
    result = exact(graph)
    assert result.status == "size_limit"
    assert not result.optimal
    validate(graph, result.assignment)


@pytest.mark.parametrize("graph,assignment", [(Graph(2, 1, ()), (0, 0)), (Graph(2, 2, ((0, 1),)), (0, 0)), (Graph(2, 2, ()), (0,)), (Graph(2, 2, ()), (0, 2))])
def test_validator_rejects_invalid_schedules(graph, assignment):
    with pytest.raises(ValueError):
        validate(graph, assignment)


@pytest.mark.parametrize("budget", [-1, float("nan"), float("inf")])
def test_invalid_budget(budget):
    with pytest.raises(ValueError):
        exact(Graph(1, 1, ()), budget)
