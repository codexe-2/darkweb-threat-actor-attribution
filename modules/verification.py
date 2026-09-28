"""
Module 9 — STAGE 2: VERIFICATION ENGINE   ("CAN WE TRUST IT?")
==============================================================

Stage 1 produced an attribution HYPOTHESIS. Stage 2 audits that hypothesis
independently and may reject it no matter how high the Stage 1 score was.

Seven checks:

    1. Evidence Reliability      - how trustworthy are the signals that carried it?
    2. Evidence Conflict         - does any signal point at a DIFFERENT actor?
    3. Evidence Independence     - are the signals really independent observations?
    4. Missing Evidence          - is there enough corroboration to conclude at all?
    5. Alternative Candidate     - how close is the runner-up?
    6. Sensitivity Analysis      - leave-one-signal-out: does it all rest on one thing?
    7. Temporal Consistency      - is the chronology of the evidence even possible?

Final verdict: SUPPORTED / UNCERTAIN / INSUFFICIENT, always with reasons.
"""

from datetime import datetime

from modules.attribution import SIGNAL_LABEL, SIGNAL_ORDER, run_stage1
from utils.helpers import events_of_persona, observations_of_persona, posts_of_persona

PASS, WARN, FAIL = "PASS", "WARNING", "FAIL"

# How much weight an investigator should place on each evidence family.
RELIABILITY = {
    "pgp": "HIGH",
    "wallet": "HIGH",
    "infrastructure": "MEDIUM",
    "persona": "MEDIUM",
    "stylometry": "HEURISTIC",
    "behaviour": "HEURISTIC",
}
RELIABILITY_VALUE = {"HIGH": 1.0, "MEDIUM": 0.65, "HEURISTIC": 0.35}

# Thresholds (kept in one place so they are auditable / tunable)
TH = {
    "conflict_min_score": 60.0,       # a signal must be this strong to "point" anywhere
    "conflict_margin": 20.0,          # ...and beat the top candidate by this much
    "ambiguity_high": 10.0,           # margin below this  -> HIGH AMBIGUITY
    "ambiguity_moderate": 20.0,       # margin below this  -> MODERATE AMBIGUITY
    "sensitivity_high": 20.0,         # single-signal drop above this -> fragile
    "sensitivity_moderate": 12.0,
    "reliability_min": 0.50,          # weighted reliability index floor
    "min_independent_sources": 2,     # distinct evidence sources required
    "min_corroborating_families": 3,  # signal families required for a conclusion
    "corroboration_min_score": 50.0,  # a family must reach this to count as corroborating
}


# ==========================================================================
# CHECK 1 — EVIDENCE RELIABILITY
# ==========================================================================
def check_reliability(top):
    rows, num, den = [], 0.0, 0.0
    for sig in SIGNAL_ORDER:
        c = top["contributions"][sig]
        tier = RELIABILITY[sig]
        used = c["status"] == "used"
        rows.append({"signal": SIGNAL_LABEL[sig], "key": sig, "tier": tier,
                     "score": c["score"], "used": used,
                     "effective_weight": c.get("effective_weight", 0.0)})
        if used:
            num += RELIABILITY_VALUE[tier] * c["effective_weight"] * (c["score"] / 100.0)
            den += c["effective_weight"]
    index = round((num / den) if den else 0.0, 3)

    heuristic_weight = sum(r["effective_weight"] for r in rows
                           if r["used"] and r["tier"] == "HEURISTIC")
    if index >= TH["reliability_min"] and heuristic_weight < 0.6:
        status, msg = PASS, (f"Weighted reliability index {index:.2f}; attribution is "
                             f"carried by at least one HIGH/MEDIUM reliability family.")
    elif heuristic_weight >= 0.6:
        status, msg = WARN, (f"{heuristic_weight * 100:.0f}% of the effective weight comes "
                             f"from HEURISTIC signals (stylometry / behaviour), which are "
                             f"suggestive but not identifying.")
    else:
        status, msg = WARN, f"Weighted reliability index {index:.2f} is below the "\
                            f"{TH['reliability_min']:.2f} threshold."
    return {"name": "Evidence Reliability", "status": status, "message": msg,
            "index": index, "rows": rows,
            "heuristic_weight_share": round(heuristic_weight, 3)}


