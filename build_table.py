#!/usr/bin/env python3
"""Build the spreadsheet page (deploy/table/index.html) from the PUBLIC
layer. Two tables — nodes and edges — sortable, filterable, CSV-download.
Data comes only from the leak-gated scrub used by the viewer build.
"""
import json
from pathlib import Path
from build_viewer import scrub_public

HERE = Path(__file__).parent
graph = json.loads((HERE / "graph.working.json").read_text())
pub = scrub_public(graph)
payload = json.dumps(pub).replace("</script>", "<\\/script>")

html = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Knowledge Graph — Tables</title>
<style>
  :root{--bg:#111417;--panel:#1a1e23;--panel2:#22272e;--ink:#e6e9ec;--dim:#9aa4ae;
        --accent:#e0a458;--line:#333a42}
  *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);
    font:14px/1.45 -apple-system,'Segoe UI',Roboto,sans-serif}
  .wrap{max-width:1180px;margin:0 auto;padding:26px 18px 60px}
  h1{font-size:22px;margin:0 0 2px} .sub{color:var(--dim);font-size:13px}
  .sub a{color:var(--accent);text-decoration:none}
  .bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:16px 0 10px}
  input[type=text],select{background:var(--panel2);color:var(--ink);border:1px solid var(--line);
    border-radius:6px;padding:6px 9px;font-size:13px}
  input[type=text]{min-width:260px}
  button{background:var(--panel2);color:var(--ink);border:1px solid var(--line);border-radius:6px;
    padding:6px 10px;cursor:pointer;font-size:13px}
  button.on{border-color:var(--accent);color:var(--accent)}
  table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line)}
  th,td{padding:6px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;font-size:13px}
  th{cursor:pointer;user-select:none;color:var(--accent);white-space:nowrap;position:sticky;top:0;background:var(--panel2)}
  td.id,td.mono{color:var(--dim);font-family:ui-monospace,Menlo,monospace;font-size:12px}
  .count{color:var(--dim);font-size:13px}
</style></head>
<body><div class="wrap">
  <h1>Knowledge graph — tables</h1>
  <div class="sub"><a href="../">Home</a> · <a href="../graph/">Graph view</a> · public layer · click a header to sort</div>
  <div class="bar">
    <button id="tabNodes" class="on">Nodes</button>
    <button id="tabEdges">Edges</button>
    <input type="text" id="q" placeholder="Filter rows…" autocomplete="off">
    <select id="facet"></select>
    <span class="count" id="count"></span>
    <button id="csv">Download CSV</button>
  </div>
  <table id="tbl"><thead></thead><tbody></tbody></table>
</div>
<script>
"use strict";
const G = __GRAPH_JSON__;
const byId = new Map(G.nodes.map(n=>[n.id,n]));
const label = id => (byId.get(id)||{}).label || id;
const NODE_COLS = [["id","ID"],["type","Type"],["label","Label"],["year","Year"],["prov","Prov"]];
const EDGE_COLS = [["source","Source"],["predicate","Predicate"],["target","Target"],["via","Via"]];
const rows = {
  nodes: G.nodes.map(n=>({id:n.id,type:n.type,label:n.label,year:n.year??"",prov:n.prov||""})),
  edges: G.edges.map(e=>({source:label(e.source),predicate:e.predicate,target:label(e.target),via:e.via||"",
                           _s:e.source,_t:e.target}))
};
let tab="nodes", sortKey=null, sortDir=1;
const thead=document.querySelector("#tbl thead"), tbody=document.querySelector("#tbl tbody");
function facetValues(){
  const key = tab==="nodes" ? "type" : "predicate";
  return [...new Set(rows[tab].map(r=>r[key]))].sort();
}
function buildFacet(){
  const sel=document.getElementById("facet");
  sel.innerHTML='<option value="">All '+(tab==="nodes"?"types":"predicates")+"</option>"+
    facetValues().map(v=>`<option>${v}</option>`).join("");
}
function render(){
  const cols = tab==="nodes" ? NODE_COLS : EDGE_COLS;
  const q = document.getElementById("q").value.toLowerCase();
  const f = document.getElementById("facet").value;
  const fkey = tab==="nodes" ? "type" : "predicate";
  let data = rows[tab].filter(r=>(!f||r[fkey]===f) &&
    (!q || Object.values(r).join(" ").toLowerCase().includes(q)));
  if(sortKey) data = [...data].sort((a,b)=> String(a[sortKey]).localeCompare(String(b[sortKey]),undefined,{numeric:true})*sortDir);
  thead.innerHTML = "<tr>"+cols.map(([k,lab])=>`<th data-k="${k}">${lab}${sortKey===k?(sortDir>0?" ▲":" ▼"):""}</th>`).join("")+"</tr>";
  tbody.innerHTML = data.map(r=>"<tr>"+cols.map(([k])=>{
    let v = r[k] ?? "";
    if(tab==="edges" && (k==="source"||k==="target")) v = `${v} <span class="id">${k==="source"?r._s:r._t}</span>`;
    return `<td class="${k==="id"?"mono":""}">${String(v).replace(/</g,"&lt;")}</td>`;
  }).join("")+"</tr>").join("");
  document.getElementById("count").textContent = `${data.length} of ${rows[tab].length} rows`;
  thead.querySelectorAll("th").forEach(th=>th.onclick=()=>{
    const k=th.dataset.k; if(sortKey===k) sortDir*=-1; else {sortKey=k; sortDir=1;} render();
  });
}
function setTab(t){ tab=t; sortKey=null;
  document.getElementById("tabNodes").classList.toggle("on",t==="nodes");
  document.getElementById("tabEdges").classList.toggle("on",t==="edges");
  buildFacet(); render(); }
document.getElementById("tabNodes").onclick=()=>setTab("nodes");
document.getElementById("tabEdges").onclick=()=>setTab("edges");
document.getElementById("q").oninput=render;
document.getElementById("facet").onchange=render;
document.getElementById("csv").onclick=()=>{
  const cols = tab==="nodes" ? NODE_COLS : EDGE_COLS;
  const q = document.getElementById("q").value.toLowerCase();
  const f = document.getElementById("facet").value, fkey = tab==="nodes" ? "type" : "predicate";
  const esc = v => `"${String(v??"").replace(/"/g,'""')}"`;
  const data = rows[tab].filter(r=>(!f||r[fkey]===f) && (!q || Object.values(r).join(" ").toLowerCase().includes(q)));
  const text = [cols.map(c=>c[1]).join(",")].concat(data.map(r=>cols.map(([k])=>esc(r[k])).join(","))).join("\\n");
  const a=document.createElement("a");
  a.href=URL.createObjectURL(new Blob([text],{type:"text/csv"}));
  a.download=`knowledge-graph-${tab}.csv`; a.click(); URL.revokeObjectURL(a.href);
};
setTab("nodes");
</script></body></html>
"""

html = html.replace("__GRAPH_JSON__", payload)
out = HERE / "deploy" / "table" / "index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(html)
print(f"wrote {out}: {len(html)/1024:.0f} KB, "
      f"{len(pub['nodes'])} nodes / {len(pub['edges'])} edges [PUBLIC ONLY]")
