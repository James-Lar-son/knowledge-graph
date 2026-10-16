#!/usr/bin/env python3
"""Build on-site reader pages (deploy/docs/<slug>/) for PUBLIC sources
whose full text is held in Taguette.

A source qualifies only when ALL of these hold:
  * the manifest gives it a doc_slug and a Taguette document number,
  * its layer in the canonical graph is public,
  * the export database actually contains the text.
Private-layer sources are skipped unconditionally — their texts never
reach the public site. Body HTML is whitelisted to <p> paragraphs.
"""
import csv, json, re, sqlite3
from pathlib import Path

HERE = Path(__file__).parent
TG = "https://larson-taguette.onrender.com"
DB = HERE / "inbox" / "knowledge-graph-cv.sqlite3"

graph = json.loads((HERE / "graph.working.json").read_text())
nodes = {n["id"]: n for n in graph["nodes"]}
private_terms = [n["id"] for n in graph["nodes"] if n.get("layer") == "private"] + \
                [n["label"] for n in graph["nodes"]
                 if n.get("layer") == "private" and len(n["label"]) > 3]

db = sqlite3.connect(DB)
docs = {i: (name, contents) for i, name, contents in
        db.execute("SELECT id, name, contents FROM documents")}

STYLE = """
  :root{--bg:#111417;--panel:#1a1e23;--panel2:#22272e;--ink:#e6e9ec;--dim:#9aa4ae;
        --accent:#e0a458;--line:#333a42}
  *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);
    font:16px/1.65 Georgia,'Times New Roman',serif}
  .wrap{max-width:720px;margin:0 auto;padding:36px 20px 60px}
  h1{font:600 24px/1.3 -apple-system,'Segoe UI',Roboto,sans-serif;margin:0 0 4px}
  .meta{color:var(--dim);font:13px -apple-system,'Segoe UI',Roboto,sans-serif;margin-bottom:22px}
  .meta a,footer a{color:var(--accent);text-decoration:none}
  p{margin:0 0 1em}
  footer{margin-top:34px;padding-top:14px;border-top:1px solid var(--line);
    font:12px -apple-system,'Segoe UI',Roboto,sans-serif;color:var(--dim)}
"""

def clean(html_text):
    # Whitelist <p> only; drop every other tag, keep paragraph text.
    txt = re.sub(r"<(?!/?p(\s[^>]*)?>)[^>]+>", "", html_text)
    txt = re.sub(r"<p(\s[^>]*)?>", "<p>", txt)
    txt = txt.replace("\xa0", " ").strip()
    # Drop empty spacer paragraphs.
    txt = re.sub(r"<p>\s*</p>", "", txt)
    return txt

built = []
with open(HERE / "sources_manifest.csv", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        slug = (row.get("doc_slug") or "").strip()
        sid = (row.get("src_id") or "").strip()
        tdoc = (row.get("taguette_document") or "").strip()
        if not slug or not sid or not tdoc:
            continue
        node = nodes.get(sid)
        if not node or node.get("layer") != "public":
            print(f"SKIP {slug}: source {sid} is not a public graph node")
            continue
        if int(tdoc) not in docs:
            print(f"SKIP {slug}: Taguette document {tdoc} not in export")
            continue
        name, contents = docs[int(tdoc)]
        body = clean(contents)
        title = node["label"]
        year = node.get("year") or row.get("year") or ""
        tglink = f"{TG}/project/{row['taguette_project']}/document/{tdoc}"
        page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{STYLE}</style></head>
<body><div class="wrap">
  <h1>{title}</h1>
  <div class="meta">{year} · Source {sid} · full text from the Taguette library ·
    <a href="{tglink}" target="_blank" rel="noopener">Code it in Taguette ↗</a></div>
{body}
  <footer><a href="../../">Home</a> · <a href="../../graph/">Graph</a> ·
  <a href="../../table/">Table</a></footer>
</div></body></html>
"""
        leaks = [t for t in private_terms if t in page]
        if leaks:
            raise SystemExit(f"DOC BUILD ABORTED — private term in {slug}: {leaks[:4]}")
        out = HERE / "deploy" / "docs" / slug / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page)
        built.append((slug, title, year))
        print(f"wrote {out}: {len(page)/1024:.0f} KB")

items = "\n".join(
    f'    <li><a href="{slug}/">{title}</a> <span class="meta">{year}</span></li>'
    for slug, title, year in built)
index = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Documents — Knowledge Graph</title>
<style>{STYLE}
  ul{{line-height:1.9}} a{{color:var(--accent);text-decoration:none}}
</style></head>
<body><div class="wrap">
  <h1>Documents</h1>
  <div class="meta">Full texts held in the Taguette library and readable here.
  A document appears when its source is public and its text has entered
  Taguette; the rest of the library is references in the graph until coded.</div>
  <ul>
{items}
  </ul>
  <footer><a href="../">Home</a> · <a href="../graph/">Graph</a> ·
  <a href="../table/">Table</a></footer>
</div></body></html>
"""
out = HERE / "deploy" / "docs" / "index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(index)
print(f"wrote {out}: {len(built)} readable document(s)")