# ==========================================================================
# CHECK 2 — EVIDENCE CONFLICT
# ==========================================================================
def check_conflict(stage1):
    top = stage1["top_candidate"]
    by_actor = {c["actor_id"]: c for c in stage1["candidates"]}
    conflicts, agreements = [], []

    for sig in SIGNAL_ORDER:
        scored = [(aid, c["signals"][sig].get("score"))
                  for aid, c in by_actor.items()
                  if c["signals"][sig].get("available") and
                  c["signals"][sig].get("score") is not None]
        if not scored:
            continue
        scored.sort(key=lambda x: -x[1])
        winner, wscore = scored[0]
        top_score = dict(scored).get(top["actor_id"], 0.0)

        if winner == top["actor_id"]:
            agreements.append({"signal": SIGNAL_LABEL[sig], "points_to": winner,
                               "score": wscore})
            continue
        if wscore < TH["conflict_min_score"] or (wscore - top_score) < TH["conflict_margin"]:
            continue

        tier = RELIABILITY[sig]
        severity = "CRITICAL" if tier == "HIGH" else ("MAJOR" if tier == "MEDIUM" else "MINOR")
        conflicts.append({
            "signal": SIGNAL_LABEL[sig], "key": sig, "tier": tier, "severity": severity,
            "points_to": winner,
            "points_to_codename": by_actor[winner]["codename"],
            "conflicting_score": wscore, "top_candidate_score": top_score,
            "message": f"{SIGNAL_LABEL[sig]} evidence ({tier} reliability) points to "
                       f"{winner} / {by_actor[winner]['codename']} at {wscore:.0f}, while "
                       f"the leading candidate {top['actor_id']} scores "
                       f"{top_score:.0f} on the same signal.",
        })

    critical = [c for c in conflicts if c["severity"] == "CRITICAL"]
    major = [c for c in conflicts if c["severity"] == "MAJOR"]
    if critical:
        status = FAIL
        msg = "CRITICAL EVIDENCE CONFLICT - " + " ".join(c["message"] for c in critical)
    elif major:
        status = WARN
        msg = "Evidence conflict - " + " ".join(c["message"] for c in major)
    elif conflicts:
        status = WARN
        msg = "Minor disagreement between heuristic signals: " + \
              "; ".join(f"{c['signal']} favours {c['points_to']}" for c in conflicts)
    else:
        status = PASS
        msg = f"All {len(agreements)} available signals agree on {top['actor_id']}."
    return {"name": "Evidence Conflict", "status": status, "message": msg,
            "conflicts": conflicts, "agreements": agreements,
            "has_critical": bool(critical)}


