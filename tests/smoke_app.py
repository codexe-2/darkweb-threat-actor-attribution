#!/usr/bin/env python3
"""
Offline smoke test for app.py.

Executes the entire Streamlit script against minimal stand-ins for `streamlit`
and `plotly.graph_objects`, exercising every render path (initial view, each
case, and the deception scenario) without a browser or a Streamlit install.
It catches the errors that actually break a demo: NameErrors, bad keys, wrong
argument shapes, unavailable-signal paths.

    python3 tests/smoke_app.py

If real Streamlit IS installed, this test still runs against the stubs - it
deliberately shadows the real package so the check works anywhere.
"""

import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CALLS = []


# ---------------------------------------------------------------- stub bits
class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __getattr__(self, name):
        return _rec(name)

    def __iter__(self):
        return iter([_Ctx(), _Ctx()])


def _rec(name):
    def fn(*a, **k):
        CALLS.append(name)
        return _Ctx()
    return fn


class _Stop(Exception):
    pass


class _SessionState(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as e:
            raise AttributeError(k) from e

    def __setattr__(self, k, v):
        self[k] = v

    def __contains__(self, k):
        return dict.__contains__(self, k)


def build_streamlit_stub(case_id, press_run, press_deceive):
    st = types.ModuleType("streamlit")
    st.session_state = _SessionState()

    def button(label, **k):
        CALLS.append(f"button:{label}")
        if label == "RUN INVESTIGATION":
            return press_run
        if label == "RUN DECEPTION SCENARIO":
            return press_deceive
        return False

    def radio(label, options, **k):
        f = k.get("format_func")
        if f:
            [f(o) for o in options]          # exercise the formatter
        return case_id

    def columns(spec, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [_Ctx() for _ in range(n)]

    def slider(label, lo, hi, default=None, step=None, **k):
        return default if default is not None else lo

    def cache_data(*a, **k):
        if a and callable(a[0]):
            return a[0]
        return lambda f: f

    def stop():
        raise _Stop()

    for name in ("markdown", "caption", "write", "info", "warning", "error", "success",
                 "dataframe", "json", "plotly_chart", "metric", "download_button",
                 "set_page_config", "title", "header", "subheader", "divider", "text"):
        setattr(st, name, _rec(name))

    st.button = button
    st.radio = radio
    st.columns = columns
    st.slider = slider
    st.cache_data = cache_data
    st.stop = stop
    st.sidebar = _Ctx()
    st.expander = _rec("expander")
    st.spinner = _rec("spinner")
    st.container = _rec("container")
    st.tabs = lambda names, **k: [_Ctx() for _ in names]
    return st


def build_plotly_stub():
    go = types.ModuleType("plotly.graph_objects")

    class Figure:
        def __init__(self, data=None, *a, **k):
            self.data = data or []

        def add_bar(self, **k):
            return self

        def add_scatter(self, **k):
            return self

        def update_layout(self, **k):
            return self

    class Scatter(dict):
        def __init__(self, **k):
            super().__init__(**k)

    class Bar(dict):
        def __init__(self, **k):
            super().__init__(**k)

    go.Figure, go.Scatter, go.Bar = Figure, Scatter, Bar
    plotly = types.ModuleType("plotly")
    plotly.graph_objects = go
    return plotly, go


def run_once(case_id, press_run=False, press_deceive=False):
    CALLS.clear()
    st = build_streamlit_stub(case_id, press_run, press_deceive)
    plotly, go = build_plotly_stub()
    sys.modules["streamlit"] = st
    sys.modules["plotly"] = plotly
    sys.modules["plotly.graph_objects"] = go
    for m in [k for k in sys.modules if k.startswith(("modules", "utils"))]:
        del sys.modules[m]

    src = open(os.path.join(ROOT, "app.py")).read()
    ns = {"__name__": "__main__", "__file__": os.path.join(ROOT, "app.py")}
    try:
        exec(compile(src, "app.py", "exec"), ns)
    except _Stop:
        pass
    return len(CALLS)


def main():
    scenarios = [
        ("CASE-001", False, False, "initial landing view"),
        ("CASE-001", True, False, "run investigation (SUPPORTED)"),
        ("CASE-002", True, False, "run investigation (UNCERTAIN)"),
        ("CASE-003", True, False, "run investigation (INSUFFICIENT, missing signals)"),
        ("CASE-001", False, True, "deception scenario"),
        ("CASE-003", False, True, "deception scenario on a sparse case"),
    ]
    ok = True
    for case_id, run, dec, label in scenarios:
        try:
            n = run_once(case_id, run, dec)
            print(f"  [ OK ] {label:<50} ({n} UI calls)")
        except Exception as exc:                                  # noqa: BLE001
            ok = False
            import traceback
            print(f"  [FAIL] {label}: {type(exc).__name__}: {exc}")
            traceback.print_exc()
    print("\n  app.py smoke test: " + ("PASSED" if ok else "FAILED"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
