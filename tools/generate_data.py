#!/usr/bin/env python3
"""
generate_data.py — deterministic generator for the 100% SYNTHETIC dataset.

Every actor, persona, post, timestamp, IP address, fingerprint and wallet
identifier produced by this script is FICTIONAL. Nothing here is collected
from, derived from, or usable against any real service, network or person.

IP ranges used are IETF documentation ranges (RFC 5737):
    198.51.100.0/24  (TEST-NET-2)
    203.0.113.0/24   (TEST-NET-3)

Run:  python3 tools/generate_data.py
Writes JSON files into data/.
"""

import hashlib
import json
import os
import random
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

SEED = 26151
rng = random.Random(SEED)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def fake_sha256(label: str) -> str:
    """Deterministic, obviously-synthetic 'fingerprint' derived from a label."""
    h = hashlib.sha256(("SYNTHETIC::" + label).encode()).hexdigest()
    return ":".join(h[i:i + 2].upper() for i in range(0, 32, 2))


def fake_pgp_fpr(label: str) -> str:
    h = hashlib.sha1(("SYNTHETIC-PGP::" + label).encode()).hexdigest().upper()
    return " ".join(h[i:i + 4] for i in range(0, 40, 4))


def fake_wallet(label: str) -> str:
    h = hashlib.sha256(("SYNTHETIC-WALLET::" + label).encode()).hexdigest()
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = int(h[:40], 16)
    out = ""
    while n and len(out) < 33:
        n, r = divmod(n, len(alphabet))
        out += alphabet[r]
    return "SYN1" + out


def fake_cert_serial(label: str) -> str:
    h = hashlib.md5(("SYNTHETIC-CERT::" + label).encode()).hexdigest().upper()
    return ":".join(h[i:i + 2] for i in range(0, 16, 2))


# --------------------------------------------------------------------------
# 1. ACTORS
# --------------------------------------------------------------------------
ACTORS = [
    {
        "actor_id": "ACT-A",
        "codename": "NIGHTJAR",
        "description": "Synthetic vendor-operator profile. Formal, verbose writing "
                       "register; nocturnal activity rhythm; self-hosted infrastructure.",
        "first_observed": "2024-03-11",
        "threat_category": "marketplace-operator (fictional)",
    },
    {
        "actor_id": "ACT-B",
        "codename": "HOLLOWKEY",
        "description": "Synthetic financial-intermediary profile. Terse lowercase "
                       "register; daytime rhythm; known to launder proceeds for peers.",
        "first_observed": "2024-05-02",
        "threat_category": "financial-intermediary (fictional)",
    },
    {
        "actor_id": "ACT-C",
        "codename": "MARBLEFOX",
        "description": "Synthetic tooling developer. Highly technical register; "
                       "afternoon/evening rhythm.",
        "first_observed": "2023-11-27",
        "threat_category": "tool-developer (fictional)",
    },
    {
        "actor_id": "ACT-D",
        "codename": "TINSMITH",
        "description": "Synthetic advertiser/reseller. Promotional register with heavy "
                       "exclamation use; diffuse activity rhythm.",
        "first_observed": "2024-08-19",
        "threat_category": "reseller (fictional)",
    },
    {
        "actor_id": "ACT-E",
        "codename": "QUIETLARK",
        "description": "Synthetic low-tier participant. Hedging, question-heavy "
                       "register; early-morning rhythm.",
        "first_observed": "2025-01-06",
        "threat_category": "peripheral-participant (fictional)",
    },
]