# ==========================================================================
# CHECK 3 — EVIDENCE INDEPENDENCE
# ==========================================================================
def check_independence(top):
    """Collapse artefacts that originate from the same synthetic source."""
    sources, notes = {}, []
    for sig in SIGNAL_ORDER:
        c = top["contributions"][sig]
        if c["status"] != "used" or not c["score"]:
            continue
        res = top["signals"][sig]
        ids = []
        for ev in res.get("evidence", []):
            if ev.get("source_id"):
                ids.append(ev["source_id"])
        if not ids:
            ids = [f"{sig}:corpus"]      # stylometry/behaviour/persona = own source
        for sid in set(ids):
            sources.setdefault(sid, []).append(SIGNAL_LABEL[sig])

    collapsed = []
    for sid, sigs in sources.items():
        if sid.startswith("SRV-") and len(set(sigs)) >= 1:
            res = top["signals"]["infrastructure"]
            fields = [e["type"].split(":")[-1] for e in res.get("evidence", [])
                      if e.get("source_id") == sid]
            if len(fields) >= 2:
                collapsed.append({"source": sid, "artefacts": fields})
                notes.append(
                    f"{len(fields)} infrastructure artefacts ({', '.join(fields)}) all "
                    f"originate from the SAME synthetic server {sid}. These are dependent "
                    f"observations of one machine, not {len(fields)} independent proofs.")

    independent = len(sources)
    if independent >= TH["min_independent_sources"] + 1 and not collapsed:
        status = PASS
        msg = f"{independent} distinct evidence sources, no dependency collapse required."
    elif independent >= TH["min_independent_sources"] + 1 and collapsed:
        status = WARN
        msg = ("DEPENDENT EVIDENCE - " + " ".join(notes) +
               f" After collapsing, {independent} distinct sources remain, which is still "
               f"adequate corroboration.")
    elif independent >= TH["min_independent_sources"]:
        status = WARN
        msg = ("DEPENDENT EVIDENCE - " + (" ".join(notes) if notes else "") +
               f" Only {independent} distinct evidence sources support this attribution.")
    else:
        status = FAIL
        msg = (f"Attribution rests on only {independent} distinct evidence source(s). "
               + " ".join(notes))
    return {"name": "Evidence Independence", "status": status, "message": msg,
            "distinct_sources": independent,
            "source_map": {k: sorted(set(v)) for k, v in sources.items()},
            "dependent_clusters": collapsed}


# ==========================================================================
# CHECK 4 — MISSING EVIDENCE
# ==========================================================================
def check_missing(top):
    used, missing = [], []
    for sig in SIGNAL_ORDER:
        c = top["contributions"][sig]
        (used if c["status"] == "used" else missing).append(sig)

    # A corroborating family only counts if it actually SAYS something. A persona
    # score of 18/100 is not corroboration, it is noise, and treating it as
    # corroboration is exactly the failure mode Stage 2 exists to prevent.
    strong_used = [s for s in used if RELIABILITY[s] in ("HIGH", "MEDIUM")
                   and (top["contributions"][s]["score"] or 0) >= TH["corroboration_min_score"]]
    heuristic_used = [s for s in used if RELIABILITY[s] == "HEURISTIC"]

    detail = {
        "present": [SIGNAL_LABEL[s] for s in used],
        "missing": [SIGNAL_LABEL[s] for s in missing],
        "missing_reasons": {SIGNAL_LABEL[s]: top["signals"][s].get("reason", "not available")
                            for s in missing},
        "strong_families_present": [SIGNAL_LABEL[s] for s in strong_used],
    }

    if len(used) >= TH["min_corroborating_families"] and strong_used:
        status = PASS
        msg = (f"{len(used)} of {len(SIGNAL_ORDER)} evidence families available, including "
               f"{len(strong_used)} of HIGH/MEDIUM reliability.")
    elif not strong_used:
        status = FAIL
        msg = ("INSUFFICIENT CORROBORATION - no HIGH or MEDIUM reliability evidence family "
               "reaches the corroboration threshold "
               f"({TH['corroboration_min_score']:.0f}/100). The attribution rests on "
               "heuristic signals alone (" +
               ", ".join(SIGNAL_LABEL[s] for s in heuristic_used) + "). "
               "Missing entirely: " + (", ".join(SIGNAL_LABEL[s] for s in missing)
                                       or "none") + ".")
    elif len(used) < TH["min_corroborating_families"]:
        status = FAIL
        msg = (f"INSUFFICIENT CORROBORATION - only {len(used)} evidence families available "
               f"(minimum {TH['min_corroborating_families']}). Missing: " +
               ", ".join(SIGNAL_LABEL[s] for s in missing) + ".")
    else:
        status = WARN
        msg = "Some evidence families are missing: " + \
              ", ".join(SIGNAL_LABEL[s] for s in missing) + "."
    return dict(name="Missing Evidence", status=status, message=msg, **detail)


