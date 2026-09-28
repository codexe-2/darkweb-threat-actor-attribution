# Dark Web Threat Actor Attribution & Verification — MVP

**Smart India Hackathon — Problem Statement 26151**
Working proof-of-concept on Linux. **100% synthetic data.**

---

## 1. Project overview

Attribution systems usually stop at the question *"who does the evidence point to?"*
That question is answerable and dangerous: multi-signal correlation will always
return a ranked list of suspects, and a confident-looking number next to a name is
easy to mistake for proof.

This project separates attribution into two stages that do different jobs:

```
             MULTI-SIGNAL EVIDENCE
                      |
                 STAGE 1  "WHO?"
                      |
              ATTRIBUTION HYPOTHESIS
                      |
          STAGE 2  "CAN WE TRUST IT?"
                      |
       +--------------+--------------+
       |              |              |
   SUPPORTED      UNCERTAIN    INSUFFICIENT
```

**Stage 1** fuses persona, stylometry, behaviour, infrastructure, PGP and wallet
evidence into an *Initial Attribution Score*. It is a weighted evidence index on a
0–100 scale — **not** a probability of guilt.

**Stage 2** then audits that hypothesis independently with seven checks and may
reject it. A Stage 1 score of 94 becomes `UNCERTAIN` the moment a single
high-reliability signal points somewhere else. That is the core contribution:

```
HIGH INITIAL ATTRIBUTION  !=  TRUSTWORTHY ATTRIBUTION
```

---

## 2. MVP vs. final architecture

This repository is a **vertical slice** of the target system, not the target system.

| | Target architecture | This MVP |
|---|---|---|
| Ingestion | Tor crawlers, forum collectors, paste feeds | pre-built synthetic JSON corpus |
| Storage | PostgreSQL + object store | JSON files |
| NLP | transformer authorship models, multilingual | TF-IDF char n-grams + text statistics |
| Infrastructure | live scan/cert-transparency correlation | synthetic server records |
| Financial | chain-analysis integration | synthetic wallet identifiers |
| Graph | property graph database | NetworkX in memory |
| Serving | FastAPI + React | Streamlit |
| Stage 1 / Stage 2 | **as designed** | **as designed** |

The two stages — the actual innovation — are implemented in full. Everything
around them is deliberately the simplest thing that demonstrates them end to end.

### Target architecture

```
                    DATA INGESTION
                          |
                 EVIDENCE EXTRACTION
                          |
          +---------------+----------------+
          |               |                |
      PERSONA         STYLOMETRY       BEHAVIOUR
      ANALYSIS          / NLP          PROFILING
          |               |                |
          +---------------+----------------+
                          |
                 INFRASTRUCTURE ANALYSIS
                          |
                  PGP / WALLET ANALYSIS
                          |
                  RELATIONSHIP GRAPH
                          |
              STAGE 1 ATTRIBUTION ENGINE   "WHO?"
                          |
              STAGE 2 VERIFICATION ENGINE  "CAN WE TRUST IT?"
                          |
                   INVESTIGATOR UI
                          |
                      CASE REPORT
```

### Current MVP implementation

```
Synthetic JSON data
        |
Python evidence modules (persona, stylometry, behaviour, infra, PGP/wallet)
        |
NetworkX relationship graph
        |
Stage 1 attribution
        |
Stage 2 verification
        |
Streamlit investigator dashboard  ->  JSON / HTML case report
```

---

## 3. Project structure

```
darkweb_attribution_mvp/
├── app.py                      Streamlit investigator dashboard
├── run.sh                      Linux launcher (run / setup / test / smoke / data)
├── requirements.txt
├── README.md
├── data/
│   ├── actors.json             5 synthetic actors
│   ├── personas.json           14 personas (11 reference + 3 case subjects)
│   ├── posts.json              96 synthetic posts
│   ├── behaviour.json          285 timestamped activity events
│   ├── infrastructure.json     6 synthetic servers + 13 observations
│   ├── pgp.json                6 synthetic PGP keys
│   ├── wallets.json            6 synthetic wallet identifiers
│   └── cases.json              3 demonstration cases
├── modules/
│   ├── persona_analysis.py     handle / alias / identifier linkage
│   ├── stylometry.py           TF-IDF char n-grams + style statistics
│   ├── behaviour.py            24h + weekday rhythm comparison
│   ├── infrastructure.py       IP/SSL/SSH/cert/banner/hosting matching
│   ├── crypto_analysis.py      PGP and wallet reuse
│   ├── graph_engine.py         NetworkX relationship graph
│   ├── attribution.py          STAGE 1
│   ├── verification.py         STAGE 2 (seven checks)
│   ├── pipeline.py             orchestration + deception scenario
│   └── reporting.py            JSON / HTML case report
├── utils/helpers.py            data loading, calibration, formatting
├── tools/generate_data.py      deterministic synthetic data generator
├── tests/
│   ├── run_cases.py            headless acceptance test / terminal demo
│   └── smoke_app.py            offline dashboard render test
└── reports/                    generated case reports land here
```