# --------------------------------------------------------------------------
# 2. STYLE ENGINES  (drive the REAL stylometry computation downstream)
# --------------------------------------------------------------------------
STYLE_POOLS = {
    "ACT-A": [
        "Following a review of the current arrangement, I have concluded that the "
        "existing escrow terms remain acceptable; accordingly, no amendment is required.",
        "Please be advised that the mirror rotation scheduled for this week has been "
        "postponed, as the prior window did not permit an orderly migration.",
        "I would ask that counterparties refrain from opening duplicate disputes; each "
        "dispute is reviewed in sequence, and duplication merely delays resolution.",
        "It is my view that the reputation system, whilst imperfect, has organised the "
        "market rather more effectively than its detractors realise.",
        "Should the uptime figures deteriorate further, I shall reconsider the hosting "
        "arrangement in its entirety.",
        "I have catalogued the relevant correspondence and shall publish a summary once "
        "the outstanding items are settled.",
        "Kindly note that unsolicited direct messages are not monitored; formal requests "
        "should be submitted through the established channel.",
        "The proposed fee structure appears reasonable, provided that the settlement "
        "window is not extended beyond the agreed period.",
        "Regards, and my thanks to those who submitted considered feedback rather than "
        "mere complaint.",
        "In my experience, patience is rewarded in this environment; haste is not.",
        "I am obliged to point out that the figures circulated yesterday were incomplete "
        "and ought not to be relied upon.",
        "Whilst I appreciate the concern raised, the matter has been resolved and requires "
        "no further discussion.",
    ],
    "ACT-B": [
        "look... not doing escrow with new accounts, dont ask",
        "rates are rates, u either take it or u dont, simple",
        "yeah i saw the msg... will sort it later maybe tonight",
        "pls stop pinging me every hour, im not ur assistant",
        "fees went up. blame the network not me lol",
        "if u want fast u pay fast, thats it",
        "did anyone actually read the pinned post... clearly not",
        "nah that vendor is fine, ive moved stuff for him b4 no issues",
        "im not covering a loss cos u fat fingered the address",
        "ok deal. send half now half on delivery, standard",
        "whatever man, do what u want",
        "cba explaining this again, check the thread from last week",
    ],
    "ACT-C": [
        "PATCH: rebuilt the client against libsodium 1.0.18, drops 2 pkt/s of overhead.",
        "CFG note - set retry_backoff=450ms, anything lower and the relay drops you.",
        "Benchmarked 3 builds: v0.4 = 118ms p50, v0.5 = 94ms p50, v0.6 = 91ms p50.",
        "KNOWN ISSUE: the parser chokes on multi-line headers, fix queued for v0.7.",
        "Do NOT run the binary from /tmp, the wrapper resolves paths relative to cwd.",
        "Rewrote the queue as a ring buffer, memory footprint down ~38 percent.",
        "TODO: deterministic builds, reproducible hashes, then signed releases.",
        "Logs are verbose by default; set LOG_LEVEL=2 unless you are debugging.",
        "The regression was introduced in commit 4 of the previous branch, reverted now.",
        "API change: the callback signature now takes (ctx, buf, len) not (buf, len).",
        "Throughput scales linearly to 8 workers then flattens, likely lock contention.",
        "STATUS: build green, tests 214/214, tagging tonight.",
    ],
    "ACT-D": [
        "NEW STOCK IN!! Best rates on the board, GUARANTEED, don't miss out!!",
        "Vouched by 40+ buyers!! Check my feedback before you buy elsewhere!!",
        "LIMITED SLOTS! First come first served! Message me NOW!!",
        "Why pay more?? My prices beat every listing in this category, FACT!!",
        "Fast, reliable, TRUSTED — three years on the boards and zero disputes!!",
        "Bundle deal this week only!! Two for the price of one, act fast!!",
        "Don't listen to the haters, my numbers speak for themselves!!",
        "PREMIUM service, PREMIUM support, same-day response GUARANTEED!!",
        "Referral bonus for anyone who brings a serious buyer!! Easy money!!",
        "Still the number one seller in this section and climbing!!",
        "SALE EXTENDED!! You asked, I delivered!! Grab it while it lasts!!",
        "Serious buyers only please!! Time wasters will be blocked!!",
    ],
    "ACT-E": [
        "sorry if this is a dumb question, but is the escrow fee refunded if the deal falls through?",
        "i think i did it right? not really sure though, can someone check?",
        "maybe im misunderstanding, but why does the listing show two different prices?",
        "is it normal for confirmation to take this long, or should i be worried?",
        "not sure who to ask about this, apologies if this is the wrong section?",
        "i read the guide but im still a bit confused about the second step, sorry",
        "would it be ok to message the vendor directly, or is that frowned upon here?",
        "probably just me, but the page seems slower than usual today?",
        "thanks for explaining, i think i get it now, mostly",
        "should i wait, or is it better to open a dispute at this point?",
        "sorry to bump this, but does anyone know if the mirror is back up?",
        "im new here so please be patient with me, still learning how this works",
    ],
}