# ==========================================================================
# CHECK 5 — ALTERNATIVE CANDIDATE TESTING
# ==========================================================================
def check_alternatives(stage1):
    cands = stage1["candidates"]
    top = cands[0]
    if len(cands) < 2:
        return {"name": "Alternative Candidate", "status": WARN,
                "message": "No alternative candidate available to test against.",
                "margin": None, "runner_up": None}
    runner = cands[1]
    margin = round(top["initial_score"] - runner["initial_score"], 1)

    if margin < TH["ambiguity_high"]:
        status, tag = FAIL, "HIGH AMBIGUITY"
    elif margin < TH["ambiguity_moderate"]:
        status, tag = WARN, "MODERATE AMBIGUITY"
    else:
        status, tag = PASS, "CLEAR SEPARATION"
    msg = (f"{tag} - {top['actor_id']} scores {top['initial_score']:.0f} against "
           f"{runner['actor_id']} at {runner['initial_score']:.0f} (margin {margin:.0f} "
           f"points).")
    # where does the runner-up draw its support from?
    runner_support = [SIGNAL_LABEL[s] for s in SIGNAL_ORDER
                      if runner["contributions"][s]["status"] == "used"
                      and (runner["contributions"][s]["score"] or 0) >= 60]
    if runner_support:
        msg += " Runner-up is supported by: " + ", ".join(runner_support) + "."
    return {"name": "Alternative Candidate", "status": status, "message": msg,
            "margin": margin, "tag": tag,
            "runner_up": {"actor_id": runner["actor_id"], "codename": runner["codename"],
                          "score": runner["initial_score"], "supported_by": runner_support},
            "ranking": [{"actor_id": c["actor_id"], "codename": c["codename"],
                         "score": c["initial_score"]} for c in cands]}


# ==========================================================================
# CHECK 6 — SENSITIVITY ANALYSIS (leave one signal out)
# ==========================================================================
def check_sensitivity(ds, case, stage1, weights=None, overrides=None):
    top_id = stage1["top_candidate"]["actor_id"]
    base = stage1["top_candidate"]["initial_score"]
    rows = []
    for sig in SIGNAL_ORDER:
        if stage1["top_candidate"]["contributions"][sig]["status"] != "used":
            continue
        alt = run_stage1(ds, case, weights=weights, overrides=overrides, exclude=(sig,))
        new_top = alt["top_candidate"]
        new_score = next(c["initial_score"] for c in alt["candidates"]
                         if c["actor_id"] == top_id)
        rows.append({
            "removed": SIGNAL_LABEL[sig], "key": sig,
            "score_without": new_score,
            "delta": round(new_score - base, 1),
            "rank1_changes": new_top["actor_id"] != top_id,
            "new_rank1": new_top["actor_id"],
        })

    if not rows:
        return {"name": "Sensitivity Analysis", "status": FAIL,
                "message": "No signals available to test.", "rows": []}

    flips = [r for r in rows if r["rank1_changes"]]
    worst = min(rows, key=lambda r: r["delta"])
    max_drop = abs(worst["delta"])

    if flips:
        status = FAIL
        msg = ("FRAGILE ATTRIBUTION - removing " +
               ", ".join(r["removed"] for r in flips) +
               f" alone changes the leading candidate (to {flips[0]['new_rank1']}). "
               f"The conclusion depends on a single evidence family.")
    elif max_drop >= TH["sensitivity_high"]:
        status = WARN
        msg = (f"HIGH SENSITIVITY - removing {worst['removed']} drops "
               f"{top_id} from {base:.0f} to {worst['score_without']:.0f} "
               f"({worst['delta']:+.0f}). Ranking is unchanged, but the score leans "
               f"heavily on one family.")
    elif max_drop >= TH["sensitivity_moderate"]:
        status = WARN
        msg = (f"MODERATE SENSITIVITY - largest single-signal effect is "
               f"{worst['removed']} ({worst['delta']:+.0f} points).")
    else:
        status = PASS
        msg = (f"STABLE - no single evidence family moves {top_id} by more than "
               f"{max_drop:.0f} points, and the ranking never changes.")
    return {"name": "Sensitivity Analysis", "status": status, "message": msg,
            "rows": rows, "base_score": base, "max_drop": round(max_drop, 1),
            "rank_flips": [r["removed"] for r in flips]}


