"""
Module 5 — INFRASTRUCTURE ANALYSIS
==================================

Compares synthetic hosting artefacts observed for the subject persona against
artefacts already attributed to each candidate actor:

    IP address, TLS/SSL fingerprint, certificate serial,
    SSH host-key fingerprint, server banner, hosting identifier.

CRITICAL DESIGN POINT (feeds Stage 2, check 3):
An IP match, an SSL match and an SSH match that all come from the SAME synthetic
server are ONE observation seen three ways, not three independent proofs. This
module therefore records, for every matched artefact, the server_id it came from,
so the verification engine can collapse dependent observations.
"""

from utils.helpers import observations_of_actor, observations_of_persona

FIELD_WEIGHTS = {
    "ip": 0.30,
    "ssl_fingerprint": 0.25,
    "ssh_fingerprint": 0.25,
    "cert_serial": 0.08,
    "server_banner": 0.05,
    "hosting_provider": 0.07,
}

FIELD_LABEL = {
    "ip": "IP address",
    "ssl_fingerprint": "TLS certificate fingerprint",
    "ssh_fingerprint": "SSH host-key fingerprint",
    "cert_serial": "certificate serial",
    "server_banner": "server banner",
    "hosting_provider": "hosting identifier",
}

# artefacts that are properties of one machine (and therefore not independent
# of one another when they come from the same server)
MACHINE_BOUND = {"ip", "ssl_fingerprint", "ssh_fingerprint", "cert_serial", "server_banner"}


def analyse(ds, subject_id, actor_id):
    subj_obs = observations_of_persona(ds, subject_id)
    act_obs = observations_of_actor(ds, actor_id)

    if not subj_obs:
        return {"score": None, "available": False, "evidence": [],
                "matched_sources": [], "reason": "no infrastructure observation "
                                                 "recovered for the subject"}
    if not act_obs:
        return {"score": 0.0, "available": True, "evidence": [],
                "matched_sources": [],
                "reason": "no infrastructure catalogued for this actor"}

    best = 0.0
    best_detail = None
    for so in subj_obs:
        for ao in act_obs:
            hits, score = [], 0.0
            for field, w in FIELD_WEIGHTS.items():
                if so.get(field) and so[field] == ao.get(field):
                    score += w
                    hits.append(field)
            if score > best:
                best, best_detail = score, (so, ao, hits)

    if best_detail is None:
        return {"score": 0.0, "available": True, "evidence": [],
                "matched_sources": [],
                "reason": "no overlapping infrastructure artefacts"}

    so, ao, hits = best_detail
    evidence, matched_sources = [], []
    for field in hits:
        evidence.append({
            "type": f"infra_match:{field}",
            "detail": f"{FIELD_LABEL[field]} matches {ao['persona_id']} "
                      f"on {ao['server_id']} ({_short(so[field])})",
            "weight": FIELD_WEIGHTS[field],
            # provenance: which physical (synthetic) machine produced this artefact
            "source_id": ao["server_id"] if field in MACHINE_BOUND else "hosting:"
                         + str(so.get("hosting_provider")),
            "machine_bound": field in MACHINE_BOUND,
        })
        matched_sources.append(evidence[-1]["source_id"])

    distinct_sources = sorted(set(matched_sources))
    return {
        "score": round(min(1.0, best) * 100, 1),
        "available": True,
        "evidence": evidence,
        "matched_fields": hits,
        "matched_sources": distinct_sources,
        "subject_observations": subj_obs,
        "matched_observation": ao,
        "components": {"raw_field_weight_sum": round(best, 3),
                       "distinct_sources": len(distinct_sources)},
    }


def _short(v, n=22):
    v = str(v)
    return v if len(v) <= n else v[:n] + "\u2026"
