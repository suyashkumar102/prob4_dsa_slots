"""Command-line exam scheduler. Run `python cli.py --help`."""

import argparse
import csv
import io
from pathlib import Path
import sys

from slotlab.benchmark import benchmark
from slotlab.io import graph_text, parse_graph, report_json, timetable_csv
from slotlab.solver import solve_all


def main(argv=None):
    parser = argparse.ArgumentParser(description="SlotLab · capacity-constrained exam scheduling")
    parser.add_argument("input", nargs="?", help="Input file; omit to read stdin")
    parser.add_argument("--density", type=float, help="Random edge probability, 0 to 1, for N R input")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--time-limit", type=float, default=5.0, help="Exact search budget in seconds")
    parser.add_argument("--out-dir", type=Path, default=Path("output"), help="Export directory")
    parser.add_argument("--benchmark", action="store_true", help="Run a reproducible scaling benchmark")
    parser.add_argument("--sizes", default="10,20,30,40,50", help="Comma-separated benchmark sizes")
    parser.add_argument("--capacity", type=int, default=5, help="Benchmark hall capacity")
    parser.add_argument("--repeats", type=int, default=3, help="Benchmark trials per size")
    args = parser.parse_args(argv)
    try:
        if args.benchmark:
            sizes = tuple(int(x) for x in args.sizes.split(","))
            rows = benchmark(sizes, args.capacity, 0.3 if args.density is None else args.density,
                             args.seed, args.repeats, args.time_limit)
            output = io.StringIO(newline="")
            writer = csv.DictWriter(output, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
            args.out_dir.mkdir(parents=True, exist_ok=True)
            path = args.out_dir / "benchmark.csv"
            path.write_text(output.getvalue(), encoding="utf-8", newline="")
            print(f"Saved {len(rows)} measurements to {path.resolve()}")
            return 0
        text = Path(args.input).read_text(encoding="utf-8-sig") if args.input else sys.stdin.read()
        graph = parse_graph(text, args.density, args.seed)
        results = solve_all(graph, args.time_limit)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        print(f"SLOTLAB | {graph.n} courses | {len(graph.edges)} conflicts | {graph.capacity} halls")
        filenames = ["dsatur.csv", "welsh_powell.csv", "exact.csv"]
        for result, filename in zip(results, filenames):
            proof = "YES" if result.optimal else "NO (best found, not a proven minimum)"
            print(f"\n{result.algorithm}: {result.slots_used} slots | Proven optimal: {proof}")
            print(f"Lower bound: {result.lower_bound} | {result.seconds * 1000:.3f} ms | {result.status}")
            for slot, courses in enumerate(result.slots, 1):
                print(f"  Slot {slot}: {', '.join(map(str, courses))}")
            (args.out_dir / filename).write_text(timetable_csv(graph, result), encoding="utf-8", newline="")
        (args.out_dir / "report.json").write_text(report_json(graph, results), encoding="utf-8")
        (args.out_dir / "graph.txt").write_text(graph_text(graph), encoding="utf-8")
        print(f"\nTimetables, graph, and report saved to {args.out_dir.resolve()}")
        return 0
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
