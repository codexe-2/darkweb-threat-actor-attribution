"""
PIPELINE ORCHESTRATOR
=====================

Wires the modules together end to end:

    synthetic data -> evidence modules -> graph -> Stage 1 -> Stage 2

and implements Module 11, the DECEPTION SCENARIO.

The deception scenario does not fake the dashboard. It injects a misleading
synthetic wallet signal into the evidence set and RE-RUNS the real pipeline, so
the drop in Stage 1 score and the change of Stage 2 verdict are both computed,
not scripted.
"""

import copy
from datetime import datetime

from modules import graph_engine
from modules.attribution import DEFAULT_WEIGHTS, run_stage1
from modules.verification import run_stage2
from utils.helpers import load_dataset


def run_investigation(case_id, weights=None, overrides=None, ds=None):
    """One complete Stage 1 + Stage 2 pass over a case."""
    ds = ds or load_dataset()
    case = ds["case_by_id"][case_id]
    weights = weights or DEFAULT_WEIGHTS

    stage1 = run_stage1(ds, case, weights=weights, overrides=overrides)
    stage2 = run_stage2(ds, case, stage1, weights=weights, overrides=overrides)
    graph = graph_engine.build_graph(ds, case, stage1)

    return {
        "case": case,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "stage1": stage1,
        "stage2": stage2,
        "graph": graph,
        "graph_summary": graph_engine.graph_summary(graph),
        "relationships": graph_engine.relationship_list(graph, case["subject_persona"]),
        "deception_applied": bool(overrides),
    }


# --------------------------------------------------------------------------
# MODULE 11 — DECEPTION SCENARIO
# --------------------------------------------------------------------------
def build_deception_overrides(ds, case, planted_actor="ACT-B"):
    """Plant a misleading financial identifier in the evidence set.

    Narrative: the subject deliberately transacts through a wallet belonging to a
    different catalogued actor (or a third party plants it) in order to
    misdirect attribution. Stage 1 sees a genuine, strong HIGH-reliability
    signal pointing elsewhere; only Stage 2 recognises what it means.
    """
    wallet = next((w for w in ds["wallets"]
                   if planted_actor.split("-")[1] in w["wallet_id"]), ds["wallets"][0])
    planted_persona = next(p["persona_id"] for p in ds["personas"]
                           if p.get("attributed_actor") == planted_actor
                           and p.get("wallet_id") == wallet["wallet_id"])

    overrides = {}
    for actor_id in case["candidates"]:
        if actor_id == planted_actor:
            overrides[actor_id] = {"wallet": {
                "score": 100.0, "available": True,
                "evidence": [{
                    "type": "wallet_reuse",
                    "detail": f"[INJECTED] wallet {wallet['wallet_id']} "
                              f"({wallet['address'][:16]}\u2026) is attributed to "
                              f"{planted_actor} via {planted_persona}",
                    "weight": 1.0,
                    "source_id": f"wallet:{wallet['wallet_id']}",
                }],
                "components": {"exact_wallet_reuse": True, "injected": True},
            }}
        else:
            overrides[actor_id] = {"wallet": {
                "score": 0.0, "available": True, "evidence": [],
                "components": {"exact_wallet_reuse": False, "injected": True},
                "reason": f"injected wallet {wallet['wallet_id']} is not associated "
                          f"with {actor_id}",
            }}
    return overrides, wallet, planted_actor


def run_deception_scenario(case_id, planted_actor="ACT-B", ds=None):
    """Run the case clean, then re-run it with the misleading signal injected."""
    ds = ds or load_dataset()
    case = ds["case_by_id"][case_id]

    before = run_investigation(case_id, ds=ds)
    overrides, wallet, planted = build_deception_overrides(ds, case, planted_actor)
    after = run_investigation(case_id, overrides=overrides, ds=ds)

    b_top, a_top = before["stage1"]["top_candidate"], after["stage1"]["top_candidate"]
    return {
        "case_id": case_id,
        "injected": {
            "signal": "wallet",
            "wallet_id": wallet["wallet_id"],
            "address": wallet["address"],
            "points_to": planted,
            "codename": ds["actor_by_id"][planted]["codename"],
            "description": f"A misleading financial identifier ({wallet['wallet_id']}) "
                           f"belonging to {planted} was attached to the subject persona. "
                           f"This is a SYNTHETIC injection used to test whether the "
                           f"verification stage can resist a plausible but contradictory "
                           f"HIGH-reliability signal.",
        },
        "before": before,
        "after": after,
        "delta": {
            "top_before": b_top["actor_id"],
            "score_before": b_top["initial_score"],
            "verdict_before": before["stage2"]["verdict"],
            "top_after": a_top["actor_id"],
            "score_after": a_top["initial_score"],
            "verdict_after": after["stage2"]["verdict"],
            "score_change": round(a_top["initial_score"] - b_top["initial_score"], 1),
            "verdict_changed": before["stage2"]["verdict"] != after["stage2"]["verdict"],
        },
    }


def strip_graph(result):
    """Return a JSON-serialisable copy of an investigation result."""
    out = copy.copy(result)
    out.pop("graph", None)
    return out