# ==========================================================================
# CHECK 7 — TEMPORAL CONSISTENCY
# ==========================================================================
def _d(s):
    return datetime.strptime(s[:10], "%Y-%m-%d")


def check_temporal(ds, case, stage1):
    subject_id = case["subject_persona"]
    subject = ds["persona_by_id"][subject_id]
    anomalies, observations = [], []
    created = _d(subject["account_created"])
    observations.append(f"Subject account {subject_id} created {subject['account_created']}.")

    # (a) content that predates the account it was posted from
    posts = posts_of_persona(ds, subject_id)
    events = events_of_persona(ds, subject_id)
    earliest = None
    for item in posts + events:
        d = _d(item["timestamp"])
        earliest = d if earliest is None or d < earliest else earliest
    if earliest and earliest < created:
        days = (created - earliest).days
        anomalies.append({
            "type": "activity_precedes_account",
            "detail": f"Activity recorded on {earliest:%Y-%m-%d}, which is {days} days "
                      f"BEFORE the subject account was created "
                      f"({subject['account_created']}). Either the account-creation record "
                      f"is wrong, the activity belongs to another account, or the data "
                      f"has been manipulated.",
            "severity": "MAJOR",
        })

    # (b) infrastructure observed outside the server's own lifetime
    for obs in observations_of_persona(ds, subject_id):
        srv = ds["server_by_id"][obs["server_id"]]
        od = _d(obs["observed_at"])
        observations.append(f"Subject observed on {srv['server_id']} at "
                            f"{obs['observed_at']} (server active "
                            f"{srv['first_seen']} to {srv['last_seen']}).")
        if od < _d(srv["first_seen"]) or od > _d(srv["last_seen"]):
            anomalies.append({
                "type": "observation_outside_server_lifetime",
                "detail": f"Infrastructure observation {obs['observation_id']} dated "
                          f"{obs['observed_at']} falls outside the recorded lifetime of "
                          f"{srv['server_id']} ({srv['first_seen']} - {srv['last_seen']}).",
                "severity": "MAJOR"})

    # (c) identifier used before it existed
    top = stage1["top_candidate"]
    for sig, table, key, idfield in (("pgp", ds["pgp"], "created", "pgp_id"),
                                     ("wallet", ds["wallets"], "first_activity", "wallet_id")):
        val = subject.get(idfield)
        if not val:
            continue
        rec = next((r for r in table if r[idfield] == val), None)
        if rec and earliest and _d(rec[key]) > earliest:
            anomalies.append({
                "type": f"{sig}_used_before_creation",
                "detail": f"{sig.upper()} identifier {val} is recorded as first existing on "
                          f"{rec[key]}, after the subject's earliest activity "
                          f"{earliest:%Y-%m-%d}.",
                "severity": "MAJOR"})

    # (d) attribution to an actor first observed after the subject's activity
    actor = ds["actor_by_id"][top["actor_id"]]
    observations.append(f"Leading candidate {actor['actor_id']} first observed "
                        f"{actor['first_observed']}.")
    if earliest and _d(actor["first_observed"]) > earliest:
        anomalies.append({
            "type": "actor_postdates_activity",
            "detail": f"{actor['actor_id']} was first observed "
                      f"{actor['first_observed']}, after the subject's earliest recorded "
                      f"activity ({earliest:%Y-%m-%d}).",
            "severity": "MINOR"})

    if not anomalies:
        status = PASS
        msg = "Chronology is internally consistent; no temporal anomaly detected."
    elif any(a["severity"] == "MAJOR" for a in anomalies):
        status = FAIL
        msg = "TEMPORAL ANOMALY - " + " ".join(a["detail"] for a in anomalies
                                               if a["severity"] == "MAJOR")
    else:
        status = WARN
        msg = "Minor temporal irregularity - " + " ".join(a["detail"] for a in anomalies)
    return {"name": "Temporal Consistency", "status": status, "message": msg,
            "anomalies": anomalies, "observations": observations}


