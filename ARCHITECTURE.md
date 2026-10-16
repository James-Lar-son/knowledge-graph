# Knowledge Graph — Software Architecture

Status: v1 design, 2026-10-16. Owner: James Larson. Operator: Pithecus.
Scale today: 277 nodes / 608 edges, 23 node types, 27 edge predicates.
Growth rate: human-coded documents — small, deliberate, reviewed.

## 1. Constraints that shape everything

1. **One user, one workstation.** No multi-user, no accounts, no server
   database. Anything heavier must justify itself against that.
2. **The quarantine is a hard boundary.** Post-2020 and unpublished
   material is `layer: private`. Private data may exist in exactly one
   place: the canonical graph file on this machine. It must never reach
   the deployed site, an export, or a commit to a public repo.
3. **Assertions are human.** The graph's value is 408 hand-asserted
   edges (`demonstrates`, `expresses`, `supports`, `grounded_in`, …)
   that cannot be derived from anything (see `EDGE_INFERENCE_AUDIT.md`).
   Machines stage, validate, and derive; a human approves assertions.
4. **The graph is a multigraph.** Identical (source, predicate, target)
   triples legitimately repeat, distinguished by `via`. Every component
   — validator, dedupe, viewer, exporter — must respect that.
5. **Prefer files over services.** The pattern already proven on this
   workstation: single self-contained artifacts, JSON formats with a
   versioned schema, git as history.

## 2. Principles

- **One source of truth.** `graph.json` (canonical, git-versioned) is
  the system. Viewers, exports, and sites are *builds* of it, never
  editors of it. There is no write path except the ingest merge.
- **Enforcement at build time, never UI time.** A layer toggle in a
  viewer is cosmetic — page source defeats it. Privacy is enforced by
  the public-export builder, which physically removes private material
  and *fails the build* if a leak scan finds any private ID or label in
  the output. (This gate exists because the first public build leaked
  private references through metadata and edge fields; nodes were
  filtered, references were not.)
- **Derived ≠ asserted, and the system knows which is which.** 179
  edges (29%) are exact duplicates of node fields (`era`, `source`,
  `org`, `authors`, `parent`) and 21 more follow a structural
  convention (Tier 1/2 in the audit). Those are generated and checked,
  never hand-coded. The remaining 408 are asserted via Taguette.
- **Every build is deterministic and gated.** Same graph in → same
  bytes out. Gates: schema validation, golden counts, multigraph-aware
  duplicate check, public-build leak scan. A red gate blocks deploy.
- **Staging before merge, always.** Nothing enters the canonical graph
  without a dry-run report a human has seen.

## 3. Components

```
 documents ──► Taguette (coding UI, external)
                  │  export: highlights.csv | project.sqlite3
                  ▼
              ┌─────────────┐   staging report   ┌──────────────┐
              │  INGEST     │ ─────────────────► │ REVIEW GATE  │
              │  adapters + │                    │ (James)      │
              │  tag codec  │ ◄───────────────── │ approve/deny │
              └─────────────┘                    └──────────────┘
                  │ merge (backup first)                │
                  ▼                                     │
              ┌─────────────┐                            │
              │  GRAPH CORE │  canonical graph.json (git)│
              │  validate · │  + schema · derive · scrub │
              │  derive ·   │  + audit                   │
              │  scrub      │                            │
              └─────────────┘                            │
                  │ builds (gated, deterministic)        │
        ┌─────────┼──────────────────┐                 │
        ▼         ▼                  ▼                   │
   local viewer  public site      GraphML                │
   (full graph,  (scrubbed, ──► Render                 │
   embedded)     leak-checked)    static deploy          │
        │                                                │
        └── copy n./s. tag ──► back into Taguette ───────┘
                       (the coding loop)
```

**Taguette** (external, unchanged): the coding surface. Tags encode
edges by co-occurrence on a highlight — `r.<predicate>` +
`n.<prefix>.<slug>` (+ optional `s.` subject, `m.` meta). Core codebook
(32 tags) imported once; node tags created as needed.

**Ingest** (`ingest_taguette.py`, today): two adapters (highlights CSV;
project SQLite — verified to produce identical staging), the tag codec,
source-manifest resolution (document → `src:` ID, quarantine default
for 2020+), staging writer, merge with timestamped backup, post-merge
validation, meta-count update. Idempotent by construction (Evidence IDs
are hashes of source + span text).

**Graph Core** (today: functions inside the scripts; target: a
`graphcore` package, §6): load/save, schema validation (types,
predicates, endpoints, fully-identical-duplicate detection),
Tier-1 derivation + consistency check against stored edges, the
public scrubber, and the inference audit.

**Builders** (`build_viewer.py`, today): emit three artifacts from the
canonical graph — the local viewer (full graph, embedded, single
file), the public site (scrubbed export + same viewer, layer unlock
removed), and `graph.graphml` (Gephi route). All builds re-run the
gates before writing output.

**Viewer** (single-file HTML, no dependencies): force layout with a
cooling schedule (settles and *stops* — the gas-particle jitter of v0
was uncapped velocity accumulation with no cooling), search, type and
layer filters, gaps view, node detail, and the copy-tag buttons that
make it a coding sidecar next to Taguette. Accepts a dropped graph
JSON to refresh without a rebuild.

