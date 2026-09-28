"""Shared utilities: dataset loading, score calibration, small formatting helpers."""

import json
import os
from functools import lru_cache

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
REPORT_DIR = os.path.join(ROOT, "reports")

SYNTHETIC_DISCLAIMER = (
    "All actors, personas, posts, timestamps, IP addresses, TLS/SSH fingerprints, "
    "PGP fingerprints and wallet identifiers in this system are SYNTHETIC and "
    "FICTIONAL. No dark-web service was accessed, crawled or attacked, no real "
    "blockchain was queried, and no real person is described or de-anonymised. "
    "This is an analytical-architecture demonstration only."
)


def _load(name):
    with open(os.path.join(DATA_DIR, name)) as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def load_dataset():
    """Load the whole synthetic corpus into one dict (cached)."""
    ds = {
        "actors": _load("actors.json"),
        "personas": _load("personas.json"),
        "posts": _load("posts.json"),
        "behaviour": _load("behaviour.json"),
        "infrastructure": _load("infrastructure.json"),
        "pgp": _load("pgp.json"),
        "wallets": _load("wallets.json"),
        "cases": _load("cases.json"),
    }
    ds["actor_by_id"] = {a["actor_id"]: a for a in ds["actors"]}
    ds["persona_by_id"] = {p["persona_id"]: p for p in ds["personas"]}
    ds["case_by_id"] = {c["case_id"]: c for c in ds["cases"]}
    ds["server_by_id"] = {s["server_id"]: s for s in ds["infrastructure"]["servers"]}
    return ds


def personas_of_actor(ds, actor_id):
    return [p for p in ds["personas"] if p.get("attributed_actor") == actor_id]


def posts_of_persona(ds, persona_id):
    return [p for p in ds["posts"] if p["persona_id"] == persona_id]


def posts_of_actor(ds, actor_id):
    ids = {p["persona_id"] for p in personas_of_actor(ds, actor_id)}
    return [p for p in ds["posts"] if p["persona_id"] in ids]


def events_of_persona(ds, persona_id):
    return [e for e in ds["behaviour"] if e["persona_id"] == persona_id]


def events_of_actor(ds, actor_id):
    ids = {p["persona_id"] for p in personas_of_actor(ds, actor_id)}
    return [e for e in ds["behaviour"] if e["persona_id"] in ids]


def observations_of_persona(ds, persona_id):
    return [o for o in ds["infrastructure"]["observations"] if o["persona_id"] == persona_id]


def observations_of_actor(ds, actor_id):
    ids = {p["persona_id"] for p in personas_of_actor(ds, actor_id)}
    return [o for o in ds["infrastructure"]["observations"] if o["persona_id"] in ids]


def calibrate(raw, low, high):
    """Stretch a raw similarity in [low, high] onto a 0-100 investigator scale.

    Raw cosine similarities between two English text corpora are never near 0,
    so a linear stretch gives an interpretable spread instead of everything
    bunching in the 70-95 band. This is a display calibration, not a probability.
    """
    if raw is None:
        return None
    x = (float(raw) - low) / (high - low)
    return round(max(0.0, min(1.0, x)) * 100, 1)


def cosine(a, b):
    num = sum(x * y for x, y in zip(a, b))
    da = sum(x * x for x in a) ** 0.5
    db = sum(y * y for y in b) ** 0.5
    if da == 0 or db == 0:
        return 0.0
    return num / (da * db)


def bar(value, width=24, char="\u2588"):
    """Plain-text contribution bar (used in the CLI runner and text report)."""
    if value is None:
        return "-" * width
    n = int(round((value / 100.0) * width))
    return char * n + "\u00b7" * (width - n)
