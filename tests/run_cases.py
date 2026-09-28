#!/usr/bin/env python3
"""
Headless runner / acceptance test for the whole pipeline.

Runs all three cases plus the deception scenario WITHOUT Streamlit, prints the
Stage 1 ranking, evidence contributions and Stage 2 audit, and asserts the
expected outcomes. Useful both as a smoke test and as a terminal demo.

    python3 tests/run_cases.py           # run everything
    python3 tests/run_cases.py CASE-002  # run one case
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.attribution import SIGNAL_LABEL, SIGNAL_ORDER          # noqa: E402
from modules.pipeline import run_deception_scenario, run_investigation  # noqa: E402
from modules.reporting import build_report_dict, save_html, save_json  # noqa: E402
from utils.helpers import bar, load_dataset                          # noqa: E402

ICON = {"PASS": "[ OK ]", "WARNING": "[WARN]", "FAIL": "[FAIL]"}
LINE = "=" * 78


def show(result):
    s1, s2, case = result["stage1"], result["stage2"], result["case"]
    top = s1["top_candidate"]

    print(LINE)
    print(f" {case['case_id']} - {case['title']}")
    print(f" subject persona: {case['subject_persona']}")
    print(LINE)
    print(f"\n{case['briefing']}\n")

    print("-- STAGE 1 : ATTRIBUTION -- \"WHO?\"")
    print(f"{'rank':<5}{'candidate':<22}{'initial score':>14}")
    for i, c in enumerate(s1["candidates"], 1):
        mark = " <-- leading hypothesis" if i == 1 else ""
        print(f"{i:<5}{c['actor_id'] + ' / ' + c['codename']:<22}"
              f"{c['initial_score']:>14.1f}{mark}")

    print(f"\n   evidence contribution for {top['actor_id']}:")
    for sig in SIGNAL_ORDER:
        c = top["contributions"][sig]
        if c["status"] != "used":
            print(f"     {SIGNAL_LABEL[sig]:<16}{'MISSING':>7}  "
                  f"{'-' * 24}  ({top['signals'][sig].get('reason', '')})")
        else:
            print(f"     {SIGNAL_LABEL[sig]:<16}{c['score']:>7.1f}  {bar(c['score'])}  "
                  f"w={c['weight']:.2f} -> +{c['contribution']:.1f}")
    print(f"     {'TOTAL':<16}{top['initial_score']:>7.1f}   "
          f"(INITIAL ATTRIBUTION SCORE - a hypothesis, not a conclusion)")

    print(f"\n-- RELATIONSHIP GRAPH --")
    gs = result["graph_summary"]
    print(f"   {gs['nodes']} nodes / {gs['edges']} edges   {gs['node_types']}")
    print(f"   edge types: {gs['edge_types']}")

    print("\n-- STAGE 2 : VERIFICATION -- \"CAN WE TRUST IT?\"")
    for key, chk in s2["checks"].items():
        print(f"  {ICON[chk['status']]} {chk['name']}")
        print(f"         {_wrap(chk['message'])}")

    if s2["checks"]["sensitivity"]["rows"]:
        print("\n   leave-one-signal-out:")
        for r in s2["checks"]["sensitivity"]["rows"]:
            flag = f"  RANK-1 CHANGES to {r['new_rank1']}" if r["rank1_changes"] else ""
            print(f"     without {r['removed']:<16}{r['score_without']:>6.1f}"
                  f"  ({r['delta']:+.1f}){flag}")

    print(f"\n{LINE}\n FINAL ASSESSMENT:  {s2['verdict']}\n{LINE}")
    print(f" {_wrap(s2['statement'], 1)}")
    for r in s2["reasons"]:
        print(f"   - {_wrap(r, 5)}")
    print()


def _wrap(text, indent=9, width=78):
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width - indent:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    lines.append(cur)
    return ("\n" + " " * indent).join(lines)


def main():
    ds = load_dataset()
    only = sys.argv[1] if len(sys.argv) > 1 else None
    failures = []

    for case in ds["cases"]:
        if only and case["case_id"] != only:
            continue
        result = run_investigation(case["case_id"], ds=ds)
        show(result)
        got, want = result["stage2"]["verdict"], case["expected_outcome"]
        if got != want:
            failures.append(f"{case['case_id']}: expected {want}, got {got}")
        else:
            print(f"  ASSERT OK: {case['case_id']} -> {got} (as expected)\n")
        rep = build_report_dict(result)
        save_json(rep)
        save_html(rep)

    if only:
        _summary(failures)
        return

    # ---- deception scenario -------------------------------------------
    print(LINE)
    print(" DECEPTION SCENARIO - injecting a misleading financial identifier")
    print(LINE)
    dec = run_deception_scenario("CASE-001", ds=ds)
    d = dec["delta"]
    print(f"\n {_wrap(dec['injected']['description'], 1)}\n")
    print(f" {'':<26}{'BEFORE':>14}{'AFTER':>16}")
    print(f" {'leading candidate':<26}{d['top_before']:>14}{d['top_after']:>16}")
    print(f" {'initial attribution score':<26}{d['score_before']:>14.1f}"
          f"{d['score_after']:>16.1f}")
    print(f" {'Stage 2 verdict':<26}{d['verdict_before']:>14}{d['verdict_after']:>16}")
    print(f"\n runner-up after injection: "
          f"{dec['after']['stage1']['candidates'][1]['actor_id']} at "
          f"{dec['after']['stage1']['candidates'][1]['initial_score']:.1f}")
    print("\n Stage 2 findings after injection:")
    for r in dec["after"]["stage2"]["reasons"]:
        print(f"   - {_wrap(r, 5)}")

    if not d["verdict_changed"]:
        failures.append("deception scenario did not change the verdict")
    else:
        print(f"\n  ASSERT OK: verdict moved {d['verdict_before']} -> {d['verdict_after']} "
              f"and the score fell by {abs(d['score_change']):.1f} points.\n")

    rep = build_report_dict(dec["after"], deception=dec)
    print(f"  report written: {os.path.relpath(save_json(rep))}")
    print(f"  report written: {os.path.relpath(save_html(rep))}\n")

    _summary(failures)


def _summary(failures):
    print(LINE)
    if failures:
        print(" ACCEPTANCE TEST: FAILED")
        for f in failures:
            print(f"   - {f}")
        sys.exit(1)
    print(" ACCEPTANCE TEST: ALL EXPECTED OUTCOMES MATCHED")
    print(LINE)


if __name__ == "__main__":
    main()