**Deployment** (Render Static Site): serves only the public build from
the repo's `deploy/` folder. Deploys are git pushes; the build command
re-runs the public builder, so the leak gate runs on every deploy.
No secrets, no environment variables, no server code.

## 4. Data contracts

- **Graph file**: `{meta, schema, review, nodes, edges, validation}`.
  Node: `id` (`<prefix>:<slug>`, prefix ⇔ type), `type`, `label`,
  `layer` ∈ {public, private}, `prov` ∈ {verified, inferred, prompt},
  plus type-specific fields (`era`, `source`, `org`, `authors`, …).
  Edge: `{source, predicate, target, prov?, via?, era?, …}` — extra
  fields are meaningful (multigraph) and must be preserved verbatim.
- **Schema** lives inside the graph file today (node types, edge
  types, type rules). Target: extract to `schema.json` so ingest,
  builders, and any future app validate against one contract (§6).
- **Staging file**: `{new_nodes, new_edges, duplicates, warnings,
  counts}` — the review gate's only input; applying consumes exactly
  what the report showed.
- **Codebook**: Taguette-importable CSV (`tag, description`); the
  graph's own predicate definitions are the descriptions.

## 5. Privacy architecture

| Data | Local viewer | Public site | GraphML | Git repo (if public) |
|---|---|---|---|---|
| Public nodes/edges | ✓ | ✓ | ✓ | ✓ |
| Private nodes/edges | ✓ (unlock) | **never** | optional flag | **never** |
| Private IDs/labels referenced in fields, edge `era`s, `review`, meta source lists | shown | **scrubbed + leak-gated** | scrubbed build only | n/a |

Rules: the scrubber drops private nodes/edges, drops reference fields
pointing at private IDs (`era`, `source`, `org`, `parent`, edge `era`,
`via`), drops `review` and meta source lists wholesale, redacts
private labels in prose, then the builder scans the serialized output
for every private ID and label and aborts on any hit. The canonical
graph file itself is **never committed to the deploy repo** — enforced
by `.gitignore`, along with every full-graph build and ID lookup
(`graph-viewer.html`, `graph.graphml`, `node_tags.csv`,
`codebook_all_nodes.csv`, `sources_manifest.csv`). The repo's tracked
files pass the same leak scan (verified 2026-10-16: clean), so the
repo — including its history — is safe to push anywhere. The canonical
graph lives only in the local folder, untracked.

## 6. Repository layout — current → target

Current (v0, flat, all working): scripts, codebooks, manifests,
`graph.working.json`, `deploy/index.html` in one folder.

Target (v1 refactor, incremental — no big-bang rewrite):

```
knowledge-graph/
  ARCHITECTURE.md  README.md  render.yaml  .gitignore
  data/
    graph.json            # canonical (PRIVATE repo or local-only)
    schema.json           # extracted contract
    manifests/            # sources_manifest.csv, new_nodes.csv
    codebooks/            # core + all-nodes + node_tags.csv
  src/
    graphcore/            # load, validate, derive, scrub, audit
    ingest/               # taguette adapters, codec, stage, merge
    build/                # viewer, public site, graphml builders + gates
  web/
    viewer.html.tmpl      # the single-file viewer source
  dist/
    local/  public/       # build outputs (public/ = Render publish dir)
  tests/                  # golden counts, idempotency, leak, viewer DOM,
                          # layout-settle
  inbox/  staging/        # gitignored working areas
```

Migration order: (1) deploy from the current flat layout — it already
satisfies every gate; (2) extract `graphcore` from the two scripts;
(3) extract `schema.json`; (4) move the canonical file to `data/` and
teach the ingest to auto-emit Tier-1 edges for new nodes that arrive
with their fields filled (new Role → `role_at` + `during_era` +
`held_role`; new Publication → `authored` + `coauthored_with`).

## 7. Deployment runbook (Render)

1. Push this repo to GitHub/GitLab (private repo is fine and preferred
   while `graph.working.json` still lives in the folder).
2. Render → New → Static Site → connect the repo (or New → Blueprint
   and point it at `render.yaml`).
3. Publish directory is `deploy/`. Since the canonical graph is never
   in the repo, Render serves the committed `deploy/index.html` — the
   leak gate runs locally at rebuild time, before commit. (If the repo
   is ever made private *and* the graph deliberately added, the
   `render.yaml` build command rebuilds and re-gates on Render, and a
   gate failure leaves the old site live.)
4. Updates: merge new coding locally → rebuild public site (gate) →
   commit → push → Render auto-deploys. No dashboard steps.

Access paths for the operator (Pithecus): (a) repo-push only — James
connects Render once, Pithecus needs no Render access at all; or
(b) Render API key (stored in the secure vault, never in chat or the
repo) + repo URL, and Pithecus creates/triggers the service via API.
Path (a) is recommended: fewer credentials, and deploys stay auditable
as git history.

## 8. Evolution triggers (decided in advance)

- **Split viewer data from viewer code** (serve `graph.public.json`
  beside `index.html`) when the graph passes ~2,000 nodes or updates
  become more frequent than weekly — until then, embedded is simpler
  and works from `file://`.
- **Neo4j / a query layer** only when standing queries (not ad-hoc
  questions Pithecus answers from the JSON) become a real workload.
- **Multi-user / auth on the public site**: out of scope while the
  site contains only the public layer by construction.
- **Refactor (§6)** when the second builder or second ingest source
  appears — the seams are already where the packages will split.
