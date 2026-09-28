"""
Module 7 — RELATIONSHIP GRAPH
=============================

Builds a NetworkX multi-type graph over the synthetic corpus.

Node types : ACTOR, PERSONA, ALIAS, FORUM, PGP, WALLET, SERVER
Edge types : USES_ALIAS, POSTED_ON, USES_PGP, USES_WALLET,
             SHARES_INFRASTRUCTURE, SIMILAR_WRITING, SIMILAR_ACTIVITY,
             ATTRIBUTED_TO

The analytic edges (SIMILAR_WRITING / SIMILAR_ACTIVITY) are added from the live
Stage 1 signal results, so the graph shown to the investigator reflects the
computation that was actually performed for that case.
"""

import networkx as nx

NODE_COLOURS = {
    "ACTOR": "#e63946", "PERSONA": "#457b9d", "ALIAS": "#a8dadc",
    "FORUM": "#f4a261", "PGP": "#8ecae6", "WALLET": "#ffb703",
    "SERVER": "#90be6d", "SUBJECT": "#f72585",
}

EDGE_STYLE = {
    "ATTRIBUTED_TO": "#e63946", "USES_ALIAS": "#8d99ae", "POSTED_ON": "#adb5bd",
    "USES_PGP": "#0077b6", "USES_WALLET": "#fb8500",
    "SHARES_INFRASTRUCTURE": "#2a9d8f", "SIMILAR_WRITING": "#7209b7",
    "SIMILAR_ACTIVITY": "#b5179e",
}


def build_graph(ds, case, stage1=None, similarity_threshold=55.0):
    g = nx.Graph()
    subject_id = case["subject_persona"]
    relevant_actors = set(case["candidates"])

    # ---- persona / actor / identifier nodes ----------------------------
    for p in ds["personas"]:
        is_subject = p["persona_id"] == subject_id
        if not is_subject and p.get("attributed_actor") not in relevant_actors:
            continue
        if p.get("role") == "subject" and not is_subject:
            continue

        label = f"{p['username']}\n({p['persona_id']})"
        g.add_node(p["persona_id"], ntype="SUBJECT" if is_subject else "PERSONA",
                   label=label, title=_persona_tooltip(p), subject=is_subject)

        if p.get("attributed_actor"):
            a = ds["actor_by_id"][p["attributed_actor"]]
            g.add_node(a["actor_id"], ntype="ACTOR",
                       label=f"{a['codename']}\n({a['actor_id']})",
                       title=a["description"])
            g.add_edge(p["persona_id"], a["actor_id"], etype="ATTRIBUTED_TO",
                       weight=3.0, label="ATTRIBUTED_TO")

        for al in p["aliases"]:
            nid = f"ALIAS::{al}"
            g.add_node(nid, ntype="ALIAS", label=al, title=f"alias '{al}'")
            g.add_edge(p["persona_id"], nid, etype="USES_ALIAS", weight=1.0,
                       label="USES_ALIAS")

        fid = f"FORUM::{p['forum']}"
        g.add_node(fid, ntype="FORUM", label=p["forum"], title=f"forum {p['forum']}")
        g.add_edge(p["persona_id"], fid, etype="POSTED_ON", weight=0.6, label="POSTED_ON")

        if p.get("pgp_id"):
            g.add_node(p["pgp_id"], ntype="PGP", label=p["pgp_id"],
                       title=f"synthetic PGP key {p['pgp_id']}")
            g.add_edge(p["persona_id"], p["pgp_id"], etype="USES_PGP", weight=2.5,
                       label="USES_PGP")

        if p.get("wallet_id"):
            g.add_node(p["wallet_id"], ntype="WALLET", label=p["wallet_id"],
                       title=f"synthetic wallet {p['wallet_id']}")
            g.add_edge(p["persona_id"], p["wallet_id"], etype="USES_WALLET", weight=2.5,
                       label="USES_WALLET")

    # ---- infrastructure ------------------------------------------------
    for obs in ds["infrastructure"]["observations"]:
        if obs["persona_id"] not in g:
            continue
        srv = ds["server_by_id"][obs["server_id"]]
        g.add_node(srv["server_id"], ntype="SERVER", label=srv["server_id"],
                   title=f"{srv['ip']} / {srv['hosting_provider']} / {srv['banner']}")
        g.add_edge(obs["persona_id"], srv["server_id"], etype="SHARES_INFRASTRUCTURE",
                   weight=2.0, label="SHARES_INFRASTRUCTURE")

    # ---- analytic edges from the live Stage 1 results -------------------
    if stage1:
        for cand in stage1["candidates"]:
            aid = cand["actor_id"]
            if aid not in g:
                continue
            sty = cand["signals"]["stylometry"]
            beh = cand["signals"]["behaviour"]
            if sty.get("score") is not None and sty["score"] >= similarity_threshold:
                g.add_edge(subject_id, aid, etype="SIMILAR_WRITING",
                           weight=sty["score"] / 40.0,
                           label=f"SIMILAR_WRITING ({sty['score']:.0f})")
            if beh.get("score") is not None and beh["score"] >= similarity_threshold:
                if not g.has_edge(subject_id, aid):
                    g.add_edge(subject_id, aid, etype="SIMILAR_ACTIVITY",
                               weight=beh["score"] / 40.0,
                               label=f"SIMILAR_ACTIVITY ({beh['score']:.0f})")
                else:
                    g[subject_id][aid]["label"] += f" + SIMILAR_ACTIVITY ({beh['score']:.0f})"
    return g


def _persona_tooltip(p):
    bits = [f"{p['username']} on {p['forum']}",
            f"created {p['account_created']}"]
    if p.get("pgp_id"):
        bits.append(f"PGP {p['pgp_id']}")
    if p.get("wallet_id"):
        bits.append(f"wallet {p['wallet_id']}")
    if p.get("attributed_actor"):
        bits.append(f"attributed to {p['attributed_actor']}")
    else:
        bits.append("UNATTRIBUTED SUBJECT")
    return " | ".join(bits)


def graph_summary(g):
    types = {}
    for _, d in g.nodes(data=True):
        types[d["ntype"]] = types.get(d["ntype"], 0) + 1
    edges = {}
    for _, _, d in g.edges(data=True):
        edges[d["etype"]] = edges.get(d["etype"], 0) + 1
    return {"nodes": g.number_of_nodes(), "edges": g.number_of_edges(),
            "node_types": types, "edge_types": edges}


def relationship_list(g, subject_id, max_hops=2):
    """Flat list of relationships around the subject, for the case report."""
    out = []
    if subject_id not in g:
        return out
    nodes = nx.single_source_shortest_path_length(g, subject_id, cutoff=max_hops)
    for u, v, d in g.edges(data=True):
        if u in nodes and v in nodes:
            out.append({"from": u, "relationship": d["etype"], "to": v,
                        "hops_from_subject": min(nodes[u], nodes[v])})
    return sorted(out, key=lambda r: (r["hops_from_subject"], r["relationship"]))


def layout(g, seed=26151):
    return nx.spring_layout(g, seed=seed, k=0.85, iterations=120)
