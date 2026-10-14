"""Independent, standard-library-only scheduling engine.

Courses are zero-indexed internally and one-indexed in all user-facing output.
Every colour class is an independent set with at most R vertices.
"""

from dataclasses import dataclass
from math import ceil, isfinite
import random
from time import perf_counter


@dataclass(frozen=True)
class Graph:
    n: int
    capacity: int
    edges: tuple[tuple[int, int], ...]

    def __post_init__(self):
        if not isinstance(self.n, int) or isinstance(self.n, bool) or self.n < 0:
            raise ValueError("N must be a nonnegative integer.")
        if not isinstance(self.capacity, int) or isinstance(self.capacity, bool) or self.capacity < 1:
            raise ValueError("R (hall capacity) must be a positive integer.")
        normalized = set()
        for u, v in self.edges:
            if not isinstance(u, int) or not isinstance(v, int) or not (0 <= u < self.n and 0 <= v < self.n):
                raise ValueError(f"Course IDs must be between 1 and {self.n}.")
            if u == v:
                raise ValueError(f"Course {u + 1} cannot conflict with itself.")
            normalized.add((min(u, v), max(u, v)))
        object.__setattr__(self, "edges", tuple(sorted(normalized)))

    @property
    def adjacency(self) -> tuple[frozenset[int], ...]:
        neighbors = [set() for _ in range(self.n)]
        for u, v in self.edges:
            neighbors[u].add(v)
            neighbors[v].add(u)
        return tuple(frozenset(x) for x in neighbors)

    @property
    def density(self) -> float:
        return len(self.edges) / (self.n * (self.n - 1) / 2) if self.n > 1 else 0.0

    @classmethod
    def random(cls, n: int, capacity: int, density: float, seed: int = 42):
        if not isfinite(density) or not 0 <= density <= 1:
            raise ValueError("Edge density must be between 0 and 1.")
        cls(n, capacity, ())  # Validate before generating anything.
        rng = random.Random(seed)
        return cls(n, capacity, tuple((u, v) for u in range(n) for v in range(u + 1, n)
                                      if rng.random() < density))


@dataclass(frozen=True)
class Result:
    algorithm: str
    assignment: tuple[int, ...]
    order: tuple[int, ...]
    seconds: float
    lower_bound: int
    optimal: bool
    status: str
    search_nodes: int = 0

    @property
    def slots_used(self) -> int:
        return max(self.assignment, default=-1) + 1

    @property
    def slots(self) -> list[list[int]]:
        return [[v + 1 for v, color in enumerate(self.assignment) if color == c]
                for c in range(self.slots_used)]


def clique_witness(graph: Graph) -> tuple[int, ...]:
    """Find a clique, not necessarily a maximum clique. Its size is a safe bound.

    Try high-degree seeds. Intersect candidate neighborhoods at every step so
    every returned pair is guaranteed to conflict. Capped seeds keep this cheap.
    """
    adj = graph.adjacency
    degrees = [len(a) for a in adj]
    best = ()
    for start in sorted(range(graph.n), key=lambda v: (-degrees[v], v))[:64]:
        clique = [start]
        candidates = set(adj[start])
        while candidates:
            v = max(candidates, key=lambda x: (degrees[x], -x))
            clique.append(v)
            candidates.intersection_update(adj[v])
        if len(clique) > len(best):
            best = tuple(clique)
    return best


def lower_bound(graph: Graph) -> int:
    return max(ceil(graph.n / graph.capacity), len(clique_witness(graph)))


def validate(graph: Graph, assignment: tuple[int, ...]) -> None:
    """Raise for missing/duplicate courses, clashes, or exceeded hall capacity."""
    if len(assignment) != graph.n:
        raise ValueError("Each course must be assigned exactly once.")
    if any(not isinstance(c, int) or c < 0 for c in assignment):
        raise ValueError("Every course must have a nonnegative integer slot.")
    colors = set(assignment)
    if colors != set(range(len(colors))):
        raise ValueError("Slot numbers must be contiguous.")
    counts = [0] * len(colors)
    for c in assignment:
        counts[c] += 1
    if any(count > graph.capacity for count in counts):
        raise ValueError("A slot exceeds the number of available halls.")
    if any(assignment[u] == assignment[v] for u, v in graph.edges):
        raise ValueError("Conflicting courses share a slot.")


