#!/usr/bin/env python3
"""
ingest_taguette.py — merge Taguette coding into James Larson's knowledge graph.

Why this design
---------------
Taguette is flat: a highlight is a span of text, and tags are just labels
attached to it. There is no subject/object, no direction, and no edge type.
The one structural fact every export preserves is CO-OCCURRENCE: tags applied
to the same highlight travel together (in the highlights CSV the highlight
`id` repeats once per tag; in the project .sqlite3 they join through
`highlight_tags`).

So an edge is encoded as co-occurrence on one highlight:

    r.<predicate>          the edge type           e.g.  r.demonstrates
    n.<prefix>.<slug>      the object node(s)      e.g.  n.skill.qual_research
    s.<prefix>.<slug>      optional subject node   e.g.  s.pub.asee2017
    m.<...>                meta: layer / prov / force-evidence

No s. tag  ->  the subject is a NEW Evidence node built from the span itself.
               (This matches the graph: Evidence is the atom, and most of its
               load-bearing edges — demonstrates / supports / expresses /
               during_era / documented_in — start at Evidence.)
With s.    ->  no Evidence node is created; the highlight is an assertion
               linking two existing (or newly proposed) nodes.
               Add m.evidence to force an Evidence node as well.

Node tags carry the graph ID, never the label, so renames don't break coding
and re-coding an existing node merges instead of duplicating. A n. tag whose
ID is not in the graph PROPOSES a new node (type is fixed by the prefix);
it lands in staging for review, never silently in the canonical graph.

Inputs
------
  --input   Taguette highlights CSV (header: id,document,tag,content)
            or a Taguette project export .sqlite3
  --graph   graph JSON (default: graph.working.json next to this script)
  --manifest sources_manifest.csv mapping Taguette document names to
             src: IDs (document,src_id,year,layer). Unmapped documents
             propose a new Source node and are flagged.
  --new-nodes optional CSV (node_id,label[,type]) giving labels for
             proposed new nodes; without it, a label is slug-derived and
             flagged PROVISIONAL.

Modes
-----
  (default) dry run: writes staging JSON + a plain-language report, graph
            is NOT modified.
  --apply   merge staging into --graph (a timestamped .bak is written first),
            re-validate, and update meta counts.

Idempotency
-----------
Evidence IDs are a hash of (source, normalised span text), and proposed
edges/nodes that already exist in the graph are reported as duplicates and
skipped. Re-running the same export is a no-op.

Validation on apply
-------------------
Every edge endpoint exists, no duplicate node IDs, no fully-identical
duplicate edges (the graph is a multigraph: the same triple may repeat
with a different `via`, e.g. coauthored_with once per shared paper),
all predicates / node types are in the graph schema. Problems abort the
apply and are listed in the report.
"""

import argparse, csv, hashlib, html, json, re, sqlite3, sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

# graph ID prefix -> node type (derived from graph.json, 2026-10-16;
# ev and gap are both Evidence in the existing graph)
PREFIX_TYPE = {
    "person": "Person", "org": "Organization", "role": "Role", "era": "Era",
    "pub": "Publication", "artifact": "Artifact", "skill": "Skill",
    "meth": "Method", "thy": "Theory", "ctb": "Contribution",
    "prn": "Principle", "val": "Value", "mot": "Motivation",
    "theme": "Theme", "aud": "Audience", "prob": "Problem",
    "proc": "Process", "place": "Place", "purp": "Purpose",
    "niche": "Niche", "ev": "Evidence", "gap": "Evidence",
    "claim": "Claim", "src": "Source",
}

# When a highlight has n. tags but no r. tag, the default predicate by
# object type (subject = the new Evidence node). Anything else is flagged.
DEFAULT_PREDICATE = {
    "Skill": "demonstrates", "Method": "demonstrates",
    "Claim": "supports", "Value": "expresses", "Era": "during_era",
}


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s[:60] or "untitled"


def parse_node_tag(raw, kind):
    """'n.skill.qual_research' / 'n.skill:qual_research' -> 'skill:qual_research'"""
    body = raw[len(kind) + 1:]  # strip 'n.' / 's.'
    if ":" in body:
        prefix, slug = body.split(":", 1)
    elif "." in body:
        prefix, slug = body.split(".", 1)
        slug = slug.replace(".", "_")
    else:
        return None
    if prefix not in PREFIX_TYPE or not slug:
        return None
    return f"{prefix}:{slug}"


def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


# ---------------------------------------------------------------- inputs

