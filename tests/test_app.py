from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


def test_studio_load_and_greedy_trap():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception
    assert app.session_state["graph"].n == 24
    app.sidebar.selectbox[0].select("Greedy trap").run()
    app.sidebar.button[0].click().run()
    assert not app.exception
    assert app.session_state["graph"].n == 8
    results = app.session_state["results"]
    assert [r.slots_used for r in results] == [3, 3, 2]
    assert results[-1].optimal


def test_invalid_input_keeps_last_valid_schedule():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    original = app.session_state["graph"]
    app.sidebar.selectbox[0].select("Paste input").run()
    app.sidebar.text_area[0].input("3 1 2\n1 9")
    app.sidebar.button[0].click().run()
    assert not app.exception
    assert app.sidebar.error
    assert app.session_state["graph"] == original
