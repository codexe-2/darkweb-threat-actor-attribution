"""
Module 12 — REPORT GENERATION
=============================

Produces a self-contained investigation report in JSON (machine readable) and
HTML (human readable). Both carry the synthetic-data disclaimer and record the
Stage 1 hypothesis and the Stage 2 audit separately, so a reader can never
mistake an initial score for a verified conclusion.
"""

import html
import json
import os
from datetime import datetime

from modules.attribution import SIGNAL_LABEL, SIGNAL_ORDER
from utils.helpers import REPORT_DIR, SYNTHETIC_DISCLAIMER

VERDICT_COLOUR = {"SUPPORTED": "#1b998b", "UNCERTAIN": "#f4a261", "INSUFFICIENT": "#8d99ae"}
STATUS_ICON = {"PASS": "&#10003;", "WARNING": "&#9888;", "FAIL": "&#10007;"}
STATUS_COLOUR = {"PASS": "#1b998b", "WARNING": "#e9a33a", "FAIL": "#d62828"}


def build_report_dict(result, deception=None):
    s1, s2, case = result["stage1"], result["stage2"], result["case"]
    top = s1["top_candidate"]

    report = {
        "report_type": "SYNTHETIC ATTRIBUTION & VERIFICATION REPORT",
        "case_id": case["case_id"],
        "case_title": case["title"],
        "case_briefing": case["briefing"],
        "subject_persona": case["subject_persona"],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "deception_injection_applied": result.get("deception_applied", False),
        "stage1_attribution": {
            "note": s1["note"],
            "weights": s1["weights"],
            "ranking": [
                {"rank": i + 1, "actor_id": c["actor_id"], "codename": c["codename"],
                 "initial_attribution_score": c["initial_score"],
                 "evidence_contributions": {
                     SIGNAL_LABEL[s]: {
                         "signal_score": c["contributions"][s]["score"],
                         "weight": c["contributions"][s]["weight"],
                         "effective_weight": c["contributions"][s].get("effective_weight"),
                         "contribution": c["contributions"][s]["contribution"],
                         "status": c["contributions"][s]["status"],
                     } for s in SIGNAL_ORDER}}
                for i, c in enumerate(s1["candidates"])],
            "margin_over_runner_up": s1["margin"],
            "evidence_detail_top_candidate": {
                SIGNAL_LABEL[s]: {
                    "score": top["signals"][s].get("score"),
                    "available": top["signals"][s].get("available"),
                    "reason_if_missing": top["signals"][s].get("reason"),
                    "evidence": top["signals"][s].get("evidence", []),
                } for s in SIGNAL_ORDER},
        },
        "graph": {
            "summary": result["graph_summary"],
            "relationships": result["relationships"],
        },
        "stage2_verification": {
            "checks": {k: {"name": v["name"], "status": v["status"],
                           "message": v["message"]}
                       for k, v in s2["checks"].items()},
            "conflicts": s2["checks"]["conflict"]["conflicts"],
            "missing_evidence": {
                "present": s2["checks"]["missing"]["present"],
                "missing": s2["checks"]["missing"]["missing"],
                "reasons": s2["checks"]["missing"]["missing_reasons"]},
            "independence": {
                "distinct_sources": s2["checks"]["independence"]["distinct_sources"],
                "dependent_clusters": s2["checks"]["independence"]["dependent_clusters"],
                "source_map": s2["checks"]["independence"]["source_map"]},
            "alternative_candidates": s2["checks"]["alternatives"]["ranking"],
            "sensitivity_analysis": s2["checks"]["sensitivity"]["rows"],
            "temporal_checks": {
                "anomalies": s2["checks"]["temporal"]["anomalies"],
                "observations": s2["checks"]["temporal"]["observations"]},
        },
        "final_assessment": {
            "verdict": s2["verdict"],
            "statement": s2["statement"],
            "reasons": s2["reasons"],
            "warnings": s2["warnings"],
        },
        "disclaimer": SYNTHETIC_DISCLAIMER,
    }
    if deception:
        report["deception_scenario"] = {
            "injected": deception["injected"],
            "delta": deception["delta"],
        }
    return report