POST_TOPICS = [
    "escrow terms", "mirror uptime", "dispute handling", "fee schedule",
    "vendor vouching", "listing policy", "account recovery", "settlement window",
]


def make_post_text(style_ids, n_sentences, r):
    """Blend one or more style pools (style_ids = list of (actor_id, weight))."""
    ids, weights = zip(*style_ids)
    sentences = []
    for _ in range(n_sentences):
        sid = r.choices(ids, weights=weights, k=1)[0]
        sentences.append(r.choice(STYLE_POOLS[sid]))
    # avoid exact duplicates inside one post
    seen, out = set(), []
    for s in sentences:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return " ".join(out)


# --------------------------------------------------------------------------
# 3. BEHAVIOUR PROFILES
# --------------------------------------------------------------------------
def hour_profile(peaks, spread=2.2):
    """Return 24-slot weight vector peaked at the given hours."""
    w = [0.25] * 24
    for p in peaks:
        for h in range(24):
            d = min(abs(h - p), 24 - abs(h - p))
            w[h] += 6.0 * pow(2.718281828, -(d * d) / (2 * spread * spread))
    return w


BEHAVIOUR_PROFILES = {
    "ACT-A": {"hours": hour_profile([23, 1, 3]), "weekdays": [0.4, 1.0, 1.2, 1.2, 1.1, 1.0, 0.5]},
    "ACT-B": {"hours": hour_profile([10, 13]), "weekdays": [1.2, 1.2, 1.1, 1.1, 1.2, 0.3, 0.2]},
    "ACT-C": {"hours": hour_profile([15, 18])},
    "ACT-D": {"hours": [1.0] * 24},
    "ACT-E": {"hours": hour_profile([6, 8])},
}
for k, v in BEHAVIOUR_PROFILES.items():
    v.setdefault("weekdays", [1.0] * 7)


def gen_timestamps(profiles, n, start, end, r):
    """profiles = [(actor_id, weight), ...]"""
    ids, ws = zip(*profiles)
    span_days = (end - start).days
    out = []
    for _ in range(n):
        pid = r.choices(ids, weights=ws, k=1)[0]
        prof = BEHAVIOUR_PROFILES[pid]
        for _try in range(200):
            day = start + timedelta(days=r.randint(0, span_days))
            if r.random() < prof["weekdays"][day.weekday()] / max(prof["weekdays"]):
                break
        hour = r.choices(range(24), weights=prof["hours"], k=1)[0]
        ts = day.replace(hour=hour, minute=r.randint(0, 59), second=r.randint(0, 59))
        out.append(ts)
    return sorted(out)


# --------------------------------------------------------------------------
# 4. INFRASTRUCTURE (synthetic servers, RFC5737 documentation IPs)
# --------------------------------------------------------------------------
SERVERS = [
    {"server_id": "SRV-A1", "ip": "198.51.100.23", "hosting_provider": "SYNTH-HOST-01",
     "banner": "nginx/1.18.0 (Ubuntu)", "first_seen": "2024-03-14", "last_seen": "2026-04-02",
     "ssl_cert_id": "CERT-A", "ssh_key_id": "SSHK-A1"},
    {"server_id": "SRV-A2", "ip": "198.51.100.24", "hosting_provider": "SYNTH-HOST-01",
     "banner": "nginx/1.18.0 (Ubuntu)", "first_seen": "2024-09-01", "last_seen": "2026-05-19",
     "ssl_cert_id": "CERT-A", "ssh_key_id": "SSHK-A2"},
    {"server_id": "SRV-B1", "ip": "203.0.113.40", "hosting_provider": "SYNTH-HOST-02",
     "banner": "Apache/2.4.52 (Debian)", "first_seen": "2024-05-20", "last_seen": "2026-05-11",
     "ssl_cert_id": "CERT-B", "ssh_key_id": "SSHK-B1"},
    {"server_id": "SRV-C1", "ip": "203.0.113.77", "hosting_provider": "SYNTH-HOST-03",
     "banner": "Caddy/2.6.4", "first_seen": "2023-12-02", "last_seen": "2026-03-30",
     "ssl_cert_id": "CERT-C", "ssh_key_id": "SSHK-C1"},
    {"server_id": "SRV-D1", "ip": "203.0.113.120", "hosting_provider": "SYNTH-HOST-02",
     "banner": "LiteSpeed", "first_seen": "2024-08-25", "last_seen": "2026-02-14",
     "ssl_cert_id": "CERT-D", "ssh_key_id": "SSHK-D1"},
    {"server_id": "SRV-E1", "ip": "203.0.113.201", "hosting_provider": "SYNTH-HOST-04",
     "banner": "nginx/1.24.0", "first_seen": "2025-01-10", "last_seen": "2026-01-22",
     "ssl_cert_id": "CERT-E", "ssh_key_id": "SSHK-E1"},
]
for s in SERVERS:
    s["ssl_fingerprint"] = fake_sha256(s["ssl_cert_id"])
    s["cert_serial"] = fake_cert_serial(s["ssl_cert_id"])
    s["ssh_fingerprint"] = fake_sha256(s["ssh_key_id"])