def read_highlights_csv(path):
    """Taguette highlights CSV: id,document,tag,content — one row per tag."""
    groups, order = {}, []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = (str(row.get("id", "")).strip(), (row.get("document") or "").strip())
            if key not in groups:
                groups[key] = {"id": key[0], "document": key[1],
                               "content": (row.get("content") or "").strip(),
                               "tags": []}
                order.append(key)
            tag = (row.get("tag") or "").strip()
            if tag and tag not in groups[key]["tags"]:
                groups[key]["tags"].append(tag)
            if not groups[key]["content"]:
                groups[key]["content"] = (row.get("content") or "").strip()
    return [groups[k] for k in order]


def read_highlights_sqlite(path):
    """Taguette project .sqlite3: documents / highlights / tags / highlight_tags."""
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    rows = db.execute(
        """SELECT h.id AS hid, d.name AS document, h.snippet AS snippet,
                  t.path AS tag
           FROM highlights h
           JOIN documents d ON d.id = h.document_id
           LEFT JOIN highlight_tags ht ON ht.highlight_id = h.id
           LEFT JOIN tags t ON t.id = ht.tag_id
           ORDER BY h.document_id, h.start_offset, h.id"""
    ).fetchall()
    groups, order = {}, []
    for r in rows:
        key = (str(r["hid"]), r["document"])
        if key not in groups:
            groups[key] = {"id": key[0], "document": key[1],
                           "content": strip_html(r["snippet"]), "tags": []}
            order.append(key)
        if r["tag"] and r["tag"] not in groups[key]["tags"]:
            groups[key]["tags"].append(r["tag"])
    return [groups[k] for k in order]


def read_manifest(path):
    mapping = {}
    if path and Path(path).exists():
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                doc = (row.get("document") or "").strip()
                if doc:
                    mapping[doc] = {
                        "src_id": (row.get("src_id") or "").strip(),
                        "year": (row.get("year") or "").strip(),
                        "layer": (row.get("layer") or "").strip(),
                    }
                # also key by the Source node's file name when given
                fn = (row.get("file") or "").strip()
                if fn and fn not in mapping:
                    mapping[fn] = mapping.get(doc, {})
    return mapping


def read_new_node_labels(path):
    labels = {}
    if path and Path(path).exists():
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                nid = (row.get("node_id") or "").strip()
                if nid:
                    labels[nid] = (row.get("label") or "").strip()
    return labels


# ---------------------------------------------------------------- staging

