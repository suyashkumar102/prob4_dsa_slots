# Problem 3: Budget Traveller with Coupons

Exam timetable scheduling with conflict and hall-capacity constraints. Includes a Streamlit application and a command-line solver.

## Run the application

Requires Python 3.10 or later.

```bash
python -m pip install -r requirements.txt
python run.py
```

Open **http://localhost:8501**. Alternatively: `python -m streamlit run app.py`.

For a reproducible Windows setup, use a local virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
python run.py
```

The launcher automatically prefers `.venv` when present. On macOS/Linux, use `.venv/bin/python` in place of `.venv\Scripts\python.exe`.

The interface uses Streamlit and Plotly. The scheduling engine uses the Python standard library.

## Features

- **DSatur** with dynamic saturation priority, deterministic tie-breaking, and hall-capacity checks.
- **Welsh–Powell** descending-degree first-fit variant, with capacity checks.
- **Exact branch-and-bound / backtracking:** tests slot counts from a certified lower bound to a greedy upper bound, using DSatur branching, forward checking, bitset conflict checks, and unused-colour symmetry pruning.
- **Solver results:** lower bounds, slot counts, optimality, timeout status, and search-node counts.
- **Conflict graph:** consistent slot colours, organic/circular layouts, course inspection and highlighted incident conflicts, and assignment replay.
- **Timetable grid:** matching colours, capacity utilization, complete slot-wise lists, and CSV downloads with slots as rows and halls as columns.
- **Benchmarks:** slots and running-time charts as N increases, repeated seeded trials, min–max error bars, proof counts, and raw benchmark CSV.
- **Exports:** original graph input and JSON reports for all algorithms.
- **Example graphs:** a sample campus, a capacity-driven greedy trap, and an odd cycle requiring a search proof.

## Input and command line

The CLI and solver use only the Python standard library; no installation is required for these.

### Option 1: conflict edges

```text
N M R
u v
... M lines total
```

Courses are numbered **1 through N**. R is the number of exams that may run in parallel. Blank lines and `# comments` are supported. Repeated edges are deduplicated after validating the declared line count. Self-conflicts, out-of-range IDs, malformed lines, negative N, and nonpositive R are rejected. N=0 is supported as an empty timetable.

```bash
python cli.py examples/sample.txt --out-dir output
python cli.py examples/greedy_trap.txt --time-limit 5
```

Read from stdin by omitting the input filename:

```bash
python cli.py --out-dir output < examples/sample.txt
```

PowerShell equivalent:

```powershell
Get-Content examples/sample.txt | python cli.py --out-dir output
```

### Option 2: random graph

```text
N R
```

```bash
python cli.py examples/random.txt --density 0.30 --seed 42
```

Density is an independent edge probability in [0, 1]; actual density may differ. A fixed seed reproduces the same graph. `--density` is required for two-number CLI input. The application offers a density slider for this input mode.

### Exports

Every CLI run prints the slot count, optimality status, lower bound, runtime, and complete course list per slot for each algorithm, and writes:

```text
output/
  dsatur.csv
  welsh_powell.csv
  exact.csv
  graph.txt
  report.json
```

CSV shape:

```csv
Slot,Hall 1,Hall 2,Hall 3
Slot 1,1,5,7
Slot 2,2,4,6
Slot 3,3,8,10
Slot 4,9,,
```

The application downloads the selected solver's CSV. Its JSON download includes all three results and their complete schedules. Existing CLI export filenames are replaced on another run; use a different `--out-dir` to retain experiments.

## Correctness and optimality

Each slot must be an **independent set** of at most R vertices. Every solver result is validated before returning: all courses appear exactly once, every conflict spans distinct slots, and capacities hold.

A safe initial lower bound is:

```text
LB = max(ceil(N / R), size of a discovered clique)
```

The clique routine constructs a valid clique; it does **not** claim to find a maximum clique. Any valid clique gives a sound bound. If a greedy schedule meets LB, it is proven optimal immediately.

Exact search independently constructs both greedy incumbents and keeps the better one. For each candidate k below that upper bound, it tries every relevant capacity-feasible colouring. It introduces only the first unused colour because unused colour names are interchangeable. Exhaustive failure for k raises the lower bound to k+1. The first successful k is optimal. If every smaller k fails, the incumbent is optimal.

**A timeout is not a proof.** On timeout, the engine returns the valid incumbent and the strongest bound established by completed searches. The initial greedy setup and final validation are included in timing; they can take the total runtime slightly beyond the requested search budget. Exact recursion is capped at 250 courses to avoid Python recursion-depth problems; above this, results are marked `size_limit` unless the initial bounds already prove optimality.

Statuses: `bound_match`, `heuristic`, `search_proof`, `timeout`, `size_limit`.

The application limits interactive input to 120 courses and 100 halls, with random generation limited to 15 halls for readable controls. The timetable preview shows at most 15 hall columns; the full list and CSV always contain the complete schedule. The CLI accepts larger instances. Large or dense instances can make exact search impractical: graph colouring is NP-hard.

## Benchmarking

```bash
python cli.py --benchmark --sizes 10,20,30,40,50 --capacity 5 --density 0.3 --seed 42 --repeats 3 --time-limit 0.5
```

The application's **Benchmarks** tab provides equivalent controls and two charts. Benchmarks run only when requested. Trials use `base_seed + 1009 * N + trial_index`. All three algorithms receive the same graph per trial. Timings use `perf_counter()` and include each algorithm's setup, but exclude graph generation, plotting, and export. Exact timing includes construction of its own greedy incumbents. The benchmark runs algorithms sequentially; these are local wall-clock measurements, not isolated hardware microbenchmarks. Saved rows include size, trial, seed, density, capacity, search budget, algorithm, slots, runtime, proof status, lower bound, and search-node count.

Lines show means across trials, with min–max error bars; runtime uses a logarithmic axis. Exact results without proofs remain valid upper bounds and are explicitly flagged. Generating a timetable in the application is cached by graph and budget; displayed timings are from the original solver execution. Benchmark runs are uncached.

## Complexity

Let V=N and E=M. Graph storage is O(V+E), plus Python integer bitsets for exact search. The straightforward greedy selection/first-fit routines are O(V²+E), excluding the shared clique-bound routine; the bounded-seed clique routine is polynomial and can take O(V³) in the worst case. Exact feasibility search is exponential, up to O(k^V) branches for a candidate k before pruning, with polynomial work per node. Capacity constraints and symmetry pruning improve practical behavior, not worst-case complexity.

## Test

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests check all graphs with up to four vertices at every relevant capacity, compare seeded graphs against an independent set-partition oracle, exercise odd-cycle proofs, greedy traps, zero-budget timeouts, resource limits, malformed inputs, CSV/JSON completeness, CLI exports, seeded benchmark reproducibility, and Streamlit interactions.

## Project map

```text
app.py                 Streamlit interface
run.py                 App launcher
cli.py                 Standard-library CLI
slotlab/solver.py      Graph model, algorithms, bounds, validation
slotlab/io.py          Input parsing and CSV/JSON export
slotlab/benchmark.py   Seeded experimental runner
slotlab/visuals.py     Plotly graph and comparison figures
examples/             Sample input graphs
tests/                Independent correctness and integration checks
```