# --------------------------------------------------------------------------
# 5. PERSONAS
# --------------------------------------------------------------------------
PERSONAS = [
    # ---- ACT-A reference personas -------------------------------------
    dict(persona_id="PSN-001", username="nightjar_ops", forum="AgoraRelay",
         account_created="2024-03-12", aliases=["nightjar", "jar_ops"],
         pgp_id="PGP-A1", wallet_id="WLT-A1", servers=["SRV-A1"],
         attributed_actor="ACT-A", role="reference"),
    dict(persona_id="PSN-002", username="n1ghtjar", forum="BlackVault",
         account_created="2024-04-02", aliases=["nightjar", "nj_relay"],
         pgp_id="PGP-A1", wallet_id="WLT-A1", servers=["SRV-A1"],
         attributed_actor="ACT-A", role="reference"),
    dict(persona_id="PSN-003", username="jar_of_night", forum="CipherDen",
         account_created="2024-07-18", aliases=["jar_ops"],
         pgp_id="PGP-A2", wallet_id="WLT-A2", servers=["SRV-A2"],
         attributed_actor="ACT-A", role="reference"),
    # ---- ACT-B reference personas -------------------------------------
    dict(persona_id="PSN-004", username="hollowkey", forum="BlackVault",
         account_created="2024-05-04", aliases=["hollow", "hk_desk"],
         pgp_id="PGP-B1", wallet_id="WLT-B1", servers=["SRV-B1"],
         attributed_actor="ACT-B", role="reference"),
    dict(persona_id="PSN-005", username="h0llow_k3y", forum="AgoraRelay",
         account_created="2024-06-21", aliases=["hollow", "vellum_desk"],
         pgp_id="PGP-B1", wallet_id="WLT-B1", servers=["SRV-B1"],
         attributed_actor="ACT-B", role="reference"),
    # ---- ACT-C ---------------------------------------------------------
    dict(persona_id="PSN-006", username="marblefox", forum="CipherDen",
         account_created="2023-11-29", aliases=["mfox"],
         pgp_id="PGP-C1", wallet_id="WLT-C1", servers=["SRV-C1"],
         attributed_actor="ACT-C", role="reference"),
    dict(persona_id="PSN-007", username="fox_marble", forum="AgoraRelay",
         account_created="2024-02-15", aliases=["mfox", "marble"],
         pgp_id="PGP-C1", wallet_id="WLT-C1", servers=["SRV-C1"],
         attributed_actor="ACT-C", role="reference"),
    # ---- ACT-D ---------------------------------------------------------
    dict(persona_id="PSN-008", username="tinsmith", forum="BlackVault",
         account_created="2024-08-20", aliases=["tin", "smithy"],
         pgp_id="PGP-D1", wallet_id="WLT-D1", servers=["SRV-D1"],
         attributed_actor="ACT-D", role="reference"),
    dict(persona_id="PSN-009", username="tinsmith_deals", forum="AgoraRelay",
         account_created="2024-10-03", aliases=["smithy"],
         pgp_id="PGP-D1", wallet_id="WLT-D1", servers=["SRV-D1"],
         attributed_actor="ACT-D", role="reference"),
    # ---- ACT-E ---------------------------------------------------------
    dict(persona_id="PSN-010", username="quietlark", forum="CipherDen",
         account_created="2025-01-08", aliases=["lark"],
         pgp_id="PGP-E1", wallet_id="WLT-E1", servers=["SRV-E1"],
         attributed_actor="ACT-E", role="reference"),
    dict(persona_id="PSN-011", username="lark_quiet", forum="AgoraRelay",
         account_created="2025-03-19", aliases=["lark"],
         pgp_id="PGP-E1", wallet_id=None, servers=["SRV-E1"],
         attributed_actor="ACT-E", role="reference"),

    # ---- UNKNOWN SUBJECTS (the personas under investigation) -----------
    # CASE-001 subject: everything points to ACT-A
    dict(persona_id="PSN-101", username="n1ghtjar_relay", forum="CipherDen",
         account_created="2025-11-04", aliases=["nightjar", "nj_relay"],
         pgp_id="PGP-A1", wallet_id="WLT-A1", servers=["SRV-A1"],
         attributed_actor=None, role="subject"),
    # CASE-002 subject: A on persona/style/behaviour/infra, B on the money
    dict(persona_id="PSN-102", username="n1ghtjar_desk", forum="BlackVault",
         account_created="2025-09-15", aliases=["jar_ops", "nj_relay"],
         pgp_id=None, wallet_id="WLT-B1", servers=["SRV-A2"],
         attributed_actor=None, role="subject"),
    # CASE-003 subject: sparse evidence only
    dict(persona_id="PSN-103", username="grey_tide", forum="AgoraRelay",
         account_created="2026-02-10", aliases=[],
         pgp_id=None, wallet_id=None, servers=[],
         attributed_actor=None, role="subject"),
]

