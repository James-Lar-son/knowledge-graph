#!/usr/bin/env python3
"""Build graph-viewer.html — a single self-contained viewer for the
knowledge graph, with graph.working.json embedded as the default snapshot.

Re-run after an ingest --apply to refresh the embedded snapshot, or just
drop a newer graph JSON onto the open viewer (it has a loader).

    python3 build_viewer.py [--graph graph.working.json] [--out graph-viewer.html]
"""
import argparse, csv, json
from pathlib import Path

HERE = Path(__file__).resolve().parent

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Knowledge Graph — Viewer</title>
<style>
  :root{--bg:#111417;--panel:#1a1e23;--panel2:#22272e;--ink:#e6e9ec;--dim:#9aa4ae;
        --accent:#e0a458;--line:#333a42}
  *{box-sizing:border-box}
  body{margin:0;font:14px/1.45 -apple-system,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--ink)}
  #app{display:flex;height:100vh}
  aside{width:264px;flex:0 0 264px;background:var(--panel);padding:12px;overflow-y:auto;border-right:1px solid var(--line)}
  aside.right{border-right:none;border-left:1px solid var(--line);width:320px;flex-basis:320px}
  h1{font-size:15px;margin:0 0 2px} h2{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--dim);margin:16px 0 6px}
  .sub{color:var(--dim);font-size:12px}
  input[type=text]{width:100%;padding:7px 9px;background:var(--panel2);border:1px solid var(--line);border-radius:6px;color:var(--ink)}
  #results div{padding:5px 8px;border-radius:5px;cursor:pointer;font-size:13px}
  #results div:hover{background:var(--panel2)}
  .typeRow{display:flex;align-items:center;gap:7px;padding:2.5px 0;font-size:13px;cursor:pointer}
  .dot{width:10px;height:10px;border-radius:50%;flex:0 0 10px}
  .typeRow .n{margin-left:auto;color:var(--dim);font-size:12px}
  .typeRow.off{opacity:.38}
  label.chk{display:flex;gap:7px;align-items:center;padding:3px 0;cursor:pointer;font-size:13px}
  button{background:var(--panel2);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:6px 10px;cursor:pointer;font-size:13px}
  a.btnlink{display:inline-block;background:var(--panel2);color:var(--accent);border:1px solid var(--line);border-radius:6px;padding:6px 10px;font-size:13px;text-decoration:none}
  a.btnlink:hover{border-color:var(--accent)}
  button:hover{border-color:var(--accent)}
  button.primary{background:var(--accent);color:#191204;border-color:var(--accent);font-weight:600}
  .row{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
  main{flex:1;position:relative;min-width:0}
  canvas{display:block;width:100%;height:100%;cursor:grab}
  #status{position:absolute;left:10px;bottom:8px;color:var(--dim);font-size:12px;background:rgba(17,20,23,.75);padding:3px 8px;border-radius:5px}
  #tip{position:absolute;pointer-events:none;background:#000c;color:#fff;padding:3px 8px;border-radius:5px;font-size:12px;display:none;max-width:300px}
  .kv{font-size:12.5px;margin:5px 0}.kv b{color:var(--dim);font-weight:600}
  .edgeRow{padding:4px 7px;border-radius:5px;cursor:pointer;font-size:12.5px}
  .edgeRow:hover{background:var(--panel2)}
  .pred{color:var(--accent)}
  #selTitle{font-size:15px;font-weight:650;margin:2px 0}
  .tagchip{font-family:ui-monospace,Menlo,monospace;font-size:12px;background:var(--panel2);padding:2px 6px;border-radius:4px}
  .empty{color:var(--dim);font-size:13px}
</style></head>
<body><div id="app">
<aside id="left">
  <h1>Knowledge graph</h1>
  <div class="sub" id="counts"></div>
  <div class="sub"><a href="__TG_PROJECT__" target="_blank" rel="noopener" style="color:#e0a458;text-decoration:none">Code in Taguette ↗</a></div>
  <div class="sub"><a href="../" style="color:#9aa4ae;text-decoration:none">Home</a> · <a href="../table/" style="color:#9aa4ae;text-decoration:none">Table view</a></div>
  <h2>Find a node</h2>
  <input type="text" id="search" placeholder="label or id:slug…" autocomplete="off">
  <div id="results"></div>
  <h2>Layers</h2>
  <label class="chk"><input type="checkbox" id="showPrivate"> Show private (quarantined)</label>
  <label class="chk"><input type="checkbox" id="gapsOnly"> Gaps only (prompt nodes)</label>
  <h2>Types</h2>
  <div class="row" style="margin:0 0 4px"><button id="allTypes">All</button><button id="noTypes">None</button></div>
  <div id="types"></div>
  <h2>Graph file</h2>
  <div class="row"><button id="loadBtn">Load graph JSON…</button><button id="resetView">Reset view</button></div>
  <input type="file" id="file" accept=".json" style="display:none">
  <div class="sub" style="margin-top:8px">Or drop a graph JSON anywhere on this page. Embedded snapshot: <span id="snap"></span></div>
</aside>
<main id="main"><canvas id="cv"></canvas><div id="status"></div><div id="tip"></div></main>
<aside class="right" id="detail"><div class="empty">Select a node — its detail, connections, and the exact tags to use for it in Taguette appear here.</div></aside>
</div>
<script>
"use strict";
const GRAPH0 = __GRAPH_JSON__;
const PUBLIC_ONLY = __PUBLIC_ONLY__;
const TGLINKS = __TG_LINKS__;
const COLORS = {Person:"#e06c5b",Organization:"#d9a441",Role:"#b5893c",Era:"#8d9e5b",
Publication:"#5b8dd9",Artifact:"#4fa8a0",Skill:"#5bbf7a",Method:"#4f9e8f",Theory:"#7d7fd9",
Contribution:"#a86fd9",Principle:"#c95fb0",Value:"#e05b9e",Motivation:"#e07fb0",Theme:"#9e9e5b",
Audience:"#5ba8d9",Problem:"#d95b5b",Process:"#5bd0c0",Place:"#7fb069",Purpose:"#f0c75e",
Niche:"#f08c4a",Evidence:"#aab4bd",Claim:"#ffd166",Source:"#768390"};
let G, nodes, byId, edges, adj;
let view={x:0,y:0,k:1}, selected=null, hovered=null, sim=null, dragNode=null, panFrom=null;
const cv=document.getElementById('cv'), ctx=cv.getContext('2d');
const mainEl=document.getElementById('main');

function loadGraph(g){
  G=g;
  if(PUBLIC_ONLY){ const lp=document.getElementById('showPrivate').closest('label'); if(lp) lp.style.display='none'; }
  byId=new Map(); nodes=g.nodes.map(n=>({...n,x:(Math.random()*2-1)*420,y:(Math.random()*2-1)*300,vx:0,vy:0}));
  nodes.forEach(n=>byId.set(n.id,n));
  edges=g.edges.filter(e=>byId.has(e.source)&&byId.has(e.target))
    .map(e=>({...e,s:byId.get(e.source),t:byId.get(e.target)}));
  adj=new Map(nodes.map(n=>[n.id,new Set()]));
  edges.forEach(e=>{adj.get(e.source).add(e.target);adj.get(e.target).add(e.source);});
  nodes.forEach(n=>n.deg=adj.get(n.id).size);
  document.getElementById('snap').textContent=(g.meta&&g.meta.generated)||"loaded file";
  buildTypes(); updateCounts(); selected=null; renderDetail(); restartSim(); draw();
}
function visible(n){
  if(!document.getElementById('showPrivate').checked && n.layer==='private') return false;
  if(document.getElementById('gapsOnly').checked && n.prov!=='prompt') return false;
  const cb=document.querySelector(`input[data-type="${CSS.escape(n.type)}"]`);
  return !cb || cb.checked;
}
function visEdges(){ return edges.filter(e=>visible(e.s)&&visible(e.t)); }
function updateCounts(){
  const vn=nodes.filter(visible).length, ve=visEdges().length;
  document.getElementById('counts').textContent=`${vn} of ${nodes.length} nodes · ${ve} of ${edges.length} edges shown`;
  document.getElementById('status').textContent = selected? `Selected: ${selected.id} · ${selected.deg} connections` : "Drag to pan · wheel to zoom · drag a node to move it · click for detail";
}
function buildTypes(){
  const counts={}; nodes.forEach(n=>counts[n.type]=(counts[n.type]||0)+1);
  const el=document.getElementById('types'); el.innerHTML='';
  Object.keys(COLORS).filter(t=>counts[t]).sort((a,b)=>counts[b]-counts[a]).forEach(t=>{
    const row=document.createElement('label'); row.className='typeRow';
    row.innerHTML=`<input type="checkbox" data-type="${t}" checked><span class="dot" style="background:${COLORS[t]}"></span>${t}<span class="n">${counts[t]}</span>`;
    row.querySelector('input').addEventListener('change',()=>{updateCounts();draw();});
    row.addEventListener('click',e=>{row.classList.toggle('off',!row.querySelector('input').checked);});
    el.appendChild(row);
  });
}
// ---- force layout: Fruchterman-Reingold with a cooling temperature ----
// The first version accumulated velocity with uncapped short-range
// repulsion and no cooling, so nodes jittered forever ("gas particles").
// Here every move is capped by `temp`, temp decays x0.97/tick, and the
// sim hard-stops below 0.05 — final positions are exactly still.
// Parameters replica-tested in Python on the real public subgraph:
// cools in ~210 ticks, no blow-ups, median edge length near K.
let simTemp=0;
function restartSim(){
  simTemp=26;
  if(sim) cancelAnimationFrame(sim);
  const K=48;
  const step=()=>{
    const ns=nodes.filter(visible), es=visEdges();
    const disp=new Map(ns.map(n=>[n.id,[0,0]]));
    for(let i=0;i<ns.length;i++) for(let j=i+1;j<ns.length;j++){
      const a=ns[i], b=ns[j];
      let dx=a.x-b.x, dy=a.y-b.y; let d=Math.hypot(dx,dy)||0.01;
      const f=K*K/d, ux=dx/d, uy=dy/d, da=disp.get(a.id), db=disp.get(b.id);
      da[0]+=ux*f; da[1]+=uy*f; db[0]-=ux*f; db[1]-=uy*f; }
    es.forEach(e=>{ if(!disp.has(e.source)||!disp.has(e.target)) return;
      let dx=e.s.x-e.t.x, dy=e.s.y-e.t.y; const d=Math.hypot(dx,dy)||0.01;
      const f=d*d/K, ux=dx/d, uy=dy/d, da=disp.get(e.source), db=disp.get(e.target);
      da[0]-=ux*f; da[1]-=uy*f; db[0]+=ux*f; db[1]+=uy*f; });
    ns.forEach(n=>{ const dp=disp.get(n.id); dp[0]+=-n.x*6; dp[1]+=-n.y*6;
      if(n===dragNode) return;
      const d=Math.hypot(dp[0],dp[1])||0.01, mv=Math.min(d,simTemp);
      n.x+=dp[0]/d*mv; n.y+=dp[1]/d*mv; });
    draw();
    simTemp*=0.97;
    if(simTemp>=0.05) sim=requestAnimationFrame(step);
    else { sim=null; simTemp=0; fitView(); draw(); }
  };
  sim=requestAnimationFrame(step);
}
function fitView(){
  const ns=nodes.filter(visible); if(!ns.length) return;
  let x0=1e18,x1=-1e18,y0=1e18,y1=-1e18;
  ns.forEach(n=>{x0=Math.min(x0,n.x);x1=Math.max(x1,n.x);y0=Math.min(y0,n.y);y1=Math.max(y1,n.y);});
  const r=mainEl.getBoundingClientRect(), pad=50;
  const kw=(r.width-pad*2)/Math.max(60,(x1-x0)), kh=(r.height-pad*2)/Math.max(60,(y1-y0));
  view.k=Math.max(.1,Math.min(1.15,Math.min(kw,kh)));
  view.x=-(x0+x1)/2; view.y=-(y0+y1)/2;
}
// ---- drawing ----
function resize(){ const r=mainEl.getBoundingClientRect(); cv.width=r.width*devicePixelRatio; cv.height=r.height*devicePixelRatio; draw(); }
new ResizeObserver(resize).observe(mainEl);
function toScreen(n){ const r=mainEl.getBoundingClientRect(); return [r.width/2+(n.x+view.x)*view.k, r.height/2+(n.y+view.y)*view.k]; }
function toWorld(px,py){ const r=mainEl.getBoundingClientRect(); return [(px-r.width/2)/view.k-view.x,(py-r.height/2)/view.k-view.y]; }
function draw(){
  if(!nodes) return;
  const r=mainEl.getBoundingClientRect(); ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);
  ctx.clearRect(0,0,r.width,r.height);
  const nb = selected? adj.get(selected.id) : null;
  ctx.lineWidth=1;
  visEdges().forEach(e=>{
    const [x1,y1]=toScreen(e.s),[x2,y2]=toScreen(e.t);
    const hot=selected&&(e.source===selected.id||e.target===selected.id);
    ctx.strokeStyle=hot?"rgba(224,164,88,.85)":"rgba(140,150,160,.16)";
    ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();});
  nodes.filter(visible).forEach(n=>{
    const [x,y]=toScreen(n); if(x<-40||y<-40||x>r.width+40||y>r.height+40) return;
    const rad=Math.max(3,Math.min(11,2.2+Math.sqrt(n.deg)*1.35))*Math.max(.6,Math.min(1.6,view.k));
    const dim=selected&&n!==selected&&!nb.has(n.id);
    ctx.globalAlpha=dim?0.25:1;
    ctx.fillStyle=COLORS[n.type]||"#ccc";
    ctx.beginPath();ctx.arc(x,y,rad,0,7);ctx.fill();
    if(n===selected||n===hovered){ctx.strokeStyle="#fff";ctx.lineWidth=1.6;ctx.stroke();}
    if(n===selected||n===hovered||n.deg>=14||view.k>1.35){
      ctx.fillStyle=dim?"#9aa4ae":"#e6e9ec"; ctx.font="11px sans-serif"; ctx.textAlign="center";
      ctx.fillText(n.label.length>44?n.label.slice(0,43)+"…":n.label, x, y-rad-4);}
    ctx.globalAlpha=1;});
}
// ---- interaction ----
function pick(px,py){ let best=null,bd=1e9; nodes.filter(visible).forEach(n=>{const [x,y]=toScreen(n);const d=Math.hypot(x-px,y-py);if(d<14&&d<bd){bd=d;best=n;}}); return best; }
cv.addEventListener('pointerdown',e=>{ const n=pick(e.offsetX,e.offsetY);
  if(n){dragNode=n; select(n);} else panFrom={x:e.offsetX,y:e.offsetY,vx:view.x,vy:view.y};
  cv.setPointerCapture(e.pointerId); });
cv.addEventListener('pointermove',e=>{ const tip=document.getElementById('tip');
  if(dragNode){ const [wx,wy]=toWorld(e.offsetX,e.offsetY); dragNode.x=wx; dragNode.y=wy; draw(); return; }
  if(panFrom){ view.x=panFrom.vx+(e.offsetX-panFrom.x)/view.k; view.y=panFrom.vy+(e.offsetY-panFrom.y)/view.k; draw(); return; }
  hovered=pick(e.offsetX,e.offsetY);
  if(hovered){ tip.style.display='block'; tip.style.left=(e.offsetX+14)+'px'; tip.style.top=(e.offsetY+10)+'px';
    tip.textContent=hovered.label+" · "+hovered.type; cv.style.cursor='pointer'; }
  else { tip.style.display='none'; cv.style.cursor='grab'; }
  draw(); });
cv.addEventListener('pointerup',()=>{ dragNode=null; panFrom=null; });
cv.addEventListener('wheel',e=>{ e.preventDefault(); const f=e.deltaY<0?1.12:0.89; view.k=Math.max(.15,Math.min(4,view.k*f)); draw(); },{passive:false});
document.getElementById('resetView').onclick=()=>{ fitView(); draw(); };
['showPrivate','gapsOnly'].forEach(id=>document.getElementById(id).addEventListener('change',()=>{updateCounts();restartSim();}));
document.getElementById('allTypes').onclick=()=>{document.querySelectorAll('input[data-type]').forEach(c=>{c.checked=true;c.closest('.typeRow').classList.remove('off')});updateCounts();restartSim();};
document.getElementById('noTypes').onclick=()=>{document.querySelectorAll('input[data-type]').forEach(c=>{c.checked=false;c.closest('.typeRow').classList.add('off')});updateCounts();draw();};
// ---- search ----
const searchEl=document.getElementById('search'), resultsEl=document.getElementById('results');
searchEl.addEventListener('input',()=>{ const q=searchEl.value.trim().toLowerCase(); resultsEl.innerHTML='';
  if(q.length<2) return;
  nodes.filter(n=>visible(n)&&(n.label.toLowerCase().includes(q)||n.id.toLowerCase().includes(q))).slice(0,12)
   .forEach(n=>{ const d=document.createElement('div'); d.innerHTML=`<span class="dot" style="display:inline-block;background:${COLORS[n.type]}"></span> ${n.label} <span style="color:#9aa4ae">${n.type}</span>`;
     d.onclick=()=>{select(n); centerOn(n); resultsEl.innerHTML='';}; resultsEl.appendChild(d); }); });
function centerOn(n){ view.x=-n.x; view.y=-n.y; if(view.k<1) view.k=1; draw(); }
// ---- detail panel ----
function tagFor(kind,n){ const [p,s]=n.id.split(/:(.*)/); return `${kind}.${p}.${s.replace(/:/g,'_')}`; }
function copyTxt(t,btn){ navigator.clipboard.writeText(t).then(()=>{ const o=btn.textContent; btn.textContent="Copied ✓"; setTimeout(()=>btn.textContent=o,1100); }); }
function tgLinkFor(n){
  if(TGLINKS[n.id]) return TGLINKS[n.id];
  if(n.type==='Evidence'){ const e=edges.find(x=>x.source===n.id&&x.predicate==='documented_in'); if(e&&TGLINKS[e.target]) return TGLINKS[e.target]; }
  return null;
}
function select(n){ selected=n; renderDetail(); updateCounts(); draw(); }
function renderDetail(){
  const el=document.getElementById('detail'); if(!selected){ el.innerHTML='<div class="empty">Select a node.</div>'; return; }
  const n=selected;
  const fields=[['detail','Detail'],['gloss','Gloss'],['note','Note'],['question','Question'],['origin','Origin'],['year','Year'],['venue','Venue'],['file','File'],['efficacy','Efficacy'],['strength','Strength'],['persistence','Persistence'],['salience','Salience'],['flag','Flag'],['n_supports','Supports'],['support_strength','Support strength']];
  let h=`<div id="selTitle">${n.label}</div>
    <div class="kv"><span class="tagchip">${n.id}</span> · ${n.type} · ${n.layer} · ${n.prov}</div>
    <div class="row"><button class="primary" id="cpN">Copy n. tag</button><button id="cpS">Copy s. tag</button></div>
    <div class="kv"><span class="tagchip" id="tagTxt">${tagFor('n',n)}</span></div>`;
  const tg=tgLinkFor(n);
  if(tg) h+=`<div class="row"><a class="btnlink" href="${tg}" target="_blank" rel="noopener">Code in Taguette ↗</a></div>`;
  fields.forEach(([k,lab])=>{ if(n[k]!==undefined&&n[k]!==null&&n[k]!=="") h+=`<div class="kv"><b>${lab}:</b> ${String(n[k])}</div>`; });
  const out=edges.filter(e=>e.source===n.id), inc=edges.filter(e=>e.target===n.id);
  const rowE=(e,other)=>`<div class="edgeRow" data-id="${other.id}"><span class="pred">${e.predicate}</span> ${e.via?`<span style="color:#9aa4ae">via ${e.via}</span> `:''}${other.label} <span style="color:#9aa4ae">${other.type}</span></div>`;
  h+=`<h2>Out · ${out.length}</h2>`+(out.map(e=>rowE(e,e.t)).join('')||'<div class="empty">none</div>');
  h+=`<h2>In · ${inc.length}</h2>`+(inc.map(e=>rowE(e,e.s)).join('')||'<div class="empty">none</div>');
  el.innerHTML=h;
  document.getElementById('cpN').onclick=e=>copyTxt(tagFor('n',n),e.target);
  document.getElementById('cpS').onclick=e=>copyTxt(tagFor('s',n),e.target);
  el.querySelectorAll('.edgeRow').forEach(r=>r.onclick=()=>{ const t=byId.get(r.dataset.id); if(t){select(t);centerOn(t);} });
}
// ---- loading a different graph file ----
const fileEl=document.getElementById('file');
document.getElementById('loadBtn').onclick=()=>fileEl.click();
fileEl.addEventListener('change',()=>{ if(fileEl.files[0]) readFile(fileEl.files[0]); });
document.addEventListener('dragover',e=>e.preventDefault());
document.addEventListener('drop',e=>{ e.preventDefault(); if(e.dataTransfer.files[0]) readFile(e.dataTransfer.files[0]); });
function readFile(f){ f.text().then(t=>{ try{ loadGraph(JSON.parse(t)); }catch(err){ alert("Not a graph JSON: "+err.message); } }); }

loadGraph(GRAPH0); resize();
window.__kg={get nodes(){return nodes}, get edges(){return edges}, get temp(){return simTemp}, select, fitView, restartSim};
</script></body></html>
"""


def scrub_public(graph):
    """Public-export enforcement (build time, not UI time).

    The viewer's layer toggle is cosmetic — anyone can read the page
    source. A public build must therefore contain NO private material:
    private nodes/edges are removed, top-level review/meta source lists
    are dropped, fields that reference private node IDs are removed, and
    private labels/IDs mentioned inside prose fields are redacted.
    The caller verifies afterwards that no private ID or label survives
    anywhere in the serialized payload, and fails the build if one does.
    """
    import copy
    g = copy.deepcopy(graph)
    priv = [n for n in g["nodes"] if n.get("layer") == "private"]
    priv_ids = {n["id"] for n in priv}
    priv_labels = sorted({n["label"] for n in priv if len(n.get("label", "")) >= 4},
                         key=len, reverse=True)
    REF_FIELDS = {"era", "source", "org", "parent"}

    def scrub_value(node, key, v):
        if isinstance(v, str):
            if v in priv_ids:
                return None if key in REF_FIELDS else "[quarantined]"
            out = v
            for pid in priv_ids:
                out = out.replace(pid, "[quarantined]")
            for lab in priv_labels:
                out = out.replace(lab, "[quarantined]")
            return out
        if isinstance(v, list):
            items = []
            for x in v:
                if isinstance(x, str) and x in priv_ids:
                    continue
                items.append(scrub_value(node, key, x))
            return items
        if isinstance(v, dict):
            return {k: scrub_value(node, k, x) for k, x in v.items()}
        return v

    def scrub_obj(obj):
        out = {}
        for k, v in obj.items():
            sv = scrub_value(obj, k, v)
            if sv is None and k in REF_FIELDS:
                continue  # reference to a private node: drop the field
            out[k] = sv
        return out

    keep = {n["id"] for n in g["nodes"] if n.get("layer") != "private"}
    nodes = [scrub_obj(n) for n in g["nodes"] if n["id"] in keep]
    # NOTE: edges carry fields too (era, stakes, voice) — an edge between
    # two public nodes can still reference a private era. Scrub them too.
    edges = [scrub_obj(e) for e in g["edges"]
             if e["source"] in keep and e["target"] in keep
             and e.get("via") not in priv_ids]
    out = {
        "meta": {"owner": g.get("meta", {}).get("owner"),
                 "generated": g.get("meta", {}).get("generated"),
                 "node_count": len(nodes), "edge_count": len(edges),
                 "note": "Public layer only — exported and leak-checked "
                         "by build_viewer.py --public-only."},
        "schema": g.get("schema", {}),
        "nodes": nodes,
        "edges": edges,
        "validation": {"ok": True, "problems": []},
    }
    # hard gate: no private ID or label anywhere in the payload
    payload = json.dumps(out)
    leaks = [s for s in (priv_ids | set(priv_labels)) if s and s in payload]
    if leaks:
        raise SystemExit(f"PUBLIC BUILD ABORTED — private material survives "
                         f"scrubbing: {leaks[:8]}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", default=str(HERE / "graph.working.json"))
    ap.add_argument("--out", default=str(HERE / "graph-viewer.html"))
    ap.add_argument("--public-only", action="store_true",
                    help="strip private/quarantined nodes+edges and hide the layer unlock — REQUIRED for any public deployment")
    args = ap.parse_args()
    graph = json.loads(Path(args.graph).read_text())
    if args.public_only:
        graph = scrub_public(graph)
    payload = json.dumps(graph).replace("</script>", "<\\/script>")
    html = TEMPLATE.replace("__GRAPH_JSON__", payload)
    html = html.replace("__PUBLIC_ONLY__", "true" if args.public_only else "false")
    # Taguette deep links: only for Source nodes present in THIS build
    # (post-scrub), so the public build can never carry a private source's
    # link. Mapping lives in sources_manifest.csv (taguette_* columns).
    links = {}
    man = HERE / "sources_manifest.csv"
    if man.exists():
        ids = {n["id"] for n in graph["nodes"]}
        with open(man, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                sid = (row.get("src_id") or "").strip()
                pr = (row.get("taguette_project") or "").strip()
                dc = (row.get("taguette_document") or "").strip()
                if sid in ids and pr and dc:
                    links[sid] = ("https://larson-taguette.onrender.com"
                                  f"/project/{pr}/document/{dc}")
    project_url = ("https://larson-taguette.onrender.com/project/1"
                   if links else "https://larson-taguette.onrender.com")
    html = html.replace("__TG_LINKS__", json.dumps(links))
    html = html.replace("__TG_PROJECT__", project_url)
    Path(args.out).write_text(html)
    print(f"wrote {args.out}: {len(html)/1024:.0f} KB, "
          f"{len(graph['nodes'])} nodes / {len(graph['edges'])} edges embedded"
          + (" [PUBLIC ONLY]" if args.public_only else ""))


if __name__ == "__main__":
    main()