---

## 4. Installation (Linux)

Tested layout for Ubuntu / Debian / Kali, Python 3.10+.

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip

cd darkweb_attribution_mvp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 5. Running

```bash
streamlit run app.py          # dashboard at http://localhost:8501
```

or use the launcher, which creates the venv on first run:

```bash
chmod +x run.sh
./run.sh setup     # create .venv and install dependencies
./run.sh           # start the dashboard
./run.sh test      # headless acceptance test - runs all 3 cases + deception
./run.sh smoke     # render-path test for app.py (no Streamlit needed)
./run.sh data      # regenerate the synthetic dataset
```

`./run.sh test` needs only pandas / numpy / scikit-learn / networkx — it is the
quickest way to verify the engine works on a fresh machine, and it prints the full
Stage 1 + Stage 2 trace to the terminal.

---

## 6. Synthetic dataset

Every record is fictional and generated by `tools/generate_data.py` from a fixed
seed (26151), so the dataset is reproducible.

- **5 actors** (`ACT-A` NIGHTJAR … `ACT-E` QUIETLARK), each with a distinct writing
  register and activity rhythm.
- **14 personas** — 11 with known attribution (the reference corpus) and 3 unknown
  subjects, one per case.
- **96 posts** generated from per-actor style pools, which is what makes the
  stylometry computation real rather than decorative.
- **285 activity events** sampled from per-actor hour and weekday distributions.
- **6 servers** using IETF documentation IP ranges (`198.51.100.0/24`,
  `203.0.113.0/24` — RFC 5737) with derived SSL/SSH fingerprints and cert serials.
- **6 PGP keys** and **6 wallet identifiers**, deliberately prefixed `SYN1` so they
  cannot be confused with real addresses.

To change the demonstration, edit `tools/generate_data.py` and run `./run.sh data`.
The scores will change accordingly — nothing in the pipeline is hardcoded.

---

## 7. Stage 1 — attribution engine

Six evidence modules run for every candidate actor:

| Signal | Weight | What it computes |
|---|---|---|
| Persona | 20% | normalised handle similarity (leetspeak-aware), alias reuse, forum co-presence, identifier reuse |
| Stylometry | 20% | TF-IDF character 3–5-gram cosine + 15 interpretable text statistics |
| Behaviour | 15% | circularly smoothed 24h histogram cosine, weekday cosine, posting intensity |
| Infrastructure | 25% | IP, TLS fingerprint, cert serial, SSH host key, banner, hosting identifier |
| PGP | 10% | key reuse across personas |
| Wallet | 10% | wallet reuse and cluster association |

```
signal score  x  weight  =  evidence contribution
```

Two deliberate design choices:

1. **Missing signals are excluded and the remaining weights are renormalised.**
   A subject with only two weak signals can therefore still produce a
   respectable-looking score. Detecting that situation is Stage 2's job. Stage 1
   is not allowed to quietly bury it.
2. **Stylometry scores are calibrated, not clipped.** Raw same-author cosine on
   this corpus is 0.83–0.91 and different-author 0.10–0.34; the calibration
   stretches that observed band across 0–100 and the raw cosine is always reported
   alongside it in the evidence detail.

---

## 8. Stage 2 — verification engine

Seven independent checks, each returning `PASS` / `WARNING` / `FAIL`:

1. **Evidence reliability** — signals are tiered `HIGH` (PGP, wallet),
   `MEDIUM` (infrastructure, persona), `HEURISTIC` (stylometry, behaviour), and a
   weighted reliability index is computed. An attribution carried mostly by
   heuristic signals is flagged.
2. **Evidence conflict** — for every signal, which actor does it *actually* favour?
   A `HIGH`-reliability signal pointing away from the leading candidate is a
   **CRITICAL CONFLICT**.
3. **Evidence independence** — an IP match, an SSL match and an SSH match from the
   *same* server are one observation seen three ways. Dependent artefacts are
   collapsed and the count of genuinely distinct sources is reported.
4. **Missing evidence** — a family only counts as corroboration if it is present
   *and* scores ≥ 50. Heuristic-only support yields
   **INSUFFICIENT CORROBORATION**.
5. **Alternative candidate testing** — margin to the runner-up, plus what the
   runner-up is supported by. Margin < 10 is **HIGH AMBIGUITY**.