# ==========================================================================
# FINAL VERDICT
# ==========================================================================
def run_stage2(ds, case, stage1, weights=None, overrides=None):
    top = stage1["top_candidate"]
    checks = {
        "reliability": check_reliability(top),
        "conflict": check_conflict(stage1),
        "independence": check_independence(top),
        "missing": check_missing(top),
        "alternatives": check_alternatives(stage1),
        "sensitivity": check_sensitivity(ds, case, stage1, weights, overrides),
        "temporal": check_temporal(ds, case, stage1),
    }

    reasons, verdict = [], "SUPPORTED"

    # ---- INSUFFICIENT takes precedence: we cannot conclude at all -------
    insufficient = []
    if checks["missing"]["status"] == FAIL:
        insufficient.append(checks["missing"]["message"])
    if checks["independence"]["status"] == FAIL:
        insufficient.append(checks["independence"]["message"])
    if insufficient:
        verdict = "INSUFFICIENT"
        # surface every other failing check too - they are still relevant findings
        for key in ("conflict", "temporal", "sensitivity", "alternatives"):
            if checks[key]["status"] == FAIL:
                insufficient.append(checks[key]["message"])
        reasons = insufficient

    # ---- otherwise: is the hypothesis trustworthy? ----------------------
    if verdict != "INSUFFICIENT":
        untrusted = []
        if checks["conflict"]["status"] == FAIL:
            untrusted.append(checks["conflict"]["message"])
        elif checks["conflict"]["status"] == WARN and checks["conflict"]["conflicts"]:
            untrusted.append(checks["conflict"]["message"])
        if checks["alternatives"]["status"] == FAIL:
            untrusted.append(checks["alternatives"]["message"])
        if checks["sensitivity"]["status"] == FAIL:
            untrusted.append(checks["sensitivity"]["message"])
        if checks["temporal"]["status"] == FAIL:
            untrusted.append(checks["temporal"]["message"])
        if untrusted:
            verdict = "UNCERTAIN"
            reasons = untrusted

    # ---- supporting narrative for a clean result ------------------------
    if verdict == "SUPPORTED":
        reasons = [
            checks["missing"]["message"],
            checks["reliability"]["message"],
            checks["conflict"]["message"],
            checks["alternatives"]["message"],
            checks["sensitivity"]["message"],
            checks["temporal"]["message"],
        ]

    warnings = [c["message"] for c in checks.values() if c["status"] == WARN]

    return {
        "case_id": case["case_id"],
        "top_candidate": {"actor_id": top["actor_id"], "codename": top["codename"],
                          "initial_score": top["initial_score"]},
        "checks": checks,
        "check_status": {k: v["status"] for k, v in checks.items()},
        "verdict": verdict,
        "reasons": reasons,
        "warnings": warnings,
        "statement": _statement(verdict, top),
    }


def _statement(verdict, top):
    if verdict == "SUPPORTED":
        return (f"The evidence supports the attribution of the subject persona to "
                f"{top['actor_id']} / {top['codename']}. This remains an analytical "
                f"conclusion on synthetic data, not a legal finding.")
    if verdict == "UNCERTAIN":
        return (f"An attribution hypothesis toward {top['actor_id']} / {top['codename']} "
                f"exists (initial score {top['initial_score']:.0f}), but it CANNOT be "
                f"trusted as it stands. The hypothesis must be treated as unverified "
                f"pending resolution of the issues below.")
    return (f"There is not enough independently corroborated evidence to attribute the "
            f"subject to any actor. {top['actor_id']} is the leading hypothesis only in "
            f"the sense that the available fragments lean that way; no conclusion should "
            f"be drawn.")
