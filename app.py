"""SlotLab: run with `python -m streamlit run app.py`."""

from html import escape
from pathlib import Path
import time

import pandas as pd
import streamlit as st

from slotlab.benchmark import benchmark
from slotlab.io import graph_text, parse_graph, report_json, timetable_csv
from slotlab.solver import Graph, clique_witness, solve_all, validate
from slotlab.visuals import benchmark_figure, comparison_figure, conflict_figure, positions, slot_color


st.set_page_config(page_title="SlotLab | Exam timetable", page_icon="📅", layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
html, body, [class*="css"], .stApp {font-family:'Segoe UI',Arial,sans-serif;}
h1,h2,h3,h4 {font-family:'Segoe UI',Arial,sans-serif !important;letter-spacing:normal;}
.stApp {background:#F8F9FC;} .block-container {padding:2rem 2.5rem;max-width:1600px;}
header[data-testid="stHeader"] {background:transparent;height:2.5rem;}
[data-testid="stSidebar"] {background:#FFF;border-right:1px solid #E8EAF2;}
[data-testid="stSidebar"] > div:first-child {padding-top:1.7rem;}
[data-testid="stSidebar"] .block-container {padding:1rem;}
[data-testid="stSidebar"] hr {margin:1.3rem 0;}
[data-testid="stVerticalBlockBorderWrapper"] > div {border-color:#E8EAF2 !important;border-radius:16px !important;}
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlockBorderWrapper"] > div {border-radius:12px !important;}
.brand {font-weight:600;font-size:23px;color:#26263C;}
.eyebrow {font-size:12px;font-weight:600;color:#62677A;}
h1.page-title {font-size:27px !important;font-weight:600 !important;color:#242438;margin:0 0 20px;padding:0;}
.stat {background:white;border:1px solid #E8EAF2;border-radius:8px;padding:14px 17px;min-height:110px;}
.stat .value {font-size:27px;font-weight:600;margin:5px 0 3px;color:#28283F;}
.stat .note {font-size:11px;color:#767B8C;}
.section-title {font-weight:700;color:#303047;font-size:16px;letter-spacing:-.4px;margin:2px 0 4px;}
.section-sub {color:#9295A7;font-size:11px;margin:0 0 10px;line-height:1.7;}
.legend {display:flex;flex-wrap:wrap;gap:14px;justify-content:center;font-size:10px;color:#878B9F;margin:0 0 9px;}
.dot {width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:5px;}
.certificate {background:#F0F8F4;border:1px solid #DDEFE5;border-radius:10px;padding:13px 15px;color:#3F8A6D;font-size:12px;line-height:1.6;margin:12px 0;}
.certificate.pending {background:#FFF8EB;border-color:#F7E4BA;color:#A07836;}
.tiny {font-size:11px;color:#9195A8;line-height:1.7;}
.solver-row {display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #EEF0F6;font-size:11px;color:#8B8EA1;}
.solver-row b {color:#44465A;font-weight:500;}
.table-scroll {overflow-x:auto;margin:13px 0;}
.schedule {width:100%;border-collapse:separate;border-spacing:7px;min-width:430px;}
.schedule th {text-align:left;font-size:10px;color:#9296AA;font-weight:500;padding:5px 8px;text-transform:uppercase;letter-spacing:1px;}
.schedule td {padding:11px 13px;border-radius:8px;font-size:12px;min-width:85px;}
.schedule .slot-label {font-weight:600;color:#62667F;white-space:nowrap;background:#F6F7FA;}
.schedule .exam {border-left:3px solid var(--slot);background:color-mix(in srgb,var(--slot) 11%,white);color:#43465E;}
.schedule .empty {color:#C7CAD8;background:#FAFBFD;text-align:center;border:1px dashed #ECEEF5;}
.st-key-graph_card,.st-key-solver_card,.st-key-timetable_card {background:#FFFFFF;border-radius:14px;}
.stTabs [data-baseweb="tab-list"] {gap:28px;border-bottom:1px solid #E6E8F1;margin:22px 0 23px;}
.stTabs [data-baseweb="tab"] {font-size:12px;padding-bottom:13px;}
.stButton button,.stDownloadButton button {border-radius:8px;font-size:12px;}
[data-testid="stMetric"] {background:white;border-radius:12px;padding:15px;}
[data-testid="stExpander"] {background:white;border-color:#E8EAF2;}
@media(max-width:900px){.block-container{padding:2rem 1rem}.stat{padding:12px}}
@media(min-width:641px) and (max-width:1100px){
  [data-testid="stHorizontalBlock"]:has(>.stColumn .st-key-graph_card),
  [data-testid="stHorizontalBlock"]:has(.st-key-graph_card) {flex-wrap:wrap;}
  [data-testid="stHorizontalBlock"]:has(.st-key-graph_card)>[data-testid="stColumn"] {width:100%;flex:1 1 100%;min-width:100%;}
  .stat {min-height:128px;}
}
</style>""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def cached_solve(graph, budget):
    return solve_all(graph, budget)


@st.cache_data(show_spinner=False)
def cached_positions(graph, layout):
    """Cache the component-aware graph layout across UI interactions."""
    return positions(graph, layout)


def section(title, subtitle=""):
    st.markdown(f'<div class="section-title">{escape(title)}</div><div class="section-sub">{escape(subtitle)}</div>', unsafe_allow_html=True)


def legend(result):
    st.markdown('<div class="legend">' + ''.join(f'<span><i class="dot" style="background:{slot_color(i)}"></i>Slot {i + 1}</span>' for i in range(result.slots_used)) + '</div>', unsafe_allow_html=True)


def timetable_html(graph, result):
    # Large R is valid; do not allocate thousands of empty UI columns.
    shown_halls = min(graph.capacity, max((len(slot) for slot in result.slots), default=1) + 1, 15)
    rows = ['<div class="table-scroll"><table class="schedule"><thead><tr><th>Time slot</th>']
    rows.extend(f'<th>Hall {i + 1:02d}</th>' for i in range(shown_halls))
    rows.append('</tr></thead><tbody>')
    for s, courses in enumerate(result.slots):
        rows.append(f'<tr><td class="slot-label"><i class="dot" style="background:{slot_color(s)}"></i>Slot {s + 1:02d}</td>')
        for h in range(shown_halls):
            rows.append(f'<td class="exam" style="--slot:{slot_color(s)}">Course {courses[h]:02d}</td>' if h < len(courses)
                        else '<td class="empty">—</td>')
        rows.append('</tr>')
    rows.append('</tbody></table></div>')
    return ''.join(rows), shown_halls


with st.sidebar:
    st.markdown('<div class="brand">SlotLab</div>', unsafe_allow_html=True)
    st.divider()
    st.markdown('<div class="eyebrow">Input</div>', unsafe_allow_html=True)
    mode = st.selectbox("Graph source", ["Sample campus", "Greedy trap", "Odd cycle", "Random graph", "Paste input", "Upload file"])
    with st.form("configuration"):
        density = 0.22
        seed = 42
        raw = None
        uploaded = None
        if mode in ("Sample campus", "Random graph"):
            n = st.slider("Courses", 4, 120, 24, 1)
            capacity = st.slider("Available halls / slot", 1, 15, 5)
            density = st.slider("Conflict density", 0.0, 1.0, 0.18 if mode == "Sample campus" else 0.30, 0.01,
                                help="Probability of an edge between each pair. Actual density varies with the seed.")
            seed = st.number_input("Random seed", min_value=0, max_value=2147483647, value=42, step=1)
        elif mode in ("Greedy trap", "Odd cycle"):
            st.caption("8 courses · 5 conflicts · 4 halls" if mode == "Greedy trap" else "5 courses · 5 conflicts · 3 halls")
            raw = Path(__file__).with_name("examples").joinpath("greedy_trap.txt" if mode == "Greedy trap" else "odd_cycle.txt").read_text()
        elif mode == "Paste input":
            raw = st.text_area("N M R + conflicts, or N R", Path(__file__).with_name("examples").joinpath("sample.txt").read_text(), height=180)
        else:
            uploaded = st.file_uploader("Conflict graph (.txt)", type=["txt"], help="Course IDs are 1 through N.")
        if mode in ("Paste input", "Upload file"):
            density = st.slider("Density for N R input", 0.0, 1.0, 0.30, 0.01)
            seed = st.number_input("Random seed", min_value=0, max_value=2147483647, value=42, step=1)
        st.markdown('<div class="eyebrow" style="margin:16px 0 8px">Solver settings</div>', unsafe_allow_html=True)
        budget = st.select_slider("Exact search budget", options=[0.1, 0.5, 1.0, 3.0, 5.0, 10.0], value=3.0, format_func=lambda x: f"{x:g} seconds")
        submitted = st.form_submit_button("Generate timetable", type="primary", use_container_width=True)
    st.caption("Generate a timetable to apply changes.")
    st.divider()
    st.markdown('<div class="eyebrow">Constraints</div><p class="tiny">One exam per course.<br>Conflicting courses use separate slots.<br>Exams per slot cannot exceed hall capacity.</p>', unsafe_allow_html=True)

if "graph" not in st.session_state:
    st.session_state.graph = Graph.random(24, 5, 0.18, 42)
    st.session_state.results = cached_solve(st.session_state.graph, 3.0)
    st.session_state.graph_revision = 0

if submitted:
    try:
        if mode in ("Sample campus", "Random graph"):
            graph = Graph.random(n, capacity, density, int(seed))
        else:
            if mode == "Upload file":
                if uploaded is None:
                    raise ValueError("Choose a .txt file before generating a timetable.")
                raw = uploaded.getvalue().decode("utf-8-sig")
            # Bound input before generating random graphs or dense adjacency structures.
            first = next((line.split("#", 1)[0].strip() for line in raw.splitlines() if line.split("#", 1)[0].strip()), "")
            if first and int(first.split()[0]) > 120:
                raise ValueError("Maximum 120 courses. Use the command-line solver for larger graphs.")
            graph = parse_graph(raw, density, int(seed))
            if graph.capacity > 100:
                raise ValueError("Maximum 100 halls. Use the command-line solver for larger capacities.")
        with st.spinner("Calculating timetable…"):
            results = cached_solve(graph, float(budget))
        st.session_state.graph = graph
        st.session_state.results = results
        st.session_state.graph_revision += 1
    except (ValueError, UnicodeError) as error:
        st.sidebar.error(str(error))

graph = st.session_state.graph
results = st.session_state.results
best = min(results, key=lambda r: (r.slots_used, not r.optimal, r.seconds))

st.markdown('<h1 class="page-title">Exam timetable</h1>', unsafe_allow_html=True)

stats = [("Courses", str(graph.n), ""),
         ("Conflicts", str(len(graph.edges)), f"{graph.density:.0%} edge density"),
         ("Halls per slot", str(graph.capacity), ""),
         ("Fewest slots found", str(best.slots_used), "Proven optimal" if best.optimal else f"Lower bound: {best.lower_bound}")]
for column, (label, value, note) in zip(st.columns(4), stats):
    column.markdown(f'<div class="stat"><div class="eyebrow">{label}</div><div class="value">{value}</div><div class="note">{note}</div></div>', unsafe_allow_html=True)

studio, lab, explain = st.tabs(["Timetable", "Benchmarks", "Methods"])

with studio:
    controls = st.columns([2, 1, 1])
    algorithm = controls[0].selectbox("Algorithm", [r.algorithm for r in results], index=2)
    layout = controls[1].selectbox("Graph layout", ["Organic", "Circular"])
    focus_label = controls[2].selectbox("Inspect conflicts", ["All courses"] + [f"Course {i + 1:02d}" for i in range(graph.n)])
    focus = None if focus_label == "All courses" else int(focus_label.split()[1]) - 1
    selected = next(r for r in results if r.algorithm == algorithm)
    pos = cached_positions(graph, layout)
    left, right = st.columns([1.65, 1], gap="large")
    with left, st.container(border=True, key="graph_card"):
        section("Conflict graph", "Edges indicate shared students; colours indicate assigned slots.")
        st.plotly_chart(conflict_figure(graph, selected, pos, focus=focus), use_container_width=True,
                        config={"displayModeBar": False, "scrollZoom": False}, key="conflict_map")
        legend(selected)
        if focus is not None:
            neighbors = sorted(graph.adjacency[focus])
            st.caption(f"Course {focus + 1} · Slot {selected.assignment[focus] + 1} · Conflicts: " + (", ".join(str(v + 1) for v in neighbors) or "None"))
    with right, st.container(border=True, key="solver_card"):
        section("Algorithm results", "Slots used and running time for this graph.")
        st.plotly_chart(comparison_figure(results), use_container_width=True, config={"displayModeBar": False})
        for result in results:
            st.markdown(f'<div class="solver-row"><b>{result.algorithm}</b><span>{result.seconds * 1000:.2f} ms &nbsp; · &nbsp; {"✓ Optimal" if result.optimal else "Best found"}</span></div>', unsafe_allow_html=True)
        if selected.optimal:
            message = f"<b>Proven optimal</b><br>{selected.slots_used} slots · Lower bound: {selected.lower_bound}"
        else:
            message = f"<b>Optimality not proven</b><br>{selected.slots_used} slots found · Lower bound: {selected.lower_bound}"
        st.markdown(f'<div class="certificate {"" if selected.optimal else "pending"}">{message}</div>', unsafe_allow_html=True)
        if selected.status == "timeout":
            st.caption("Search reached its time budget. The best valid timetable was retained.")
        st.markdown(f'<div class="tiny">{selected.search_nodes:,} search states explored · {algorithm}<br>Times include solver setup; graph rendering is excluded.</div>', unsafe_allow_html=True)

    with st.container(border=True, key="timetable_card"):
        heading, download = st.columns([3, 1])
        with heading:
            section("Slot assignments", "Rows: time slots. Columns: halls.")
        with download:
            st.download_button("Export CSV", timetable_csv(graph, selected),
                               file_name=f"slotlab_{algorithm.lower().replace(' ', '_')}.csv", mime="text/csv", use_container_width=True)
        html, shown_halls = timetable_html(graph, selected)
        st.markdown(html, unsafe_allow_html=True)
        if graph.capacity > shown_halls:
            st.caption(f"Preview shows the first {shown_halls} of {graph.capacity} halls. The CSV and complete list below include all halls and courses.")
        validate(graph, selected.assignment)
        utilization = graph.n / (selected.slots_used * graph.capacity) if selected.slots_used else 0
        st.markdown(f'<div class="tiny">{graph.n} courses scheduled · 0 conflicts · Capacity verified · {utilization:.0%} hall utilization</div>', unsafe_allow_html=True)
        with st.expander("Complete slot-wise course list"):
            st.text("\n".join(f"Slot {i}: {', '.join(map(str, courses))}" for i, courses in enumerate(selected.slots, 1)) or "No courses to schedule.")

    with st.expander("Assignment replay"):
        st.caption("Assignment order for the final timetable. Rejected search branches are excluded.")
        if graph.n:
            step_key = f"replay_step_{st.session_state.graph_revision}_{algorithm}"
            step = st.slider("Assigned courses", 0, graph.n, graph.n, key=step_key)
            play = st.button("Play", key="play_replay")
            stage = st.empty()
            caption = st.empty()
            sequence = range(graph.n + 1) if play else [step]
            for count in sequence:
                stage.plotly_chart(conflict_figure(graph, selected, pos, step=count, height=370),
                                   use_container_width=True, config={"displayModeBar": False}, key=f"replay_{count}")
                course = selected.order[count - 1] if count else None
                caption.caption(f"{count}/{graph.n} assigned" + (f" · Course {course + 1} → Slot {selected.assignment[course] + 1}" if course is not None else " · Ready to begin"))
                if play:
                    time.sleep(min(0.3, 8 / graph.n))
    export_cols = st.columns(2)
    export_cols[0].download_button("Download graph input (.txt)", graph_text(graph), "slotlab_graph.txt", mime="text/plain", use_container_width=True)
    export_cols[1].download_button("Download all solver results (.json)", report_json(graph, results), "slotlab_report.json", mime="application/json", use_container_width=True)

with lab:
    section("Benchmarks", "Compare slots used and running time as the number of courses increases.")
    st.caption("All algorithms use the same graphs for each trial.")
    with st.form("benchmark_controls"):
        bc = st.columns(4)
        maximum = bc[0].select_slider("Maximum courses", options=[20, 30, 40, 50, 60, 80], value=40)
        repeats = bc[1].selectbox("Trials per size", [1, 3, 5], index=1)
        bench_density = bc[2].slider("Edge density", 0.0, 1.0, 0.30, 0.05)
        bench_budget = bc[3].selectbox("Exact budget / instance", [0.1, 0.25, 0.5, 1.0], index=1)
        hall_count = st.number_input("Halls per slot", 1, 100, 5)
        bench_seed = st.number_input("Benchmark seed", 0, 2147483647, 42)
        run_bench = st.form_submit_button("Run benchmark", type="primary")
    if run_bench:
        bar = st.progress(0.0, text="Running benchmark…")
        rows = benchmark(tuple(range(10, maximum + 1, 10)), int(hall_count), bench_density,
                         int(bench_seed), repeats, bench_budget, lambda p: bar.progress(p))
        st.session_state.benchmark = rows
        bar.empty()
    if "benchmark" in st.session_state:
        frame = pd.DataFrame(st.session_state.benchmark)
        first = frame.iloc[0]
        st.caption(f"Displayed run: R={first.capacity} · density={first.density:.0%} · exact budget={first.exact_budget_s:g}s · {frame.trial.max()} trial(s) per size. Bars show min–max; lines show means.")
        a, b = st.columns(2)
        with a, st.container(border=True):
            st.plotly_chart(benchmark_figure(frame, "slots", "Slots used"), use_container_width=True)
        with b, st.container(border=True):
            st.plotly_chart(benchmark_figure(frame, "runtime_ms", "Running time"), use_container_width=True)
        summary = frame.groupby("algorithm").agg(Mean_slots=("slots", "mean"), Mean_ms=("runtime_ms", "mean"), Proven_optimal=("optimal", "sum"), Runs=("optimal", "count"))
        st.dataframe(summary, use_container_width=True)
        unproven = len(frame[(frame.algorithm == "Exact B&B") & ~frame.optimal])
        if unproven:
            st.warning(f"{unproven} exact run(s) ended without proof. Their plotted slot counts are valid upper bounds, not proven minima.")
        st.download_button("Export benchmark CSV", frame.to_csv(index=False), "slotlab_benchmark.csv", mime="text/csv")
        with st.expander("Raw measurements"):
            st.dataframe(frame, hide_index=True, use_container_width=True)
    else:
        st.caption("No benchmark results. Select parameters and run a benchmark.")

with explain:
    section("Scheduling methods", "Courses are graph vertices, conflicts are edges, and slots are colours.")
    cols = st.columns(3)
    descriptions = [
        ("DSatur", "Saturation-based greedy colouring", "Pick the unassigned vertex with the most distinct neighbour colours. Break ties by degree, then course ID. Place it in the first nonconflicting slot with a free hall; open a slot if necessary."),
        ("Welsh–Powell", "Degree-based greedy colouring", "Sort courses by descending conflict degree, breaking ties by course ID. Use first-fit colouring with a capacity check. This is the descending-degree first-fit variant of Welsh–Powell."),
        ("Exact branch & bound", "Capacity-constrained backtracking", "Start with the best greedy timetable. From the lower bound upward, exhaustively test each smaller slot count using DSatur branching, forward checking, and symmetric-colour pruning. Stop on proof or the time budget.")]
    for col, (title, subtitle, description) in zip(cols, descriptions):
        with col, st.container(border=True):
            st.markdown(f"**{title}**")
            st.markdown(subtitle)
            st.caption(description)
    st.markdown("#### Lower bound")
    st.latex(r"\mathrm{OPT} \geq \max\left(\left\lceil \frac{N}{R}\right\rceil,\; |Q|\right)")
    witness = clique_witness(graph)
    st.write(f"Capacity alone needs at least **{(graph.n + graph.capacity - 1) // graph.capacity} slots**. A clique is a group in which every pair conflicts: our discovered clique contains **{len(witness)} courses**, which also require different slots. This is a valid bound even when the clique is not maximum.")
    st.caption("Clique witness: " + (", ".join(str(v + 1) for v in witness) or "Empty graph"))
    st.write("When a valid schedule meets a certified lower bound, it is optimal—even if a greedy algorithm found it. Exact search can strengthen the bound by exhaustively ruling out smaller schedules. A timeout never rules out a schedule.")

