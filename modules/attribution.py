"""
Module 8 — STAGE 1: ATTRIBUTION ENGINE   ("WHO?")
=================================================

Runs every evidence module for every candidate actor and combines the resulting
signal scores with TRANSPARENT weighted scoring:

        signal score  x  weight  =  evidence contribution

The sum of the contributions is the candidate's INITIAL ATTRIBUTION SCORE.

Two things are deliberately true of this engine:

  * It is NOT a probability. It is a weighted evidence index on a 0-100 scale.
  * Missing signals are EXCLUDED and the remaining weights are renormalised,
    so a subject with only two weak signals can still produce a high-looking
    number. That is intentional: detecting that situation is Stage 2's job,
    not Stage 1's. A high Stage 1 score is a HYPOTHESIS, never a conclusion.
"""

from modules import behaviour as behaviour_mod
from modules import crypto_analysis, infrastructure, persona_analysis, stylometry

# Default weights (sum = 1.00). PGP+Wallet together make up the 20% that the
# specification allocates to identifier evidence.
DEFAULT_WEIGHTS = {
    "persona": 0.20,
    "stylometry": 0.20,
    "behaviour": 0.15,
    "infrastructure": 0.25,
    "pgp": 0.10,
    "wallet": 0.10,
}

SIGNAL_LABEL = {
    "persona": "Persona",
    "stylometry": "Stylometry",
    "behaviour": "Behaviour",
    "infrastructure": "Infrastructure",
    "pgp": "PGP",
    "wallet": "Wallet",
}

SIGNAL_ORDER = ["persona", "stylometry", "behaviour", "infrastructure", "pgp", "wallet"]


def run_signals(ds, subject_id, actor_id, overrides=None):
    """Execute all six evidence modules for one (subject, candidate) pair."""
    results = {
        "persona": persona_analysis.analyse(ds, subject_id, actor_id),
        "stylometry": stylometry.analyse(ds, subject_id, actor_id),
        "behaviour": behaviour_mod.analyse(ds, subject_id, actor_id),
        "infrastructure": infrastructure.analyse(ds, subject_id, actor_id),
        "pgp": crypto_analysis.analyse_pgp(ds, subject_id, actor_id),
        "wallet": crypto_analysis.analyse_wallet(ds, subject_id, actor_id),
    }
    # deception / what-if injection: replace a signal result wholesale
    if overrides:
        for sig, res in overrides.get(actor_id, {}).items():
            results[sig] = res
    return results


def score_candidate(signals, weights=None, exclude=()):
    """Weighted combination with renormalisation over AVAILABLE signals."""
    weights = weights or DEFAULT_WEIGHTS
    contributions, available_weight = {}, 0.0
    for sig in SIGNAL_ORDER:
        res = signals.get(sig, {})
        w = weights.get(sig, 0.0)
        if sig in exclude or not res.get("available") or res.get("score") is None:
            contributions[sig] = {
                "score": None if not res.get("available") else res.get("score"),
                "weight": w, "contribution": 0.0,
                "status": "excluded" if sig in exclude else "missing",
            }
            continue
        available_weight += w
        contributions[sig] = {"score": res["score"], "weight": w,
                              "contribution": res["score"] * w, "status": "used"}

    if available_weight == 0:
        return 0.0, contributions, 0.0

    total = sum(c["contribution"] for c in contributions.values()) / available_weight
    # rescale the displayed contribution to the renormalised basis
    for c in contributions.values():
        if c["status"] == "used":
            c["effective_weight"] = round(c["weight"] / available_weight, 4)
            c["contribution"] = round(c["score"] * c["weight"] / available_weight, 2)
        else:
            c["effective_weight"] = 0.0
    return round(total, 1), contributions, round(available_weight, 4)


def run_stage1(ds, case, weights=None, overrides=None, exclude=()):
    """Full Stage 1 pass: score every candidate, rank them, keep all evidence."""
    subject_id = case["subject_persona"]
    weights = weights or DEFAULT_WEIGHTS
    candidates = []
    for actor_id in case["candidates"]:
        signals = run_signals(ds, subject_id, actor_id, overrides)
        total, contributions, avail_w = score_candidate(signals, weights, exclude)
        candidates.append({
            "actor_id": actor_id,
            "codename": ds["actor_by_id"][actor_id]["codename"],
            "initial_score": total,
            "contributions": contributions,
            "signals": signals,
            "available_weight": avail_w,
        })
    candidates.sort(key=lambda c: -c["initial_score"])
    return {
        "case_id": case["case_id"],
        "subject_persona": subject_id,
        "weights": dict(weights),
        "candidates": candidates,
        "top_candidate": candidates[0] if candidates else None,
        "margin": round(candidates[0]["initial_score"] - candidates[1]["initial_score"], 1)
        if len(candidates) > 1 else None,
        "note": "INITIAL ATTRIBUTION SCORE - a weighted evidence index, "
                "NOT a real-world probability of guilt.",
    }