def stage(graph, highlights, manifest, new_labels):
    nodes = {n["id"]: n for n in graph["nodes"]}
    edge_set = {(e["source"], e["predicate"], e["target"]) for e in graph["edges"]}
    predicates = set(graph["schema"]["edge_types"])
    observed = {(e["predicate"],
                 nodes[e["source"]]["type"] if e["source"] in nodes else "?",
                 nodes[e["target"]]["type"] if e["target"] in nodes else "?")
                for e in graph["edges"]}

    new_nodes, new_edges = {}, []
    seen_edges = set()
    warnings, duplicates = [], []
    sources_proposed = {}

    def propose_node(nid, layer, prov, label_hint=None):
        if nid in nodes or nid in new_nodes:
            return
        prefix = nid.split(":", 1)[0]
        ntype = PREFIX_TYPE.get(prefix)
        label = new_labels.get(nid) or label_hint or \
            nid.split(":", 1)[1].replace("_", " ").strip().capitalize()
        new_nodes[nid] = {
            "id": nid, "type": ntype, "label": label,
            "prov": prov, "layer": layer,
            "note": "Proposed via Taguette ingest "
                    + ("(label from sidecar)." if nid in new_labels
                       else "(PROVISIONAL label — slug-derived, review)."),
        }
        warnings.append(f"new node proposed: {nid} ({ntype}) — '{label}'")

    def add_edge(src, pred, tgt, why):
        key = (src, pred, tgt)
        if pred not in predicates:
            warnings.append(f"UNKNOWN predicate '{pred}' ({why}) — edge dropped")
            return
        if key in edge_set or key in seen_edges:
            duplicates.append(f"edge already in graph: {src} -{pred}-> {tgt}")
            return
        seen_edges.add(key)
        new_edges.append({"source": src, "predicate": pred, "target": tgt})
        st = (nodes.get(src) or new_nodes.get(src) or {}).get("type", "?")
        tt = (nodes.get(tgt) or new_nodes.get(tgt) or {}).get("type", "?")
        if (pred, st, tt) not in observed and st != "?" and tt != "?":
            warnings.append(
                f"unobserved edge shape {pred}: {st} -> {tt} "
                f"({src} -> {tgt}) — kept, review")

    for hl in highlights:
        tags = hl["tags"]
        n_ids, s_ids, preds = [], [], []
        layer = prov = None
        force_ev = False
        unmapped = []
        for t in tags:
            low = t.strip()
            if low.startswith("n.") or low.startswith("n:"):
                nid = parse_node_tag(low, "n")
                (n_ids.append(nid) if nid else unmapped.append(t))
            elif low.startswith("s.") or low.startswith("s:"):
                nid = parse_node_tag(low, "s")
                (s_ids.append(nid) if nid else unmapped.append(t))
            elif low.startswith("r.") or low.startswith("r:"):
                preds.append(low[2:].strip())
            elif low == "m.evidence":
                force_ev = True
            elif low.startswith("m.layer."):
                layer = low.rsplit(".", 1)[1]
            elif low.startswith("m.prov."):
                prov = low.rsplit(".", 1)[1]
            else:
                unmapped.append(t)
        if unmapped:
            warnings.append(
                f"highlight {hl['id']} ({hl['document']}): unmapped tag(s) "
                f"{unmapped} — ignored")
        if not n_ids and not s_ids:
            if tags:
                warnings.append(
                    f"highlight {hl['id']} ({hl['document']}): no n./s. tag — "
                    "nothing to ingest")
            continue

        # --- source for this document
        man = manifest.get(hl["document"], {})
        src_id = man.get("src_id")
        if not src_id:
            src_id = "src:" + slugify(hl["document"])
            if src_id not in sources_proposed and src_id not in nodes:
                yr = man.get("year")
                sources_proposed[src_id] = {
                    "id": src_id, "type": "Source",
                    "label": hl["document"],
                    "prov": "verified",
                    "layer": man.get("layer") or
                             ("private" if (yr and int(yr) >= 2020) else "public"),
                    **({"year": int(yr)} if yr else {}),
                    "note": "Proposed via Taguette ingest — document not in "
                            "sources_manifest.csv. Confirm ID/year/layer.",
                }
                warnings.append(
                    f"document '{hl['document']}' not in manifest — "
                    f"Source proposed as {src_id}")
            new_nodes.setdefault(src_id, sources_proposed.get(src_id))
        if src_id not in nodes and src_id not in new_nodes:
            yr = man.get("year")
            new_nodes[src_id] = {
                "id": src_id, "type": "Source", "label": hl["document"],
                "prov": "verified",
                "layer": man.get("layer") or
                         ("private" if (yr and int(yr) >= 2020) else "public"),
                **({"year": int(yr)} if yr else {}),
                "note": "Proposed via Taguette ingest — src_id from "
                        "sources_manifest.csv but not yet in the graph.",
            }
            warnings.append(
                f"manifest src_id {src_id} not in graph — Source proposed")
        src_node = nodes.get(src_id) or new_nodes.get(src_id) or {}
        doc_layer = layer or src_node.get("layer", "public")
        doc_prov = prov or "verified"
        year = src_node.get("year") or (int(man["year"]) if man.get("year") else None)

        # --- subject: explicit s. node, else a new Evidence node from the span
        subject = s_ids[0] if s_ids else None
        if len(s_ids) > 1:
            warnings.append(
                f"highlight {hl['id']}: multiple s. tags {s_ids} — "
                f"using {s_ids[0]} as subject")
        if subject:
            propose_node(subject, doc_layer, doc_prov)
        ev_id = None
        if (not subject) or force_ev:
            digest = hashlib.sha1(
                (src_id + "|" + re.sub(r"\s+", " ",
                 hl["content"].lower()).strip()).encode()).hexdigest()[:10]
            ev_id = f"ev:tgt_{digest}"
            if ev_id in nodes:
                duplicates.append(
                    f"highlight {hl['id']} already ingested as {ev_id} — skipped")
                ev_id = None
                subject = None
                continue_ev = False
            else:
                label = (hl["content"][:77] + "…") if len(hl["content"]) > 78 \
                        else hl["content"]
                new_nodes[ev_id] = {
                    "id": ev_id, "type": "Evidence", "label": label,
                    "detail": hl["content"], "source": src_id,
                    "prov": doc_prov, "layer": doc_layer,
                    **({"year": year} if year else {}),
                    "note": f"Ingested from Taguette highlight {hl['id']} "
                            f"in '{hl['document']}'.",
                }
                add_edge(ev_id, "documented_in", src_id, "auto: evidence source")
                subject = ev_id
                continue_ev = True
            if ev_id is None and not subject:
                continue
        if subject is None:
            subject = ev_id

        # --- edges: subject -(pred)-> each n. node
        for nid in n_ids:
            propose_node(nid, doc_layer, doc_prov)
            use_preds = preds
            if not use_preds:
                tt = (nodes.get(nid) or new_nodes.get(nid) or {}).get("type")
                default = DEFAULT_PREDICATE.get(tt or "")
                if default and (ev_id and subject == ev_id):
                    use_preds = [default]
                    warnings.append(
                        f"highlight {hl['id']}: no r. tag — defaulted to "
                        f"{default} for {tt} {nid}")
                else:
                    warnings.append(
                        f"highlight {hl['id']}: n. tag {nid} with no r. tag "
                        "and no default — edge dropped")
                    continue
            for pred in use_preds:
                add_edge(subject, pred, nid,
                         f"highlight {hl['id']} in {hl['document']}")

    return {
        "new_nodes": [new_nodes[k] for k in sorted(new_nodes) if new_nodes[k]],
        "new_edges": new_edges,
        "duplicates": duplicates,
        "warnings": warnings,
        "counts": {
            "highlights_seen": len(highlights),
            "new_nodes": len([v for v in new_nodes.values() if v]),
            "new_edges": len(new_edges),
            "duplicates_skipped": len(duplicates),
            "warnings": len(warnings),
        },
    }


