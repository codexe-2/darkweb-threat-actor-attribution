#!/usr/bin/env python3
"""
DARK WEB THREAT INTELLIGENCE PLATFORM — Investigator Dashboard
==============================================================
SIH Problem Statement 26151 — Dark Web Threat Actor De-anonymization (MVP)

    streamlit run app.py

Stage 1 (blue) asks WHO the evidence points to.
Stage 2 (amber) asks whether that answer can be TRUSTED.
The two are kept visually and logically separate on purpose.

ALL DATA IN THIS APPLICATION IS SYNTHETIC.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.attribution import DEFAULT_WEIGHTS, SIGNAL_LABEL, SIGNAL_ORDER
from modules.behaviour import WEEKDAY_ORDER, profile
from modules.graph_engine import NODE_COLOURS, layout
from modules.pipeline import run_deception_scenario, run_investigation
from modules.reporting import build_report_dict, render_html, save_html, save_json
from utils.helpers import (SYNTHETIC_DISCLAIMER, events_of_persona, load_dataset,
                           posts_of_persona)

import json

st.set_page_config(page_title="Dark Web Threat Intelligence Platform",
                   page_icon="\U0001f50e", layout="wide",
                   initial_sidebar_state="expanded")

VERDICT_STYLE = {
    "SUPPORTED":    ("#1b998b", "\u2713", "The attribution hypothesis survived verification."),
    "UNCERTAIN":    ("#e9a33a", "\u26a0", "A hypothesis exists but CANNOT be trusted as it stands."),
    "INSUFFICIENT": ("#8d99ae", "\u25cb", "There is not enough corroborated evidence to conclude."),
}
STATUS_ICON = {"PASS": "\u2713", "WARNING": "\u26a0", "FAIL": "\u2717"}
STATUS_COLOUR = {"PASS": "#1b998b", "WARNING": "#e9a33a", "FAIL": "#d62828"}

st.markdown("""
<style>
  .block-container {padding-top: 1.6rem; max-width: 1500px;}
  .hero {background: linear-gradient(90deg,#11161f 0%,#1b2433 60%,#11161f 100%);
         border:1px solid #2a3446; border-radius:10px; padding:1.1rem 1.4rem; margin-bottom:1rem;}
  .hero h1 {margin:0; font-size:1.55rem; letter-spacing:.06em; color:#e6edf3;}
  .hero p {margin:.25rem 0 0; color:#8b949e; font-size:.85rem; letter-spacing:.14em;
           text-transform:uppercase;}
  .stage-1 {border-left:5px solid #1f6feb; background:#1f6feb14; padding:.7rem 1rem;
            border-radius:6px; margin:.4rem 0 1rem;}
  .stage-2 {border-left:5px solid #e9a33a; background:#e9a33a14; padding:.7rem 1rem;
            border-radius:6px; margin:.4rem 0 1rem;}
  .stage-1 h3, .stage-2 h3 {margin:0; font-size:1.1rem; letter-spacing:.05em;}
  .stage-1 span, .stage-2 span {color:#8b949e; font-size:.82rem;}
  .chk {border:1px solid #30363d; border-radius:6px; padding:.55rem .75rem; margin-bottom:.45rem;
        background:#0f141c;}
  .chk .t {font-weight:700; font-size:.92rem;}
  .chk .m {color:#a9b4c0; font-size:.81rem; margin-top:.2rem; line-height:1.45;}
  .verdict {border-radius:10px; padding:1.3rem 1.5rem; margin:.6rem 0 1rem;}
  .verdict .v {font-size:2.4rem; font-weight:800; letter-spacing:.1em; margin:0;}
  .verdict .s {color:#c9d1d9; font-size:.9rem; margin-top:.3rem;}
  .disc {border:1px dashed #6e7681; border-radius:6px; padding:.7rem .9rem; color:#8b949e;
         font-size:.76rem; line-height:1.5; margin-top:1.2rem;}
  .pill {display:inline-block; padding:.1rem .5rem; border-radius:10px; font-size:.7rem;
         font-weight:700; letter-spacing:.05em;}
</style>""", unsafe_allow_html=True)


# ==========================================================================
# helpers
# ==========================================================================
@st.cache_data(show_spinner=False)
def _dataset_meta():
    ds = load_dataset()
    return {"cases": [(c["case_id"], c["title"], c["subject_persona"]) for c in ds["cases"]],
            "counts": {"actors": len(ds["actors"]), "personas": len(ds["personas"]),
                       "posts": len(ds["posts"]), "events": len(ds["behaviour"]),
                       "servers": len(ds["infrastructure"]["servers"]),
                       "pgp": len(ds["pgp"]), "wallets": len(ds["wallets"])}}


def contribution_frame(cand):
    rows = []
    for sig in SIGNAL_ORDER:
        c = cand["contributions"][sig]
        rows.append({"Signal": SIGNAL_LABEL[sig],
                     "Score": c["score"] if c["status"] == "used" else None,
                     "Weight": c["weight"],
                     "Effective weight": c.get("effective_weight", 0.0),
                     "Contribution": c["contribution"] if c["status"] == "used" else 0.0,
                     "Status": c["status"]})
    return pd.DataFrame(rows)


def graph_figure(g, subject_id):
    pos = layout(g)
    edge_traces = []
    for u, v, d in g.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        analytic = d["etype"] in ("SIMILAR_WRITING", "SIMILAR_ACTIVITY")
        edge_traces.append(go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None], mode="lines",
            line=dict(width=2.4 if analytic else 1.0,
                      color="#b5179e" if analytic else "#39424e",
                      dash="dot" if analytic else "solid"),
            hoverinfo="text", text=d.get("label", d["etype"]), showlegend=False))

    by_type = {}
    for n, d in g.nodes(data=True):
        by_type.setdefault(d["ntype"], []).append(n)

    node_traces = []
    for ntype, nodes in sorted(by_type.items()):
        node_traces.append(go.Scatter(
            x=[pos[n][0] for n in nodes], y=[pos[n][1] for n in nodes],
            mode="markers+text",
            marker=dict(size=[34 if n == subject_id else (26 if ntype == "ACTOR" else 16)
                              for n in nodes],
                        color=NODE_COLOURS.get(ntype, "#888"),
                        line=dict(width=2 if ntype in ("ACTOR", "SUBJECT") else 0.8,
                                  color="#0e1117")),
            text=[g.nodes[n]["label"].replace("\n", "<br>") for n in nodes],
            textposition="top center",
            textfont=dict(size=9, color="#c9d1d9"),
            hovertext=[g.nodes[n].get("title", n) for n in nodes],
            hoverinfo="text", name=ntype))

    fig = go.Figure(edge_traces + node_traces)
    fig.update_layout(height=620, showlegend=True,
                      legend=dict(orientation="h", y=-0.03, font=dict(size=10)),
                      margin=dict(l=8, r=8, t=8, b=8),
                      paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                      xaxis=dict(visible=False), yaxis=dict(visible=False),
                      hoverlabel=dict(font_size=11))
    return fig


def activity_figure(ds, subject_id, actor_id, actor_profile):
    subj = profile(events_of_persona(ds, subject_id))
    hours = list(range(24))
    fig = go.Figure()
    fig.add_bar(x=hours, y=[v * 100 for v in subj["hours_norm"]],
                name=f"Subject {subject_id}", marker_color="#f72585", opacity=0.85)
    fig.add_scatter(x=hours, y=[v * 100 for v in actor_profile["hours_norm"]],
                    name=f"{actor_id} (known)", mode="lines+markers",
                    line=dict(color="#1f6feb", width=3))
    fig.update_layout(height=290, barmode="overlay",
                      margin=dict(l=10, r=10, t=30, b=10),
                      title=dict(text="24-hour activity rhythm (% of events)",
                                 font=dict(size=13)),
                      xaxis=dict(title="hour of day (UTC)", dtick=2),
                      yaxis=dict(title="% of activity"),
                      paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                      font=dict(color="#c9d1d9", size=11),
                      legend=dict(orientation="h", y=1.15))
    return fig


def weekday_figure(ds, subject_id, actor_id, actor_profile):
    subj = profile(events_of_persona(ds, subject_id))
    fig = go.Figure()
    fig.add_bar(x=WEEKDAY_ORDER, y=[v * 100 for v in subj["weekdays_norm"]],
                name="Subject", marker_color="#f72585", opacity=0.85)
    fig.add_bar(x=WEEKDAY_ORDER, y=[v * 100 for v in actor_profile["weekdays_norm"]],
                name=actor_id, marker_color="#1f6feb", opacity=0.7)
    fig.update_layout(height=290, barmode="group",
                      margin=dict(l=10, r=10, t=30, b=10),
                      title=dict(text="Weekday distribution (% of events)",
                                 font=dict(size=13)),
                      paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                      font=dict(color="#c9d1d9", size=11),
                      legend=dict(orientation="h", y=1.15))
    return fig


def render_stage1(result, ds):
    s1 = result["stage1"]
    top = s1["top_candidate"]
    st.markdown('<div class="stage-1"><h3>STAGE 1 &mdash; ATTRIBUTION ENGINE</h3>'
                '<span>"WHO does the available evidence point to?" &mdash; produces a '
                'HYPOTHESIS, not a conclusion.</span></div>', unsafe_allow_html=True)

    left, right = st.columns([1.05, 1.15])

    with left:
        st.markdown("**Candidate ranking &mdash; Initial Attribution Score**")
        cands = s1["candidates"]
        fig = go.Figure(go.Bar(
            x=[c["initial_score"] for c in cands][::-1],
            y=[f"{c['actor_id']} / {c['codename']}" for c in cands][::-1],
            orientation="h",
            marker_color=["#1f6feb" if i == len(cands) - 1 else "#3d4756"
                          for i in range(len(cands))],
            text=[f"{c['initial_score']:.1f}" for c in cands][::-1],
            textposition="outside"))
        fig.update_layout(height=260, margin=dict(l=8, r=40, t=8, b=8),
                          xaxis=dict(range=[0, 108], title="initial attribution score"),
                          paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                          font=dict(color="#c9d1d9", size=11))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Leading hypothesis: **{top['actor_id']} / {top['codename']}** at "
                   f"**{top['initial_score']:.1f}**. Margin over runner-up: "
                   f"{s1['margin']:.1f} points. This index is NOT a probability of guilt.")

    with right:
        st.markdown(f"**Evidence contribution &mdash; {top['actor_id']}**")
        df = contribution_frame(top)
        used = df[df["Status"] == "used"]
        fig = go.Figure(go.Bar(
            x=used["Score"], y=used["Signal"], orientation="h",
            marker_color="#1f6feb",
            text=[f"{s:.0f} x {w:.2f} = +{c:.1f}"
                  for s, w, c in zip(used["Score"], used["Effective weight"],
                                     used["Contribution"])],
            textposition="outside"))
        fig.update_layout(height=260, margin=dict(l=8, r=110, t=8, b=8),
                          xaxis=dict(range=[0, 120], title="signal score (0-100)"),
                          yaxis=dict(autorange="reversed"),
                          paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                          font=dict(color="#c9d1d9", size=11))
        st.plotly_chart(fig, use_container_width=True)
        miss = df[df["Status"] != "used"]["Signal"].tolist()
        if miss:
            st.caption("Signals excluded (weights renormalised over the remainder): "
                       + ", ".join(miss)
                       + ". **Stage 1 does not penalise missing evidence &mdash; detecting "
                         "that is Stage 2's job.**")
        else:
            st.caption("All six evidence families were available for this candidate.")

    with st.expander("Evidence detail — why each signal scored what it did"):
        for sig in SIGNAL_ORDER:
            res = top["signals"][sig]
            c = top["contributions"][sig]
            if c["status"] != "used":
                st.markdown(f"**{SIGNAL_LABEL[sig]}** &mdash; `MISSING` &mdash; "
                            f"{res.get('reason', 'not available')}")
                continue
            st.markdown(f"**{SIGNAL_LABEL[sig]} = {res['score']:.1f}**")
            for ev in res.get("evidence", []):
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;`{ev['type']}` {ev['detail']}")
            if res.get("components"):
                st.caption(f"components: {res['components']}")

    with st.expander("Subject corpus — the actual synthetic posts being analysed"):
        subject_id = s1["subject_persona"]
        for p in posts_of_persona(ds, subject_id):
            st.markdown(f"**{p['post_id']}** &middot; {p['forum']} &middot; "
                        f"{p['timestamp']} &middot; *{p['thread_topic']}*")
            st.markdown(f"> {p['text']}")


def render_stage2(result):
    s2 = result["stage2"]
    st.markdown('<div class="stage-2"><h3>STAGE 2 &mdash; VERIFICATION ENGINE</h3>'
                '<span>"CAN WE TRUST that attribution?" &mdash; audits Stage 1 '
                'independently and may reject it.</span></div>', unsafe_allow_html=True)

    order = ["reliability", "conflict", "independence", "missing",
             "alternatives", "sensitivity", "temporal"]
    cols = st.columns(2)
    for i, key in enumerate(order):
        chk = s2["checks"][key]
        colour = STATUS_COLOUR[chk["status"]]
        with cols[i % 2]:
            st.markdown(
                f'<div class="chk"><div class="t" style="color:{colour}">'
                f'{STATUS_ICON[chk["status"]]} {chk["name"]} '
                f'<span class="pill" style="background:{colour}22;color:{colour}">'
                f'{chk["status"]}</span></div>'
                f'<div class="m">{chk["message"]}</div></div>', unsafe_allow_html=True)

    with st.expander("Sensitivity analysis — leave-one-signal-out"):
        rows = s2["checks"]["sensitivity"]["rows"]
        if rows:
            df = pd.DataFrame([{
                "Signal removed": r["removed"],
                "Score without it": r["score_without"],
                "Change": f"{r['delta']:+.1f}",
                "Effect on ranking": f"RANK-1 CHANGES to {r['new_rank1']}"
                if r["rank1_changes"] else "rank stable"} for r in rows])
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"Baseline score with all evidence: "
                       f"{s2['checks']['sensitivity']['base_score']:.1f}")
        else:
            st.info("No signals were available to test.")

    with st.expander("Evidence reliability tiers"):
        st.dataframe(pd.DataFrame([{
            "Signal": r["signal"], "Reliability": r["tier"],
            "Score": r["score"], "Used": "yes" if r["used"] else "no",
            "Effective weight": r["effective_weight"]}
            for r in s2["checks"]["reliability"]["rows"]]),
            use_container_width=True, hide_index=True)
        st.caption("HIGH = identifier reuse (PGP / wallet). MEDIUM = infrastructure and "
                   "persona linkage. HEURISTIC = stylometry and behaviour, which are "
                   "suggestive but never identifying on their own.")

    with st.expander("Evidence independence — source map"):
        sm = s2["checks"]["independence"]["source_map"]
        st.dataframe(pd.DataFrame([{"Evidence source": k, "Signals derived from it":
                                    ", ".join(v)} for k, v in sm.items()]),
                     use_container_width=True, hide_index=True)
        for cl in s2["checks"]["independence"]["dependent_clusters"]:
            st.warning(f"Dependent cluster: {len(cl['artefacts'])} artefacts "
                       f"({', '.join(cl['artefacts'])}) all come from {cl['source']} — "
                       f"one observation, not {len(cl['artefacts'])} independent proofs.")

    with st.expander("Temporal consistency detail"):
        for o in s2["checks"]["temporal"]["observations"]:
            st.markdown(f"- {o}")
        for a in s2["checks"]["temporal"]["anomalies"]:
            st.error(f"**{a['severity']} / {a['type']}** — {a['detail']}")


def render_verdict(result):
    s2 = result["stage2"]
    colour, icon, blurb = VERDICT_STYLE[s2["verdict"]]
    st.markdown(
        f'<div class="verdict" style="background:{colour}1f;border-left:6px solid {colour}">'
        f'<p class="v" style="color:{colour}">{icon} {s2["verdict"]}</p>'
        f'<p class="s">{blurb}</p></div>', unsafe_allow_html=True)
    st.markdown(f"**Assessment.** {s2['statement']}")
    st.markdown("**Reasons:**")
    for r in s2["reasons"]:
        st.markdown(f"- {r}")
    if s2["warnings"] and s2["verdict"] == "SUPPORTED":
        st.markdown("**Caveats noted during verification:**")
        for w in s2["warnings"]:
            st.markdown(f"- {w}")


# ==========================================================================
# SIDEBAR
# ==========================================================================
meta = _dataset_meta()

with st.sidebar:
    st.markdown("### CASE SELECTOR")
    case_titles = {cid: title for cid, title, _ in meta["cases"]}
    case_id = st.radio(
        "Select a case", list(case_titles),
        format_func=lambda cid: f"{cid} — {case_titles[cid]}",
        label_visibility="collapsed")

    st.markdown("---")
    run = st.button("RUN INVESTIGATION", type="primary", use_container_width=True)
    deceive = st.button("RUN DECEPTION SCENARIO", use_container_width=True)

    st.markdown("---")
    with st.expander("Attribution weights (Stage 1)"):
        st.caption("Weights are renormalised over the signals actually available.")
        weights = {}
        for sig in SIGNAL_ORDER:
            weights[sig] = st.slider(SIGNAL_LABEL[sig], 0.0, 0.5,
                                     float(DEFAULT_WEIGHTS[sig]), 0.05, key=f"w_{sig}")
        if abs(sum(weights.values()) - 1.0) > 1e-6:
            st.caption(f"Sum = {sum(weights.values()):.2f} (normalised automatically).")

    st.markdown("---")
    st.markdown("### SYNTHETIC CORPUS")
    c = meta["counts"]
    st.markdown(
        f"- {c['actors']} actors\n- {c['personas']} personas\n- {c['posts']} posts\n"
        f"- {c['events']} activity events\n- {c['servers']} servers\n"
        f"- {c['pgp']} PGP keys\n- {c['wallets']} wallets")
    st.caption("100% fictional. No real service, network, chain or person is involved.")


# ==========================================================================
# MAIN
# ==========================================================================
st.markdown(
    '<div class="hero"><h1>\U0001f50e DARK WEB THREAT INTELLIGENCE PLATFORM</h1>'
    '<p>Threat Actor Attribution &amp; Verification &middot; SIH 26151 &middot; '
    'MVP on synthetic data</p></div>', unsafe_allow_html=True)

if "result" not in st.session_state:
    st.session_state.result = None
    st.session_state.deception = None
    st.session_state.case_id = None

if run:
    with st.spinner("Running evidence modules, Stage 1 and Stage 2…"):
        st.session_state.result = run_investigation(case_id, weights=weights)
        st.session_state.deception = None
        st.session_state.case_id = case_id

if deceive:
    with st.spinner("Injecting misleading synthetic evidence and re-running the pipeline…"):
        dec = run_deception_scenario(case_id)
        st.session_state.deception = dec
        st.session_state.result = dec["after"]
        st.session_state.case_id = case_id

ds = load_dataset()
case_meta = ds["case_by_id"][case_id]

if st.session_state.result is None:
    st.info("Select a case in the sidebar and press **RUN INVESTIGATION**.")
    st.markdown(f"#### {case_meta['case_id']} — {case_meta['title']}")
    st.markdown(f"**Subject persona:** `{case_meta['subject_persona']}`")
    st.markdown(case_meta["briefing"])
    st.markdown(
        "---\n"
        "**How to read this dashboard.** Stage 1 (blue) answers *who* the evidence "
        "points to and produces an Initial Attribution Score. Stage 2 (amber) audits "
        "that hypothesis with seven independent checks and returns "
        "**SUPPORTED**, **UNCERTAIN** or **INSUFFICIENT**. "
        "A high Stage 1 score does **not** produce a supported attribution by itself — "
        "that is the whole point of the architecture.")
    st.markdown(f'<div class="disc"><b>SYNTHETIC DATA NOTICE.</b> '
                f'{SYNTHETIC_DISCLAIMER}</div>', unsafe_allow_html=True)
    st.stop()

result = st.session_state.result
case = result["case"]
dec = st.session_state.deception

st.markdown(f"#### {case['case_id']} — {case['title']}")
st.markdown(f"**Subject persona:** `{case['subject_persona']}` &nbsp;&middot;&nbsp; "
            f"analysed {result['generated_at']}")
st.markdown(case["briefing"])

if dec:
    st.warning(f"**DECEPTION SCENARIO ACTIVE** — {dec['injected']['description']}")
    d = dec["delta"]
    k1, k2, k3 = st.columns(3)
    k1.metric("Leading candidate", d["top_after"],
              "unchanged" if d["top_before"] == d["top_after"] else f"was {d['top_before']}")
    k2.metric("Initial attribution score", f"{d['score_after']:.1f}",
              f"{d['score_change']:+.1f}")
    k3.metric("Stage 2 verdict", d["verdict_after"],
              f"was {d['verdict_before']}", delta_color="inverse")
    st.caption("The score and verdict above were RECOMPUTED by the real pipeline after "
               "injecting the misleading signal — nothing here is scripted.")

st.markdown("---")
render_stage1(result, ds)

st.markdown("---")
st.markdown("### RELATIONSHIP GRAPH")
g = result["graph"]
gs = result["graph_summary"]
st.caption(f"{gs['nodes']} nodes / {gs['edges']} edges &middot; "
           f"node types: {gs['node_types']} &middot; edge types: {gs['edge_types']}")
st.plotly_chart(graph_figure(g, case["subject_persona"]), use_container_width=True)

bcol1, bcol2 = st.columns(2)
top_actor = result["stage1"]["top_candidate"]
beh = top_actor["signals"]["behaviour"]
if beh.get("available"):
    with bcol1:
        st.plotly_chart(activity_figure(ds, case["subject_persona"],
                                        top_actor["actor_id"], beh["actor_profile"]),
                        use_container_width=True)
    with bcol2:
        st.plotly_chart(weekday_figure(ds, case["subject_persona"],
                                       top_actor["actor_id"], beh["actor_profile"]),
                        use_container_width=True)
else:
    st.info("Behavioural comparison unavailable: " + beh.get("reason", ""))

st.markdown("---")
render_stage2(result)

st.markdown("---")
st.markdown("### FINAL ASSESSMENT")
render_verdict(result)

# ---- report --------------------------------------------------------------
st.markdown("---")
st.markdown("### CASE REPORT")
report = build_report_dict(result, deception=dec)
rcol1, rcol2, rcol3 = st.columns([1, 1, 2])
with rcol1:
    st.download_button("GENERATE REPORT (JSON)",
                       data=json.dumps(report, indent=2),
                       file_name=f"{case['case_id']}-report.json",
                       mime="application/json", use_container_width=True)
with rcol2:
    st.download_button("GENERATE REPORT (HTML)", data=render_html(report),
                       file_name=f"{case['case_id']}-report.html",
                       mime="text/html", use_container_width=True)
with rcol3:
    if st.button("Save both to reports/ on disk", use_container_width=True):
        pj, ph = save_json(report), save_html(report)
        st.success(f"Saved `{os.path.relpath(pj)}` and `{os.path.relpath(ph)}`")

with st.expander("Report preview (JSON)"):
    st.json(report, expanded=False)

st.markdown(f'<div class="disc"><b>SYNTHETIC DATA NOTICE.</b> {SYNTHETIC_DISCLAIMER}'
            f'</div>', unsafe_allow_html=True)
