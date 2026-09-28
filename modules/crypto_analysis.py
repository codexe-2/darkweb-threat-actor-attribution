"""
Module 6 — PGP / WALLET ANALYSIS
================================

Works purely on SYNTHETIC identifiers held in data/pgp.json and data/wallets.json.
No external key server, no blockchain API, no real address is ever queried.

Two separate signals are produced (they are kept separate on purpose so that
Stage 2 can detect the case where the financial identifier contradicts every
other evidence family):

    pgp    — key reuse between the subject persona and the actor's personas
    wallet — wallet reuse, plus weaker same-cluster association

Identifier reuse is treated as HIGH-reliability evidence downstream.
"""

from utils.helpers import personas_of_actor


def _lookup(records, key, value):
    for r in records:
        if r[key] == value:
            return r
    return None


def analyse_pgp(ds, subject_id, actor_id):
    subject = ds["persona_by_id"][subject_id]
    pgp_id = subject.get("pgp_id")
    if not pgp_id:
        return {"score": None, "available": False, "evidence": [],
                "reason": "no PGP material recovered for the subject"}

    key = _lookup(ds["pgp"], "pgp_id", pgp_id)
    actor_personas = {p["persona_id"] for p in personas_of_actor(ds, actor_id)}
    actor_keys = {p["pgp_id"] for p in personas_of_actor(ds, actor_id) if p.get("pgp_id")}

    if pgp_id in actor_keys:
        shared = sorted(set(key["used_by_personas"]) & actor_personas)
        return {
            "score": 100.0, "available": True,
            "evidence": [{
                "type": "pgp_key_reuse",
                "detail": f"key {pgp_id} ({key['fingerprint'][:24]}\u2026) is already "
                          f"attributed to {actor_id} via {', '.join(shared)}",
                "weight": 1.0,
                "source_id": f"pgp:{pgp_id}",
            }],
            "components": {"exact_key_reuse": True},
        }
    return {"score": 0.0, "available": True, "evidence": [],
            "components": {"exact_key_reuse": False},
            "reason": f"subject key {pgp_id} is not associated with {actor_id}"}


def analyse_wallet(ds, subject_id, actor_id):
    subject = ds["persona_by_id"][subject_id]
    wid = subject.get("wallet_id")
    if not wid:
        return {"score": None, "available": False, "evidence": [],
                "reason": "no financial identifier recovered for the subject"}

    wallet = _lookup(ds["wallets"], "wallet_id", wid)
    actor_personas = {p["persona_id"] for p in personas_of_actor(ds, actor_id)}
    actor_wallets = {p["wallet_id"] for p in personas_of_actor(ds, actor_id) if p.get("wallet_id")}
    actor_clusters = {
        (_lookup(ds["wallets"], "wallet_id", w) or {}).get("cluster_id")
        for w in actor_wallets
    }

    if wid in actor_wallets:
        shared = sorted(set(wallet["used_by_personas"]) & actor_personas)
        return {
            "score": 100.0, "available": True,
            "evidence": [{
                "type": "wallet_reuse",
                "detail": f"wallet {wid} ({wallet['address'][:16]}\u2026) is already "
                          f"attributed to {actor_id} via {', '.join(shared)}",
                "weight": 1.0,
                "source_id": f"wallet:{wid}",
            }],
            "components": {"exact_wallet_reuse": True, "cluster_match": True},
        }

    if wallet and wallet["cluster_id"] in actor_clusters:
        return {
            "score": 55.0, "available": True,
            "evidence": [{
                "type": "wallet_cluster_association",
                "detail": f"wallet {wid} sits in synthetic cluster "
                          f"{wallet['cluster_id']}, also used by {actor_id}",
                "weight": 0.55,
                "source_id": f"cluster:{wallet['cluster_id']}",
            }],
            "components": {"exact_wallet_reuse": False, "cluster_match": True},
        }

    return {"score": 0.0, "available": True, "evidence": [],
            "components": {"exact_wallet_reuse": False, "cluster_match": False},
            "reason": f"subject wallet {wid} is not associated with {actor_id}"}