def _greedy(graph: Graph, dynamic: bool) -> Result:
    start = perf_counter()
    adj = graph.adjacency
    colors = [-1] * graph.n
    counts: list[int] = []
    uncolored = set(range(graph.n))
    fixed = sorted(uncolored, key=lambda v: (-len(adj[v]), v))
    saturation = [set() for _ in range(graph.n)]
    order = []
    while uncolored:
        v = max(uncolored, key=lambda x: (len(saturation[x]), len(adj[x]), -x)) if dynamic else fixed[len(order)]
        c = next((c for c, count in enumerate(counts)
                  if count < graph.capacity and c not in saturation[v]), len(counts))
        if c == len(counts):
            counts.append(0)
        counts[c] += 1
        colors[v] = c
        uncolored.remove(v)
        order.append(v)
        for neighbor in adj[v]:
            if neighbor in uncolored:
                saturation[neighbor].add(c)
    lb = lower_bound(graph)
    assignment = tuple(colors)
    validate(graph, assignment)
    optimal = len(counts) == lb
    return Result("DSatur" if dynamic else "Welsh–Powell", assignment, tuple(order),
                  perf_counter() - start, lb, optimal, "bound_match" if optimal else "heuristic")


def dsatur(graph: Graph) -> Result:
    return _greedy(graph, True)


def welsh_powell(graph: Graph) -> Result:
    return _greedy(graph, False)


class _SearchTimeout(Exception):
    pass


def exact(graph: Graph, time_limit: float = 3.0) -> Result:
    """Exact k-colour feasibility search with capacity and symmetry pruning.

    Start at a certified lower bound; disprove each k until a solution exists.
    A DSatur/Welsh–Powell incumbent remains available on timeout. A timeout is
    never considered proof of infeasibility. Timings include incumbent setup.
    """
    if not isfinite(time_limit) or time_limit < 0:
        raise ValueError("The exact-search time limit must be finite and nonnegative.")
    start = perf_counter()
    deadline = start + time_limit
    incumbent = min((dsatur(graph), welsh_powell(graph)), key=lambda r: r.slots_used)
    lb = incumbent.lower_bound
    nodes = 0

    def result(status, assignment=None, order=None, bound=None):
        chosen = incumbent.assignment if assignment is None else tuple(assignment)
        trace = incumbent.order if order is None else tuple(order)
        certified = lb if bound is None else bound
        validate(graph, chosen)
        return Result("Exact B&B", chosen, trace, perf_counter() - start, certified,
                      max(chosen, default=-1) + 1 == certified, status, nodes)

    if incumbent.slots_used == lb:
        return result("bound_match")
    # Keep recursive depth safe for the CLI as well as the interactive app.
    if graph.n > 250:
        return result("size_limit")
    adj = graph.adjacency
    adjacency_masks = [sum(1 << u for u in a) for a in adj]
    try:
        for k in range(lb, incumbent.slots_used):
            lb = k
            colors = [-1] * graph.n
            members = [0] * k
            counts = [0] * k
            order: list[int] = []

            def search(remaining: int, used: int) -> bool:
                nonlocal nodes
                nodes += 1
                if perf_counter() >= deadline:
                    raise _SearchTimeout
                if not remaining:
                    return True
                # DSatur branching plus forward checking of every unassigned vertex.
                chosen = -1
                choices = []
                best_key = (-1, -1, -1)
                pending = remaining
                while pending:
                    bit = pending & -pending
                    v = bit.bit_length() - 1
                    pending ^= bit
                    blocked = [bool(adjacency_masks[v] & members[c]) for c in range(used)]
                    allowed = [c for c in range(used) if not blocked[c] and counts[c] < graph.capacity]
                    if used < k:
                        allowed.append(used)  # All unused colours are symmetric.
                    if not allowed:
                        return False
                    key = (sum(blocked), len(adj[v]), -v)
                    if key > best_key:
                        chosen, choices, best_key = v, allowed, key
                # Fill the fullest feasible slots first to preserve open hall capacity.
                choices.sort(key=lambda c: (-counts[c], c))
                bit = 1 << chosen
                for c in choices:
                    colors[chosen] = c
                    members[c] |= bit
                    counts[c] += 1
                    order.append(chosen)
                    if search(remaining ^ bit, max(used, c + 1)):
                        return True
                    order.pop()
                    counts[c] -= 1
                    members[c] ^= bit
                    colors[chosen] = -1
                return False

            if search((1 << graph.n) - 1, 0):
                return result("search_proof", colors, order, k)
            lb = k + 1  # Only exhaustive failure raises the certified lower bound.
        return result("search_proof")
    except _SearchTimeout:
        return result("timeout")


def solve_all(graph: Graph, time_limit: float = 3.0) -> list[Result]:
    return [dsatur(graph), welsh_powell(graph), exact(graph, time_limit)]
