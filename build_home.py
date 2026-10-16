#!/usr/bin/env python3
"""Build the shell home page (deploy/index.html) from the PUBLIC layer.

Everything on the page derives from the scrubbed public graph plus the
Taguette mapping columns of sources_manifest.csv, and the build aborts
if any private node ID or label would appear in the output.
"""
import csv, json
from pathlib import Path
from build_viewer import scrub_public

HERE = Path(__file__).parent
TG = "https://larson-taguette.onrender.com"

graph = json.loads((HERE / "graph.working.json").read_text())
private_ids = {n["id"] for n in graph["nodes"] if n.get("layer") == "private"}
private_labels = {n["label"] for n in graph["nodes"]
                  if n.get("layer") == "private" and len(n["label"]) > 3}
pub = scrub_public(graph)
nodes, edges = pub["nodes"], pub["edges"]
generated = (pub.get("meta") or {}).get("generated", "")

links = {}
with open(HERE / "sources_manifest.csv", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        sid = (row.get("src_id") or "").strip()
        if sid and (row.get("taguette_document") or "").strip():
            links[sid] = True
taguette_docs = 2  # documents physically loaded in the hosted project

sources = [n for n in nodes if n["type"] == "Source"]
queue = sorted(n["label"] for n in sources if n["id"] not in links)
evidence = sum(1 for n in nodes if n["type"] == "Evidence")
claims = sum(1 for n in nodes if n["type"] == "Claim")

queue_html = "\n".join(f"      <li>{label}</li>" for label in queue)

html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Knowledge Graph — Home</title>
<style>
  :root{{--bg:#111417;--panel:#1a1e23;--panel2:#22272e;--ink:#e6e9ec;--dim:#9aa4ae;
        --accent:#e0a458;--line:#333a42}}
  *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);
    font:15px/1.5 -apple-system,'Segoe UI',Roboto,sans-serif}}
  .wrap{{max-width:880px;margin:0 auto;padding:40px 20px 60px}}
  h1{{font-size:26px;margin:0 0 4px}} .sub{{color:var(--dim);font-size:13px}}
  .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px;margin:26px 0}}
  .card{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px}}
  .card h2{{margin:0 0 6px;font-size:17px}} .card p{{color:var(--dim);font-size:13px;margin:0 0 12px}}
  a.btn{{display:inline-block;background:var(--panel2);color:var(--accent);border:1px solid var(--line);
    border-radius:6px;padding:6px 12px;font-size:13px;text-decoration:none}}
  a.btn:hover{{border-color:var(--accent)}}
  .stat{{font-size:22px;color:var(--ink)}} .stat small{{font-size:12px;color:var(--dim)}}
  section{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px;margin:14px 0}}
  section h2{{margin:0 0 8px;font-size:16px}} ul{{margin:6px 0 0 18px;padding:0;color:var(--dim);font-size:13px}}
  footer{{color:var(--dim);font-size:12px;margin-top:22px}}
</style></head>
<body><div class="wrap">
  <h1>Knowledge Graph</h1>
  <div class="sub">James Larson — adaptive expertise, maker culture, energy-transition workforce. Public layer.</div>

  <div class="cards">
    <div class="card"><h2>Graph</h2>
      <div class="stat">{len(nodes)} <small>nodes</small> · {len(edges)} <small>edges</small></div>
      <p>Traverse the network — people, publications, skills, values, and the evidence under them.</p>
      <a class="btn" href="graph/">Open the graph</a></div>
    <div class="card"><h2>Table</h2>
      <div class="stat">{len(nodes) + len(edges)} <small>rows</small></div>
      <p>The same graph as spreadsheets — sortable, searchable, downloadable as CSV.</p>
      <a class="btn" href="table/">Open the tables</a></div>
    <div class="card"><h2>Code</h2>
      <div class="stat">{taguette_docs} <small>documents in Taguette</small></div>
      <p>Where new evidence gets coded into the graph. Sign-in required.</p>
      <a class="btn" href="{TG}/project/1" target="_blank" rel="noopener">Open Taguette ↗</a></div>
  </div>

  <section><h2>Library</h2>
    <div class="sub">{len(sources)} public sources · {evidence} evidence nodes · {claims} claims.
    Full texts live in Taguette when a source is being coded; the rest are
    references in the graph until they enter the coding queue.</div>
    <h2 style="margin-top:14px">Not yet in Taguette ({len(queue)})</h2>
    <ul>
{queue_html}
    </ul>
  </section>

  <footer>Snapshot {generated} · Public layer only — quarantined material is
  removed at build time and never reaches this site.</footer>
</div></body></html>
"""

leaks = [x for x in private_ids | private_labels if x in html]
if leaks:
    raise SystemExit(f"HOME BUILD ABORTED — private material in output: {leaks[:6]}")
out = HERE / "deploy" / "index.html"
out.parent.mkdir(exist_ok=True)
out.write_text(html)
print(f"wrote {out}: {len(html)/1024:.0f} KB, queue {len(queue)}, "
      f"{len(nodes)} nodes / {len(edges)} edges")