# ---------------------------------------------------------------- validate

def validate(graph):
    problems = []
    ids = [n["id"] for n in graph["nodes"]]
    if len(ids) != len(set(ids)):
        problems.append("duplicate node IDs: " +
                        str([i for i, c in Counter(ids).items() if c > 1]))
    idset = set(ids)
    # NOTE: the graph is a multigraph — the same (source, predicate, target)
    # triple may legitimately repeat with a different `via` (e.g.
    # coauthored_with x4, once per shared paper). Only a fully identical
    # edge dict counts as a duplicate here.
    eset = Counter(json.dumps(e, sort_keys=True) for e in graph["edges"])
    for raw, c in eset.items():
        if c > 1:
            problems.append(f"fully duplicate edge x{c}: {raw}")
    for e in graph["edges"]:
        if e["source"] not in idset or e["target"] not in idset:
            problems.append(
                f"dangling edge {e['source']} -{e['predicate']}-> {e['target']}")
    types = set(graph["schema"]["node_types"])
    preds = set(graph["schema"]["edge_types"])
    for n in graph["nodes"]:
        if n["type"] not in types:
            problems.append(f"node {n['id']} has unknown type {n['type']}")
    for e in graph["edges"]:
        if e["predicate"] not in preds:
            problems.append(f"unknown predicate {e['predicate']}")
    return problems


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", required=True,
                    help="Taguette highlights .csv or project .sqlite3")
    ap.add_argument("--graph", default=str(HERE / "graph.working.json"))
    ap.add_argument("--manifest", default=str(HERE / "sources_manifest.csv"))
    ap.add_argument("--new-nodes", default=str(HERE / "new_nodes.csv"))
    ap.add_argument("--staging-out", default=str(HERE / "staging" / "staging.json"))
    ap.add_argument("--report-out", default=str(HERE / "staging" / "report.md"))
    ap.add_argument("--apply", action="store_true",
                    help="merge into --graph (backup written first)")
    args = ap.parse_args()

    graph = json.loads(Path(args.graph).read_text())
    inp = Path(args.input)
    if inp.suffix in (".sqlite3", ".sqlite", ".db"):
        highlights = read_highlights_sqlite(inp)
    else:
        highlights = read_highlights_csv(inp)
    manifest = read_manifest(args.manifest)
    new_labels = read_new_node_labels(args.new_nodes)

    result = stage(graph, highlights, manifest, new_labels)

    Path(args.staging_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.staging_out).write_text(json.dumps(result, indent=2))
    lines = [f"# Taguette ingest — {'APPLY' if args.apply else 'DRY RUN'}",
             f"input: {inp.name} · graph: {Path(args.graph).name}", ""]
    for k, v in result["counts"].items():
        lines.append(f"- {k}: {v}")
    if result["warnings"]:
        lines += ["", "## Warnings / review"] + [f"- {w}" for w in result["warnings"]]
    if result["duplicates"]:
        lines += ["", "## Duplicates skipped"] + \
                 [f"- {d}" for d in result["duplicates"]]

    if args.apply:
        merged = json.loads(Path(args.graph).read_text())
        merged["nodes"].extend(result["new_nodes"])
        merged["edges"].extend(result["new_edges"])
        problems = validate(merged)
        if problems:
            lines += ["", "## APPLY ABORTED — validation problems"] + \
                     [f"- {p}" for p in problems]
            Path(args.report_out).write_text("\n".join(lines) + "\n")
            print("\n".join(lines))
            sys.exit(1)
        merged.setdefault("meta", {})["node_count"] = len(merged["nodes"])
        merged["meta"]["edge_count"] = len(merged["edges"])
        merged["validation"] = {"ok": True, "problems": []}
        stamp = inp.stem
        bak = Path(args.graph).with_suffix(f".{stamp}.bak.json")
        bak.write_text(Path(args.graph).read_text())
        Path(args.graph).write_text(json.dumps(merged, indent=2))
        lines += ["", f"Applied. Graph now {len(merged['nodes'])} nodes / "
                      f"{len(merged['edges'])} edges. Backup: {bak.name}"]

    Path(args.report_out).write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
