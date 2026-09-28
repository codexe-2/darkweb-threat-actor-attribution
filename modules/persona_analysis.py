"""
Module 2 — PERSONA ANALYSIS
===========================

Compares the subject persona's identity surface (username, aliases, forum
presence, identifier handles) against every catalogued actor's known personas.

Returns a 0-100 Persona Similarity score plus the evidence items that produced
it, so the investigator can see WHY the score is what it is.
"""

import re
from difflib import SequenceMatcher

from utils.helpers import personas_of_actor

LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "$": "s"})


def normalise(name: str) -> str:
    """Lowercase, strip separators, undo common leetspeak substitutions."""
    return re.sub(r"[^a-z0-9]", "", (name or "").lower().translate(LEET))


def token_set(name: str):
    return {t for t in re.split(r"[^a-z0-9]+", (name or "").lower().translate(LEET)) if len(t) > 2}


def bigrams(s: str):
    return {s[i:i + 2] for i in range(len(s) - 1)}


def name_similarity(a: str, b: str) -> float:
    """0-1 similarity between two handles: edit-ratio + bigram Jaccard + tokens."""
    na, nb = normalise(a), normalise(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ratio = SequenceMatcher(None, na, nb).ratio()
    ba, bb = bigrams(na), bigrams(nb)
    jacc = len(ba & bb) / len(ba | bb) if (ba | bb) else 0.0
    ta, tb = token_set(a), token_set(b)
    tok = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
    return 0.45 * ratio + 0.30 * jacc + 0.25 * tok


def analyse(ds, subject_id, actor_id):
    """Persona similarity between a subject persona and one candidate actor."""
    subject = ds["persona_by_id"][subject_id]
    refs = personas_of_actor(ds, actor_id)
    if not refs:
        return {"score": None, "available": False, "evidence": [],
                "reason": "no reference personas catalogued for this actor"}

    evidence = []
    best_name = 0.0
    for r in refs:
        s = name_similarity(subject["username"], r["username"])
        if s > best_name:
            best_name = s
        if s >= 0.55:
            evidence.append({
                "type": "handle_similarity",
                "detail": f"'{subject['username']}' ~ '{r['username']}' "
                          f"({r['persona_id']})",
                "weight": round(s, 3),
            })
        # subject handle may also echo a known alias
        for al in r["aliases"]:
            sa = name_similarity(subject["username"], al)
            if sa > best_name:
                best_name = sa
            if sa >= 0.6:
                evidence.append({
                    "type": "handle_matches_alias",
                    "detail": f"'{subject['username']}' ~ alias '{al}' ({r['persona_id']})",
                    "weight": round(sa, 3),
                })

    # alias reuse (exact shared alias strings are a strong identity link)
    subj_aliases = {normalise(a) for a in subject["aliases"]}
    ref_aliases = set()
    for r in refs:
        ref_aliases |= {normalise(a) for a in r["aliases"]}
    shared = subj_aliases & ref_aliases
    alias_score = min(1.0, len(shared) / 2.0) if subj_aliases else 0.0
    for a in sorted(shared):
        evidence.append({"type": "alias_reuse", "detail": f"shared alias '{a}'", "weight": 1.0})

    # forum co-presence (weak signal on its own)
    subj_forum = subject["forum"]
    forum_hit = any(r["forum"] == subj_forum for r in refs)
    forum_score = 1.0 if forum_hit else 0.0
    if forum_hit:
        evidence.append({"type": "forum_copresence",
                         "detail": f"actor also operates on {subj_forum}", "weight": 0.3})

    # identifier handle reuse (PGP id / wallet id strings recorded on the persona)
    ident_score, ident_hits = 0.0, 0
    for field, label in (("pgp_id", "PGP key id"), ("wallet_id", "wallet id")):
        val = subject.get(field)
        if val and any(r.get(field) == val for r in refs):
            ident_hits += 1
            evidence.append({"type": "identifier_reuse",
                             "detail": f"{label} {val} already attributed to {actor_id}",
                             "weight": 1.0})
    if subject.get("pgp_id") or subject.get("wallet_id"):
        denom = sum(1 for f in ("pgp_id", "wallet_id") if subject.get(f))
        ident_score = ident_hits / denom

    # Handle/alias evidence dominates. Identifier reuse is deliberately given only
    # a small share here because PGP and wallet are ALSO scored as their own
    # signals - over-weighting them in persona would double-count one observation.
    raw = (0.50 * best_name + 0.25 * alias_score +
           0.10 * forum_score + 0.15 * ident_score)

    return {
        "score": round(min(100.0, raw * 100), 1),
        "available": True,
        "evidence": evidence,
        "components": {
            "best_handle_similarity": round(best_name, 3),
            "alias_reuse": round(alias_score, 3),
            "forum_copresence": forum_score,
            "identifier_reuse": round(ident_score, 3),
        },
        "source_refs": [r["persona_id"] for r in refs],
    }
