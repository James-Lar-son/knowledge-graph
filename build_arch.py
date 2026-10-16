#!/usr/bin/env python3
"""Build the architecture page (deploy/architecture/index.html).
The diagram is hand-placed SVG describing the system exactly as built:
sources of truth -> pipeline -> repositories -> Render services.
"""
from pathlib import Path

HERE = Path(__file__).parent

BOX = ('<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" '
       'fill="#1a1e23" stroke="{c}" stroke-width="1.4"/>'
       '<text x="{tx}" y="{ty}" fill="#e6e9ec" font-size="14" '
       'font-weight="600">{t}</text>{sub}')
SUB = '<text x="{tx}" y="{ty}" fill="#9aa4ae" font-size="11.5">{s}</text>'

def box(x, y, w, h, color, title, subs):
    tx = x + 14
    s = "".join(SUB.format(tx=tx, ty=y + 40 + 16 * i, s=t)
                for i, t in enumerate(subs))
    return BOX.format(x=x, y=y, w=w, h=h, c=color, tx=tx, ty=y + 24,
                      t=title, sub=s)

def arrow(x1, y1, x2, y2, label="", ly=None, color="#9aa4ae"):
    mid = (x1 + x2) / 2
    lab = (f'<text x="{mid}" y="{ly or y1 - 7}" fill="#9aa4ae" '
           f'font-size="11" text-anchor="middle">{label}</text>'
           if label else "")
    return (f'<path d="M{x1},{y1} L{x2},{y2}" stroke="{color}" '
            f'stroke-width="1.4" marker-end="url(#arr)"/>{lab}')

def colhead(x, text):
    return (f'<text x="{x}" y="26" fill="#e0a458" font-size="12.5" '
            f'letter-spacing="2">{text}</text>')

A = "#e0a458"   # accent — public site
B = "#5b8dd9"   # blue — pipeline
C = "#5bbf7a"   # green — truth
D = "#c95fb0"   # pink — Taguette side

svg_parts = [
    '<svg viewBox="0 0 1180 600" width="100%" role="img" '
    'aria-label="Architecture diagram" '
    'font-family="-apple-system,Segoe UI,Roboto,sans-serif">',
    '<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" '
    'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
    '<path d="M0,0 L10,5 L0,10 z" fill="#9aa4ae"/></marker></defs>',
    colhead(24, "SOURCES OF TRUTH"),
    colhead(330, "PIPELINE (LOCAL)"),
    colhead(646, "REPOSITORIES"),
    colhead(932, "RENDER (LIVE)"),
    # column 1
    box(24, 48, 262, 92, C, "Canonical graph",
        ["graph.working.json · git-versioned",
         "277 nodes · 608 edges · two layers:",
         "public + quarantined (2020+, drafts)"]),
    box(24, 168, 262, 92, D, "Taguette library",
        ["documents + qualitative coding",
         "SQLite on a 1 GB persistent disk",
         "2 documents · 277-tag codebook"]),
    box(24, 288, 262, 78, C, "Sources manifest + codebooks",
        ["CSV maps: document ↔ source node",
         "↔ Taguette document ↔ reader page"]),
    box(24, 394, 262, 66, "#768390", "James",
        ["codes documents · reviews staging",
         "approves every merge"]),
    # column 2
    box(330, 48, 272, 92, B, "Ingest — ingest_taguette.py",
        ["Taguette export → staging report",
         "new nodes proposed, never auto-merged",
         "merge is the ONLY write path"]),
    box(330, 168, 272, 92, B, "Privacy scrub + leak gate",
        ["public builds drop the quarantined",
         "layer, then scan: any private ID or",
         "label in the output ABORTS the build"]),
    box(330, 288, 272, 92, B, "Builders",
        ["build_viewer · build_table · build_home",
         "build_docs · build_arch — deterministic,",
         "same input → same pages"]),
    # column 3
    box(646, 48, 242, 92, A, "GitHub: knowledge-graph",
        ["this site's pages + builders",
         "big pages travel as chunks,",
         "reassembled at deploy build"]),
    box(646, 168, 242, 92, D, "GitHub: Taguette-server",
        ["Docker image + config",
         "template patch adds the",
         "Knowledge Graph nav link"]),
    # column 4
    box(932, 48, 224, 118, A, "Static site (free)",
        ["/ — home", "/graph/ — viewer", "/table/ — spreadsheets",
         "/docs/ — readable texts", "/architecture/ — this page"]),
    box(932, 194, 224, 78, D, "Web service — Taguette",
        ["larson-taguette.onrender.com",
         "Docker · starter plan · disk /data"]),
    box(932, 300, 224, 66, "#768390", "Public readers",
        ["see the public layer only —",
         "nothing private is ever deployed"]),
    # flows
    arrow(286, 214, 330, 94, "export .sqlite3"),
    arrow(286, 120, 330, 120, "", color=C),
    arrow(157, 140, 157, 160, "", color=C),  # canonical <-> ingest zone
    arrow(330, 214, 286, 120, "", color=B),   # scrubbed graph back? (skip)
    arrow(466, 140, 466, 160, ""),
    arrow(602, 120, 646, 94, "pages"),
    arrow(602, 214, 646, 214, "", color=D),
    arrow(602, 334, 646, 120, ""),
    arrow(888, 94, 932, 94, "API-triggered deploy", ly=80),
    arrow(888, 214, 932, 224, "Docker build", ly=206),
    arrow(1044, 272, 1044, 292, ""),
    arrow(286, 427, 330, 240, "approves merges", ly=420, color="#768390"),
    # cross-link note
    '<rect x="330" y="420" width="826" height="52" rx="8" fill="#14171b" '
    'stroke="#333a42"/>'
    '<text x="346" y="442" fill="#e6e9ec" font-size="12.5">Moving between '
    'rooms: viewer Source/Evidence panels deep-link into the exact Taguette '
    'document · Taguette nav links back here · reader pages link both ways.'
    '</text>'
    '<text x="346" y="460" fill="#9aa4ae" font-size="11.5">Pushes do not '
    'auto-deploy (no GitHub-app webhook) — every publish ends with an '
    'explicit API deploy trigger, then a byte-for-byte check of the live '
    'page.</text>',
    "</svg>",
]
DIAGRAM = "".join(svg_parts)