# --------------------------------------------------------------------------
# 6. POST / BEHAVIOUR GENERATION PLAN
# --------------------------------------------------------------------------
#   persona_id -> (style blend, behaviour blend, n_posts, window)
PLAN = {
    "PSN-001": ([("ACT-A", 1.0)], [("ACT-A", 1.0)], 8, ("2024-03-15", "2026-04-01")),
    "PSN-002": ([("ACT-A", 1.0)], [("ACT-A", 1.0)], 7, ("2024-04-05", "2026-03-20")),
    "PSN-003": ([("ACT-A", 1.0)], [("ACT-A", 1.0)], 7, ("2024-07-20", "2026-05-10")),
    "PSN-004": ([("ACT-B", 1.0)], [("ACT-B", 1.0)], 8, ("2024-05-06", "2026-05-01")),
    "PSN-005": ([("ACT-B", 1.0)], [("ACT-B", 1.0)], 7, ("2024-06-25", "2026-04-18")),
    "PSN-006": ([("ACT-C", 1.0)], [("ACT-C", 1.0)], 7, ("2023-12-05", "2026-03-25")),
    "PSN-007": ([("ACT-C", 1.0)], [("ACT-C", 1.0)], 7, ("2024-02-20", "2026-02-27")),
    "PSN-008": ([("ACT-D", 1.0)], [("ACT-D", 1.0)], 7, ("2024-08-22", "2026-02-10")),
    "PSN-009": ([("ACT-D", 1.0)], [("ACT-D", 1.0)], 6, ("2024-10-05", "2026-01-30")),
    "PSN-010": ([("ACT-E", 1.0)], [("ACT-E", 1.0)], 7, ("2025-01-10", "2026-01-20")),
    "PSN-011": ([("ACT-E", 1.0)], [("ACT-E", 1.0)], 6, ("2025-03-21", "2025-12-15")),
    # subjects
    "PSN-101": ([("ACT-A", 1.0)], [("ACT-A", 1.0)], 8, ("2025-11-06", "2026-05-12")),
    "PSN-102": ([("ACT-A", 0.80), ("ACT-B", 0.20)],
                [("ACT-A", 0.85), ("ACT-B", 0.15)], 8, ("2025-09-18", "2026-05-14")),
    "PSN-103": ([("ACT-A", 0.55), ("ACT-E", 0.45)], [("ACT-A", 1.0)], 3,
                ("2025-11-20", "2026-05-02")),   # NOTE: starts BEFORE account_created
}