6. **Sensitivity analysis** — leave-one-signal-out. If removing any single family
   changes rank 1, the attribution is **FRAGILE**.
7. **Temporal consistency** — activity predating account creation, observations
   outside a server's recorded lifetime, identifiers used before they existed,
   actors first seen after the activity they are blamed for.

### Verdict logic

| Verdict | Condition |
|---|---|
| `INSUFFICIENT` | missing-evidence or independence check FAILS — we cannot conclude at all (evaluated first) |
| `UNCERTAIN` | a conflict, high ambiguity, rank-flipping sensitivity or a temporal anomaly |
| `SUPPORTED` | enough corroborated, sufficiently independent, non-conflicting, stable evidence |

Reasons are always displayed. A `SUPPORTED` verdict still lists its caveats.

---

## 9. The three demonstration cases

| Case | Evidence picture | Stage 1 | Stage 2 |
|---|---|---|---|
| **CASE-001** Consistent | persona, stylometry, behaviour, infra, PGP and wallet all → ACT-A | ACT-A ≈ **94** | **SUPPORTED** (with a dependent-infrastructure warning) |
| **CASE-002** Deception | persona, stylometry, behaviour, infra → ACT-A, but **wallet → ACT-B**, no PGP recovered | ACT-A ≈ **77**, ACT-B ≈ **30** | **UNCERTAIN** — critical evidence conflict |
| **CASE-003** Sparse | 3 short posts, 6 events, no infra/PGP/wallet, one post predates the account | ACT-A ≈ **42** | **INSUFFICIENT** — no corroborating family, plus a temporal anomaly |

---

## 10. Deception scenario

`[ RUN DECEPTION SCENARIO ]` in the dashboard (or the last section of
`./run.sh test`) injects a misleading synthetic wallet belonging to `ACT-B` into
the evidence set and **re-runs the real pipeline**. Nothing is scripted; the
numbers below are recomputed.

```
BEFORE                               AFTER INJECTION
leading candidate   ACT-A            leading candidate   ACT-A
initial score        94.3            initial score        84.3
Stage 2 verdict  SUPPORTED           Stage 2 verdict  UNCERTAIN

  Stage 2:  CRITICAL EVIDENCE CONFLICT
            Wallet evidence (HIGH reliability) points to ACT-B / HOLLOWKEY
```

The leading candidate does **not** change — and that is the point. The system does
not flip to the actor the planted evidence names, and it does not keep its
confident verdict either. It reports that the picture is now contradictory and
refuses to call it supported.

---

## 11. Ethical scope and limitations

This project is an **analytical architecture demonstration on synthetic data**.

It does **not** and will not:

- crawl, scrape, attack or otherwise interact with Tor or any dark-web service
- de-anonymise, profile or target any real person
- query real blockchains or perform real cryptocurrency tracing
- collect credentials, exploit infrastructure or conduct any real-world targeting

All IP addresses come from IETF documentation ranges. All fingerprints and wallet
identifiers are derived from labels by a hash function and are marked synthetic in
the data files. Every report carries a synthetic-data notice.

More broadly: attribution output of this kind is an **investigative aid**, not
evidence. A `SUPPORTED` verdict here means "the synthetic evidence is internally
consistent", never "this person is guilty". The Stage 2 design exists precisely
because systems that output a single confident name invite exactly that
misreading.

## 12. Current MVP limitations

- Scores are weighted evidence indices, not calibrated probabilities; there is no
  ground-truth corpus to calibrate against.
- Stylometry is a TF-IDF baseline. It has no defence against deliberate style
  imitation or machine translation, and it is monolingual.
- The stylometry calibration constants are fitted to this synthetic corpus and
  would need refitting on real data.
- Behaviour analysis assumes a single timezone and no VPN/scheduler obfuscation.
- The verification thresholds in `verification.py` (`TH`) are expert-set, not
  learned.
- Everything is in-memory and single-user; no persistence, auth or audit log.
- The graph is a small NetworkX object laid out with a spring layout; it will not
  scale to a realistic corpus.

## 13. Future development roadmap

**Near term** — persistence (PostgreSQL + a property graph), a real ingestion
layer with provenance and chain-of-custody metadata, multilingual stylometry,
confidence calibration against a labelled corpus.

**Medium term** — FastAPI service + React investigator UI, transformer-based
authorship models with adversarial-imitation testing, analyst feedback loops that
tune the Stage 2 thresholds, an immutable audit trail for every verdict.

**Long term** — formal uncertainty quantification (Bayesian evidence fusion
instead of weighted sums), automated counter-deception modelling, and legal-grade
report generation with per-claim evidence provenance.

---

*All data in this repository is synthetic. Built for SIH Problem Statement 26151.*
