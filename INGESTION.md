# Knowledge graph — Taguette ingestion

Working copy: `graph.working.json` (277 nodes / 608 edges, identical to the
`graph.json` you gave me — that original is untouched). All growth happens
on the working copy, in reviewed steps.

## Why the earlier attempt stalled

Taguette is flat, and I verified this against its own source rather than
assuming: a highlight is a span + a set of labels. There is no subject,
object, direction, or edge type, and its codebook import is just
`tag, description` rows. Its highlights CSV is exactly
`id, document, tag, content` — one row per tag, the highlight `id`
repeating — and its project export is a SQLite database
(`documents / highlights / tags / highlight_tags`).

So any scheme that tries to store an edge *inside one tag* explodes
combinatorially and can't be validated. The one structural fact every
export preserves is **co-occurrence**: tags on the same highlight travel
together. This pipeline encodes edges as co-occurrence.

## The convention

On one highlight, combine:

| Tag | Meaning | Example |
|---|---|---|
| `r.<predicate>` | the edge type | `r.demonstrates` |
| `n.<prefix>.<slug>` | object node — its graph ID, not its label | `n.skill.qual_research` |
| `s.<prefix>.<slug>` | optional subject node | `s.pub.asee2017` |
| `m.layer.private` / `m.layer.public` | layer override (default: the source's) | |
| `m.prov.inferred` / `m.prov.prompt` | provenance override (default: verified) | |
| `m.evidence` | also make an Evidence node when an `s.` tag is present | |

Rules that do the work:

- **No `s.` tag → the span itself becomes a new Evidence node**, and the
  `r.`/`n.` tags are its outgoing edges. That matches your graph, where
  Evidence is the atom: `demonstrates` (66), `supports` (38),
  `during_era` (41) and `documented_in` (41) are mostly Evidence edges.
  `documented_in → Source` is added automatically.
- **The prefix fixes the type** (`skill`→Skill, `thy`→Theory, `ctb`→
  Contribution, `val`→Value, `ev`/`gap`→Evidence, …). Full lookup:
  `node_tags.csv` — all 277 current nodes with their exact `n.` tag.
- **An `n.` ID that isn't in the graph proposes a new node.** It lands in
  staging for your review, never straight into the graph. Give it a proper
  label in `new_nodes.csv`; otherwise the label is slug-derived and
  flagged PROVISIONAL.
- **No `r.` tag** → a default is used where the graph makes it unambiguous
  (Skill/Method→`demonstrates`, Claim→`supports`, Value→`expresses`,
  Era→`during_era`) and flagged in the report. Otherwise the edge is
  dropped and flagged.
- **Documents = Sources.** `sources_manifest.csv` maps each Taguette
  document name to its `src:` ID. Unmapped documents propose a new
  Source, and the quarantine rule is applied by default: a source from
  2020 or later defaults to the private layer unless the manifest says
  otherwise.

Taguette tag paths group by prefix, so `n.skill.…`, `r.…`, `m.…` stay
tidy in its sidebar, and clicking a prefix shows all highlights under it.

## The continuous workflow

1. Import `codebook_core.csv` into Taguette (Project → import codebook).
   That's the 27 `r.` predicates + 5 `m.` meta tags, each with the
   graph's own definition as its description. **Decision (2026-10-16):
   core only** — create `n.`/`s.` tags on the fly, copying IDs from
   `node_tags.csv`. `codebook_all_nodes.csv` (all 277 as tags) is kept
   as a reference file only; do not import it. Day-to-day coding
   recipes: `TAGUETTE_CHEATSHEET.md`.
2. Code a document.
3. Export — either *Highlights → Export this view → CSV* (simplest) or
   the whole project as `.sqlite3` (lossless; both verified to produce
   identical staging). Drop the export in `inbox/` or hand it to me in
   chat.
4. I run the ingest dry-run and show you the staging report: new Evidence
   nodes, proposed new nodes, new edges, duplicates skipped, and every
   warning (unknown predicate, unobserved edge shape, weak defaults).
5. You approve, I run `--apply`. A timestamped backup is written first,
   the merged graph is re-validated, and meta counts are updated.

Re-running the same export is a no-op: Evidence IDs are a hash of
(source, span text) and existing edges are skipped.

## Verified, not asserted (2026-10-16)

- Sample export (4 highlights, incl. a new-node proposal and an
  `s.`-subject edge) applied to a **test copy**: 277→282 nodes,
  608→615 edges, validation clean.
- Re-running the same export against the merged graph: **0 new nodes,
  0 new edges** — idempotent.
- The SQLite route produced staging identical to the CSV route.
- One real find from testing: your graph is a **multigraph** —
  `coauthored_with` repeats per shared paper, distinguished by a `via`
  field (599 unique triples in 608 edges). Validation now only flags
  fully identical edge duplicates, so those survive every merge.

## Viewing the graph, and coding alongside it

- **Everyday display: `graph-viewer.html`** (built by `build_viewer.py`,
  single self-contained file, graph embedded). Opens in the public layer
  by default (231 nodes / 503 edges; tick "Show private" to unlock all
  277/608). Search, per-type filters, gaps-only view, click a node for
  its detail + in/out edges. Use it *filtered or one ego-network at a
  time* — the whole graph at once is a hairball, as any 277-node graph
  is. After a merge, drop the new `graph.working.json` onto the open
  viewer (or re-run `build_viewer.py`).
- **Coding alongside:** Taguette in one window, the viewer in the other.
  The viewer's detail panel has **Copy n. tag / Copy s. tag** buttons —
  find the node, copy its exact tag, paste it into Taguette. That closes
  the loop on creating node tags as you go: no typing IDs from memory.
- **Analysis / print: `graph.graphml`** — all nodes, edges, types,
  layers and `via` fields, for Gephi (layout, community detection,
  figures). Generic tools (Obsidian's graph view, most web viewers)
  were passed over: they flatten typed edges and drop the multigraph
  `via` distinctions and the public/private layering that this graph
  depends on. Neo4j remains an option if you ever want standing queries,
  but it needs a server and a re-import on every merge.

Files: `ingest_taguette.py` · `build_viewer.py` · `graph-viewer.html` ·
`graph.graphml` · `codebook_core.csv` · `codebook_all_nodes.csv` ·
`node_tags.csv` · `sources_manifest.csv` · `new_nodes.csv` ·
`TAGUETTE_CHEATSHEET.md` · `sample_highlights.csv` · `staging/` (tests)
