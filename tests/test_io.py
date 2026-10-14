import csv
import io
import json

import pytest

from cli import main
from slotlab.benchmark import benchmark
from slotlab.io import graph_text, parse_graph, report_json, timetable_csv
from slotlab.solver import Graph, exact, solve_all


@pytest.mark.parametrize("text", ["", "a b c", "3 2 2\n1 2", "3 1 2\n1 4", "3 1 2\n1 1", "3 1 2\n0 2", "3 1 2\n1 2 3", "3 0 0", "-1 0 2", "3 1 2\n1 a", "3 2\n1 2", "3", "3 0 2 1"])
def test_reject_invalid_input(text):
    with pytest.raises(ValueError):
        parse_graph(text)


def test_roundtrip_and_comments_and_duplicates():
    graph = parse_graph("# sample\n3 3 2\n1 2\n2 1 # duplicate\n2 3\n")
    assert len(graph.edges) == 2
    assert parse_graph(graph_text(graph)) == graph


def test_random_input_requires_density():
    with pytest.raises(ValueError):
        parse_graph("12 3")
    assert parse_graph("12 3", .4, 8) == Graph.random(12, 3, .4, 8)
    for density in [-.1, 1.1, float("nan")]:
        with pytest.raises(ValueError):
            parse_graph("12 3", density)


def test_exports_complete_and_one_indexed():
    graph = Graph.random(17, 4, .3)
    results = solve_all(graph, .2)
    for result in results:
        rows = list(csv.reader(io.StringIO(timetable_csv(graph, result))))
        assert all(len(row) == graph.capacity + 1 for row in rows)
        assert sorted(int(v) for row in rows[1:] for v in row[1:] if v) == list(range(1, 18))
        assert len(rows) == result.slots_used + 1
    report = json.loads(report_json(graph, results))
    assert report["results"][0]["assignment"]["1"] >= 1
    assert all(v >= 1 for edge in report["edges"] for v in edge)


def test_cli_writes_all_results(tmp_path, capsys):
    source = tmp_path / "input.txt"
    source.write_text("4 2 2\n1 2\n3 4\n")
    destination = tmp_path / "results"
    assert main([str(source), "--out-dir", str(destination)]) == 0
    assert {p.name for p in destination.iterdir()} == {"dsatur.csv", "welsh_powell.csv", "exact.csv", "report.json", "graph.txt"}
    assert "Proven optimal: YES" in capsys.readouterr().out


def test_benchmark_reproducibility_and_schema():
    a = benchmark((6, 9), 3, .3, seed=7, repeats=2, time_limit=.1)
    b = benchmark((6, 9), 3, .3, seed=7, repeats=2, time_limit=.1)
    assert len(a) == 12
    for row, other in zip(a, b):
        assert row["slots"] == other["slots"]
        assert row["seed"] == other["seed"]
        assert row["runtime_ms"] >= 0
    assert {r["algorithm"] for r in a} == {"DSatur", "Welsh–Powell", "Exact B&B"}