def build_posts_and_behaviour():
    posts, behaviour = [], []
    for pid, (style, beh, n, window) in PLAN.items():
        r = random.Random(SEED + int(pid.split("-")[1]))
        start = datetime.strptime(window[0], "%Y-%m-%d")
        end = datetime.strptime(window[1], "%Y-%m-%d")
        n_events = n * 3 if pid != "PSN-103" else 6
        stamps = gen_timestamps(beh, n_events, start, end, r)
        for i, ts in enumerate(stamps):
            behaviour.append({
                "event_id": f"EVT-{pid[-3:]}-{i:03d}",
                "persona_id": pid,
                "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "date": ts.strftime("%Y-%m-%d"),
                "hour": ts.hour,
                "weekday": ts.strftime("%A"),
                "event_type": r.choice(["post", "post", "login", "listing_update"]),
            })
        for i in range(n):
            ts = stamps[i % len(stamps)]
            n_sent = 2 if pid == "PSN-103" else r.randint(3, 5)
            posts.append({
                "post_id": f"PST-{pid[-3:]}-{i:03d}",
                "persona_id": pid,
                "forum": next(p["forum"] for p in PERSONAS if p["persona_id"] == pid),
                "thread_topic": r.choice(POST_TOPICS),
                "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "text": make_post_text(style, n_sent, r),
            })
    return posts, behaviour


# --------------------------------------------------------------------------
# 7. PGP / WALLETS / INFRA OBSERVATIONS
# --------------------------------------------------------------------------
def build_pgp():
    keys = {}
    for p in PERSONAS:
        if not p["pgp_id"]:
            continue
        k = keys.setdefault(p["pgp_id"], {
            "pgp_id": p["pgp_id"],
            "fingerprint": fake_pgp_fpr(p["pgp_id"]),
            "key_uid": f"synthetic-{p['pgp_id'].lower()}@example.invalid",
            "created": "2024-01-15",
            "algorithm": "RSA-4096 (synthetic record)",
            "used_by_personas": [],
        })
        k["used_by_personas"].append(p["persona_id"])
    created = {"PGP-A1": "2024-03-10", "PGP-A2": "2024-07-15", "PGP-B1": "2024-05-01",
               "PGP-C1": "2023-11-20", "PGP-D1": "2024-08-18", "PGP-E1": "2025-01-05"}
    for kid, k in keys.items():
        k["created"] = created.get(kid, "2024-01-15")
    return list(keys.values())


def build_wallets():
    wallets = {}
    for p in PERSONAS:
        if not p["wallet_id"]:
            continue
        w = wallets.setdefault(p["wallet_id"], {
            "wallet_id": p["wallet_id"],
            "address": fake_wallet(p["wallet_id"]),
            "cluster_id": None,
            "first_activity": "2024-03-20",
            "used_by_personas": [],
            "note": "SYNTHETIC identifier - not a real blockchain address",
        })
        w["used_by_personas"].append(p["persona_id"])
    clusters = {"WLT-A1": "CLU-1", "WLT-A2": "CLU-1", "WLT-B1": "CLU-2",
                "WLT-C1": "CLU-3", "WLT-D1": "CLU-4", "WLT-E1": "CLU-5"}
    first = {"WLT-A1": "2024-03-20", "WLT-A2": "2024-07-25", "WLT-B1": "2024-05-10",
             "WLT-C1": "2023-12-06", "WLT-D1": "2024-08-27", "WLT-E1": "2025-01-14"}
    for wid, w in wallets.items():
        w["cluster_id"] = clusters.get(wid, "CLU-0")
        w["first_activity"] = first.get(wid, "2024-01-01")
    return list(wallets.values())