def save_json(report, out_dir=None):
    out_dir = out_dir or REPORT_DIR
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = "-deception" if report.get("deception_injection_applied") else ""
    path = os.path.join(out_dir, f"{report['case_id']}{suffix}-{ts}.json")
    with open(path, "w") as fh:
        json.dump(report, fh, indent=2)
    return path


# --------------------------------------------------------------------------
def _e(x):
    return html.escape(str(x))


def render_html(report):
    v = report["final_assessment"]["verdict"]
    rows = []
    for c in report["stage1_attribution"]["ranking"]:
        cells = []
        for d in c["evidence_contributions"].values():
            s = d["signal_score"]
            cells.append("<td class='num'>&ndash;</td>" if s is None
                         else f"<td class='num'>{s:.0f}</td>")
        contrib = "".join(cells)
        rows.append(
            f"<tr class='{'top' if c['rank'] == 1 else ''}'><td>{c['rank']}</td>"
            f"<td><b>{_e(c['actor_id'])}</b> / {_e(c['codename'])}</td>"
            f"<td class='num score'>{c['initial_attribution_score']:.1f}</td>{contrib}</tr>")

    checks = "".join(
        f"<li><span style='color:{STATUS_COLOUR[c['status']]};font-weight:700'>"
        f"{STATUS_ICON[c['status']]} {_e(c['name'])}</span> &mdash; {_e(c['message'])}</li>"
        for c in report["stage2_verification"]["checks"].values())

    sens = "".join(
        f"<tr><td>{_e(r['removed'])}</td><td class='num'>{r['score_without']:.1f}</td>"
        f"<td class='num'>{r['delta']:+.1f}</td>"
        f"<td>{'RANK CHANGES to ' + _e(r['new_rank1']) if r['rank1_changes'] else 'rank stable'}</td></tr>"
        for r in report["stage2_verification"]["sensitivity_analysis"])

    reasons = "".join(f"<li>{_e(r)}</li>" for r in report["final_assessment"]["reasons"])
    rels = "".join(
        f"<tr><td>{_e(r['from'])}</td><td><code>{_e(r['relationship'])}</code></td>"
        f"<td>{_e(r['to'])}</td></tr>"
        for r in report["graph"]["relationships"][:40])

    temporal = report["stage2_verification"]["temporal_checks"]
    anomalies = "".join(f"<li><b>{_e(a['severity'])}</b> {_e(a['detail'])}</li>"
                        for a in temporal["anomalies"]) or "<li>None detected.</li>"

    missing = report["stage2_verification"]["missing_evidence"]
    conflicts = "".join(f"<li><b>{_e(c['severity'])}</b> &mdash; {_e(c['message'])}</li>"
                        for c in report["stage2_verification"]["conflicts"]) \
        or "<li>No conflicting evidence detected.</li>"

    dec = ""
    if "deception_scenario" in report:
        d = report["deception_scenario"]
        dec = f"""
        <h2>Deception Scenario</h2>
        <p>{_e(d['injected']['description'])}</p>
        <table><tr><th></th><th>Before</th><th>After injection</th></tr>
        <tr><td>Leading candidate</td><td>{_e(d['delta']['top_before'])}</td>
            <td>{_e(d['delta']['top_after'])}</td></tr>
        <tr><td>Initial attribution score</td><td class='num'>{d['delta']['score_before']:.1f}</td>
            <td class='num'>{d['delta']['score_after']:.1f}</td></tr>
        <tr><td>Stage 2 verdict</td><td>{_e(d['delta']['verdict_before'])}</td>
            <td><b>{_e(d['delta']['verdict_after'])}</b></td></tr></table>"""

    headers = "".join(f"<th>{_e(s)}</th>" for s in SIGNAL_LABEL.values())

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{_e(report['case_id'])} &mdash; Attribution &amp; Verification Report</title>
<style>
 body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
   margin:0;padding:2rem;background:#0e1117;color:#e6edf3;line-height:1.55}}
 .wrap{{max-width:1000px;margin:0 auto}}
 h1{{font-size:1.5rem;margin:0 0 .2rem}}
 h2{{font-size:1.1rem;margin:2rem 0 .6rem;padding-bottom:.3rem;
   border-bottom:1px solid #30363d;color:#9dd6ff;letter-spacing:.04em;text-transform:uppercase}}
 .sub{{color:#8b949e;font-size:.85rem}}
 .verdict{{margin:1.2rem 0;padding:1rem 1.2rem;border-radius:8px;
   background:{VERDICT_COLOUR[v]}22;border-left:5px solid {VERDICT_COLOUR[v]}}}
 .verdict .big{{font-size:1.8rem;font-weight:800;color:{VERDICT_COLOUR[v]};letter-spacing:.06em}}
 table{{border-collapse:collapse;width:100%;font-size:.86rem;margin:.5rem 0}}
 th,td{{border:1px solid #30363d;padding:.4rem .55rem;text-align:left}}
 th{{background:#161b22;color:#9dd6ff;font-weight:600}}
 td.num{{text-align:right;font-variant-numeric:tabular-nums}}
 td.score{{font-weight:700}}
 tr.top{{background:#1f6feb22}}
 ul{{padding-left:1.2rem}} li{{margin:.3rem 0;font-size:.88rem}}
 code{{background:#161b22;padding:.05rem .3rem;border-radius:3px;font-size:.8rem}}
 .disc{{margin-top:2rem;padding:.9rem;border:1px dashed #6e7681;border-radius:6px;
   color:#8b949e;font-size:.8rem}}
</style></head><body><div class="wrap">
<h1>Dark Web Threat Intelligence Platform &mdash; Case Report</h1>
<div class="sub">{_e(report['case_id'])} &middot; {_e(report['case_title'])} &middot;
 subject persona {_e(report['subject_persona'])} &middot;
 generated {_e(report['generated_at'])}</div>

<h2>Case Briefing</h2><p>{_e(report['case_briefing'])}</p>

<h2>Stage 1 &mdash; Attribution Hypothesis (&ldquo;Who?&rdquo;)</h2>
<p class="sub">{_e(report['stage1_attribution']['note'])}</p>
<table><tr><th>#</th><th>Candidate</th><th>Initial score</th>{headers}</tr>{''.join(rows)}</table>

<h2>Relationship Graph</h2>
<p class="sub">{report['graph']['summary']['nodes']} nodes,
 {report['graph']['summary']['edges']} edges.</p>
<table><tr><th>From</th><th>Relationship</th><th>To</th></tr>{rels}</table>

<h2>Stage 2 &mdash; Verification Audit (&ldquo;Can we trust it?&rdquo;)</h2>
<ul>{checks}</ul>

<h3>Evidence conflicts</h3><ul>{conflicts}</ul>
<h3>Evidence availability</h3>
<p class="sub">Present: {_e(', '.join(missing['present']) or 'none')}<br>
Missing: {_e(', '.join(missing['missing']) or 'none')}</p>
<h3>Sensitivity analysis (leave-one-signal-out)</h3>
<table><tr><th>Signal removed</th><th>Score without</th><th>Delta</th><th>Effect</th></tr>{sens}</table>
<h3>Temporal consistency</h3><ul>{anomalies}</ul>
{dec}

<h2>Final Assessment</h2>
<div class="verdict"><div class="big">{_e(v)}</div>
<p>{_e(report['final_assessment']['statement'])}</p>
<ul>{reasons}</ul></div>

<div class="disc"><b>SYNTHETIC DATA NOTICE.</b> {_e(report['disclaimer'])}</div>
</div></body></html>"""


def save_html(report, out_dir=None):
    out_dir = out_dir or REPORT_DIR
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = "-deception" if report.get("deception_injection_applied") else ""
    path = os.path.join(out_dir, f"{report['case_id']}{suffix}-{ts}.html")
    with open(path, "w") as fh:
        fh.write(render_html(report))
    return path
