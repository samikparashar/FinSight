import importlib
import sys
from pathlib import Path
from types import ModuleType


class FakeApp:
    def __init__(self, result_state):
        self._result_state = result_state

    def invoke(self, _initial_state):
        return self._result_state


def _load_main_with_fake_graph(result_state):
    fake_graph = ModuleType("graph")

    def build_graph():
        return FakeApp(result_state)

    fake_graph.build_graph = build_graph
    sys.modules["graph"] = fake_graph

    main_mod = importlib.import_module("main")
    return importlib.reload(main_mod)


def test_run_finsight_happy_path_creates_report_file(tmp_path, monkeypatch):
    main_mod = _load_main_with_fake_graph({"final_report": "# Final Report\n\nBody"})

    monkeypatch.chdir(tmp_path)
    returned = main_mod.run_finsight("aapl")

    assert returned.startswith("# Final Report")
    report_files = list(Path("reports").glob("AAPL_*.md"))
    assert len(report_files) == 1
    assert "# Final Report" in report_files[0].read_text(encoding="utf-8")


def test_run_finsight_returns_none_when_report_missing(tmp_path, monkeypatch):
    main_mod = _load_main_with_fake_graph({"final_report": ""})

    monkeypatch.chdir(tmp_path)
    returned = main_mod.run_finsight("msft")

    assert returned is None
    assert not Path("reports").exists()