OBS_DATES = {
    ("PSN-001", "SRV-A1"): "2024-04-01", ("PSN-002", "SRV-A1"): "2024-05-12",
    ("PSN-003", "SRV-A2"): "2024-09-14", ("PSN-004", "SRV-B1"): "2024-06-01",
    ("PSN-005", "SRV-B1"): "2024-07-09", ("PSN-006", "SRV-C1"): "2023-12-11",
    ("PSN-007", "SRV-C1"): "2024-03-02", ("PSN-008", "SRV-D1"): "2024-09-04",
    ("PSN-009", "SRV-D1"): "2024-11-11", ("PSN-010", "SRV-E1"): "2025-02-02",
    ("PSN-011", "SRV-E1"): "2025-04-06", ("PSN-101", "SRV-A1"): "2026-01-19",
    ("PSN-102", "SRV-A2"): "2025-10-22",
}


def build_infrastructure():
    obs = []
    i = 0
    for p in PERSONAS:
        for sid in p["servers"]:
            srv = next(s for s in SERVERS if s["server_id"] == sid)
            i += 1
            obs.append({
                "observation_id": f"OBS-{i:03d}",
                "persona_id": p["persona_id"],
                "server_id": sid,
                "observed_at": OBS_DATES.get((p["persona_id"], sid), "2025-01-01"),
                "ip": srv["ip"],
                "ssl_fingerprint": srv["ssl_fingerprint"],
                "cert_serial": srv["cert_serial"],
                "ssh_fingerprint": srv["ssh_fingerprint"],
                "server_banner": srv["banner"],
                "hosting_provider": srv["hosting_provider"],
                "collection_source": "synthetic-scan-simulation",
            })
    return {"servers": SERVERS, "observations": obs}


# --------------------------------------------------------------------------
# 8. CASES
# --------------------------------------------------------------------------
CASES = [
    {
        "case_id": "CASE-001",
        "title": "Consistent multi-signal attribution",
        "subject_persona": "PSN-101",
        "candidates": ["ACT-A", "ACT-B", "ACT-C", "ACT-D", "ACT-E"],
        "expected_outcome": "SUPPORTED",
        "briefing": "A newly observed persona on CipherDen reuses a known alias, a known "
                    "PGP key and a known wallet identifier, and was observed on a server "
                    "already associated with a catalogued actor. All evidence families "
                    "are present.",
    },
    {
        "case_id": "CASE-002",
        "title": "Deceptive / conflicting financial evidence",
        "subject_persona": "PSN-102",
        "candidates": ["ACT-A", "ACT-B", "ACT-C", "ACT-D", "ACT-E"],
        "expected_outcome": "UNCERTAIN",
        "briefing": "Persona, writing style, activity rhythm and infrastructure all point "
                    "toward one actor, but the financial identifier attached to the persona "
                    "belongs to a different catalogued actor. No PGP material was recovered.",
    },
    {
        "case_id": "CASE-003",
        "title": "Sparse evidence / insufficient corroboration",
        "subject_persona": "PSN-103",
        "candidates": ["ACT-A", "ACT-B", "ACT-C", "ACT-D", "ACT-E"],
        "expected_outcome": "INSUFFICIENT",
        "briefing": "Only three short posts and a handful of activity events were recovered. "
                    "No infrastructure, PGP or financial evidence is available, and one post "
                    "predates the recorded account creation date.",
    },
]


# --------------------------------------------------------------------------
def main():
    os.makedirs(DATA, exist_ok=True)
    posts, behaviour = build_posts_and_behaviour()

    payloads = {
        "actors.json": ACTORS,
        "personas.json": PERSONAS,
        "posts.json": posts,
        "behaviour.json": behaviour,
        "infrastructure.json": build_infrastructure(),
        "pgp.json": build_pgp(),
        "wallets.json": build_wallets(),
        "cases.json": CASES,
    }
    for name, payload in payloads.items():
        with open(os.path.join(DATA, name), "w") as fh:
            json.dump(payload, fh, indent=2)
        size = len(payload) if isinstance(payload, list) else len(payload["observations"])
        print(f"  wrote data/{name:24s} ({size} records)")
    print("\nAll data is SYNTHETIC and fictional.")


if __name__ == "__main__":
    main()