page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Architecture — Knowledge Graph</title>
<style>
  :root{{--bg:#111417;--panel:#1a1e23;--ink:#e6e9ec;--dim:#9aa4ae;
        --accent:#e0a458;--line:#333a42}}
  *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);
    font:14.5px/1.55 -apple-system,'Segoe UI',Roboto,sans-serif}}
  .wrap{{max-width:1220px;margin:0 auto;padding:32px 18px 60px}}
  h1{{font-size:23px;margin:0 0 4px}} .sub{{color:var(--dim);font-size:13px}}
  .sub a,footer a{{color:var(--accent);text-decoration:none}}
  .diagram{{background:var(--panel);border:1px solid var(--line);
    border-radius:10px;padding:14px;margin:20px 0;overflow-x:auto}}
  h2{{font-size:16px;margin:22px 0 6px}} p,li{{color:var(--dim);font-size:13.5px}}
  ol,ul{{margin:4px 0 0 18px;padding:0}} footer{{margin-top:26px;color:var(--dim);font-size:12px}}
</style></head>
<body><div class="wrap">
  <h1>How this site is built</h1>
  <div class="sub"><a href="../">Home</a> · <a href="../graph/">Graph</a> ·
  <a href="../table/">Table</a> · <a href="../docs/">Documents</a></div>
  <div class="diagram">{DIAGRAM}</div>

  <h2>The update loop</h2>
  <ol>
    <li>James codes a document in Taguette, tagging spans with graph nodes.</li>
    <li>He exports the project; the ingest tool turns highlights into a
    staging report — new Evidence, new edges, proposed nodes.</li>
    <li>He reviews; on approval the merge writes to the canonical graph
    (the only write path in the system).</li>
    <li>Builders regenerate every page from the graph; the leak gate
    aborts if any quarantined material survives.</li>
    <li>Pages push to GitHub; a deploy is triggered through the Render
    API; the live pages are verified byte-for-byte.</li>
  </ol>

  <h2>Privacy model</h2>
  <p>Enforced at build time, never at display time. The public site is
  generated from a scrubbed copy of the graph: quarantined nodes and edges
  are removed, references to them are dropped, and a final scan aborts the
  build if any private ID or label remains. There is no login on this
  site because there is nothing private on it to protect. The private
  working material — unpublished documents and the quarantined layer —
  lives in Taguette (behind its login) and in the local canonical file.</p>

  <footer>Generated by build_arch.py from the same pipeline it describes.</footer>
</div></body></html>
"""

out = HERE / "deploy" / "architecture" / "index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page)
(HERE / "staging" / "architecture.svg").write_text(DIAGRAM)
print(f"wrote {out}: {len(page)/1024:.0f} KB")
